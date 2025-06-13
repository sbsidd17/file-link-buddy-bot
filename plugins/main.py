
import os
import io
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import STREAM_URL, BIN_CHANNEL, temp


@Client.on_message(filters.command("start") & filters.private)
async def start(client, message):
    start_text = f"""**Hello {message.from_user.mention},

I am a Telegram Video Stream Bot. Send me any video and I will give you streaming & download link.

📋 **Available Commands:**
• Send any file - Get instant download link
• /bulk_links - Start bulk file collection
• /get_bulk_link - Get all bulk links in a text file
• /clear_bulk - Clear your bulk file queue

**Powered By - @sdbots1**"""
    
    await message.reply_text(start_text)


@Client.on_message(filters.command("bulk_links") & filters.private)
async def bulk_links_start(client, message):
    user_id = message.from_user.id
    
    # Initialize bulk files list for user
    if user_id not in temp.BULK_FILES:
        temp.BULK_FILES[user_id] = []
    
    await message.reply_text(
        "**🔄 Bulk Link Mode Activated!**\n\n"
        "Now you can send multiple files to me. I'll add them to your queue.\n\n"
        "📋 **Commands:**\n"
        "• Send files - Add to bulk queue\n"
        "• /get_bulk_link - Get all links in a text file\n"
        "• /clear_bulk - Clear your queue\n\n"
        f"**Current queue: {len(temp.BULK_FILES[user_id])} files**"
    )


@Client.on_message(filters.command("get_bulk_link") & filters.private)
async def get_bulk_links(client, message):
    user_id = message.from_user.id
    
    if user_id not in temp.BULK_FILES or not temp.BULK_FILES[user_id]:
        await message.reply_text("❌ **No files in your bulk queue!**\n\nUse /bulk_links to start adding files.")
        return
    
    # Create text content with all links
    links_content = "📁 **Your Bulk Download Links**\n\n"
    
    for idx, file_data in enumerate(temp.BULK_FILES[user_id], 1):
        file_name = file_data['name']
        download_url = file_data['download_url']
        links_content += f"{idx}. {file_name} : {download_url}\n\n"
    
    # Create a text file
    file_content = links_content.encode('utf-8')
    file_buffer = io.BytesIO(file_content)
    file_buffer.name = f"bulk_links_{user_id}.txt"
    
    await message.reply_document(
        document=file_buffer,
        file_name=f"bulk_links_{message.from_user.first_name}.txt",
        caption=f"📋 **Bulk Links Generated!**\n\n**Total Files:** {len(temp.BULK_FILES[user_id])}\n\n**Powered By - @sdbots1**"
    )


@Client.on_message(filters.command("clear_bulk") & filters.private)
async def clear_bulk_links(client, message):
    user_id = message.from_user.id
    
    if user_id in temp.BULK_FILES:
        cleared_count = len(temp.BULK_FILES[user_id])
        temp.BULK_FILES[user_id] = []
        await message.reply_text(f"✅ **Bulk queue cleared!**\n\nRemoved {cleared_count} files from your queue.")
    else:
        await message.reply_text("❌ **No files to clear!**")


@Client.on_message((filters.private) & (filters.document | filters.video), group=4)
async def private_receive_handler(client, message):
    user_id = message.from_user.id
    file_id = message.document or message.video
    
    # Copy file to bin channel
    msg = await message.copy(
        chat_id=BIN_CHANNEL,
        caption=f"**File Name:** {file_id.file_name}\n\n**Requested By:** {message.from_user.mention}"
    )
    
    file_name = file_id.file_name.replace(" ", "_")
    online = f"{STREAM_URL}/watch/{msg.id}/{file_name}"
    download = f"{STREAM_URL}/download/{msg.id}/{file_name}"
    d_play = f"https://sidplayer.vercel.app?direct_link={download}"
    
    # Check if user is in bulk mode
    if user_id in temp.BULK_FILES:
        # Add to bulk queue
        temp.BULK_FILES[user_id].append({
            'name': file_name,
            'download_url': download,
            'watch_url': d_play
        })
        
        await message.reply_text(
            f"✅ **Added to bulk queue!**\n\n"
            f"**File:** `{file_name}`\n"
            f"**Queue position:** {len(temp.BULK_FILES[user_id])}\n\n"
            f"📋 Use /get_bulk_link to get all links\n"
            f"🗑️ Use /clear_bulk to clear queue",
            reply_to_message_id=message.id
        )
    else:
        # Send instant link (original behavior)
        await message.reply_text(
            text=f"<b>Here Is Your Streamable Link\n\nFile Name</b>:\n<code>{file_name}</code>\n\n<b>Powered By - <a href=https://t.me/sdbots1>©sdBots</a></b>",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Watch", url=d_play),
                    InlineKeyboardButton("Download", url=download)
                ]
            ]),
            reply_to_message_id=message.id,
            disable_web_page_preview=True
        )


@Client.on_message((filters.private) & (filters.photo | filters.audio), group=4)
async def photo_audio_error(client, message):
    await message.reply_text("**Dude! Send me a video file.**")
