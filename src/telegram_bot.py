import os
import requests
from src.news_fetcher import NewsFetcher
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, JobQueue, CallbackQueryHandler, MessageHandler, filters
from src.db_helper import (
    create_user, update_user_activity, get_user_sources,
    get_enabled_sources_for_user,
    get_all_users, get_user_preferences, toggle_user_topic, get_user_topics,
    get_enabled_topics_for_user, initialize_user_topics, initialize_user_sources,
    get_user, set_user_language, get_user_language
)
from src.categories import TOPIC_CATEGORIES, SOURCE_CATEGORIES, get_all_topics, get_all_sources
import pytz
from datetime import datetime, timedelta
import logging

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
                    language='en'
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
                [InlineKeyboardButton("📰 Get News Now" if lang != 'fa' else "📰 دریافت خبر", callback_data="get_news")]
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
            # Initialize topics if not already done
            initialize_user_topics(chat_id)
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
            # Initialize sources if not already done
            initialize_user_sources(chat_id)
            message = "📰 Choose a source category to manage your news sources:\n\n" if lang != 'fa' else "📰 یک دسته‌بندی منبع را برای مدیریت منابع خبری انتخاب کنید:\n\n"
            # Create first-level keyboard with categories
            keyboard = []
            for cat_id, cat_data in SOURCE_CATEGORIES.items():
                keyboard.append([
                    InlineKeyboardButton(
                        cat_data["name"], 
                        callback_data=f"src_cat:{cat_id}"
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
            if data == "set_lang_en":
                set_user_language(chat_id, 'en')
                await query.answer()
                await query.edit_message_text("Language set to English.\nزبان به انگلیسی تغییر یافت.")
                await self.send_welcome_message(query, 'en')
            elif data == "set_lang_fa":
                set_user_language(chat_id, 'fa')
                await query.answer()
                await query.edit_message_text("زبان به فارسی تغییر یافت.\nLanguage set to Farsi.")
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
                elif data.startswith("src_cat:"):
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
                    from src.categories import get_topic_category
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
                    from src.db_helper import get_user, get_session
                    from src.models import UserSource
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
                    from src.categories import get_source_category
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
                    # Initialize topics if not already done
                    initialize_user_topics(chat_id)
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
                    # Initialize sources if not already done
                    initialize_user_sources(chat_id)
                    lang = get_user_language(chat_id)
                    
                    message = "📰 Choose a source category to manage your news sources:\n\n" if lang != 'fa' else "📰 یک دسته‌بندی منبع را برای مدیریت منابع خبری انتخاب کنید:\n\n"
                    
                    # Create first-level keyboard with categories
                    keyboard = []
                    for cat_id, cat_data in SOURCE_CATEGORIES.items():
                        keyboard.append([
                            InlineKeyboardButton(
                                cat_data["name"], 
                                callback_data=f"src_cat:{cat_id}"
                            )
                        ])
                    
                    # Add navigation buttons
                    keyboard.append([
                        InlineKeyboardButton("📚 Topics" if lang != 'fa' else "📚 موضوعات", callback_data="show_topics"),
                        InlineKeyboardButton("📰 Get News" if lang != 'fa' else "📰 دریافت خبر", callback_data="get_news")
                    ])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(text=message, reply_markup=reply_markup)
                    
                elif data == "get_news":
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
            # Get user preferences and language
            enabled_sources = get_enabled_sources_for_user(chat_id)
            enabled_topics = get_enabled_topics_for_user(chat_id)
            lang = get_user_language(chat_id)
            
            # Check if user has any preferences set
            if not enabled_topics and not enabled_sources:
                message = "❌ No preferences set. Use /topics to set up your news topics!" if lang != 'fa' else "❌ هیچ تنظیماتی انتخاب نشده. از /topics برای تنظیم موضوعات خبری استفاده کنید!"
                if update:
                    await update.message.reply_text(message)
                return
            
            # Fetch personalized news using the new topic system
            articles = self.news_fetcher.fetch_news_by_topics_and_sources(
                enabled_topics, enabled_sources
            )
            
            if not articles:
                message = "📭 No news found matching your preferences. Try adjusting your topics or sources." if lang != 'fa' else "📭 هیچ خبری مطابق با تنظیمات شما یافت نشد. موضوعات یا منابع خود را تنظیم کنید."
                if update:
                    await update.message.reply_text(message)
                return
            
            # Format news message
            news_message = f"📰 Latest News (based on your preferences):\n\n" if lang != 'fa' else f"📰 آخرین اخبار (بر اساس تنظیمات شما):\n\n"
            
            # Show what topics/sources were used
            if enabled_topics:
                topics_label = "📚 Topics:" if lang != 'fa' else "📚 موضوعات:"
                news_message += f"{topics_label} {', '.join(enabled_topics[:3])}"
                if len(enabled_topics) > 3:
                    more_text = " more" if lang != 'fa' else " بیشتر"
                    news_message += f" (+{len(enabled_topics)-3}{more_text})"
                news_message += "\n"
            
            if enabled_sources:
                sources_label = "📰 Sources:" if lang != 'fa' else "📰 منابع:"
                news_message += f"{sources_label} {', '.join(enabled_sources[:3])}"
                if len(enabled_sources) > 3:
                    more_text = " more" if lang != 'fa' else " بیشتر"
                    news_message += f" (+{len(enabled_sources)-3}{more_text})"
                news_message += "\n"
            
            news_message += "\n" + "="*50 + "\n\n"
            
            for i, article in enumerate(articles[:5], 1):  # Limit to 5 articles
                title = article.get("title", "No title")
                url = article.get("url", "")
                desc = article.get("description", "No description")
                source = article.get("source", {}).get("name", "Unknown")
                
                news_message += f"🔸 {title}\n"
                news_message += f"📝 {desc[:100]}...\n"
                source_label = "📰 Source:" if lang != 'fa' else "📰 منبع:"
                news_message += f"{source_label} {source}\n"
                news_message += f"🔗 {url}\n\n"
            
            # Send message
            if update:
                await update.message.reply_text(news_message)
            else:
                await self.app.bot.send_message(chat_id, news_message)
        except Exception as e:
            logger.exception("Error in send_news_to_user")
            error_message = "❌ An error occurred while fetching news. Please try again later." if lang != 'fa' else "❌ خطایی در دریافت اخبار رخ داد. لطفا دوباره تلاش کنید."
            if update:
                await update.message.reply_text(error_message)
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

