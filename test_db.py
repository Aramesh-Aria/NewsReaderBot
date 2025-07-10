#!/usr/bin/env python3
"""
Test script for NewsReaderBot database functionality
Updated for current codebase structure and modern testing practices
"""

import sys
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Add src to path
sys.path.append("src")

def test_database_connection():
    """Test basic database connection"""
    logger.info("🔌 Testing database connection...")
    try:
        from models import create_database, get_session
        from db_helper import create_user, get_user
        
        # Test database creation
        create_database()
        logger.info("✅ Database connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

def test_user_operations():
    """Test user creation and retrieval"""
    logger.info("👤 Testing user operations...")
    try:
        from db_helper import create_user, get_user, update_user_activity
        
        test_chat_id = "123456789"
        
        # Test user creation
        user = create_user(
            chat_id=test_chat_id,
            username="testuser",
            first_name="Test",
            last_name="User",
            language='en'
        )
        logger.info(f"✅ User created: {test_chat_id}")
        
        # Test user retrieval
        retrieved_user = get_user(test_chat_id)
        if retrieved_user:
            logger.info(f"✅ User retrieved: {retrieved_user.chat_id}")
        else:
            logger.error("❌ User retrieval failed")
            return False
        
        # Test activity update
        update_user_activity(test_chat_id)
        logger.info("✅ User activity updated")
        
        return True
    except Exception as e:
        logger.error(f"❌ User operations failed: {e}")
        return False

def test_source_operations():
    """Test source management operations"""
    logger.info("📰 Testing source operations...")
    try:
        from db_helper import (
            get_user_sources, 
            get_enabled_sources_for_user,
            initialize_user_sources
        )
        
        test_chat_id = "123456789"
        
        # Initialize sources
        initialize_user_sources(test_chat_id)
        logger.info("✅ Sources initialized")
        
        # Get all sources
        sources = get_user_sources(test_chat_id)
        logger.info(f"✅ All sources: {len(sources)} found")
        
        # Get enabled sources
        enabled_sources = get_enabled_sources_for_user(test_chat_id)
        logger.info(f"✅ Enabled sources: {len(enabled_sources)} found")
        
        return True
    except Exception as e:
        logger.error(f"❌ Source operations failed: {e}")
        return False

def test_topic_operations():
    """Test topic management operations"""
    logger.info("📚 Testing topic operations...")
    try:
        from db_helper import (
            get_user_topics,
            get_enabled_topics_for_user,
            initialize_user_topics,
            toggle_user_topic
        )
        
        test_chat_id = "123456789"
        
        # Initialize topics
        initialize_user_topics(test_chat_id)
        logger.info("✅ Topics initialized")
        
        # Get all topics
        topics = get_user_topics(test_chat_id)
        logger.info(f"✅ All topics: {len(topics)} found")
        
        # Get enabled topics
        enabled_topics = get_enabled_topics_for_user(test_chat_id)
        logger.info(f"✅ Enabled topics: {len(enabled_topics)} found")
        
        # Test topic toggle
        if topics:
            first_topic = list(topics.keys())[0]
            new_status = toggle_user_topic(test_chat_id, first_topic)
            logger.info(f"✅ Topic '{first_topic}' toggled to: {new_status}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Topic operations failed: {e}")
        return False

def test_language_operations():
    """Test language management operations"""
    logger.info("🌐 Testing language operations...")
    try:
        from db_helper import set_user_language, get_user_language
        
        test_chat_id = "123456789"
        
        # Test language setting
        set_user_language(test_chat_id, 'fa')
        logger.info("✅ Language set to Farsi")
        
        # Test language retrieval
        language = get_user_language(test_chat_id)
        logger.info(f"✅ Language retrieved: {language}")
        
        # Test language change
        set_user_language(test_chat_id, 'en')
        language = get_user_language(test_chat_id)
        logger.info(f"✅ Language changed to: {language}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Language operations failed: {e}")
        return False

def test_preferences():
    """Test user preferences"""
    logger.info("⚙️ Testing user preferences...")
    try:
        from db_helper import get_user_preferences
        
        test_chat_id = "123456789"
        
        preferences = get_user_preferences(test_chat_id)
        logger.info(f"✅ User preferences retrieved")
        logger.info(f"   - Sources: {len(preferences['sources'])}")
        logger.info(f"   - Topics: {len(preferences['topics'])}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Preferences test failed: {e}")
        return False

def test_categories():
    """Test category system"""
    logger.info("📂 Testing category system...")
    try:
        from categories import TOPIC_CATEGORIES, SOURCE_CATEGORIES, get_all_topics, get_all_sources
        
        # Test topic categories
        logger.info(f"✅ Topic categories: {len(TOPIC_CATEGORIES)} found")
        for cat_id, cat_data in TOPIC_CATEGORIES.items():
            logger.info(f"   - {cat_data['name']}: {len(cat_data['topics'])} topics")
        
        # Test source categories
        logger.info(f"✅ Source categories: {len(SOURCE_CATEGORIES)} found")
        for cat_id, cat_data in SOURCE_CATEGORIES.items():
            logger.info(f"   - {cat_data['name']}: {len(cat_data['sources'])} sources")
        
        # Test getting all topics and sources
        all_topics = get_all_topics()
        all_sources = get_all_sources()
        logger.info(f"✅ All topics: {len(all_topics)}")
        logger.info(f"✅ All sources: {len(all_sources)}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Category test failed: {e}")
        return False

def cleanup_test_data():
    """Clean up test data"""
    logger.info("🧹 Cleaning up test data...")
    try:
        from db_helper import get_session
        from models import User
        
        session = get_session()
        try:
            test_users = session.query(User).filter(User.chat_id.like("123456789%")).all()
            for user in test_users:
                session.delete(user)
            session.commit()
            logger.info("✅ Test data cleaned up")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Cleanup failed: {e}")
            return False
        finally:
            session.close()
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 NewsReaderBot Database Test Suite")
    print("=" * 50)
    
    # Check environment variables
    required_vars = ["API_KEY", "BOT_TOKEN", "DATABASE_URL"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file")
        return
    
    logger.info("✅ Environment variables configured")
    
    # Run tests
    tests = [
        ("Database Connection", test_database_connection),
        ("User Operations", test_user_operations),
        ("Source Operations", test_source_operations),
        ("Topic Operations", test_topic_operations),
        ("Language Operations", test_language_operations),
        ("User Preferences", test_preferences),
        ("Category System", test_categories),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                logger.info(f"✅ {test_name} passed")
                passed += 1
            else:
                logger.error(f"❌ {test_name} failed")
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
    
    # Cleanup
    cleanup_test_data()
    
    # Results
    print(f"\n{'='*50}")
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Database is working correctly.")
    else:
        print(f"⚠️  {total - passed} test(s) failed. Please check the logs above.")
    
    print("\n📋 Next steps:")
    print("1. If all tests passed, your database is ready")
    print("3. Run python setup.py to begin")
    print("2. Run the bot: python run_bot.py")
    

if __name__ == "__main__":
    main() 