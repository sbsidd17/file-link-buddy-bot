
import os
import io
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, ChatAdminRequired, UserNotParticipant
from pyrogram.enums import ChatType
from info import STREAM_URL, BIN_CHANNEL, ADMIN_ID, temp
import time
from collections import defaultdict


# Queue system for bulk operations
class BulkQueue:
    def __init__(self):
        self.queues = defaultdict(list)  # user_id -> list of tasks
        self.processing = defaultdict(bool)  # user_id -> is_processing
    
    async def add_task(self, user_id, task_data):
        """Add a task to user's queue"""
        self.queues[user_id].append(task_data)
        
        # Start processing if not already processing
        if not self.processing[user_id]:
            await self.process_queue(user_id)
    
    async def process_queue(self, user_id):
        """Process all tasks in user's queue"""
        if self.processing[user_id]:
            return
        
        self.processing[user_id] = True
        
        while self.queues[user_id]:
            task = self.queues[user_id].pop(0)
            await self.execute_task(task)
        
        self.processing[user_id] = False
    
    async def execute_task(self, task_data):
        """Execute a single task"""
        try:
            if task_data['type'] == 'link_txt':
                await self.process_link_txt_task(task_data)
            elif task_data['type'] == 'link':
                await self.process_link_task(task_data)
        except Exception as e:
            print(f"Error executing task: {e}")
            if 'status_msg' in task_data:
                try:
                    await task_data['status_msg'].edit_text(f"❌ **Error:** {str(e)}")
                except:
                    pass
    
    async def process_link_txt_task(self, task_data):
        """Process link_txt task"""
        client = task_data['client']
        message = task_data['message']
        count = task_data['count']
        chat_id = task_data['chat_id']
        replied_message_id = task_data['replied_message_id']
        status_msg = task_data['status_msg']
        
        # Get messages starting from replied message
        processed_files = []
        current_message_id = replied_message_id
        
        for i in range(count):
            try:
                # Add delay to prevent flood
                if i > 0:
                    await asyncio.sleep(2)
                
                # Update status every 5 files
                if i % 5 == 0 and i > 0:
                    await status_msg.edit_text(f"⏳ **Processing files... {i}/{count} completed**")
                
                # Get the current message
                current_message = await client.get_messages(chat_id, current_message_id)
                
                # Check if message has file
                if current_message and (current_message.document or current_message.video):
                    file_id = current_message.document or current_message.video
                    
                    # Copy file to bin channel
                    msg = await copy_file_with_retry(client, current_message)
                    
                    if msg:
                        file_name = file_id.file_name.replace(" ", "_") if file_id.file_name else f"file_{msg.id}"
                        download_url = f"{STREAM_URL}/download/{msg.id}/{file_name}"
                        
                        processed_files.append({
                            'name': file_name,
                            'url': download_url
                        })
                
                # Move to next message
                current_message_id += 1
                
            except Exception as e:
                print(f"Error processing message {current_message_id}: {e}")
                current_message_id += 1
                continue
        
        if processed_files:
            # Create text file content
            txt_content = f"📁 Batch Download Links - {len(processed_files)} Files\n"
            txt_content += f"Generated from: {message.chat.title or 'Channel/Group'}\n"
            txt_content += f"Date: {message.date.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            for idx, file_data in enumerate(processed_files, 1):
                txt_content += f"{file_data['name']} : {file_data['url']}\n"
            
            # Create file buffer
            file_content = txt_content.encode('utf-8')
            file_buffer = io.BytesIO(file_content)
            file_buffer.name = f"batch_links_{message.chat.id}_{replied_message_id}.txt"
            
            await status_msg.delete()
            
            # Try to send in the same chat, if fails send to user privately
            try:
                await message.reply_document(
                    document=file_buffer,
                    file_name=f"batch_links_{count}_files.txt",
                    caption=f"📋 **Batch Links Generated!**\n\n**Total Files:** {len(processed_files)}\n**Source:** {message.chat.title or 'Channel/Group'}\n\n**Powered By - @sdbots1**"
                )
            except Exception as e:
                # If can't send in channel, send to user privately
                try:
                    await client.send_document(
                        chat_id=message.from_user.id,
                        document=file_buffer,
                        file_name=f"batch_links_{count}_files.txt",
                        caption=f"📋 **Batch Links Generated!**\n\n**Total Files:** {len(processed_files)}\n**Source:** {message.chat.title or 'Channel/Group'}\n**Note:** Sent privately because bot can't send files in the channel.\n\n**Powered By - @sdbots1**"
                    )
                except Exception as private_error:
                    print(f"Failed to send document privately: {private_error}")
        else:
            await status_msg.edit_text("❌ **No valid files found in the specified range!**")
    
    async def process_link_task(self, task_data):
        """Process link task"""
        # Similar implementation to link_txt but without file generation
        pass

