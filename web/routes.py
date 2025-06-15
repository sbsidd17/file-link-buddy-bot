
import math
import logging
import secrets
import mimetypes
from info import BIN_CHANNEL, temp
from aiohttp import web
from web.utils.custom_dl import TGCustomYield, chunk_size, offset_fix
from web.utils.render_template import render_page

routes = web.RouteTableDef()

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.Response(text="file2link Backend is working")


@routes.get("/watch/{message_id}/{file_name}")
async def stream_handler(request):
    try:
        message_id = int(request.match_info['message_id'])
        return web.Response(text=await render_page(message_id), content_type='text/html')
    except ValueError as e:
        logging.error(e)
        raise web.HTTPNotFound


@routes.get("/download/{message_id}/{file_name}")
@routes.get("/{message_id}/{file_name}")
async def old_stream_handler(request):
    try:
        message_id = int(request.match_info['message_id'])
        return await media_streamer(request, message_id)
    except ValueError as e:
        logging.error(e)
        raise web.HTTPNotFound


async def media_streamer(request, message_id: int):
    range_header = request.headers.get('Range', 0)
    media_msg = await temp.BOT.get_messages(BIN_CHANNEL, message_id)
    file_properties = await TGCustomYield().generate_file_properties(media_msg)
    file_size = file_properties.file_size

    # Enhanced range request handling for better video seeking
    if range_header:
        from_bytes, until_bytes = range_header.replace('bytes=', '').split('-')
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = request.http_range.stop or file_size - 1

    req_length = until_bytes - from_bytes

    # Optimize chunk size for video streaming - larger chunks for better performance
    if file_properties.mime_type and 'video' in file_properties.mime_type:
        # Use larger chunks for video files to improve streaming performance
        new_chunk_size = await chunk_size(min(req_length, 1024 * 1024))  # Max 1MB chunks for video
    else:
        new_chunk_size = await chunk_size(req_length)
    
    offset = await offset_fix(from_bytes, new_chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes % new_chunk_size) + 1
    part_count = math.ceil(req_length / new_chunk_size)
    body = TGCustomYield().yield_file(media_msg, offset, first_part_cut, last_part_cut, part_count, new_chunk_size)

    file_name = file_properties.file_name if file_properties.file_name else f"{secrets.token_hex(2)}.jpeg"
    mime_type = file_properties.mime_type if file_properties.mime_type else f"{mimetypes.guess_type(file_name)}"

    # Enhanced headers for better video streaming and caching
    headers = {
        "Content-Type": mime_type,
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'attachment; filename="{file_name}"',
    }
    
    # Add range headers for partial content
    if range_header:
        headers["Content-Range"] = f"bytes {from_bytes}-{until_bytes}/{file_size}"
        headers["Content-Length"] = str(req_length + 1)
    else:
        headers["Content-Length"] = str(file_size)
    
    # Add caching and streaming optimization headers for video files
    if mime_type and 'video' in mime_type:
        headers.update({
            "Cache-Control": "public, max-age=3600",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
        })

    return_resp = web.Response(
        status=206 if range_header else 200,
        body=body,
        headers=headers
    )

    return return_resp
