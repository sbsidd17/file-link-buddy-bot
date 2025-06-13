
from info import BIN_CHANNEL, STREAM_URL, temp
from web.utils.custom_dl import TGCustomYield
import urllib.parse
import secrets
import mimetypes
import aiofiles
import aiohttp


def get_size(size):
    """Get size in readable format"""
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])


async def fetch_properties(message_id):
    media_msg = await temp.BOT.get_messages(BIN_CHANNEL, message_id)
    file_properties = await TGCustomYield().generate_file_properties(media_msg)
    file_name = file_properties.file_name if file_properties.file_name else f"{secrets.token_hex(2)}.jpeg"
    mime_type = file_properties.mime_type if file_properties.mime_type else f"{mimetypes.guess_type(file_name)}"
    return file_name, mime_type


async def render_page(message_id):
    file_name, mime_type = await fetch_properties(message_id)
    src = urllib.parse.urljoin(STREAM_URL, str(message_id))
    audio_formats = ['audio/mpeg', 'audio/mp4', 'audio/x-mpegurl', 'audio/vnd.wav']
    video_formats = ['video/mp4', 'video/avi', 'video/ogg', 'video/h264', 'video/h265', 'video/x-matroska']
    
    if mime_type.lower() in video_formats:
        async with aiofiles.open('web/template/req.html') as r:
            heading = 'Watch {}'.format(file_name)
            tag = mime_type.split('/')[0].strip()
            html = (await r.read()).replace('tag', tag) % (heading, file_name, src)
    elif mime_type.lower() in audio_formats:
        async with aiofiles.open('web/template/req.html') as r:
            heading = 'Listen {}'.format(file_name)
            tag = mime_type.split('/')[0].strip()
            html = (await r.read()).replace('tag', tag) % (heading, file_name, src)
    else:
        async with aiofiles.open('web/template/dl.html') as r:
            heading = 'Download {}'.format(file_name)
            async with aiohttp.ClientSession() as s:
                async with s.get(src) as u:
                    file_size = get_size(u.headers.get('Content-Length', 0))
                    html = (await r.read()) % (heading, file_name, src, file_size)
    return html
