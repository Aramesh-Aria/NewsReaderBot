import os
from dotenv import load_dotenv
from news_fetcher import NewsFetcher
from telegram_bot import TelegramBot
from flask import Flask
import threading
from db_helper import create_subscribers_table
import time

# بارگذاری متغیرهای محیطی
load_dotenv()

app = Flask(__name__)


@app.route('/')
def index():
    return "Bot is running!"


def run():
    app.run(host="0.0.0.0", port=5000)


def main():

    # شروع Web Server در یک Thread جداگانه
    threading.Thread(target=run).start()

    # ایجاد جدول subscribers در دیتابیس
    create_subscribers_table()

    # گرفتن کلیدهای API از فایل .env
    news_api_key = os.getenv("API_KEY")
    bot_token = os.getenv("BOT_TOKEN")

    # ساخت نمونه‌های کلاس
    news = NewsFetcher(api_key=news_api_key)
    bot = TelegramBot(token=bot_token, api_key=news_api_key)

    # شروع بات
    bot.start_polling()

    # چک کردن چت‌های جدید و ذخیره آن‌ها
    bot.get_new_chat_ids()

    # گرفتن اخبار از NewsAPI
    articles = news.fetch_news()
    if not articles:
        print("❌ No news found.")
        return

    # ارسال اخبار به همه کاربران
    for article in articles:
        title = article.get("title", "No title")
        url = article.get("url", "")
        desc = article.get("description", "")
        message = f"📰 [{title}]({url})\n📄 {desc or 'No description'}"


if __name__ == "__main__":
    # شروع Web Server در یک Thread جداگانه
    threading.Thread(target=run).start()

    # اجرای بات تلگرام
    main()
