from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Base, User, UserQuery, UserSource, UserTopic
from datetime import datetime
from categories import TOPIC_CATEGORIES, SOURCE_CATEGORIES, get_all_topics, get_all_sources

# Database setup
engine = create_engine('sqlite:///news_bot.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_session():
    """Get a new database session"""
    return Session()

def create_user(chat_id, username=None, first_name=None, last_name=None):
    """Create a new user in the database"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if not user:
            user = User(
                chat_id=str(chat_id),
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            session.add(user)
            session.commit()
            
            # Initialize default sources for new user
            default_sources = ['cnn.com', 'bbc.com', 'theverge.com', 'techcrunch.com', 'nytimes.com']
            for source in default_sources:
                user_source = UserSource(
                    user_id=user.id,
                    source_domain=source,
                    is_enabled=True
                )
                session.add(user_source)
            
            # Initialize default topics for new user (Technology category)
            default_topics = ["Technology", "Programming", "AI", "Machine Learning"]
            for topic in default_topics:
                user_topic = UserTopic(
                    user_id=user.id,
                    topic_name=topic,
                    category="tech",
                    is_enabled=True
                )
                session.add(user_topic)
            
            session.commit()
            
        return user
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def update_user_activity(chat_id):
    """Update user's last activity timestamp"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            user.last_activity = datetime.utcnow()
            session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_user(chat_id):
    """Get user by chat_id"""
    session = get_session()
    try:
        return session.query(User).filter_by(chat_id=str(chat_id)).first()
    finally:
        session.close()

def get_all_users():
    """Get all users"""
    session = get_session()
    try:
        return session.query(User).all()
    finally:
        session.close()

def add_user_query(chat_id, query_text):
    """Add a new query for a user"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            # Check if query already exists
            existing_query = session.query(UserQuery).filter_by(
                user_id=user.id, 
                query_text=query_text
            ).first()
            
            if not existing_query:
                user_query = UserQuery(
                    user_id=user.id,
                    query_text=query_text
                )
                session.add(user_query)
                session.commit()
                return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def remove_user_query(chat_id, query_text):
    """Remove a query for a user"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            query = session.query(UserQuery).filter_by(
                user_id=user.id, 
                query_text=query_text
            ).first()
            if query:
                session.delete(query)
                session.commit()
                return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_user_queries(chat_id):
    """Get all queries for a user"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            return [query.query_text for query in user.queries]
        return []
    finally:
        session.close()

def toggle_user_source(chat_id, source_domain):
    """Toggle a source on/off for a user"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            user_source = session.query(UserSource).filter_by(
                user_id=user.id,
                source_domain=source_domain
            ).first()
            
            if user_source:
                user_source.is_enabled = not user_source.is_enabled
                session.commit()
                return user_source.is_enabled
            else:
                # Create new source entry if it doesn't exist
                user_source = UserSource(
                    user_id=user.id,
                    source_domain=source_domain,
                    is_enabled=True
                )
                session.add(user_source)
                session.commit()
                return True
        return None
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_user_sources(chat_id):
    """Get all sources and their enabled status for a user"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            return {source.source_domain: source.is_enabled for source in user.sources}
        return {}
    finally:
        session.close()

def get_enabled_sources_for_user(chat_id):
    """Get only enabled sources for a user"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            return [source.source_domain for source in user.sources if source.is_enabled]
        return []
    finally:
        session.close()

def get_user_preferences(chat_id):
    """Get complete user preferences (queries, sources, and topics)"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            return {
                'queries': [query.query_text for query in user.queries],
                'sources': {source.source_domain: source.is_enabled for source in user.sources},
                'topics': {topic.topic_name: topic.is_enabled for topic in user.topics}
            }
        return {'queries': [], 'sources': {}, 'topics': {}}
    finally:
        session.close()

# New functions for topic management
def toggle_user_topic(chat_id, topic_name):
    """Toggle a topic on/off for a user"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            user_topic = session.query(UserTopic).filter_by(
                user_id=user.id,
                topic_name=topic_name
            ).first()
            
            if user_topic:
                user_topic.is_enabled = not user_topic.is_enabled
                session.commit()
                return user_topic.is_enabled
            else:
                # Create new topic entry if it doesn't exist
                from categories import get_topic_category
                category = get_topic_category(topic_name)
                if category:
                    user_topic = UserTopic(
                        user_id=user.id,
                        topic_name=topic_name,
                        category=category,
                        is_enabled=True
                    )
                    session.add(user_topic)
                    session.commit()
                    return True
        return None
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_user_topics(chat_id):
    """Get all topics and their enabled status for a user"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            return {topic.topic_name: topic.is_enabled for topic in user.topics}
        return {}
    finally:
        session.close()

def get_enabled_topics_for_user(chat_id):
    """Get only enabled topics for a user"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            return [topic.topic_name for topic in user.topics if topic.is_enabled]
        return []
    finally:
        session.close()

def initialize_user_topics(chat_id):
    """Initialize all available topics for a user (disabled by default)"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            all_topics = get_all_topics()
            existing_topics = {topic.topic_name for topic in user.topics}
            
            for topic_name in all_topics:
                if topic_name not in existing_topics:
                    from categories import get_topic_category
                    category = get_topic_category(topic_name)
                    if category:
                        user_topic = UserTopic(
                            user_id=user.id,
                            topic_name=topic_name,
                            category=category,
                            is_enabled=False  # Disabled by default
                        )
                        session.add(user_topic)
            
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def initialize_user_sources(chat_id):
    """Initialize all available sources for a user (disabled by default)"""
    session = get_session()
    try:
        user = session.query(User).filter_by(chat_id=str(chat_id)).first()
        if user:
            all_sources = get_all_sources()
            existing_sources = {source.source_domain for source in user.sources}
            
            for source_domain in all_sources:
                if source_domain not in existing_sources:
                    user_source = UserSource(
                        user_id=user.id,
                        source_domain=source_domain,
                        is_enabled=False  # Disabled by default
                    )
                    session.add(user_source)
            
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()