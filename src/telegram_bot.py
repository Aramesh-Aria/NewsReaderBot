import os
import requests

class TelegramBot:
    """ 
    این کلاس مسئول ارتباط با ربات تلگرام است:
    - دریافت chat_id کاربرانی که پیام می‌دن
    - ذخیره chat_id جدید در فایل
    - ارسال پیام به کاربران
    """
    def __init__(self, token, subscribers_file="subscribers.txt"):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.subscribers_file = subscribers_file

         # اگر فایل مشترکین وجود نداشت، بساز (خالی)
        if not os.path.exists(self.subscribers_file):
            open(self.subscribers_file, "w").close()
            
    def get_new_chat_ids(self):
        """
        بررسی پیام‌های جدید با getUpdates و ثبت chat_id کاربرانی که قبلاً ذخیره نشدن.
        خروجی: لیستی از chat_id های جدید
        """
        response = requests.get(f"{self.base_url}/getUpdates") #از getUpdates تلگرام، پیام‌های دریافتی رو می‌گیره
        updates = response.json()

        existing = set() 
        if os.path.exists(self.subscribers_file):
            with open(self.subscribers_file, "r") as f:
                existing = set(f.read().splitlines())

        new_ids = set() #چک می‌کنه کدوم chat_id  جدیدن و قبلاً ذخیره نشدن 
        if "result" in updates:
            for update in updates["result"]:
                try:
                    chat_id = str(update["message"]["chat"]["id"])
                    if chat_id not in existing:
                        new_ids.add(chat_id)
                except KeyError:
                    continue

        if new_ids: #chat_id جدیدها رو به subscribers.txt اضافه می‌کنه
            with open(self.subscribers_file, "a") as f:
                for cid in new_ids:
                    f.write(cid + "\n")
        return new_ids

    def send_message(self, chat_id, message):
        """
        ارسال یک پیام به chat_id خاص با فرمت Markdown
        """
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        res = requests.post(f"{self.base_url}/sendMessage", data=payload)
        return res.ok

    def broadcast(self, message):
        """
        ارسال پیام به همه مشترکین ذخیره‌شده در فایل subscribers.txt
        """
        if not os.path.exists(self.subscribers_file):
            print("❌ No subscribers found.")
            return

        with open(self.subscribers_file, "r") as f:
            chat_ids = f.read().splitlines()

        for cid in chat_ids:
            success = self.send_message(cid, message)
            print(f"{cid}: {'✅' if success else '❌'}")
