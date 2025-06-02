import os
from dotenv import load_dotenv
from news_fetcher import NewsFetcher
from telegram_bot import TelegramBot

load_dotenv()

def main():
    # گرفتن کلیدهای API از فایل .env
    news_api_key = os.getenv("API_KEY")
    bot_token = os.getenv("BOT_TOKEN")
    
    ## ساخت نمونه‌های کلاس
    news = NewsFetcher(api_key=news_api_key)
    bot = TelegramBot(token=bot_token)

    bot.get_new_chat_ids() #چک می‌کنه آیا کاربر جدیدی به ربات پیام داده یا نه و اگر داده، ذخیره می‌کنه.
    
    ## گرفتن خبرها از NewsAPI
    articles = news.fetch_news()
    if not articles:
        print("❌ No news found.")
        return
    
    #لیست خبرها رو می‌گیره و به صورت پیام به همه کاربران ارسال می‌کنه.
    for article in articles:
        title = article.get("title", "No title")
        url = article.get("url", "")
        desc = article.get("description", "")
        message = f"📰 [{title}]({url})\n📄 {desc or 'No description'}"
        bot.broadcast(message)

if __name__ == "__main__":
    main()
