import os
import time
import logging
import threading
from datetime import datetime

from NewsBot.models import User, UserSource, UserTopic
from NewsBot.categories import (
    TOPIC_CATEGORIES,
    SOURCE_CATEGORIES,
    get_all_topics,
    get_all_sources,
)
from NewsBot.db import session_scope

logger = logging.getLogger(__name__)

_last_activity_write_at = {}
_last_activity_lock = threading.Lock()
_perf_log_enabled = os.getenv("PERF_LOG", "").strip() == "1"


def _get_user_id(session, chat_id):
    return (
        session.query(User.id)
        .filter(User.chat_id == str(chat_id))
        .scalar()
    )

def create_user(chat_id, username=None, first_name=None, last_name=None, language='en'):
    """Create a new user in the database"""
    with session_scope() as session:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            return user

        user = User(
            chat_id=str(chat_id),
            username=username,
            first_name=first_name,
            last_name=last_name,
            language=language,
        )
        session.add(user)
        session.flush()
        return user

def update_user_activity(chat_id, min_interval_seconds: int = 90):
    """Update user's last activity timestamp"""
    now = time.time()
    chat_id_str = str(chat_id)

    with _last_activity_lock:
        last = _last_activity_write_at.get(chat_id_str)
        if last is not None and (now - float(last)) < float(min_interval_seconds):
            return False

    t0 = time.perf_counter()
    with session_scope() as session:
        session.query(User).filter(User.chat_id == chat_id_str).update(
            {"last_activity": datetime.utcnow()},
            synchronize_session=False,
        )

    with _last_activity_lock:
        _last_activity_write_at[chat_id_str] = now

    if _perf_log_enabled:
        logger.debug("perf:update_user_activity chat_id=%s ms=%.1f", chat_id_str, (time.perf_counter() - t0) * 1000.0)
    return True

def get_user(chat_id):
    """Get user by chat_id"""
    with session_scope(commit=False) as session:
        return session.query(User).filter_by(chat_id=str(chat_id)).first()

def get_all_users():
    """Get all users"""
    with session_scope(commit=False) as session:
        return session.query(User).all()

def delete_user(chat_id):
    """Delete a user and all related data (sources/topics)"""
    with session_scope() as session:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if not user:
            return False
        session.delete(user)
        return True

def get_user_sources(chat_id):
    """Get all sources and their enabled status for a user"""
    with session_scope(commit=False) as session:
        user_id = _get_user_id(session, chat_id)
        if not user_id:
            return {}
        rows = (
            session.query(UserSource.source_domain, UserSource.is_enabled)
            .filter(UserSource.user_id == user_id)
            .all()
        )
        return {domain: bool(enabled) for domain, enabled in rows}

def get_enabled_sources_for_user(chat_id):
    """Get only enabled sources for a user"""
    with session_scope(commit=False) as session:
        user_id = _get_user_id(session, chat_id)
        if not user_id:
            return []
        rows = (
            session.query(UserSource.source_domain)
            .filter(UserSource.user_id == user_id, UserSource.is_enabled.is_(True))
            .all()
        )
        return [r[0] for r in rows if r and r[0]]

def get_user_preferences(chat_id):
    """Get complete user preferences (queries, sources, and topics)"""
    with session_scope(commit=False) as session:
        user_id = _get_user_id(session, chat_id)
        if not user_id:
            return {"queries": [], "sources": {}, "topics": {}}

        sources = (
            session.query(UserSource.source_domain, UserSource.is_enabled)
            .filter(UserSource.user_id == user_id)
            .all()
        )
        topics = (
            session.query(UserTopic.topic_name, UserTopic.is_enabled)
            .filter(UserTopic.user_id == user_id)
            .all()
        )
        return {
            "queries": [],
            "sources": {d: bool(e) for d, e in sources},
            "topics": {t: bool(e) for t, e in topics},
        }

