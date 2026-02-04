#!/usr/bin/env python3
"""
Production startup script for the Telegram bot.
This script runs only the bot without the Flask server.
"""

import os
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv
from NewsBot.telegram_bot import TelegramBot
from NewsBot.db import init_db

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global exception handler to log uncaught exceptions

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

# Load environment variables
load_dotenv()

def main():
    # Optionally run Alembic migrations at startup (recommended for servers).
    # If the DB is already up-to-date, this is a fast no-op.
    if os.getenv("RUN_MIGRATIONS", "0").strip() == "1":
        logger.info("Running Alembic migrations...")
        from alembic import command
        from alembic.config import Config

        alembic_ini = str(Path(__file__).with_name("alembic.ini"))
        cfg = Config(alembic_ini)
        command.upgrade(cfg, "head")

    # Create tables via SQLAlchemy only for local/dev (avoid mixing with Alembic in prod).
    create_tables = os.getenv("DB_CREATE_TABLES", "0").strip() == "1"
    logger.info("Initializing database (create_tables=%s)...", create_tables)
    init_db(create_tables=create_tables)

    # Get API keys from environment
    news_api_key = os.getenv("API_KEY")
    bot_token = os.getenv("BOT_TOKEN")

    # Validate required environment variables
    if not news_api_key:
        raise ValueError("API_KEY is not set in environment variables.")
    if not bot_token:
        raise ValueError("BOT_TOKEN is not set in environment variables.")

    logger.info("Starting Telegram bot...")

    # Run bot (no await, no asyncio.run)
    bot = TelegramBot(token=bot_token, api_key=news_api_key)
    bot.app.run_polling(
        poll_interval=3.0,
        timeout=30,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )

if __name__ == "__main__":
    main() 
