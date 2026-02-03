from datetime import datetime
from datetime import timedelta
import requests


class NewsFetcher:

    def __init__(self, api_key, language="en", page_size=10):
        """
        Initialize NewsFetcher with API key and default settings
        """
        self.api_key = api_key
        self.language = language
        self.page_size = page_size
        self.url = "https://newsapi.org/v2/everything"

    def fetch_news_for_user(self, user_queries, enabled_sources):
        """
        Fetch news for a specific user based on their queries and enabled sources
        """
        if not user_queries or not enabled_sources:
            return []
        
        # Combine all user queries with OR operator
        combined_query = " OR ".join(user_queries)
        
        # Combine enabled sources with comma separator
        domains = ",".join(enabled_sources)
        
        # Date range: from 2 days ago to today
        two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        params = {
            "q": combined_query,
            "language": self.language,
            "sortBy": "relevancy",
            "from": two_days_ago,
            "to": today,
            "pageSize": self.page_size,
            "domains": domains,
            "apiKey": self.api_key,
        }

        try:
            response = requests.get(self.url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("articles", [])
        except requests.RequestException as e:
            print(f"Error fetching news: {e}")
            return []

    def fetch_news_by_topics_and_sources(
        self,
        enabled_topics,
        enabled_sources,
        user_queries=None,
        max_articles=None,
    ):
        """
        Fetch news for a user based on their enabled topics and sources
        """
        if not enabled_topics and not enabled_sources:
            return []
        
        # Build query from enabled topics
        topic_queries = []
        for topic in enabled_topics:
            # Add quotes around multi-word topics
            if " " in topic:
                topic_queries.append(f'"{topic}"')
            else:
                topic_queries.append(topic)
        
        # Add user queries if provided
        if user_queries:
            topic_queries.extend(user_queries)
        
        # Combine all queries with OR operator
        combined_query = " OR ".join(topic_queries) if topic_queries else "technology"
        
        # Combine enabled sources with comma separator
        domains = ",".join(enabled_sources) if enabled_sources else ""
        
        # Date range: from 2 days ago to today
        two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        target_count = max_articles or self.page_size
        per_page = min(100, max(1, int(target_count)))
        max_pages = max(1, (target_count + per_page - 1) // per_page)

        all_articles = []
        seen_urls = set()

        for page in range(1, max_pages + 1):
            params = {
                "q": combined_query,
                "language": self.language,
                "sortBy": "relevancy",
                "from": two_days_ago,
                "to": today,
                "pageSize": per_page,
                "page": page,
                "apiKey": self.api_key,
            }

            # Add domains parameter only if sources are specified
            if domains:
                params["domains"] = domains

            try:
                response = requests.get(self.url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                articles = data.get("articles", []) or []
            except requests.RequestException as e:
                print(f"Error fetching news: {e}")
                break

            if not articles:
                break

            for article in articles:
                url = (article or {}).get("url")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                all_articles.append(article)
                if len(all_articles) >= target_count:
                    break

            if len(all_articles) >= target_count:
                break

            # If the API returned fewer than requested for this page, there are no more results.
            if len(articles) < per_page:
                break

        return all_articles

    def fetch_news(self, query=None, sources=None):
        """
        Legacy method for backward compatibility - uses default settings
        """
        if query is None:
            query = "technology OR programming OR politics OR entertainment OR sports OR AI OR 'machine learning' OR 'data science'"
        
        if sources is None:
            sources = ["cnn.com", "bbc.com", "theverge.com", "techcrunch.com", "nytimes.com"]
        
        return self.fetch_news_for_user([query], sources)
