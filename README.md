
# File to Link Bot

A Telegram bot that converts files to direct download links with bulk link generation feature.

## Features

- ✅ Convert any Telegram file to direct download link
- ✅ Stream videos online with built-in player
- ✅ Bulk link generation - collect multiple files and get all links in a text file
- ✅ Clean and user-friendly interface
- ✅ Support for videos, documents, and other file types

## Commands

- `/start` - Start the bot and see available commands
- `/bulk_links` - Start bulk file collection mode
- `/get_bulk_link` - Get all collected files as download links in a text file
- `/clear_bulk` - Clear your bulk file queue

## Setup

1. Set environment variables:
   - `BOT_TOKEN` - Your bot token from BotFather
   - `API_ID` - Your API ID from my.telegram.org
   - `API_HASH` - Your API hash from my.telegram.org
   - `BIN_CHANNEL` - Channel ID for storing files
   - `STREAM_URL` - Your domain URL for streaming

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the bot:
   ```bash
   python bot.py
   ```

## Bulk Link Feature

1. Use `/bulk_links` command to start collecting files
2. Send multiple files to the bot
3. Use `/get_bulk_link` to receive a text file with all download links
4. Format: `filename : download_url`

## Deployment

- Deploy on Render.com using the provided `render.yaml`
- Or use Docker with the provided `Dockerfile`

## License

MIT License - Feel free to use and modify as needed.
