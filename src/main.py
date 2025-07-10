import os
from dotenv import load_dotenv
from news_fetcher import NewsFetcher
from telegram_bot import TelegramBot
from flask import Flask
import threading
from models import create_database
import asyncio
import nest_asyncio
import logging

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

nest_asyncio.apply()
# Load environment variables
load_dotenv()

host = os.getenv('HOST')
port = os.getenv('PORT')

if not host or not port:
    raise ValueError("HOST or PORT not set in .env file")

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def start_flask():
    try:
        port_int = int(port) if port else 5000
        logger.info(f"Starting Flask server on {host}:{port_int}")
        app.run(host=host, port=port_int)
    except ValueError:
        logger.error(f"Invalid PORT value: {port}. Using default port 5000.")
        app.run(host=host, port=5000)

async def main():
    # Create database tables
    logger.info("Creating database tables...")
    create_database()

    # Get API keys from .env file
    news_api_key = os.getenv("API_KEY")
    bot_token = os.getenv("BOT_TOKEN")

    # Validate required environment variables
    if not news_api_key:
        raise ValueError("API_KEY is not set in environment variables.")
    if not bot_token:
        raise ValueError("BOT_TOKEN is not set in environment variables.")

    logger.info("Starting Telegram bot...")
    # Run Flask in a separate thread
    threading.Thread(target=start_flask, daemon=True).start()

    # Run bot in main thread
    bot = TelegramBot(token=bot_token, api_key=news_api_key)
    await bot.run_async()

if __name__ == "__main__":
    import sys
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    else:
        asyncio.run(main())