# New functions for topic management
def toggle_user_topic(chat_id, topic_name):
    """Toggle a topic on/off for a user"""
    with session_scope() as session:
        user_id = _get_user_id(session, chat_id)
        if not user_id:
            return None

        user_topic = (
            session.query(UserTopic)
            .filter(UserTopic.user_id == user_id, UserTopic.topic_name == topic_name)
            .first()
        )

        if user_topic:
            user_topic.is_enabled = not bool(user_topic.is_enabled)
            return bool(user_topic.is_enabled)

        # Create new topic entry if it doesn't exist
        from NewsBot.categories import get_topic_category

        category = get_topic_category(topic_name)
        if not category:
            return None

        user_topic = UserTopic(
            user_id=user_id,
            topic_name=topic_name,
            category=category,
            is_enabled=True,
        )
        session.add(user_topic)
        return True


def toggle_user_source(chat_id, source_domain):
    """Toggle a source on/off for a user"""
    with session_scope() as session:
        user_id = _get_user_id(session, chat_id)
        if not user_id:
            return None

        user_source = (
            session.query(UserSource)
            .filter(UserSource.user_id == user_id, UserSource.source_domain == source_domain)
            .first()
        )
        if user_source:
            user_source.is_enabled = not bool(user_source.is_enabled)
            return bool(user_source.is_enabled)

        user_source = UserSource(
            user_id=user_id,
            source_domain=source_domain,
            is_enabled=True,
        )
        session.add(user_source)
        return True

def get_user_topics(chat_id):
    """Get all topics and their enabled status for a user"""
    with session_scope(commit=False) as session:
        user_id = _get_user_id(session, chat_id)
        if not user_id:
            return {}
        rows = (
            session.query(UserTopic.topic_name, UserTopic.is_enabled)
            .filter(UserTopic.user_id == user_id)
            .all()
        )
        return {name: bool(enabled) for name, enabled in rows}

def get_enabled_topics_for_user(chat_id):
    """Get only enabled topics for a user"""
    with session_scope(commit=False) as session:
        user_id = _get_user_id(session, chat_id)
        if not user_id:
            return []
        rows = (
            session.query(UserTopic.topic_name)
            .filter(UserTopic.user_id == user_id, UserTopic.is_enabled.is_(True))
            .all()
        )
        return [r[0] for r in rows if r and r[0]]

def initialize_user_topics(chat_id):
    """Initialize all available topics for a user (disabled by default)"""
    with session_scope() as session:
        user_id = _get_user_id(session, chat_id)
        if not user_id:
            return False

        all_topics = get_all_topics()
        existing = (
            session.query(UserTopic.topic_name)
            .filter(UserTopic.user_id == user_id)
            .all()
        )
        existing_topics = {r[0] for r in existing if r and r[0]}

        from NewsBot.categories import get_topic_category

        for topic_name in all_topics:
            if topic_name in existing_topics:
                continue
            category = get_topic_category(topic_name)
            if not category:
                continue
            session.add(
                UserTopic(
                    user_id=user_id,
                    topic_name=topic_name,
                    category=category,
                    is_enabled=False,
                )
            )
        return True

def initialize_user_sources(chat_id):
    """Initialize all available sources for a user (disabled by default)"""
    with session_scope() as session:
        user_id = _get_user_id(session, chat_id)
        if not user_id:
            return False

        all_sources = get_all_sources()
        existing = (
            session.query(UserSource.source_domain)
            .filter(UserSource.user_id == user_id)
            .all()
        )
        existing_sources = {r[0] for r in existing if r and r[0]}

        for source_domain in all_sources:
            if source_domain in existing_sources:
                continue
            session.add(
                UserSource(
                    user_id=user_id,
                    source_domain=source_domain,
                    is_enabled=False,
                )
            )
        return True

def set_user_language(chat_id, language):
    with session_scope() as session:
        session.query(User).filter(User.chat_id == str(chat_id)).update(
            {"language": language},
            synchronize_session=False,
        )

def get_user_language(chat_id):
    with session_scope(commit=False) as session:
        lang = (
            session.query(User.language)
            .filter(User.chat_id == str(chat_id))
            .scalar()
        )
        return lang or "en"