# Initialize queue system
bulk_queue = BulkQueue()


def is_authorized(user_id):
    """Check if user is authorized (admin or in authorized users list)"""
    return user_id == ADMIN_ID or user_id in temp.AUTHORIZED_USERS


async def check_channel_permissions(client, chat_id, user_id):
    """Check if bot has necessary permissions in channel"""
    try:
        # Check if it's a channel
        chat = await client.get_chat(chat_id)
        if chat.type not in [ChatType.CHANNEL, ChatType.SUPERGROUP]:
            return True  # Not a channel, no special checks needed
        
        # Check bot permissions
        bot_member = await client.get_chat_member(chat_id, "me")
        if not bot_member.privileges:
            return False
            
        # Check if user is admin or has permissions
        try:
            user_member = await client.get_chat_member(chat_id, user_id)
            if user_member.status in ["creator", "administrator"]:
                return True
        except Exception:
            pass
            
        return bot_member.privileges.can_delete_messages or bot_member.status == "administrator"
    except Exception as e:
        print(f"Error checking channel permissions: {e}")
        return False


@Client.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **Access Denied!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
    start_text = f"""**Hello {message.from_user.mention},

I am a Telegram Video Stream Bot. Send me any video and I will give you streaming & download link.

📋 **Available Commands:**
• Send any file - Get instant download link
• /bulk_links - Start bulk file collection
• /get_bulk_link - Get all bulk links in a text file
• /clear_bulk - Clear your bulk file queue
• /exit_bulk - Exit bulk mode and return to normal mode
• /link_txt <count> - Generate links for your bulk files (Private chat only)

**Group/Channel Commands:**
• Reply to file: /link <count> - Get links for next files
• Reply to file: /link_txt <count> - Get links in text file

**Channel Usage Tips:**
• Make sure bot is admin in channel
• Use /link_txt for large batches (better for channels)
• Files will be sent to you privately if bot can't send in channel

**Getting Links from Other Bots:**
• Forward files from URL uploader bots to this bot
• Use /bulk_links mode for multiple files
• Bot can process files from any source

**Powered By - @sdbots1**"""
    
    await message.reply_text(start_text)


