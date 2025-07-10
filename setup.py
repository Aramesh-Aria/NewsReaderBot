#!/usr/bin/env python3
"""
Setup script for NewsReaderBot
Updated for modern Python practices and current codebase structure
"""

import os
import sys
import subprocess
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        logger.error("❌ Python 3.8 or higher is required")
        return False
    logger.info(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def install_requirements():
    """Install required packages"""
    logger.info("📦 Installing required packages...")
    try:
        # Upgrade pip first
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        
        # Install requirements
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        logger.info("✅ Packages installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install packages: {e}")
        logger.error("Please install manually: pip install -r requirements.txt")
        return False

def create_env_file():
    """Create .env file with template"""
    env_file = Path(".env")
    if not env_file.exists():
        logger.info("📝 Creating .env file...")
        env_content = """# NewsReaderBot Environment Variables
# Get your API keys from:
# - NewsAPI: https://newsapi.org/
# - Telegram Bot: https://t.me/BotFather

# API Keys
API_KEY=your_newsapi_key_here
BOT_TOKEN=your_telegram_bot_token_here

# Database Configuration
# For SQLite (default - no setup required):
DATABASE_URL=sqlite:///newsreader.db

# For PostgreSQL (optional):
# DATABASE_URL=postgresql://username:password@localhost:5432/newsreader

# For MySQL (optional):
# DATABASE_URL=mysql://username:password@localhost:3306/newsreader

# Bot Configuration
BOT_WEBHOOK_URL=  # Leave empty for polling mode
BOT_PORT=8443     # Only needed for webhook mode

# News API Configuration
NEWS_API_BASE_URL=https://newsapi.org/v2/
NEWS_API_TIMEOUT=30

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=bot.log

# Development Settings
DEBUG=False
ENVIRONMENT=production
"""
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(env_content)
        logger.info("✅ .env file created!")
        logger.warning("⚠️  Please edit .env file with your actual API keys")
        return False
    else:
        logger.info("✅ .env file found")
        return True

def check_env_variables():
    """Check if required environment variables are set"""
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ["API_KEY", "BOT_TOKEN"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var) or os.getenv(var) == f"your_{var.lower()}_here":
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing or invalid environment variables: {', '.join(missing_vars)}")
        logger.error("Please update your .env file with actual values")
        return False
    
    logger.info("✅ Environment variables configured")
    return True

def setup_database():
    """Set up the database using Alembic"""
    logger.info("🗄️  Setting up database...")
    try:
        # Check if alembic is available
        subprocess.check_call([sys.executable, "-m", "alembic", "--version"])
        
        # Run database migrations
        logger.info("Running database migrations...")
        subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"])
        
        logger.info("✅ Database setup completed!")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to setup database: {e}")
        logger.error("Please run manually: python -m alembic upgrade head")
        return False
    except FileNotFoundError:
        logger.error("❌ Alembic not found. Please install: pip install alembic")
        return False

def test_database_connection():
    """Test database connection and basic operations"""
    logger.info("🧪 Testing database connection...")
    try:
        # Import and test database functions
        sys.path.append("src")
        from models import create_database
        from db_helper import create_user, get_user
        
        # Test database creation
        create_database()
        
        # Test user creation
        test_chat_id = "999999999"
        user = create_user(
            chat_id=test_chat_id,
            username="testuser",
            first_name="Test",
            last_name="User"
        )
        
        # Test user retrieval
        retrieved_user = get_user(test_chat_id)
        if retrieved_user:
            logger.info("✅ Database connection and operations successful!")
            return True
        else:
            logger.error("❌ Database test failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ["logs", "data"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    logger.info("✅ Directories created")

def main():
    """Main setup function"""
    print("🚀 NewsReaderBot Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return
    
    # Create directories
    create_directories()
    
    # Install requirements
    if not install_requirements():
        return
    
    # Create environment file
    env_ok = create_env_file()
    
    # Check environment variables
    if not check_env_variables():
        return
    
    # Setup database
    if not setup_database():
        return
    
    # Test database
    if not test_database_connection():
        return
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Make sure your .env file has correct API keys")
    print("2. Run the bot: python run_bot.py")
    print("3. Send /start to your bot to begin")
    
    if not env_ok:
        print("\n⚠️  Remember to add your API keys to .env file before running!")
    
    print("\n📚 Documentation:")
    print("- README.md: Project overview and setup")
    print("- src/: Source code directory")

if __name__ == "__main__":
    main() 