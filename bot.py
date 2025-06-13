
from pyrogram import Client, __version__
from info import API_ID, API_HASH, BOT_TOKEN, PORT, BIN_CHANNEL, temp
from aiohttp import web
from plugins import web_server


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
        
        # Try to join the BIN_CHANNEL if not already a member
        try:
            await self.get_chat(BIN_CHANNEL)
            print(f"Bot is already in BIN_CHANNEL: {BIN_CHANNEL}")
        except Exception as e:
            print(f"Error accessing BIN_CHANNEL {BIN_CHANNEL}: {e}")
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
