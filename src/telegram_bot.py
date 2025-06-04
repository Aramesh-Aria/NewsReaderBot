import os
import requests
from news_fetcher import NewsFetcher
from telegram import Update,InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, JobQueue,CallbackQueryHandler
from db_helper import add_subscriber, get_subscribers
import pytz
from datetime import datetime, timedelta

class TelegramBot:

    def __init__(self, token, api_key):
        self.token = token
        self.api_key = api_key
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        print("Starting Bot...")
        self.app = Application.builder().token(token).build()

        # ایجاد نمونه NewsFetcher با ارسال api_key
        self.news_fetcher = NewsFetcher(api_key=self.api_key)

        # Commands
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CommandHandler('info', self.send_info))
        self.app.add_handler(CommandHandler('news', self.send_news))
        self.app.add_handler(CallbackQueryHandler(self.button_click))

        # errors
        self.app.add_error_handler(self.error)

        # تنظیم زمان‌بندی برای ارسال اخبار به صورت خودکار
        self.job_queue = self.app.job_queue
        self.schedule_news_updates()


    async def run_async(self):
        print("polling...")
        await self.app.run_polling(poll_interval=3)

    def schedule_news_updates(self):
        # زمان‌بندی اخبار هر 4 ساعت یکبار بر اساس زمان IRST (زمان ایران)
        iran_time_zone = pytz.timezone('Asia/Tehran')
        now = datetime.now(iran_time_zone)

        # تنظیم زمان‌های ارسال اخبار هر 4 ساعت یکبار
        times = [8, 12, 16, 20, 0, 4]  # ساعات 8 صبح، 12 ظهر، 4 عصر، 8 شب، 12 شب، 4 صبح
        for hour in times:
            # ایجاد زمان جدید با ساعت مشخص‌شده
            scheduled_time = iran_time_zone.localize(datetime(now.year, now.month, now.day, hour, 0))
            if scheduled_time < now:
                scheduled_time += timedelta(days=1)  # اگر زمان گذشته بود، یک روز به آن اضافه می‌کنیم

            # تنظیم زمان‌بندی برای ارسال اخبار
            self.job_queue.run_once(self.send_news, when=scheduled_time)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        start_message = (
            "Welcome to MyTelegramNewsBot!\n\n"
            "I will send you the latest news every 4 hours at the following times:\n"
            "- 8:00 AM IRST\n"
            "- 12:00 PM IRST\n"
            "- 4:00 PM IRST\n"
            "- 8:00 PM IRST\n"
            "- 12:00 AM IRST\n"
            "- 4:00 AM IRST\n\n"
        )
        await update.message.reply_text(start_message)

        chat_id = str(update.message.chat.id)

        # افزودن کاربر به دیتابیس اگر جدید باشد
        add_subscriber(chat_id)

    async def send_info(self, update: Update, context: CallbackContext):
        info_message = (
            "Here are some of the things you can do with this bot:\n"
            "- Get the latest news in various categories like technology, politics, etc.\n"
            "- Receive news updates at scheduled times.\n"
            "To get the news now, click the button below!"
        )

        # اضافه کردن دکمه send_news به پیام info
        keyboard = [
            [InlineKeyboardButton("Get Latest News Now", callback_data='get_latest_news')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # ارسال پیام همراه با دکمه
        await update.message.reply_text(info_message, reply_markup=reply_markup)

    async def send_news(self, update: Update = None, context: CallbackContext = None):
        """
        Fetches the latest news from NewsFetcher and sends it.
        If update is provided, news is sent to the user; otherwise, news is sent to all subscribers.
        """
        articles = self.news_fetcher.fetch_news()
        if not articles:
            # ارسال پیام به کاربر یا تمام مشترکین در صورتی که خبری یافت نشود
            no_news_message = "No news found at the moment. Please try again later."
            if update:
                await update.message.reply_text(no_news_message)
            else:
                # ارسال به تمام مشترکین
                subscribers = get_subscribers()  # این تابع لیست تمام مشترکین را می‌گیرد
                for chat_id in subscribers:
                    await self.app.bot.send_message(chat_id, no_news_message)
            return  # پس از ارسال پیام خطا، از اجرای باقی کد جلوگیری می‌شود

        news_message = "Latest News:\n\n"
        for article in articles:
            title = article.get("title", "No title")
            url = article.get("url", "")
            desc = article.get("description", "No description")
            news_message += f"{title}\n{desc}\n{url}\n\n"

        # ارسال اخبار به کاربرانی که درخواست کرده‌اند
        if update:
            await update.message.reply_text(news_message)
        else:
            # ارسال اخبار به تمام مشترکین از دیتابیس
            subscribers = get_subscribers()  # این تابع لیست تمام مشترکین را می‌گیرد
            for chat_id in subscribers:
                await self.app.bot.send_message(chat_id, news_message)

    async def button_click(self, update: Update, context: CallbackContext):
        query = update.callback_query
        if query.data == 'get_latest_news':
            # ارسال اخبار به کاربر
            articles = self.news_fetcher.fetch_news()
            if not articles:
                await query.message.reply_text("No news found at the moment. Please try again later.")
                return
            news_message = "Latest News:\n\n"
            for article in articles:
                title = article.get("title", "No title")
                url = article.get("url", "")
                desc = article.get("description", "No description")
                news_message += f"{title}\n{desc}\n{url}\n\n"

            await query.answer()  # پاسخ به دکمه
            await query.message.reply_text(news_message)

    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(f"Update{update} caused error {context.error}")

