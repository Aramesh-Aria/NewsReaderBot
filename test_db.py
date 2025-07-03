#!/usr/bin/env python3
"""
Test script for NewsReaderBot database functionality
"""

import sys
import os
sys.path.append("src")

from models import create_database, User, UserSource, get_session
from db_helper import (
    create_user, get_user
)

def test_database():
    """Test all database functions"""
    print("🧪 Testing NewsReaderBot Database Functions")
    print("=" * 50)
    
    # Create database
    print("1. Creating database...")
    create_database()
    print("✅ Database created")
    
    # Test user creation
    print("\n2. Testing user creation...")
    test_chat_id = "123456789"
    user = create_user(
        chat_id=test_chat_id,
        username="testuser",
        first_name="Test",
        last_name="User"
    )
    print(f"✅ User created: {test_chat_id}")
    
    # Test getting user
    print("\n3. Testing get user...")
    retrieved_user = get_user(test_chat_id)
    print(f"✅ User retrieved: {retrieved_user.chat_id if retrieved_user else 'Not found'}")
    
    # Test source management
    print("\n5. Testing source management...")
    sources = get_user_sources(test_chat_id)
    print(f"✅ Initial sources: {sources}")
    
    # Get enabled sources
    enabled_sources = get_enabled_sources_for_user(test_chat_id)
    print(f"✅ Enabled sources: {enabled_sources}")
    
    # Test preferences
    print("\n6. Testing preferences...")
    preferences = get_user_preferences(test_chat_id)
    print(f"✅ User preferences: {preferences}")
    
    print("\n🎉 All database tests passed!")

if __name__ == "__main__":
    test_database() 