import os
import requests
from NewsBot.news_fetcher import NewsFetcher
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, JobQueue, CallbackQueryHandler, MessageHandler, filters
from NewsBot.db_helper import (
    create_user, update_user_activity, get_user_sources,
    get_enabled_sources_for_user,
    get_all_users, get_user_preferences, toggle_user_topic, get_user_topics,
    get_enabled_topics_for_user,
    get_user, set_user_language, get_user_language, delete_user
)
from NewsBot.categories import TOPIC_CATEGORIES, SOURCE_CATEGORIES, get_all_topics, get_all_sources
import pytz
from datetime import datetime, timedelta
import logging
import time
from math import ceil
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class TelegramBot:

    def __init__(self, token, api_key):
        self.token = token
        self.api_key = api_key
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        print("Starting Bot...")
        self.app = Application.builder().token(token).build()

        # Create NewsFetcher instance
        self.news_fetcher = NewsFetcher(api_key=self.api_key)

        # In-memory pagination cache for news messages (keyed by chat_id:message_id)
        self._news_pagination_cache = {}
        self._news_pagination_ttl_seconds = 60 * 60  # 1 hour
        self._news_items_per_page = 5
        self._news_fetch_max_articles = 50

        # Available news sources (now from categories)
        self.available_sources = get_all_sources()

        # Commands
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CommandHandler('help', self.help))
        self.app.add_handler(CommandHandler('info', self.show_info))
        self.app.add_handler(CommandHandler('news', self.send_news))
        self.app.add_handler(CommandHandler('topics', self.show_topics))
        self.app.add_handler(CommandHandler('sources', self.show_sources))
        self.app.add_handler(CommandHandler('language', self.language))
        self.app.add_handler(CommandHandler('delete', self.delete))
        
        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self.button_click))
        
        # Message handler for adding queries
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Error handler
        self.app.add_error_handler(self.error)

        # Job queue for scheduled news (only if available)
        try:
            self.job_queue = self.app.job_queue
            if self.job_queue:
                self.schedule_news_updates()
        except Exception as e:
            print(f"Job queue not available: {e}")
            self.job_queue = None

    def _prune_news_pagination_cache(self):
        now = time.time()
        expired_keys = [
            k
            for k, v in self._news_pagination_cache.items()
            if (now - float(v.get("created_at", now))) > self._news_pagination_ttl_seconds
        ]
        for k in expired_keys:
            self._news_pagination_cache.pop(k, None)

        # Hard cap to avoid unbounded growth (best-effort by created_at)
        max_entries = 500
        if len(self._news_pagination_cache) > max_entries:
            items = sorted(
                self._news_pagination_cache.items(),
                key=lambda kv: float(kv[1].get("created_at", 0.0)),
            )
            for k, _ in items[: len(self._news_pagination_cache) - max_entries]:
                self._news_pagination_cache.pop(k, None)

    def _news_cache_key(self, chat_id, message_id):
        return f"{chat_id}:{message_id}"

    @staticmethod
    def _google_translate_url(original_url: str, target_lang: str = "fa") -> str:
        if not original_url:
            return original_url
        try:
            return "https://translate.google.com/translate?" + urlencode(
                {"sl": "auto", "tl": target_lang, "u": original_url}
            )
        except Exception:
            return original_url

    def _translate_text(self, text: str, target_lang: str = "fa") -> str:
        text = (text or "").strip()
        if not text:
            return text

        # Very small best-effort in-memory cache to avoid re-translating across pagination.
        cache = getattr(self, "_translation_cache", None)
        if cache is None:
            cache = {}
            self._translation_cache = cache

        key = (target_lang, text)
        cached = cache.get(key)
        if isinstance(cached, str):
            return cached

        # Keep requests small: avoid very long query params / URLs.
        text_for_request = text[:500]
        try:
            resp = requests.get(
                "https://translate.googleapis.com/translate_a/single",
                params={
                    "client": "gtx",
                    "sl": "auto",
                    "tl": target_lang,
                    "dt": "t",
                    "q": text_for_request,
                },
                timeout=6,
            )
            resp.raise_for_status()
            data = resp.json()
            segments = (data or [None])[0] or []
            translated = "".join(
                seg[0] for seg in segments if isinstance(seg, list) and seg and isinstance(seg[0], str)
            ).strip()
            if not translated:
                translated = text
        except Exception:
            translated = text

        # Bound cache size (simple FIFO eviction).
        cache[key] = translated
        if len(cache) > 2000:
            try:
                oldest_key = next(iter(cache.keys()))
                cache.pop(oldest_key, None)
            except Exception:
                pass

        return translated

    def _build_news_page_text(self, articles, page_index, items_per_page, enabled_topics, enabled_sources, lang):
        total_items = len(articles)
        total_pages = max(1, ceil(total_items / max(1, items_per_page)))
        page_index = max(0, min(int(page_index), total_pages - 1))

        start = page_index * items_per_page
        end = min(total_items, start + items_per_page)
        page_articles = articles[start:end]

        header = "📰 Latest News (based on your preferences):\n\n" if lang != 'fa' else "📰 آخرین اخبار (بر اساس تنظیمات شما):\n\n"

        if enabled_topics:
            topics_label = "📚 Topics:" if lang != 'fa' else "📚 موضوعات:"
            header += f"{topics_label} {', '.join(enabled_topics[:3])}"
            if len(enabled_topics) > 3:
                more_text = " more" if lang != 'fa' else " بیشتر"
                header += f" (+{len(enabled_topics)-3}{more_text})"
            header += "\n"

        if enabled_sources:
            sources_label = "📰 Sources:" if lang != 'fa' else "📰 منابع:"
            header += f"{sources_label} {', '.join(enabled_sources[:3])}"
            if len(enabled_sources) > 3:
                more_text = " more" if lang != 'fa' else " بیشتر"
                header += f" (+{len(enabled_sources)-3}{more_text})"
            header += "\n"

        if lang == 'fa':
            header += f"\nصفحه {page_index + 1} از {total_pages}  |  خبرهای {start + 1} تا {end} از {total_items}\n"
        else:
            header += f"\nPage {page_index + 1} of {total_pages}  |  Items {start + 1}-{end} of {total_items}\n"

        header += "\n" + "=" * 50 + "\n\n"

        body = ""
        for article in page_articles:
            title_raw = (article or {}).get("title") or ("No title" if lang != 'fa' else "بدون عنوان")
            url = (article or {}).get("url") or ""
            desc_raw = (article or {}).get("description") or ("No description" if lang != 'fa' else "بدون توضیح")
            source = ((article or {}).get("source") or {}).get("name") or ("Unknown" if lang != 'fa' else "نامشخص")

            if lang == "fa":
                title = self._translate_text(title_raw, "fa")
                desc = self._translate_text(desc_raw, "fa")
            else:
                title = title_raw
                desc = desc_raw

            desc = desc.replace("\n", " ").strip()
            if len(desc) > 160:
                desc = desc[:160].rstrip() + "..."

            body += f"🔸 {title}\n"
            body += f"📝 {desc}\n"
            source_label = "📰 Source:" if lang != 'fa' else "📰 منبع:"
            body += f"{source_label} {source}\n"
            if url:
                if lang == "fa":
                    translated_url = self._google_translate_url(url, "fa")
                    body += f"🔗 لینک فارسی: {translated_url}\n"
                    body += f"🔗 لینک اصلی: {url}\n"
                else:
                    body += f"🔗 {url}\n"
            body += "\n"

        text = header + body

        # Telegram message limit is 4096; keep a safety margin.
        if len(text) > 3900:
            text = text[:3890].rstrip() + "\n…"

        return text, total_pages

    def _build_news_pagination_keyboard(self, lang):
        prev_text = "⬅️ Prev" if lang != 'fa' else "⬅️ قبلی"
        next_text = "Next ➡️" if lang != 'fa' else "بعدی ➡️"
        keyboard = [[
            InlineKeyboardButton(prev_text, callback_data="news:prev"),
            InlineKeyboardButton(next_text, callback_data="news:next"),
        ]]
        return InlineKeyboardMarkup(keyboard)

    async def run_async(self):
        print("polling...")
        await self.app.run_polling(
            poll_interval=3.0,
            timeout=30,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )

    def schedule_news_updates(self):
        """Schedule news updates every 4 hours"""
        if not self.job_queue:
            return
            
        iran_time_zone = pytz.timezone('Asia/Tehran')
        now = datetime.now(iran_time_zone)

        # Schedule times: 8 AM, 12 PM, 4 PM, 8 PM, 12 AM, 4 AM IRST
        times = [8, 12, 16, 20, 0, 4]
        for hour in times:
            scheduled_time = iran_time_zone.localize(datetime(now.year, now.month, now.day, hour, 0))
            if scheduled_time < now:
                scheduled_time += timedelta(days=1)

            self.job_queue.run_once(self.send_scheduled_news, when=scheduled_time)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            if not hasattr(update, 'message') or update.message is None or not hasattr(update, 'effective_user') or update.effective_user is None:
                return
            chat_id = str(update.message.chat.id)
            user = update.effective_user
            user_obj = get_user(chat_id)
            if not user_obj:
                create_user(
                    chat_id=chat_id,
                    username=getattr(user, 'username', None),
                    first_name=getattr(user, 'first_name', None),
                    last_name=getattr(user, 'last_name', None),
                    language=None
                )
                user_obj = get_user(chat_id)
            # Ask for language selection if not set
            if not user_obj or not getattr(user_obj, 'language', None):
                keyboard = [
                    [InlineKeyboardButton("English 🇬🇧", callback_data="set_lang_en")],
                    [InlineKeyboardButton("فارسی 🇮🇷", callback_data="set_lang_fa")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                if update.message:
                    await update.message.reply_text("Please select your language:\nلطفا زبان خود را انتخاب کنید:", reply_markup=reply_markup)
                return
            lang = user_obj.language
            await self.send_welcome_message(update, lang)
        except Exception as e:
            print(f"Error in start command: {e}")
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text("❌ An error occurred. Please try again.\nیک خطا رخ داد. لطفا دوباره تلاش کنید.")

    async def send_welcome_message(self, update_or_query, lang):
        if lang == 'fa':
            welcome_message = (
                "🎉 به ربات خبرخوان تلگرام خوش آمدید!\n\n"
                "📰 من اخبار شخصی‌سازی شده بر اساس علاقه‌مندی‌های شما ارسال می‌کنم.\n\n"
                "🔧 دستورات موجود:\n"
                "/topics - مدیریت موضوعات خبری\n"
                "/sources - مدیریت منابع خبری\n"
                "/news - دریافت آخرین اخبار\n"
                "/help - راهنمای ربات\n"
                "/language - تغییر زبان ربات\n\n"
                "⚙️ می‌توانید موارد زیر را شخصی‌سازی کنید:\n"
                "• موضوعات خبری (تکنولوژی، علم، سیاست و ...)\n"
                "• منابع خبری (CNN، BBC، TechCrunch و ...)\n\n"
                "📅 اخبار به صورت خودکار هر ۴ ساعت در زمان‌های زیر ارسال می‌شود:\n"
                "۸ صبح، ۱۲ ظهر، ۴ عصر، ۸ شب، ۱۲ شب، ۴ صبح (به وقت ایران)\n\n"
                "برای تنظیم موضوعات، روی /topics کلیک کنید!"
            )
        else:
            welcome_message = (
                "🎉 Welcome to MyTelegramNewsBot!\n\n"
                "📰 I'll send you personalized news based on your preferences.\n\n"
                "🔧 Available commands:\n"
                "/topics - Manage your news topics by category\n"
                "/sources - Manage your news sources by category\n"
                "/news - Get latest news now\n"
                "/help - Show this help message\n"
                "/language - Change bot language\n\n"
                "⚙️ You can customize:\n"
                "• News topics (Technology, Science, Politics, etc.)\n"
                "• News sources (CNN, BBC, TechCrunch, etc.)\n\n"
                "📅 News will be sent automatically every 4 hours at:\n"
                "8 AM, 12 PM, 4 PM, 8 PM, 12 AM, 4 AM (IRST)\n\n"
                "Click /topics to set up your topics!"
            )
        # Handle both Update and CallbackQuery
        if hasattr(update_or_query, 'message') and update_or_query.message:
            await update_or_query.message.reply_text(welcome_message)
        elif hasattr(update_or_query, 'edit_message_text'):
            await update_or_query.edit_message_text(welcome_message)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        lang = get_user_language(str(update.message.chat.id)) if hasattr(update, 'message') and update.message else 'en'
        if lang == 'fa':
            help_message = (
                "📚 دستورات ربات:\n\n"
                "/start - شروع ربات\n"
                "/help - راهنمای ربات\n"
                "/info - نمایش تنظیمات فعلی شما\n"
                "/topics - مدیریت موضوعات خبری\n"
                "/sources - مدیریت منابع خبری\n"
                "/news - دریافت آخرین اخبار\n"
                "/language - تغییر زبان ربات\n\n"
                "🔧 با استفاده از /topics و /sources خبرهای خود را شخصی‌سازی کنید!"
            )
        else:
            help_message = (
                "📚 Bot Commands:\n\n"
                "/start - Initialize the bot\n"
                "/help - Show this help message\n"
                "/info - Show your current preferences\n"
                "/topics - Manage news topics by category\n"
                "/sources - Manage news sources by category\n"
                "/news - Get latest news now\n"
                "/language - Change bot language\n\n"
                "🔧 Use /topics and /sources to customize your news feed!"
            )
        await update.message.reply_text(help_message)

    async def show_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command - Show user's current preferences"""
        try:
            if not hasattr(update, 'message') or update.message is None:
                return
            chat_id = str(update.message.chat.id)
            update_user_activity(chat_id)
            lang = get_user_language(chat_id)
            # Get user preferences
            enabled_topics = get_enabled_topics_for_user(chat_id)
            enabled_sources = get_enabled_sources_for_user(chat_id)
            # queries = get_user_queries(chat_id)  # Removed
            # Build info message
            if lang == 'fa':
                info_message = "📊 تنظیمات فعلی شما:\n\n"
                info_message += f"📚 موضوعات فعال ({len(enabled_topics)}):\n"
                if enabled_topics:
                    for i, topic in enumerate(enabled_topics, 1):
                        info_message += f"{i}. {topic}\n"
                else:
                    info_message += "هیچ موضوعی فعال نیست. با /topics موضوعات را فعال کنید!\n"
                info_message += f"\n📰 منابع فعال ({len(enabled_sources)}):\n"
                if enabled_sources:
                    for i, source in enumerate(enabled_sources, 1):
                        info_message += f"{i}. {source}\n"
                else:
                    info_message += "هیچ منبعی فعال نیست. با /sources منابع را فعال کنید!\n"
            else:
                info_message = "📊 Your Current Preferences:\n\n"
                info_message += f"📚 Enabled Topics ({len(enabled_topics)}):\n"
                if enabled_topics:
                    for i, topic in enumerate(enabled_topics, 1):
                        info_message += f"{i}. {topic}\n"
                else:
                    info_message += "No topics enabled. Use /topics to enable some!\n"
                info_message += f"\n📰 Enabled Sources ({len(enabled_sources)}):\n"
                if enabled_sources:
                    for i, source in enumerate(enabled_sources, 1):
                        info_message += f"{i}. {source}\n"
                else:
                    info_message += "No sources enabled. Use /sources to enable some!\n"
            # Add action buttons
            keyboard = [
                [InlineKeyboardButton("📚 Manage Topics" if lang != 'fa' else "📚 مدیریت موضوعات", callback_data="show_topics")],
                [InlineKeyboardButton("📰 Manage Sources" if lang != 'fa' else "📰 مدیریت منابع", callback_data="show_sources")],
                [InlineKeyboardButton("📰 Get News Now" if lang != 'fa' else "📰 دریافت خبر", callback_data="get_news")],
                [InlineKeyboardButton("🗑 Delete My Data" if lang != 'fa' else "🗑 حذف اطلاعات من", callback_data="delete_user")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if update.message:
                await update.message.reply_text(info_message, reply_markup=reply_markup)
        except Exception as e:
            print(f"Error in show_info: {e}")
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text("❌ An error occurred. Please try again." if lang != 'fa' else "❌ خطایی رخ داد. لطفا دوباره تلاش کنید.")

    async def show_topics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show topic categories with inline buttons"""
        try:
            if not hasattr(update, 'message') or update.message is None:
                return
            chat_id = str(update.message.chat.id)
            update_user_activity(chat_id)
            lang = get_user_language(chat_id)
            message = "📚 Choose a topic category to manage your news topics:\n\n" if lang != 'fa' else "📚 یک دسته‌بندی موضوعی را برای مدیریت موضوعات خبری انتخاب کنید:\n\n"
            # Create first-level keyboard with categories
            keyboard = []
            for cat_id, cat_data in TOPIC_CATEGORIES.items():
                keyboard.append([
                    InlineKeyboardButton(
                        cat_data["name"], 
                        callback_data=f"cat:{cat_id}"
                    )
                ])
            # Add navigation buttons
            keyboard.append([
                InlineKeyboardButton("🔧 Sources" if lang != 'fa' else "🔧 منابع", callback_data="show_sources"),
                InlineKeyboardButton("📰 Get News" if lang != 'fa' else "📰 دریافت خبر", callback_data="get_news")
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            if update.message:
                await update.message.reply_text(message, reply_markup=reply_markup)
        except Exception as e:
            print(f"Error in show_topics: {e}")
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text("❌ An error occurred. Please try again." if lang != 'fa' else "❌ خطایی رخ داد. لطفا دوباره تلاش کنید.")

    async def show_sources(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show source categories with inline buttons"""
        try:
            if not hasattr(update, 'message') or update.message is None:
                return
            chat_id = str(update.message.chat.id)
            update_user_activity(chat_id)
            lang = get_user_language(chat_id)
            message = "📰 Choose a source category to manage your news sources:\n\n" if lang != 'fa' else "📰 یک دسته‌بندی منبع را برای مدیریت منابع خبری انتخاب کنید:\n\n"
            # Create first-level keyboard with categories
            keyboard = []
            for cat_id, cat_data in SOURCE_CATEGORIES.items():
                keyboard.append([
                    InlineKeyboardButton(
                        cat_data["name"], 
                        callback_data=f"NewsBot_cat:{cat_id}"
                    )
                ])
            # Add navigation buttons
            keyboard.append([
                InlineKeyboardButton("📚 Topics" if lang != 'fa' else "📚 موضوعات", callback_data="show_topics"),
                InlineKeyboardButton("📰 Get News" if lang != 'fa' else "📰 دریافت خبر", callback_data="get_news")
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            if update.message:
                await update.message.reply_text(message, reply_markup=reply_markup)
        except Exception as e:
            print(f"Error in show_sources: {e}")
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text("❌ An error occurred. Please try again." if lang != 'fa' else "❌ خطایی رخ داد. لطفا دوباره تلاش کنید.")

    async def show_topic_category(self, chat_id, category_id):
        """Show topics within a specific category"""
        try:
            cat_data = TOPIC_CATEGORIES.get(category_id)
            if not cat_data:
                return None
            
            user_topics = get_user_topics(chat_id)
            lang = get_user_language(chat_id)
            
            message_text = f"📚 {cat_data['name']}\n\nSelect topics to enable/disable:\n\n" if lang != 'fa' else f"📚 {cat_data['name']}\n\nموضوعات را برای فعال/غیرفعال کردن انتخاب کنید:\n\n"
            
            # Create second-level keyboard with topic toggles
            keyboard = []
            for topic in cat_data["topics"]:
                is_enabled = user_topics.get(topic, False)
                status = "✅" if is_enabled else "❌"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status} {topic}", 
                        callback_data=f"topic:{topic}"
                    )
                ])
            
            # Add navigation buttons
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Categories" if lang != 'fa' else "⬅️ بازگشت به دسته‌ها", callback_data="show_topics"),
                InlineKeyboardButton("🔧 Sources" if lang != 'fa' else "🔧 منابع", callback_data="show_sources")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            return message_text, reply_markup
            
        except Exception as e:
            print(f"Error in show_topic_category: {e}")
            return None

    async def show_source_category(self, chat_id, category_id):
        """Show sources within a specific category"""
        try:
            cat_data = SOURCE_CATEGORIES.get(category_id)
            if not cat_data:
                return None
            
            user_sources = get_user_sources(chat_id)
            lang = get_user_language(chat_id)
            
            message_text = f"📰 {cat_data['name']}\n\nSelect sources to enable/disable:\n\n" if lang != 'fa' else f"📰 {cat_data['name']}\n\nمنابع را برای فعال/غیرفعال کردن انتخاب کنید:\n\n"
            
            # Create second-level keyboard with source toggles
            keyboard = []
            for source in cat_data["sources"]:
                is_enabled = user_sources.get(source, False)
                status = "✅" if is_enabled else "❌"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status} {source}", 
                        callback_data=f"source:{source}"
                    )
                ])
            
            # Add navigation buttons
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Categories" if lang != 'fa' else "⬅️ بازگشت به دسته‌ها", callback_data="show_sources"),
                InlineKeyboardButton("📚 Topics" if lang != 'fa' else "📚 موضوعات", callback_data="show_topics")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            return message_text, reply_markup
            
        except Exception as e:
            print(f"Error in show_source_category: {e}")
            return None

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        try:
            chat_id = str(update.message.chat.id)
            update_user_activity(chat_id)
            
            # Regular message - suggest using commands
            await update.message.reply_text(
                "💡 Use /help to see available commands or /topics to manage your settings!"
            )
        except Exception as e:
            print(f"Error in handle_message: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")

    async def button_click(self, update: Update, context: CallbackContext):
        """Handle inline button clicks"""
        query = update.callback_query
        chat_id = str(query.message.chat.id)
        data = query.data
        try:
            update_user_activity(chat_id)

            # If user record was deleted, allow re-registration via the same initial flow.
            if not get_user(chat_id) and data not in ("confirm_delete", "cancel_delete") and not data.startswith("set_lang_"):
                user = update.effective_user
                create_user(
                    chat_id=chat_id,
                    username=getattr(user, 'username', None),
                    first_name=getattr(user, 'first_name', None),
                    last_name=getattr(user, 'last_name', None),
                    language=None,
                )
                keyboard = [
                    [InlineKeyboardButton("English 🇬🇧", callback_data="set_lang_en")],
                    [InlineKeyboardButton("فارسی 🇮🇷", callback_data="set_lang_fa")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    "Please select your language:\nلطفا زبان خود را انتخاب کنید:",
                    reply_markup=reply_markup,
                )
                return

            if data in ("news:prev", "news:next"):
                self._prune_news_pagination_cache()
                lang = get_user_language(chat_id)
                key = self._news_cache_key(chat_id, query.message.message_id)
                state = self._news_pagination_cache.get(key)

                if not state:
                    expired_message = "⏳ This news list expired. Send /news again." if lang != 'fa' else "⏳ این لیست منقضی شده. دوباره /news را ارسال کنید."
                    await query.answer(expired_message, show_alert=False)
                    return

                delta = -1 if data == "news:prev" else 1
                current_page = int(state.get("page_index", 0))
                items_per_page = int(state.get("items_per_page", self._news_items_per_page))
                articles = state.get("articles", []) or []
                enabled_topics = state.get("enabled_topics", []) or []
                enabled_sources = state.get("enabled_sources", []) or []

                _, total_pages = self._build_news_page_text(
                    articles,
                    current_page,
                    items_per_page,
                    enabled_topics,
                    enabled_sources,
                    lang,
                )
                next_page = current_page + delta

                if next_page < 0:
                    await query.answer("Already on the first page." if lang != 'fa' else "شما در اولین صفحه هستید.", show_alert=False)
                    return
                if next_page >= total_pages:
                    await query.answer("Already on the last page." if lang != 'fa' else "شما در آخرین صفحه هستید.", show_alert=False)
                    return

                state["page_index"] = next_page
                state["created_at"] = time.time()
                self._news_pagination_cache[key] = state

                new_text, _ = self._build_news_page_text(
                    articles,
                    next_page,
                    items_per_page,
                    enabled_topics,
                    enabled_sources,
                    lang,
                )
                await query.answer()
                await query.edit_message_text(
                    text=new_text,
                    reply_markup=self._build_news_pagination_keyboard(lang),
                    disable_web_page_preview=(lang == "fa"),
                )
                return

            if data == "set_lang_en":
                if not get_user(chat_id):
                    user = update.effective_user
                    create_user(
                        chat_id=chat_id,
                        username=getattr(user, 'username', None),
                        first_name=getattr(user, 'first_name', None),
                        last_name=getattr(user, 'last_name', None),
                        language=None,
                    )
                set_user_language(chat_id, 'en')
                await query.answer()
                await query.edit_message_text("✅ Registration completed.\nLanguage set to English.\nزبان به انگلیسی تغییر یافت.")
                await self.send_welcome_message(query, 'en')
            elif data == "set_lang_fa":
                if not get_user(chat_id):
                    user = update.effective_user
                    create_user(
                        chat_id=chat_id,
                        username=getattr(user, 'username', None),
                        first_name=getattr(user, 'first_name', None),
                        last_name=getattr(user, 'last_name', None),
                        language=None,
                    )
                set_user_language(chat_id, 'fa')
                await query.answer()
                await query.edit_message_text("✅ ثبت‌نام انجام شد.\nزبان به فارسی تغییر یافت.\nLanguage set to Farsi.")
                await self.send_welcome_message(query, 'fa')
            else:
                # Handle topic category selection
                if data.startswith("cat:"):
                    category_id = data.split(":")[1]
                    result = await self.show_topic_category(chat_id, category_id)
                    if result:
                        message_text, reply_markup = result
                        await query.edit_message_text(text=message_text, reply_markup=reply_markup)
                    else:
                        await query.message.reply_text("❌ Category not found.")
                    
                # Handle source category selection
                elif data.startswith("NewsBot_cat:"):
                    category_id = data.split(":")[1]
                    result = await self.show_source_category(chat_id, category_id)
                    if result:
                        message_text, reply_markup = result
                        await query.edit_message_text(text=message_text, reply_markup=reply_markup)
                    else:
                        await query.message.reply_text("❌ Category not found.")
                    
                # Handle topic toggle
                elif data.startswith("topic:"):
                    topic_name = data.split(":", 1)[1]
                    is_enabled = toggle_user_topic(chat_id, topic_name)
                    status = "enabled" if is_enabled else "disabled"
                    
                    # Recreate the keyboard with updated status
                    keyboard = []
                    user_topics = get_user_topics(chat_id)
                    
                    # Find which category this topic belongs to
                    from NewsBot.categories import get_topic_category
                    category_id = get_topic_category(topic_name)
                    if category_id and category_id in TOPIC_CATEGORIES:
                        cat_data = TOPIC_CATEGORIES[category_id]
                        
                        # Recreate topic buttons
                        for topic in cat_data["topics"]:
                            is_topic_enabled = user_topics.get(topic, False)
                            status_icon = "✅" if is_topic_enabled else "❌"
                            keyboard.append([
                                InlineKeyboardButton(
                                    f"{status_icon} {topic}", 
                                    callback_data=f"topic:{topic}"
                                )
                            ])
                        
                        # Add navigation buttons
                        lang = get_user_language(chat_id)
                        keyboard.append([
                            InlineKeyboardButton("⬅️ Back to Categories" if lang != 'fa' else "⬅️ بازگشت به دسته‌ها", callback_data="show_topics"),
                            InlineKeyboardButton("🔧 Sources" if lang != 'fa' else "🔧 منابع", callback_data="show_sources")
                        ])
                        
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        # Check if markup is different before updating
                        if query.message.reply_markup and query.message.reply_markup.to_dict() == reply_markup.to_dict():
                            await query.answer("No change.")
                        else:
                            await query.edit_message_reply_markup(reply_markup=reply_markup)
                    else:
                        await query.message.reply_text(f"❌ Error: Topic category not found")
                
                # Handle source toggle
                elif data.startswith("source:"):
                    source_domain = data.split(":", 1)[1]
                    # Inline toggle_user_source logic
                    from NewsBot.db_helper import get_session
                    from NewsBot.models import UserSource
                    session = get_session()
                    try:
                        user = get_user(chat_id)
                        is_enabled = None
                        if user:
                            user_source = session.query(UserSource).filter_by(user_id=user.id, source_domain=source_domain).first()
                            if user_source:
                                user_source.is_enabled = not user_source.is_enabled
                                session.commit()
                                is_enabled = user_source.is_enabled
                            else:
                                # Create new source entry if it doesn't exist
                                user_source = UserSource(
                                    user_id=user.id,
                                    source_domain=source_domain,
                                    is_enabled=True
                                )
                                session.add(user_source)
                                session.commit()
                                is_enabled = True
                    except Exception as e:
                        session.rollback()
                        raise e
                    finally:
                        session.close()
                    status = "enabled" if is_enabled else "disabled"
                    
                    # Recreate the keyboard with updated status
                    keyboard = []
                    user_sources = get_user_sources(chat_id)
                    
                    # Find which category this source belongs to
                    from NewsBot.categories import get_source_category
                    category_id = get_source_category(source_domain)
                    if category_id and category_id in SOURCE_CATEGORIES:
                        cat_data = SOURCE_CATEGORIES[category_id]
                        
                        # Recreate source buttons
                        for source in cat_data["sources"]:
                            is_source_enabled = user_sources.get(source, False)
                            status_icon = "✅" if is_source_enabled else "❌"
                            keyboard.append([
                                InlineKeyboardButton(
                                    f"{status_icon} {source}", 
                                    callback_data=f"source:{source}"
                                )
                            ])
                        
                        # Add navigation buttons
                        lang = get_user_language(chat_id)
                        keyboard.append([
                            InlineKeyboardButton("⬅️ Back to Categories" if lang != 'fa' else "⬅️ بازگشت به دسته‌ها", callback_data="show_sources"),
                            InlineKeyboardButton("📚 Topics" if lang != 'fa' else "📚 موضوعات", callback_data="show_topics")
                        ])
                        
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        # Check if markup is different before updating
                        if query.message.reply_markup and query.message.reply_markup.to_dict() == reply_markup.to_dict():
                            await query.answer("No change.")
                        else:
                            await query.edit_message_reply_markup(reply_markup=reply_markup)
                    else:
                        await query.message.reply_text(f"❌ Error: Source category not found")
                
                # Handle navigation buttons
                elif data == "show_topics":
                    lang = get_user_language(chat_id)
                    
                    message = "📚 Choose a topic category to manage your news topics:\n\n" if lang != 'fa' else "📚 یک دسته‌بندی موضوعی را برای مدیریت موضوعات خبری انتخاب کنید:\n\n"
                    
                    # Create first-level keyboard with categories
                    keyboard = []
                    for cat_id, cat_data in TOPIC_CATEGORIES.items():
                        keyboard.append([
                            InlineKeyboardButton(
                                cat_data["name"], 
                                callback_data=f"cat:{cat_id}"
                            )
                        ])
                    
                    # Add navigation buttons
                    keyboard.append([
                        InlineKeyboardButton("🔧 Sources" if lang != 'fa' else "🔧 منابع", callback_data="show_sources"),
                        InlineKeyboardButton("📰 Get News" if lang != 'fa' else "📰 دریافت خبر", callback_data="get_news")
                    ])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(text=message, reply_markup=reply_markup)
                    
                elif data == "show_sources":
                    lang = get_user_language(chat_id)
                    
                    message = "📰 Choose a source category to manage your news sources:\n\n" if lang != 'fa' else "📰 یک دسته‌بندی منبع را برای مدیریت منابع خبری انتخاب کنید:\n\n"
                    
                    # Create first-level keyboard with categories
                    keyboard = []
                    for cat_id, cat_data in SOURCE_CATEGORIES.items():
                        keyboard.append([
                            InlineKeyboardButton(
                                cat_data["name"], 
                                callback_data=f"NewsBot_cat:{cat_id}"
                            )
                        ])
                    
                    # Add navigation buttons
                    keyboard.append([
                        InlineKeyboardButton("📚 Topics" if lang != 'fa' else "📚 موضوعات", callback_data="show_topics"),
                        InlineKeyboardButton("📰 Get News" if lang != 'fa' else "📰 دریافت خبر", callback_data="get_news")
                    ])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(text=message, reply_markup=reply_markup)
                    
                elif data == "delete_user":
                    lang = get_user_language(chat_id)
                    if lang == 'fa':
                        text = "⚠️ آیا مطمئن هستید می‌خواهید تمام اطلاعات شما از دیتابیس حذف شود؟\nاین کار برگشت‌پذیر نیست."
                        confirm_text = "✅ تایید حذف"
                        cancel_text = "❌ انصراف"
                    else:
                        text = "⚠️ Are you sure you want to delete all your data from the database?\nThis action cannot be undone."
                        confirm_text = "✅ Confirm Delete"
                        cancel_text = "❌ Cancel"
                    reply_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton(confirm_text, callback_data="confirm_delete")],
                        [InlineKeyboardButton(cancel_text, callback_data="cancel_delete")],
                    ])
                    await query.edit_message_text(text=text, reply_markup=reply_markup)

                elif data == "confirm_delete":
                    lang = get_user_language(chat_id)
                    deleted = delete_user(chat_id)

                    # Clear any in-memory cached news for this chat
                    keys_to_delete = [k for k in self._news_pagination_cache.keys() if k.startswith(f"{chat_id}:")]
                    for k in keys_to_delete:
                        self._news_pagination_cache.pop(k, None)

                    if lang == 'fa':
                        text = "✅ اطلاعات شما با موفقیت حذف شد.\nبرای ثبت‌نام مجدد، دستور /start را بزنید." if deleted else "ℹ️ اطلاعاتی برای حذف وجود نداشت.\nبرای ثبت‌نام، /start را بزنید."
                    else:
                        text = "✅ Your data has been deleted successfully.\nTo register again, send /start." if deleted else "ℹ️ No data was found to delete.\nTo register, send /start."
                    await query.edit_message_text(text=text)

                elif data == "cancel_delete":
                    lang = get_user_language(chat_id)
                    text = "✅ Deletion canceled." if lang != 'fa' else "✅ عملیات حذف لغو شد."
                    keyboard = [
                        [InlineKeyboardButton("📚 Manage Topics" if lang != 'fa' else "📚 مدیریت موضوعات", callback_data="show_topics")],
                        [InlineKeyboardButton("📰 Manage Sources" if lang != 'fa' else "📰 مدیریت منابع", callback_data="show_sources")],
                        [InlineKeyboardButton("📰 Get News Now" if lang != 'fa' else "📰 دریافت خبر", callback_data="get_news")],
                        [InlineKeyboardButton("🗑 Delete My Data" if lang != 'fa' else "🗑 حذف اطلاعات من", callback_data="delete_user")],
                    ]
                    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))

                elif data == "get_news":
                    enabled_sources = get_enabled_sources_for_user(chat_id)
                    enabled_topics = get_enabled_topics_for_user(chat_id)
                    if not enabled_topics or not enabled_sources:
                        await self.send_news_to_user(chat_id, None, context)
                        return

                    # Send a loading message first
                    lang = get_user_language(chat_id)
                    loading_message = "📰 Fetching your personalized news..." if lang != 'fa' else "📰 در حال دریافت اخبار شخصی‌سازی شده شما..."
                    await query.message.reply_text(loading_message)
                    await self.send_news_to_user(chat_id, None, context)
                
        except Exception as e:
            print("Exception in button_click:", e)
            logger.exception("Error in button_click")
            await query.edit_message_text("❌ An error occurred. Please try again.\nیک خطا رخ داد. لطفا دوباره تلاش کنید.")

    async def send_news(self, update: Update, context: CallbackContext):
        """Handle /news command"""
        try:
            chat_id = str(update.message.chat.id)
            update_user_activity(chat_id)
            await self.send_news_to_user(chat_id, update, context)
        except Exception as e:
            logger.exception("Error in send_news")
            lang = get_user_language(chat_id)
            error_message = "❌ An error occurred. Please try again." if lang != 'fa' else "❌ خطایی رخ داد. لطفا دوباره تلاش کنید."
            await update.message.reply_text(error_message)

    async def send_news_to_user(self, chat_id, update=None, context=None):
        """Send personalized news to a specific user"""
        try:
            if not get_user(chat_id):
                message = "❌ Please send /start and choose your language first.\nلطفاً ابتدا /start را بزنید و زبان را انتخاب کنید."
                if update and getattr(update, "message", None):
                    await update.message.reply_text(message)
                else:
                    await self.app.bot.send_message(chat_id, message)
                return

            # Get user preferences and language
            enabled_sources = get_enabled_sources_for_user(chat_id)
            enabled_topics = get_enabled_topics_for_user(chat_id)
            lang = get_user_language(chat_id)

            async def send_text(text):
                if update and getattr(update, "message", None):
                    await update.message.reply_text(text)
                else:
                    await self.app.bot.send_message(chat_id, text)
            
            # Check if user has selected both topics and sources
            if not enabled_topics or not enabled_sources:
                if lang == 'fa':
                    if not enabled_topics and not enabled_sources:
                        message = "❌ ابتدا از بخش «موضوعات» و «منابع»، موارد دلخواه را انتخاب کنید و بعد دوباره روی «دریافت خبر» بزنید.\n/topics و /sources"
                    elif not enabled_topics:
                        message = "❌ ابتدا از بخش «موضوعات» حداقل یک موضوع را انتخاب کنید و بعد دوباره روی «دریافت خبر» بزنید.\n/topics"
                    else:
                        message = "❌ ابتدا از بخش «منابع» حداقل یک منبع را انتخاب کنید و بعد دوباره روی «دریافت خبر» بزنید.\n/sources"
                else:
                    if not enabled_topics and not enabled_sources:
                        message = "❌ First select at least one Topic and one Source, then tap News again.\n/topics and /sources"
                    elif not enabled_topics:
                        message = "❌ First select at least one Topic, then tap News again.\n/topics"
                    else:
                        message = "❌ First select at least one Source, then tap News again.\n/sources"
                await send_text(message)
                return
            
            # Fetch personalized news using the new topic system
            articles = self.news_fetcher.fetch_news_by_topics_and_sources(
                enabled_topics, enabled_sources, max_articles=self._news_fetch_max_articles
            )
            
            if not articles:
                message = "📭 No news found matching your preferences. Try adjusting your topics or sources." if lang != 'fa' else "📭 هیچ خبری مطابق با تنظیمات شما یافت نشد. موضوعات یا منابع خود را تنظیم کنید."
                await send_text(message)
                return
            
            items_per_page = self._news_items_per_page
            page_text, total_pages = self._build_news_page_text(
                articles,
                0,
                items_per_page,
                enabled_topics,
                enabled_sources,
                lang,
            )

            reply_markup = self._build_news_pagination_keyboard(lang) if total_pages > 1 else None

            disable_preview = lang == "fa"
            if update:
                sent = await update.message.reply_text(
                    page_text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_preview,
                )
            else:
                sent = await self.app.bot.send_message(
                    chat_id,
                    page_text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_preview,
                )

            if total_pages > 1 and sent:
                self._prune_news_pagination_cache()
                key = self._news_cache_key(chat_id, sent.message_id)
                self._news_pagination_cache[key] = {
                    "created_at": time.time(),
                    "page_index": 0,
                    "items_per_page": items_per_page,
                    "articles": articles,
                    "enabled_topics": enabled_topics,
                    "enabled_sources": enabled_sources,
                }
        except Exception as e:
            logger.exception("Error in send_news_to_user")
            lang = get_user_language(chat_id)
            error_message = "❌ An error occurred while fetching news. Please try again later." if lang != 'fa' else "❌ خطایی در دریافت اخبار رخ داد. لطفا دوباره تلاش کنید."
            if update and getattr(update, "message", None):
                await update.message.reply_text(error_message)
            else:
                await self.app.bot.send_message(chat_id, error_message)
            return

    async def send_scheduled_news(self, context: CallbackContext):
        """Send scheduled news to all users"""
        try:
            users = get_all_users()
            for user in users:
                await self.send_news_to_user(user.chat_id)
        except Exception as e:
            logger.exception("Error in send_scheduled_news")

    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error", exc_info=context.error)
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again later."
                )
        except:
            pass

    async def language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.message.chat.id)
        lang = get_user_language(chat_id)
        if lang == 'fa':
            prompt = "لطفا زبان مورد نظر خود را انتخاب کنید:"
        else:
            prompt = "Please select your language:"
        keyboard = [
            [InlineKeyboardButton("English 🇬🇧", callback_data="set_lang_en")],
            [InlineKeyboardButton("فارسی 🇮🇷", callback_data="set_lang_fa")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(prompt, reply_markup=reply_markup)

    async def delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.message.chat.id)
        lang = get_user_language(chat_id)
        if lang == 'fa':
            text = "⚠️ آیا مطمئن هستید می‌خواهید تمام اطلاعات شما از دیتابیس حذف شود؟\nاین کار برگشت‌پذیر نیست."
            confirm_text = "✅ تایید حذف"
            cancel_text = "❌ انصراف"
        else:
            text = "⚠️ Are you sure you want to delete all your data from the database?\nThis action cannot be undone."
            confirm_text = "✅ Confirm Delete"
            cancel_text = "❌ Cancel"
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(confirm_text, callback_data="confirm_delete")],
            [InlineKeyboardButton(cancel_text, callback_data="cancel_delete")],
        ])
        await update.message.reply_text(text, reply_markup=reply_markup)

