import os
from dotenv import load_dotenv
from news_fetcher import NewsFetcher
from telegram_bot import TelegramBot
from flask import Flask
import threading
from models import create_database
import asyncio
import nest_asyncio

nest_asyncio.apply()
# Load environment variables
load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def start_flask():
    app.run(host="0.0.0.0", port=5000)

async def main():
    # Create database tables
    create_database()

    # Get API keys from .env file
    news_api_key = os.getenv("API_KEY")
    bot_token = os.getenv("BOT_TOKEN")

    # Run Flask in a separate thread
    threading.Thread(target=start_flask).start()

    # Run bot in main thread
    bot = TelegramBot(token=bot_token, api_key=news_api_key)
    await bot.run_async()

if __name__ == "__main__":
    asyncio.run(main())
