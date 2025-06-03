import sqlite3
import requests

def create_subscribers_table():
    conn = sqlite3.connect('subscribers.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id TEXT PRIMARY KEY,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()


def add_subscriber(chat_id):
    """افزودن کاربر جدید به دیتابیس"""
    conn = sqlite3.connect('subscribers.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO subscribers (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()


def update_last_activity(chat_id):
    """به‌روزرسانی تاریخ آخرین فعالیت زمانی که کاربر پیام ارسال می‌کند"""
    conn = sqlite3.connect('subscribers.db')
    c = conn.cursor()
    c.execute('''UPDATE subscribers SET last_activity = CURRENT_TIMESTAMP WHERE chat_id = ?''', (chat_id,))
    conn.commit()
    conn.close()


def get_subscribers():
    """بازگشت لیست تمام مشترکین (chat_id ها)"""
    conn = sqlite3.connect('subscribers.db')
    c = conn.cursor()
    c.execute("SELECT chat_id FROM subscribers")
    subscribers = [row[0] for row in c.fetchall()]
    conn.close()
    return subscribers


async def get_new_chat_ids(self):
    """
    بررسی پیام‌های جدید با getUpdates و ارسال پیام خوشامدگویی به کاربرانی که جدیدا start می‌زنند.
    """
    response = requests.get(f"{self.base_url}/getUpdates")
    updates = response.json()

    if "result" in updates:
        for update in updates["result"]:
            try:
                chat_id = str(update["message"]["chat"]["id"])

                # اگر پیام start باشد و کاربر قبلاً پیام خوشامد دریافت نکرده باشد
                if "/start" in update["message"]["text"]:
                    # فقط پیام خوشامدگویی بدون چک کردن مشترکین
                    await update.message.reply_text("Welcome to the bot! You will receive the latest news shortly.")
                    # افزودن کاربر به دیتابیس مشترکین
                    add_subscriber(chat_id)
            except KeyError:
                continue
