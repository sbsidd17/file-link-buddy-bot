
import os
import io
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
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


async def copy_file_with_retry(client, message, max_retries=3):
    """Copy file to BIN_CHANNEL with flood wait handling"""
    for attempt in range(max_retries):
        try:
            file_id = message.document or message.video
            msg = await message.copy(
                chat_id=BIN_CHANNEL,
                caption=f"**File Name:** {file_id.file_name}\n\n**Requested By:** {message.from_user.mention}"
            )
            return msg
        except FloodWait as e:
            print(f"FloodWait: Sleeping for {e.value} seconds (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(e.value)
            if attempt == max_retries - 1:
                raise
        except Exception as e:
            print(f"Error copying file: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2)  # Wait 2 seconds before retry
    
    return None


@Client.on_message((filters.private) & (filters.document | filters.video), group=4)
async def private_receive_handler(client, message):
    user_id = message.from_user.id
    file_id = message.document or message.video
    
    # Check if user is in bulk mode
    if user_id in temp.BULK_FILES:
        try:
            # Add rate limiting for bulk mode - wait 1 second between uploads
            await asyncio.sleep(1)
            
            status_msg = await message.reply_text("⏳ **Processing file...**")
            
            # Copy file to bin channel with retry logic
            msg = await copy_file_with_retry(client, message)
            
            if msg:
                file_name = file_id.file_name.replace(" ", "_")
                online = f"{STREAM_URL}/watch/{msg.id}/{file_name}"
                download = f"{STREAM_URL}/download/{msg.id}/{file_name}"
                d_play = f"https://sidplayer.vercel.app?direct_link={download}"
                
                # Add to bulk queue
                temp.BULK_FILES[user_id].append({
                    'name': file_name,
                    'download_url': download,
                    'watch_url': d_play
                })
                
                await status_msg.edit_text(
                    f"✅ **Added to bulk queue!**\n\n"
                    f"**File:** `{file_name}`\n"
                    f"**Queue position:** {len(temp.BULK_FILES[user_id])}\n\n"
                    f"📋 Use /get_bulk_link to get all links\n"
                    f"🗑️ Use /clear_bulk to clear queue"
                )
            else:
                await status_msg.edit_text("❌ **Failed to process file. Please try again.**")
                
        except FloodWait as e:
            await message.reply_text(
                f"⚠️ **Rate limit exceeded!**\n\n"
                f"Please wait {e.value} seconds before sending next file.\n"
                f"This helps prevent flooding Telegram servers."
            )
        except Exception as e:
            print(f"Error in bulk mode: {e}")
            await message.reply_text("❌ **Error processing file. Please try again.**")
    else:
        # Send instant link (original behavior)
        try:
            # Copy file to bin channel
            msg = await copy_file_with_retry(client, message)
            
            if msg:
                file_name = file_id.file_name.replace(" ", "_")
                online = f"{STREAM_URL}/watch/{msg.id}/{file_name}"
                download = f"{STREAM_URL}/download/{msg.id}/{file_name}"
                d_play = f"https://sidplayer.vercel.app?direct_link={download}"
                
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
            else:
                await message.reply_text("❌ **Failed to process file. Please try again.**")
                
        except FloodWait as e:
            await message.reply_text(
                f"⚠️ **Rate limit exceeded!**\n\n"
                f"Please wait {e.value} seconds before sending another file."
            )
        except Exception as e:
            print(f"Error in normal mode: {e}")
            await message.reply_text("❌ **Error processing file. Please try again.**")


@Client.on_message((filters.private) & (filters.photo | filters.audio), group=4)
async def photo_audio_error(client, message):
    await message.reply_text("**Dude! Send me a video file.**")
