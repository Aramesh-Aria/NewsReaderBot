# Migration Guide: NewsReaderBot v2.0

## Overview

NewsReaderBot has been completely refactored to support **per-user customization** with individual search queries and news source preferences. This is a major upgrade that replaces the simple subscriber system with a sophisticated user preference management system.

## Key Changes

### 🔄 Database Structure
**Old System:**
- Single `subscribers` table with just `chat_id` and `last_activity`

**New System:**
- `users` table: User profiles with chat_id, username, etc.
- `user_queries` table: Individual search queries per user
- `user_sources` table: News source preferences per user

### 🎯 User Experience
**Old System:**
- All users received the same news
- Fixed search query: "technology OR programming OR politics..."
- Fixed news sources: All 5 sources always enabled

**New System:**
- Each user gets personalized news
- Multiple custom search queries per user
- Individual source toggles (CNN, BBC, etc.)
- Inline button interface for easy preference management

### 🛠️ Technical Architecture
**Old System:**
- SQLite with raw SQL queries
- Simple subscriber management
- Fixed news fetching parameters

**New System:**
- SQLAlchemy ORM with proper relationships
- Alembic migrations for database versioning
- Per-user news filtering
- Advanced preference management

## Migration Steps

### 1. Backup Existing Data
```bash
# Backup the old database
cp subscribers.db subscribers_backup.db
```

### 2. Install New Dependencies
```bash
pip install sqlalchemy alembic
```

### 3. Run Setup
```bash
python setup.py
```

### 4. Update Environment
The bot will automatically create the new database structure when started.

### 5. User Migration
Users will need to:
1. Send `/start` to initialize their profile
2. Set up their preferred search queries
3. Configure their news source preferences

## New Features

### 📝 Query Management
Users can now add multiple search queries:
```
/addquery technology AI
/addquery 'machine learning' OR 'data science'
/addquery Tesla electric vehicles
```

### 🔧 Source Preferences
Users can toggle individual news sources:
- CNN (cnn.com)
- BBC (bbc.com) 
- The Verge (theverge.com)
- TechCrunch (techcrunch.com)
- New York Times (nytimes.com)

### 🎛️ Preference Interface
- `/preferences` - Opens interactive preference management
- Inline buttons for easy source toggling
- Add/remove queries through buttons
- Real-time preference updates

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    chat_id VARCHAR(50) UNIQUE NOT NULL,
    username VARCHAR(100),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at DATETIME,
    last_activity DATETIME
);
```

### User Queries Table
```sql
CREATE TABLE user_queries (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    query_text TEXT NOT NULL,
    created_at DATETIME
);
```

### User Sources Table
```sql
CREATE TABLE user_sources (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    source_domain VARCHAR(100) NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME,
    UNIQUE(user_id, source_domain)
);
```

## New Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot and set default preferences |
| `/help` | Show available commands |
| `/preferences` | Open preference management interface |
| `/addquery <keywords>` | Add search keywords |
| `/removequery <keywords>` | Remove search keywords |
| `/news` | Get personalized news |

## Breaking Changes

### ❌ Removed Features
- Simple `/info` command (replaced with `/help`)
- Fixed news content for all users
- Basic subscriber management

### ✅ New Features
- Per-user news personalization
- Advanced query management
- Source preference toggles
- Interactive preference interface
- Better error handling
- Improved user experience

## Testing

Run the test script to verify database functionality:
```bash
python test_db.py
```

## Rollback Plan

If you need to rollback to the old version:

1. **Restore old database:**
   ```bash
   cp subscribers_backup.db subscribers.db
   ```

2. **Revert code changes:**
   ```bash
   git checkout HEAD~1
   ```

3. **Uninstall new dependencies:**
   ```bash
   pip uninstall sqlalchemy alembic
   ```

## Support

For issues during migration:
1. Check the test script output
2. Verify database creation
3. Ensure all dependencies are installed
4. Check environment variables

## Benefits of New System

### For Users
- **Personalized Content**: News tailored to individual interests
- **Flexible Preferences**: Easy to modify queries and sources
- **Better UX**: Interactive interface with inline buttons
- **More Control**: Choose exactly what news to receive

### For Developers
- **Scalable Architecture**: SQLAlchemy ORM for better data management
- **Migration Support**: Alembic for database versioning
- **Better Code Organization**: Separated concerns and cleaner structure
- **Extensible Design**: Easy to add new features

---

**Note**: This migration is designed to be smooth and automatic. Users will be guided through the setup process when they first interact with the updated bot. 