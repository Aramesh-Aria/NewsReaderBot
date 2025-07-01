#!/usr/bin/env python3
"""
Setup script for NewsReaderBot
"""

import os
import sys
import subprocess
from pathlib import Path

def install_requirements():
    """Install required packages"""
    print("📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Packages installed successfully!")
    except subprocess.CalledProcessError:
        print("❌ Failed to install packages. Please install manually:")
        print("   pip install -r requirements.txt")
        return False
    return True

def check_env_file():
    """Check if .env file exists and has required variables"""
    env_file = Path(".env")
    if not env_file.exists():
        print("📝 Creating .env file...")
        with open(env_file, "w") as f:
            f.write("# NewsReaderBot Environment Variables\n")
            f.write("# Get your API keys from:\n")
            f.write("# - NewsAPI: https://newsapi.org/\n")
            f.write("# - Telegram Bot: https://t.me/BotFather\n\n")
            f.write("API_KEY=your_newsapi_key_here\n")
            f.write("BOT_TOKEN=your_telegram_bot_token_here\n")
        print("✅ .env file created!")
        print("⚠️  Please edit .env file with your actual API keys")
        return False
    else:
        print("✅ .env file found")
        return True

def setup_database():
    """Set up the database"""
    print("🗄️  Setting up database...")
    try:
        # Import and create database
        sys.path.append("src")
        from models import create_database
        create_database()
        print("✅ Database created successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to create database: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 NewsReaderBot Setup")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        return
    
    # Install requirements
    if not install_requirements():
        return
    
    # Check environment file
    env_ok = check_env_file()
    
    # Setup database
    if not setup_database():
        return
    
    print("\n🎉 Setup completed!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your API keys")
    print("2. Run the bot: python src/main.py")
    print("3. Send /start to your bot to begin")
    
    if not env_ok:
        print("\n⚠️  Remember to add your API keys to .env file before running!")

if __name__ == "__main__":
    main() 