@Client.on_message(filters.command("link_txt") & filters.private)
async def private_link_txt_handler(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **Access Denied!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
    # Check if user has bulk files
    if user_id not in temp.BULK_FILES or not temp.BULK_FILES[user_id]:
        await message.reply_text("❌ **No files in your bulk queue!**\n\nUse /bulk_links to start adding files, then use this command.")
        return
    
    # Extract count from command
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply_text(f"**Usage:** `/link_txt <count>`\n\nExample: `/link_txt 10`\n\n**Available files in queue:** {len(temp.BULK_FILES[user_id])}")
            return
        
        count = int(command_parts[1])
        available_files = len(temp.BULK_FILES[user_id])
        
        if count <= 0:
            await message.reply_text("❌ **Count must be greater than 0!**")
            return
        
        if count > available_files:
            await message.reply_text(f"❌ **You only have {available_files} files in queue!**\n\nUse a count between 1 and {available_files}")
            return
        
    except ValueError:
        await message.reply_text("❌ **Invalid count! Please provide a number.**\n\nExample: `/link_txt 10`")
        return
    
    # Create text file from bulk files
    selected_files = temp.BULK_FILES[user_id][:count]
    
    # Create text file content
    txt_content = f"📁 Bulk Download Links - {count} Files\n"
    txt_content += f"Generated from: Private Bot Chat\n"
    txt_content += f"Date: {message.date.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for idx, file_data in enumerate(selected_files, 1):
        txt_content += f"{file_data['name']} : {file_data['download_url']}\n"
    
    # Create file buffer
    file_content = txt_content.encode('utf-8')
    file_buffer = io.BytesIO(file_content)
    file_buffer.name = f"bulk_links_{user_id}_{int(time.time())}.txt"
    
    await message.reply_document(
        document=file_buffer,
        file_name=f"bulk_links_{count}_files.txt",
        caption=f"📋 **Bulk Links Generated!**\n\n**Files processed:** {count}/{len(temp.BULK_FILES[user_id])}\n**Remaining in queue:** {len(temp.BULK_FILES[user_id]) - count}\n\n**Powered By - @sdbots1**"
    )
    
    # Remove processed files from queue
    temp.BULK_FILES[user_id] = temp.BULK_FILES[user_id][count:]


@Client.on_message(filters.command("link") & (filters.group | filters.channel))
async def group_link_handler(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **Access Denied!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
    # Check if message is a reply
    if not message.reply_to_message:
        await message.reply_text("❌ **Please reply to a file message to use this command!**\n\n**Usage:** Reply to file and use `/link 5` to get 5 file links")
        return
    
    # Extract count from command
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply_text("**Usage:** `/link <count>`\n\nExample: Reply to a file and use `/link 5`")
            return
        
        count = int(command_parts[1])
        if count <= 0 or count > 20:
            await message.reply_text("❌ **Count must be between 1 and 20!**")
            return
        
    except ValueError:
        await message.reply_text("❌ **Invalid count! Please provide a number.**\n\nExample: `/link 5`")
        return
    
    try:
        chat_id = message.chat.id
        replied_message_id = message.reply_to_message.id
        
        # Check channel permissions
        if not await check_channel_permissions(client, chat_id, user_id):
            await message.reply_text("❌ **Insufficient permissions!**\n\nBot needs admin permissions in this channel or you need to be an admin.")
            return
        
        status_msg = await message.reply_text(f"⏳ **Processing {count} files starting from replied message...**")
        
        # Get messages starting from replied message
        processed_files = []
        current_message_id = replied_message_id
        
        for i in range(count):
            try:
                # Add delay to prevent flood
                if i > 0:
                    await asyncio.sleep(2)
                
                # Get the current message
                current_message = await client.get_messages(chat_id, current_message_id)
                
                # Check if message has file
                if current_message and (current_message.document or current_message.video):
                    file_id = current_message.document or current_message.video
                    
                    # Copy file to bin channel
                    msg = await copy_file_with_retry(client, current_message)
                    
                    if msg:
                        file_name = file_id.file_name.replace(" ", "_") if file_id.file_name else f"file_{msg.id}"
                        download_url = f"{STREAM_URL}/download/{msg.id}/{file_name}"
                        
                        processed_files.append({
                            'name': file_name,
                            'url': download_url,
                            'msg_id': current_message_id
                        })
                
                # Move to next message
                current_message_id += 1
                
            except Exception as e:
                print(f"Error processing message {current_message_id}: {e}")
                current_message_id += 1
                continue
        
        if processed_files:
            # Create response message
            response_text = f"📋 **Generated {len(processed_files)} file links:**\n\n"
            
            for idx, file_data in enumerate(processed_files, 1):
                response_text += f"{idx}. [{file_data['name']}]({file_data['url']})\n"
            
            response_text += f"\n**Powered By - @sdbots1**"
            
            try:
                await status_msg.edit_text(response_text, disable_web_page_preview=True)
            except Exception:
                # If can't edit in channel, send to user privately
                await client.send_message(
                    chat_id=user_id,
                    text=f"📋 **Links from {message.chat.title}:**\n\n{response_text}",
                    disable_web_page_preview=True
                )
                await status_msg.edit_text("✅ **Links generated and sent to you privately!**")
        else:
            await status_msg.edit_text("❌ **No valid files found in the specified range!**")
            
    except Exception as e:
        print(f"Error in group link handler: {e}")
        await message.reply_text(f"❌ **Error processing files:** {str(e)}")


@Client.on_message(filters.command("link_txt") & (filters.group | filters.channel))
async def group_link_txt_handler(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **Access Denied!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
    # Check if message is a reply
    if not message.reply_to_message:
        await message.reply_text("❌ **Please reply to a file message to use this command!**\n\n**Usage:** Reply to file and use `/link_txt 9` to get 9 file links in text file")
        return
    
    # Extract count from command
    try:
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply_text("**Usage:** `/link_txt <count>`\n\nExample: Reply to a file and use `/link_txt 9`")
            return
        
        count = int(command_parts[1])
        if count <= 0 or count > 200:
            await message.reply_text("❌ **Count must be between 1 and 200 for text file generation!**")
            return
        
    except ValueError:
        await message.reply_text("❌ **Invalid count! Please provide a number.**\n\nExample: `/link_txt 9`")
        return
    
    chat_id = message.chat.id
    replied_message_id = message.reply_to_message.id
    
    # Check channel permissions
    if not await check_channel_permissions(client, chat_id, user_id):
        await message.reply_text("❌ **Insufficient permissions!**\n\nBot needs admin permissions in this channel or you need to be an admin.")
        return
    
    status_msg = await message.reply_text(f"⏳ **Processing {count} files for text file generation...**")
    
    # Check if user has ongoing task, add to queue if yes
    task_data = {
        'type': 'link_txt',
        'client': client,
        'message': message,
        'count': count,
        'chat_id': chat_id,
        'replied_message_id': replied_message_id,
        'status_msg': status_msg
    }
    
    queue_position = len(bulk_queue.queues[user_id])
    if queue_position > 0:
        await status_msg.edit_text(f"📋 **Added to queue!**\n\n**Position:** {queue_position + 1}\n**Processing:** {count} files\n\n⏳ **Will start when current tasks complete...**")
    
    await bulk_queue.add_task(user_id, task_data)


async def copy_file_with_retry(client, message, retries=3, delay=5):
    for attempt in range(retries):
        try:
            # Determine if the message has a document or video
            if message.document:
                file_id = message.document.file_id
            elif message.video:
                file_id = message.video.file_id
            else:
                print("No document or video found in the message.")
                return None

            # Copy the message to the bin channel
            msg = await client.copy_message(
                chat_id=BIN_CHANNEL,
                from_chat_id=message.chat.id,
                message_id=message.id
            )
            return msg  # If successful, return the message object

        except FloodWait as e:
            print(f"FloodWait encountered, sleeping for {e.value} seconds.")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(delay)  # Wait before retrying
            else:
                print("Max retries reached. Could not copy the file.")
                return None  # If all retries fail, return None


# ... keep existing code (auth, unauth, users, bulk_links, get_bulk_links, clear_bulk, exit_bulk, private_receive_handler, photo_audio_error functions) the same ...


@Client.on_message(filters.command("auth") & filters.private)
async def auth_user(client, message):
    user_id = message.from_user.id
    
    # Only admin can authorize users
    if user_id != ADMIN_ID:
        await message.reply_text("❌ **Access Denied!**\n\nOnly admin can authorize users.")
        return
    
    try:
        # Extract user ID from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply_text("**Usage:** `/auth <user_id>`\n\nExample: `/auth 123456789`")
            return
        
        target_user_id = int(command_parts[1])
        
        if target_user_id in temp.AUTHORIZED_USERS:
            await message.reply_text(f"✅ **User {target_user_id} is already authorized!**")
            return
        
        # Add user to authorized list
        temp.AUTHORIZED_USERS.add(target_user_id)
        
        await message.reply_text(f"✅ **User {target_user_id} has been authorized!**\n\nThey can now use the bot.")
        
    except ValueError:
        await message.reply_text("❌ **Invalid user ID!**\n\nPlease provide a valid numeric user ID.")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@Client.on_message(filters.command("unauth") & filters.private)
async def unauth_user(client, message):
    user_id = message.from_user.id
    
    # Only admin can unauthorize users
    if user_id != ADMIN_ID:
        await message.reply_text("❌ **Access Denied!**\n\nOnly admin can unauthorize users.")
        return
    
    try:
        # Extract user ID from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply_text("**Usage:** `/unauth <user_id>`\n\nExample: `/unauth 123456789`")
            return
        
        target_user_id = int(command_parts[1])
        
        if target_user_id not in temp.AUTHORIZED_USERS:
            await message.reply_text(f"❌ **User {target_user_id} is not in authorized list!**")
            return
        
        # Remove user from authorized list
        temp.AUTHORIZED_USERS.remove(target_user_id)
        
        await message.reply_text(f"✅ **User {target_user_id} has been removed from authorized list!**")
        
    except ValueError:
        await message.reply_text("❌ **Invalid user ID!**\n\nPlease provide a valid numeric user ID.")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@Client.on_message(filters.command("users") & filters.private)
async def list_users(client, message):
    user_id = message.from_user.id
    
    # Only admin can view authorized users
    if user_id != ADMIN_ID:
        await message.reply_text("❌ **Access Denied!**\n\nOnly admin can view authorized users.")
        return
    
    if not temp.AUTHORIZED_USERS:
        await message.reply_text("📝 **No authorized users found!**\n\nUse `/auth <user_id>` to authorize users.")
        return
    
    users_list = "\n".join([f"• {user_id}" for user_id in temp.AUTHORIZED_USERS])
    await message.reply_text(f"📋 **Authorized Users ({len(temp.AUTHORIZED_USERS)}):**\n\n{users_list}")


@Client.on_message(filters.command("bulk_links") & filters.private)
async def bulk_links_start(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **Access Denied!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
    # Initialize bulk files list for user
    if user_id not in temp.BULK_FILES:
        temp.BULK_FILES[user_id] = []
    
    await message.reply_text(
        "**🔄 Bulk Link Mode Activated!**\n\n"
        "Now you can send multiple files to me. I'll add them to your queue.\n\n"
        "📋 **Commands:**\n"
        "• Send files - Add to bulk queue\n"
        "• /get_bulk_link - Get all links in a text file\n"
        "• /clear_bulk - Clear your queue\n"
        "• /exit_bulk - Exit bulk mode completely\n"
        "• /link_txt <count> - Generate text file from queue\n\n"
        f"**Current queue: {len(temp.BULK_FILES[user_id])} files**"
    )


@Client.on_message(filters.command("get_bulk_link") & filters.private)
async def get_bulk_links(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **Access Denied!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
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
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **Access Denied!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
    if user_id in temp.BULK_FILES:
        cleared_count = len(temp.BULK_FILES[user_id])
        temp.BULK_FILES[user_id] = []
        await message.reply_text(f"✅ **Bulk queue cleared!**\n\nRemoved {cleared_count} files from your queue.\n\n💡 **Still in bulk mode** - Use /exit_bulk to return to normal mode.")
    else:
        await message.reply_text("❌ **No files to clear!**")


@Client.on_message(filters.command("exit_bulk") & filters.private)
async def exit_bulk_mode(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **Access Denied!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
    if user_id in temp.BULK_FILES:
        # Remove user from bulk mode completely
        del temp.BULK_FILES[user_id]
        await message.reply_text(
            "✅ **Successfully exited bulk mode!**\n\n"
            "🔄 **Now in normal mode** - Send any file to get instant download links.\n\n"
            "💡 Use /bulk_links to enter bulk mode again."
        )
    else:
        await message.reply_text("❌ **You're not in bulk mode!**\n\nYou're already in normal mode. Send any file to get instant links.")


@Client.on_message((filters.private) & (filters.document | filters.video), group=4)
async def private_receive_handler(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **You can't use this bot!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
    file_id = message.document or message.video
    
    if not file_id:
        await message.reply_text("❌ **No valid file found. Please send a document or video file.**")
        return
    
    print(f"Processing file from user {user_id}: {file_id.file_name}")
    
    # Check if user is in bulk mode
    if user_id in temp.BULK_FILES:
        try:
            # Add rate limiting for bulk mode - wait 3 seconds between uploads
            await asyncio.sleep(3)
            
            status_msg = await message.reply_text("⏳ **Processing file for bulk queue...**")
            
            # Copy file to bin channel with retry logic
            msg = await copy_file_with_retry(client, message)
            
            if msg:
                file_name = file_id.file_name.replace(" ", "_") if file_id.file_name else f"file_{msg.id}"
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
                    f"🗑️ Use /clear_bulk to clear queue\n"
                    f"🚪 Use /exit_bulk to exit bulk mode\n"
                    f"📄 Use /link_txt <count> to generate file from queue"
                )
            else:
                await status_msg.edit_text("❌ **Failed to process file. Please check if bot has access to the channel.**")
                
        except FloodWait as e:
            await message.reply_text(
                f"⚠️ **Rate limit exceeded!**\n\n"
                f"Please wait {e.value} seconds before sending next file.\n"
                f"This helps prevent flooding Telegram servers.\n\n"
                f"💡 Use /exit_bulk to switch to normal mode."
            )
        except Exception as e:
            print(f"Error in bulk mode: {e}")
            await message.reply_text(f"❌ **Error processing file:** {str(e)}")
    else:
        # Send instant link (normal mode)
        try:
            print("Processing file in normal mode")
            
            status_msg = await message.reply_text("⏳ **Processing file...**")
            
            # Copy file to bin channel
            msg = await copy_file_with_retry(client, message)
            
            if msg:
                file_name = file_id.file_name.replace(" ", "_") if file_id.file_name else f"file_{msg.id}"
                online = f"{STREAM_URL}/watch/{msg.id}/{file_name}"
                download = f"{STREAM_URL}/download/{msg.id}/{file_name}"
                d_play = f"https://sidplayer.vercel.app?direct_link={download}"
                
                print(f"Generated links - Watch: {d_play}, Download: {download}")
                
                await status_msg.edit_text(
                    text=f"<b>Here Is Your Streamable Link\n\nFile Name</b>:\n<code>{file_name}</code>\n\n<b>Powered By - <a href=https://t.me/sdbots1>©sdBots</a></b>",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("Watch", url=d_play),
                            InlineKeyboardButton("Download", url=download)
                        ]
                    ]),
                    disable_web_page_preview=True
                )
            else:
                await status_msg.edit_text("❌ **Failed to process file. Please check if bot has access to the channel.**")
                
        except FloodWait as e:
            await message.reply_text(
                f"⚠️ **Rate limit exceeded!**\n\n"
                f"Please wait {e.value} seconds before sending another file."
            )
        except Exception as e:
            print(f"Error in normal mode: {e}")
            await message.reply_text(f"❌ **Error processing file:** {str(e)}")


@Client.on_message((filters.private) & (filters.photo | filters.audio), group=4)
async def photo_audio_error(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ **You can't use this bot!**\n\nYou are not authorized to use this bot.\n\n📞 Contact the admin to get access.")
        return
    
    await message.reply_text("**Dude! Send me a video file.**")
