
import os

class temp(object):
    BOT = None
    # Store bulk files for each user
    BULK_FILES = {}

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

PORT = int(os.getenv('PORT', 8080))
BIN_CHANNEL = int(os.getenv("BIN_CHANNEL"))
STREAM_URL = os.getenv("STREAM_URL")
