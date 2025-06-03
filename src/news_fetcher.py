from datetime import datetime
from datetime import timedelta
import requests


class NewsFetcher:

    def __init__(
            self,
            api_key,
            query = "technology OR programming OR politics OR entertainment OR sports OR AI OR 'machine learning' OR 'data science'",
            language="en",
            page_size=10):
        """
        تنظیمات اولیه برای دریافت خبر:
        - api_key: کلید API از NewsAPI
        - query: کلیدواژه‌هایی که به دنبال‌شون هستیم
        - language: زبان خبرها (مثلاً 'en' برای انگلیسی)
        - page_size: تعداد خبرهایی که می‌خوایم دریافت کنیم
        """
        self.api_key = api_key
        self.query = query
        self.language = language
        self.page_size = page_size

        # تاریخ از دو روز قبل تا امروز
        self.two_days_ago = (datetime.now() -
                             timedelta(days=2)).strftime("%Y-%m-%d")
        self.today = datetime.now().strftime("%Y-%m-%d")

        self.url = "https://newsapi.org/v2/everything"
        self.params = {
            "q": self.query,
            "language": self.language,
            "sortBy": "relevancy",
            "from": self.two_days_ago,
            "to": self.today,
            "pageSize": self.page_size,
            "domains":
            "cnn.com,bbc.com,theverge.com,techcrunch.com,nytimes.com",
            "apiKey": self.api_key,  # استفاده از api_key در اینجا
        }

    def fetch_news(self):
        """
        دریافت اخبار از NewsAPI به تعداد دلخواه
        """
        response = requests.get(
            self.url,
            params=self.params)  # استفاده از params که در __init__ تعریف شده
        data = response.json()

        return data.get("articles", [])
