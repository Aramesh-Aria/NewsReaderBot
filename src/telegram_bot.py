import os
import requests
from news_fetcher import NewsFetcher
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, JobQueue, CallbackQueryHandler, MessageHandler, filters
from db_helper import (
    create_user, update_user_activity, get_user_queries, get_user_sources,
    add_user_query, remove_user_query, toggle_user_source, get_enabled_sources_for_user,
    get_all_users, get_user_preferences, toggle_user_topic, get_user_topics,
    get_enabled_topics_for_user, initialize_user_topics, initialize_user_sources
)
from categories import TOPIC_CATEGORIES, SOURCE_CATEGORIES, get_all_topics, get_all_sources
import pytz
from datetime import datetime, timedelta

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
            chat_id = str(update.message.chat.id)
            user = update.effective_user
            
            # Create or get user
            create_user(
                chat_id=chat_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            
            # Initialize topics and sources for the user
            initialize_user_topics(chat_id)
            initialize_user_sources(chat_id)
            
            welcome_message = (
                "🎉 Welcome to MyTelegramNewsBot!\n\n"
                "📰 I'll send you personalized news based on your preferences.\n\n"
                "🔧 Available commands:\n"
                "/topics - Manage your news topics by category\n"
                "/sources - Manage your news sources by category\n"
                "/news - Get latest news now\n"
                "/help - Show this help message\n\n"
                "⚙️ You can customize:\n"
                "• News topics (Technology, Science, Politics, etc.)\n"
                "• News sources (CNN, BBC, TechCrunch, etc.)\n\n"
                "📅 News will be sent automatically every 4 hours at:\n"
                "8 AM, 12 PM, 4 PM, 8 PM, 12 AM, 4 AM (IRST)\n\n"
                "Click /topics to set up your topics!"
            )
            
            await update.message.reply_text(welcome_message)
        except Exception as e:
            print(f"Error in start command: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = (
            "📚 Bot Commands:\n\n"
            "/start - Initialize the bot\n"
            "/help - Show this help message\n"
            "/info - Show your current preferences\n"
            "/topics - Manage news topics by category\n"
            "/sources - Manage news sources by category\n"
            "/news - Get latest news now\n\n"
            "🔧 Use /topics and /sources to customize your news feed!"
        )
        await update.message.reply_text(help_message)

    async def show_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command - Show user's current preferences"""
        try:
            chat_id = str(update.message.chat.id)
            update_user_activity(chat_id)
            
            # Get user preferences
            enabled_topics = get_enabled_topics_for_user(chat_id)
            enabled_sources = get_enabled_sources_for_user(chat_id)
            queries = get_user_queries(chat_id)
            
            # Build info message
            info_message = "📊 Your Current Preferences:\n\n"
            
            # Topics section
            info_message += f"📚 Enabled Topics ({len(enabled_topics)}):\n"
            if enabled_topics:
                for i, topic in enumerate(enabled_topics, 1):
                    info_message += f"{i}. {topic}\n"
            else:
                info_message += "No topics enabled. Use /topics to enable some!\n"
            
            # Sources section
            info_message += f"\n📰 Enabled Sources ({len(enabled_sources)}):\n"
            if enabled_sources:
                for i, source in enumerate(enabled_sources, 1):
                    info_message += f"{i}. {source}\n"
            else:
                info_message += "No sources enabled. Use /sources to enable some!\n"
            
            # # Queries section
            # info_message += f"\n📝 Search Queries ({len(queries)}):\n"
            # if queries:
            #     for i, query in enumerate(queries, 1):
            #         info_message += f"{i}. {query}\n"
            # else:
            #     info_message += "No custom queries set.\n"
            
            # Add action buttons
            keyboard = [
                [InlineKeyboardButton("📚 Manage Topics", callback_data="show_topics")],
                [InlineKeyboardButton("📰 Manage Sources", callback_data="show_sources")],
                [InlineKeyboardButton("📰 Get News Now", callback_data="get_news")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(info_message, reply_markup=reply_markup)
            
        except Exception as e:
            print(f"Error in show_info: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")

    async def show_topics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show topic categories with inline buttons"""
        try:
            chat_id = str(update.message.chat.id)
            update_user_activity(chat_id)
            
            # Initialize topics if not already done
            initialize_user_topics(chat_id)
            
            message = "📚 Choose a topic category to manage your news topics:\n\n"
            
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
                InlineKeyboardButton("🔧 Sources", callback_data="show_sources"),
                InlineKeyboardButton("📰 Get News", callback_data="get_news")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            print(f"Error in show_topics: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")

    async def show_sources(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show source categories with inline buttons"""
        try:
            chat_id = str(update.message.chat.id)
            update_user_activity(chat_id)
            
            # Initialize sources if not already done
            initialize_user_sources(chat_id)
            
            message = "📰 Choose a source category to manage your news sources:\n\n"
            
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
                InlineKeyboardButton("📚 Topics", callback_data="show_topics"),
                InlineKeyboardButton("📰 Get News", callback_data="get_news")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            print(f"Error in show_sources: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")

    async def show_topic_category(self, chat_id, category_id):
        """Show topics within a specific category"""
        try:
            cat_data = TOPIC_CATEGORIES.get(category_id)
            if not cat_data:
                return None
            
            user_topics = get_user_topics(chat_id)
            
            message_text = f"📚 {cat_data['name']}\n\nSelect topics to enable/disable:\n\n"
            
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
                InlineKeyboardButton("⬅️ Back to Categories", callback_data="show_topics"),
                InlineKeyboardButton("🔧 Sources", callback_data="show_sources")
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
            
            message_text = f"📰 {cat_data['name']}\n\nSelect sources to enable/disable:\n\n"
            
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
                InlineKeyboardButton("⬅️ Back to Categories", callback_data="show_sources"),
                InlineKeyboardButton("📚 Topics", callback_data="show_topics")
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
        try:
            query = update.callback_query
            chat_id = str(query.from_user.id)
            update_user_activity(chat_id)
            
            await query.answer()
            
            # Handle topic category selection
            if query.data.startswith("cat:"):
                category_id = query.data.split(":")[1]
                result = await self.show_topic_category(chat_id, category_id)
                if result:
                    message_text, reply_markup = result
                    await query.edit_message_text(text=message_text, reply_markup=reply_markup)
                else:
                    await query.message.reply_text("❌ Category not found.")
                    
            # Handle source category selection
            elif query.data.startswith("src_cat:"):
                category_id = query.data.split(":")[1]
                result = await self.show_source_category(chat_id, category_id)
                if result:
                    message_text, reply_markup = result
                    await query.edit_message_text(text=message_text, reply_markup=reply_markup)
                else:
                    await query.message.reply_text("❌ Category not found.")
                    
            # Handle topic toggle
            elif query.data.startswith("topic:"):
                topic_name = query.data.split(":", 1)[1]
                is_enabled = toggle_user_topic(chat_id, topic_name)
                status = "enabled" if is_enabled else "disabled"
                
                # Recreate the keyboard with updated status
                keyboard = []
                user_topics = get_user_topics(chat_id)
                
                # Find which category this topic belongs to
                from categories import get_topic_category
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
                    keyboard.append([
                        InlineKeyboardButton("⬅️ Back to Categories", callback_data="show_topics"),
                        InlineKeyboardButton("🔧 Sources", callback_data="show_sources")
                    ])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_reply_markup(reply_markup=reply_markup)
                else:
                    await query.message.reply_text(f"❌ Error: Topic category not found")
                
            # Handle source toggle
            elif query.data.startswith("source:"):
                source_domain = query.data.split(":", 1)[1]
                is_enabled = toggle_user_source(chat_id, source_domain)
                status = "enabled" if is_enabled else "disabled"
                
                # Recreate the keyboard with updated status
                keyboard = []
                user_sources = get_user_sources(chat_id)
                
                # Find which category this source belongs to
                from categories import get_source_category
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
                    keyboard.append([
                        InlineKeyboardButton("⬅️ Back to Categories", callback_data="show_sources"),
                        InlineKeyboardButton("📚 Topics", callback_data="show_topics")
                    ])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_reply_markup(reply_markup=reply_markup)
                else:
                    await query.message.reply_text(f"❌ Error: Source category not found")
                
            # Handle navigation buttons
            elif query.data == "show_topics":
                # Initialize topics if not already done
                initialize_user_topics(chat_id)
                
                message = "📚 Choose a topic category to manage your news topics:\n\n"
                
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
                    InlineKeyboardButton("🔧 Sources", callback_data="show_sources"),
                    InlineKeyboardButton("📰 Get News", callback_data="get_news")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text=message, reply_markup=reply_markup)
                
            elif query.data == "show_sources":
                # Initialize sources if not already done
                initialize_user_sources(chat_id)
                
                message = "📰 Choose a source category to manage your news sources:\n\n"
                
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
                    InlineKeyboardButton("📚 Topics", callback_data="show_topics"),
                    InlineKeyboardButton("📰 Get News", callback_data="get_news")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text=message, reply_markup=reply_markup)
                
            elif query.data == "get_news":
                # Send a loading message first
                await query.message.reply_text("📰 Fetching your personalized news...")
                await self.send_news_to_user(chat_id, None, context)
                
        except Exception as e:
            print(f"Error in button_click: {e}")
            try:
                await query.message.reply_text("❌ An error occurred. Please try again.")
            except:
                pass

    async def send_news(self, update: Update, context: CallbackContext):
        """Handle /news command"""
        try:
            chat_id = str(update.message.chat.id)
            update_user_activity(chat_id)
            await self.send_news_to_user(chat_id, update, context)
        except Exception as e:
            print(f"Error in send_news: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")

    async def send_news_to_user(self, chat_id, update=None, context=None):
        """Send personalized news to a specific user"""
        try:
            # Get user preferences
            queries = get_user_queries(chat_id)
            enabled_sources = get_enabled_sources_for_user(chat_id)
            enabled_topics = get_enabled_topics_for_user(chat_id)
            
            # Check if user has any preferences set
            if not enabled_topics and not enabled_sources and not queries:
                message = "❌ No preferences set. Use /topics to set up your news topics!"
                if update:
                    await update.message.reply_text(message)
                return
            
            # Fetch personalized news using the new topic system
            articles = self.news_fetcher.fetch_news_by_topics_and_sources(
                enabled_topics, enabled_sources, queries
            )
            
            if not articles:
                message = "📭 No news found matching your preferences. Try adjusting your topics or sources."
                if update:
                    await update.message.reply_text(message)
                return
            
            # Format news message
            news_message = f"📰 Latest News (based on your preferences):\n\n"
            
            # Show what topics/sources were used
            if enabled_topics:
                news_message += f"📚 Topics: {', '.join(enabled_topics[:3])}"
                if len(enabled_topics) > 3:
                    news_message += f" (+{len(enabled_topics)-3} more)"
                news_message += "\n"
            
            if enabled_sources:
                news_message += f"📰 Sources: {', '.join(enabled_sources[:3])}"
                if len(enabled_sources) > 3:
                    news_message += f" (+{len(enabled_sources)-3} more)"
                news_message += "\n"
            
            news_message += "\n" + "="*50 + "\n\n"
            
            for i, article in enumerate(articles[:5], 1):  # Limit to 5 articles
                title = article.get("title", "No title")
                url = article.get("url", "")
                desc = article.get("description", "No description")
                source = article.get("source", {}).get("name", "Unknown")
                
                news_message += f"🔸 {title}\n"
                news_message += f"📝 {desc[:100]}...\n"
                news_message += f"📰 Source: {source}\n"
                news_message += f"🔗 {url}\n\n"
            
            # Send message
            if update:
                await update.message.reply_text(news_message)
            else:
                await self.app.bot.send_message(chat_id, news_message)
        except Exception as e:
            print(f"Error in send_news_to_user: {e}")
            if update:
                await update.message.reply_text("❌ An error occurred while fetching news. Please try again later.")
            return

    async def send_scheduled_news(self, context: CallbackContext):
        """Send scheduled news to all users"""
        try:
            users = get_all_users()
            for user in users:
                await self.send_news_to_user(user.chat_id)
        except Exception as e:
            print(f"Error in send_scheduled_news: {e}")

    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        print(f"Update {update} caused error {context.error}")
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again later."
                )
        except:
            pass

