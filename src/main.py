import os
from dotenv import load_dotenv
from news_fetcher import NewsFetcher
from telegram_bot import TelegramBot
from flask import Flask
import threading
from db_helper import create_subscribers_table
import asyncio
import nest_asyncio

nest_asyncio.apply()
# بارگذاری متغیرهای محیطی
load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def start_flask():
    app.run(host="0.0.0.0", port=5000)

async def main():
    # ایجاد جدول subscribers در دیتابیس
    create_subscribers_table()

    # گرفتن کلیدهای API از فایل .env
    news_api_key = os.getenv("API_KEY")
    bot_token = os.getenv("BOT_TOKEN")

    # اجرای Flask در یک Thread جداگانه
    threading.Thread(target=start_flask).start()

    # اجرای بات در thread اصلی
    bot = TelegramBot(token=bot_token, api_key=news_api_key)
    await bot.run_async()

if __name__ == "__main__":
    asyncio.run(main())
