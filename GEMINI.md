# Gemini Project Context: NewsReaderBot

This document provides a comprehensive overview of the NewsReaderBot project for instructional context.

## 1. Project Overview

NewsReaderBot is a sophisticated, bilingual (English and Farsi) Telegram bot built with Python. Its primary function is to deliver personalized news articles to users based on their preferred topics and sources. The bot fetches news from [NewsAPI.org](https://newsapi.org/) and manages user data and preferences through a relational database.

Key features include a hierarchical, interactive menu system for managing news topics and sources, scheduled news delivery, and user-specific language preferences.

## 2. Key Technologies

- **Language:** Python 3.8+
- **Telegram Bot Framework:** `python-telegram-bot`
- **Database ORM:** `SQLAlchemy`
- **Database Migrations:** `Alembic`
- **Configuration:** `.env` file for environment variables
- **News Source:** [NewsAPI.org](https://newsapi.org/)

## 3. File Structure

The project follows a modular structure to separate concerns.

- `main.py`: The main entry point for running the bot in production (polling mode).
- `setup.py`: An automated script that checks prerequisites, installs dependencies, creates the `.env` file, and sets up the database.
- `requirements.txt`: A list of all Python package dependencies.
- `.env`: A file (needs to be created) to store secret keys and configuration variables (e.g., API keys, database URL).
- `alembic.ini` & `alembic/`: Configuration and versioning scripts for database migrations.
- `src/`: The main directory containing the application's source code.
  - `telegram_bot.py`: The core of the bot, containing all command handlers, callback logic, and interaction with users.
  - `news_fetcher.py`: A dedicated class responsible for fetching and filtering news from the NewsAPI.
  - `db_helper.py`: A set of functions that abstract all database interactions, such as creating users and managing preferences.
  - `models.py`: Defines the database schema using SQLAlchemy ORM, including `User`, `UserSource`, and `UserTopic` tables.
  - `categories.py`: Contains the static definitions for news topic and source categories used in the bot's interactive menus.

## 4. Setup and Running

### Prerequisites

- Python 3.8 or higher.
- A Telegram Bot Token from [BotFather](https://t.me/BotFather).
- An API Key from [NewsAPI.org](https://newsapi.org/).

### Step 1: Configuration

The project uses a `.env` file for configuration. You can create this file automatically by running the setup script or by creating it manually with the following content:

```env
# API Keys
API_KEY=your_newsapi_key_here
BOT_TOKEN=your_telegram_bot_token_here

# Database Configuration (SQLite is the default)
DATABASE_URL=sqlite:///newsreader.db
```

**Replace the placeholder values with your actual API keys.**

### Step 2: Installation and Database Setup

You can use the automated setup script or perform the steps manually.

**Automated Setup (Recommended):**
This script handles dependency installation and database migration in one step.

```bash
python setup.py
```

**Manual Setup:**

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run Database Migrations:** This command applies all pending database schema changes.
    ```bash
    python -m alembic upgrade head
    ```

### Step 3: Running the Bot

Once the setup is complete, you can start the bot using the `main.py` script.

```bash
python main.py
```

The bot will start polling for new messages.

## 5. Development Conventions

- **Modular Design:** The codebase is organized into distinct modules by functionality (bot logic, database helpers, news fetching) inside the `src/` directory.
- **Database Management:** All database interactions are handled through the `SQLAlchemy` ORM, with schema changes managed declaratively in `models.py`. Database migrations are managed by `Alembic`, ensuring schema consistency.
- **Configuration:** All secrets and environment-specific settings are loaded from a `.env` file and accessed via `os.getenv()`. No hardcoded keys should be present in the source code.
- **Bilingual Support:** The bot is designed to be fully bilingual, with the user's language preference stored in the database. All user-facing strings and interactions should be available in both English and Farsi.
