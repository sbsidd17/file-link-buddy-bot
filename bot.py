

from pyrogram import Client, __version__
from info import API_ID, API_HASH, BOT_TOKEN, PORT, BIN_CHANNEL, temp
from aiohttp import web
from plugins import web_server
import os


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="FileToLinkBot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=30,
            plugins={"root": "plugins"},
            sleep_threshold=5,
        )

    async def start(self):
        await super().start()
        temp.BOT = self
        
        # Try to access the BIN_CHANNEL and handle session issues
        try:
            await self.get_chat(BIN_CHANNEL)
            print(f"Bot successfully connected to BIN_CHANNEL: {BIN_CHANNEL}")
        except Exception as e:
            print(f"Error accessing BIN_CHANNEL {BIN_CHANNEL}: {e}")
            
            # If it's a peer resolution issue, clear session and restart
            if "Peer id invalid" in str(e) or "ID not found" in str(e):
                print("Detected session cache issue. Clearing session and restarting...")
                
                # Clear session files
                session_files = [
                    "FileToLinkBot.session",
                    "FileToLinkBot.session-journal"
                ]
                
                for session_file in session_files:
                    if os.path.exists(session_file):
                        try:
                            os.remove(session_file)
                            print(f"Removed {session_file}")
                        except Exception as remove_error:
                            print(f"Error removing {session_file}: {remove_error}")
                
                # Stop current session
                await super().stop()
                
                # Restart with fresh session
                await super().start()
                temp.BOT = self
                
                # Try accessing channel again
                try:
                    await self.get_chat(BIN_CHANNEL)
                    print(f"Bot successfully reconnected to BIN_CHANNEL: {BIN_CHANNEL}")
                except Exception as retry_error:
                    print(f"Still unable to access BIN_CHANNEL after session reset: {retry_error}")
                    print("Please ensure:")
                    print("1. Bot is added to the channel as administrator")
                    print("2. Channel ID is correct")
                    print("3. Bot has permission to read messages and post")
            else:
                print("Please add the bot to the BIN_CHANNEL as an administrator")
        
        app = web.AppRunner(await web_server())
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()
        print(f"Bot started. Pyrogram v{__version__}")

    async def stop(self, *args):
        await super().stop()
        print("Bot stopped. Bye.")

app = Bot()
app.run()

