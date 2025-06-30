import os
import requests
from news_fetcher import NewsFetcher
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, JobQueue, CallbackQueryHandler, MessageHandler, filters
from db_helper import (
    create_user, update_user_activity, get_user_queries, get_user_sources,
    add_user_query, remove_user_query, toggle_user_source, get_enabled_sources_for_user,
    get_all_users, get_user_preferences
)
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

        # Available news sources
        self.available_sources = ['cnn.com', 'bbc.com', 'theverge.com', 'techcrunch.com', 'nytimes.com']

        # Commands
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CommandHandler('help', self.help))
        self.app.add_handler(CommandHandler('news', self.send_news))
        self.app.add_handler(CommandHandler('preferences', self.show_preferences))
        self.app.add_handler(CommandHandler('addquery', self.add_query_command))
        self.app.add_handler(CommandHandler('removequery', self.remove_query_command))
        
        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self.button_click))
        
        # Message handler for adding queries
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Error handler
        self.app.add_error_handler(self.error)

        # Job queue for scheduled news
        self.job_queue = self.app.job_queue
        self.schedule_news_updates()

    async def run_async(self):
        print("polling...")
        await self.app.run_polling(poll_interval=3)

    def schedule_news_updates(self):
        """Schedule news updates every 4 hours"""
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
        chat_id = str(update.message.chat.id)
        user = update.effective_user
        
        # Create or get user
        create_user(
            chat_id=chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        welcome_message = (
            "🎉 Welcome to MyTelegramNewsBot!\n\n"
            "📰 I'll send you personalized news based on your preferences.\n\n"
            "🔧 Available commands:\n"
            "/preferences - Manage your news preferences\n"
            "/addquery <keywords> - Add search keywords\n"
            "/removequery <keywords> - Remove search keywords\n"
            "/news - Get latest news now\n"
            "/help - Show this help message\n\n"
            "⚙️ You can customize:\n"
            "• Search queries (keywords you're interested in)\n"
            "• News sources (CNN, BBC, TechCrunch, etc.)\n\n"
            "📅 News will be sent automatically every 4 hours at:\n"
            "8 AM, 12 PM, 4 PM, 8 PM, 12 AM, 4 AM (IRST)\n\n"
            "Click /preferences to set up your preferences!"
        )
        
        await update.message.reply_text(welcome_message)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = (
            "📚 Bot Commands:\n\n"
            "/start - Initialize the bot\n"
            "/help - Show this help message\n"
            "/preferences - Manage your news preferences\n"
            "/addquery <keywords> - Add search keywords\n"
            "/removequery <keywords> - Remove search keywords\n"
            "/news - Get latest news now\n\n"
            "💡 Examples:\n"
            "/addquery technology AI\n"
            "/addquery 'machine learning' OR 'data science'\n"
            "/removequery technology\n\n"
            "🔧 Use /preferences to toggle news sources on/off!"
        )
        await update.message.reply_text(help_message)

    async def show_preferences(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user preferences with inline buttons"""
        chat_id = str(update.message.chat.id)
        update_user_activity(chat_id)
        
        # Get user preferences
        preferences = get_user_preferences(chat_id)
        queries = preferences.get('queries', [])
        sources = preferences.get('sources', {})
        
        # Build message
        message = "🔧 Your News Preferences:\n\n"
        
        # Queries section
        message += "📝 Search Queries:\n"
        if queries:
            for i, query in enumerate(queries, 1):
                message += f"{i}. {query}\n"
        else:
            message += "No queries set. Use /addquery to add keywords.\n"
        
        message += "\n📰 News Sources:\n"
        
        # Create inline keyboard for sources
        keyboard = []
        for source in self.available_sources:
            is_enabled = sources.get(source, True)
            status = "✅" if is_enabled else "❌"
            keyboard.append([
                InlineKeyboardButton(
                    f"{status} {source}",
                    callback_data=f"toggle_source:{source}"
                )
            ])
        
        # Add other action buttons
        keyboard.append([
            InlineKeyboardButton("➕ Add Query", callback_data="add_query"),
            InlineKeyboardButton("🗑️ Remove Query", callback_data="remove_query")
        ])
        keyboard.append([
            InlineKeyboardButton("📰 Get News Now", callback_data="get_news"),
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_preferences")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, reply_markup=reply_markup)

    async def add_query_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /addquery command"""
        chat_id = str(update.message.chat.id)
        update_user_activity(chat_id)
        
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide keywords to add.\n"
                "Example: /addquery technology AI\n"
                "Example: /addquery 'machine learning' OR 'data science'"
            )
            return
        
        query_text = " ".join(context.args)
        if add_user_query(chat_id, query_text):
            await update.message.reply_text(f"✅ Added query: {query_text}")
        else:
            await update.message.reply_text(f"❌ Query already exists: {query_text}")

    async def remove_query_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /removequery command"""
        chat_id = str(update.message.chat.id)
        update_user_activity(chat_id)
        
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide keywords to remove.\n"
                "Example: /removequery technology"
            )
            return
        
        query_text = " ".join(context.args)
        if remove_user_query(chat_id, query_text):
            await update.message.reply_text(f"✅ Removed query: {query_text}")
        else:
            await update.message.reply_text(f"❌ Query not found: {query_text}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages for adding queries"""
        chat_id = str(update.message.chat.id)
        update_user_activity(chat_id)
        
        # Check if user is in "add query" mode
        if hasattr(context.user_data, 'adding_query') and context.user_data.get('adding_query'):
            query_text = update.message.text
            if add_user_query(chat_id, query_text):
                await update.message.reply_text(f"✅ Added query: {query_text}")
            else:
                await update.message.reply_text(f"❌ Query already exists: {query_text}")
            
            context.user_data['adding_query'] = False
        else:
            # Regular message - suggest using commands
            await update.message.reply_text(
                "💡 Use /help to see available commands or /preferences to manage your settings!"
            )

    async def button_click(self, update: Update, context: CallbackContext):
        """Handle inline button clicks"""
        query = update.callback_query
        chat_id = str(query.from_user.id)
        update_user_activity(chat_id)
        
        await query.answer()
        
        if query.data.startswith("toggle_source:"):
            source = query.data.split(":")[1]
            is_enabled = toggle_user_source(chat_id, source)
            status = "enabled" if is_enabled else "disabled"
            await query.message.reply_text(f"✅ {source} {status}")
            await self.show_preferences(update, context)
            
        elif query.data == "add_query":
            context.user_data['adding_query'] = True
            await query.message.reply_text(
                "📝 Please send the keywords you want to add as a search query.\n"
                "Example: technology AI\n"
                "Example: 'machine learning' OR 'data science'"
            )
            
        elif query.data == "remove_query":
            queries = get_user_queries(chat_id)
            if not queries:
                await query.message.reply_text("❌ No queries to remove.")
                return
            
            keyboard = []
            for query_text in queries:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🗑️ {query_text[:30]}...",
                        callback_data=f"remove_query:{query_text}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Select a query to remove:", reply_markup=reply_markup)
            
        elif query.data.startswith("remove_query:"):
            query_text = query.data.split(":", 1)[1]
            if remove_user_query(chat_id, query_text):
                await query.message.reply_text(f"✅ Removed query: {query_text}")
            else:
                await query.message.reply_text(f"❌ Query not found: {query_text}")
                
        elif query.data == "get_news":
            await self.send_news_to_user(chat_id, update, context)
            
        elif query.data == "refresh_preferences":
            await self.show_preferences(update, context)

    async def send_news(self, update: Update, context: CallbackContext):
        """Handle /news command"""
        chat_id = str(update.message.chat.id)
        update_user_activity(chat_id)
        await self.send_news_to_user(chat_id, update, context)

    async def send_news_to_user(self, chat_id, update=None, context=None):
        """Send personalized news to a specific user"""
        # Get user preferences
        queries = get_user_queries(chat_id)
        enabled_sources = get_enabled_sources_for_user(chat_id)
        
        if not queries:
            message = "❌ No search queries set. Use /addquery to add keywords."
            if update:
                await update.message.reply_text(message)
            return
        
        if not enabled_sources:
            message = "❌ No news sources enabled. Use /preferences to enable sources."
            if update:
                await update.message.reply_text(message)
            return
        
        # Fetch personalized news
        articles = self.news_fetcher.fetch_news_for_user(queries, enabled_sources)
        
        if not articles:
            message = "📭 No news found matching your preferences. Try adjusting your queries or sources."
            if update:
                await update.message.reply_text(message)
            return
        
        # Format news message
        news_message = f"📰 Latest News (based on your preferences):\n\n"
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

    async def send_scheduled_news(self, context: CallbackContext):
        """Send scheduled news to all users"""
        users = get_all_users()
        for user in users:
            await self.send_news_to_user(user.chat_id)

    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        print(f"Update {update} caused error {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )

