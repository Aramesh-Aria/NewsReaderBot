# Topic categories and their topics
TOPIC_CATEGORIES = {
    "tech": {
        "name": "Technology & Digital",
        "topics": [
            "Technology",
            "Programming", 
            "AI",
            "Machine Learning",
            "Data Science",
            "Cybersecurity",
            "Startups",
            "Gadgets",
            "Internet",
            "Mobile"
        ]
    },
    "sci": {
        "name": "Science & Education",
        "topics": [
            "Science",
            "Space",
            "Health",
            "Education",
            "Environment"
        ]
    },
    "pol": {
        "name": "Politics & Economy",
        "topics": [
            "Politics",
            "Economy",
            "World Politics",
            "Business",
            "Law",
            "Elections"
        ]
    },
    "cul": {
        "name": "Culture & Media",
        "topics": [
            "Entertainment",
            "Movies",
            "TV Shows",
            "Music",
            "Lifestyle",
            "Culture"
        ]
    },
    "soc": {
        "name": "Society",
        "topics": [
            "Society",
            "Human Rights",
            "Immigration"
        ]
    },
    "spt": {
        "name": "Sports & Gaming",
        "topics": [
            "Sports",
            "Football",
            "Basketball",
            "Esports",
            "Gaming"
        ]
    },
    "geo": {
        "name": "Geopolitical & Regional",
        "topics": [
            "Iran News",
            "US News",
            "Middle East",
            "Global Affairs",
            "Sanctions",
            "Nuclear Talks"
        ]
    }
}

# Source categories and their sources
SOURCE_CATEGORIES = {
    "gen": {
        "name": "General & International",
        "sources": [
            "cnn.com",          # CNN
            "bbc.com",          # BBC
            "nytimes.com",      # The New York Times
            "reuters.com",      # Reuters
            "apnews.com",       # Associated Press
            "theguardian.com",  # The Guardian
            "bloomberg.com",    # Bloomberg
            "aljazeera.com"     # Al Jazeera
        ]
    },
    "tech": {
        "name": "Technology",
        "sources": [
            "theverge.com",     # The Verge
            "techcrunch.com",   # TechCrunch
            "wired.com",        # WIRED
            "engadget.com",     # Engadget
            "arstechnica.com",  # Ars Technica
            "mashable.com",     # Mashable
            "cnet.com"          # CNET
        ]
    },
    "us": {
        "name": "U.S. Politics & National",
        "sources": [
            "politico.com",     # Politico
            "foxnews.com",      # Fox News
            "nbcnews.com",      # NBC News
            "abcnews.go.com",   # ABC News
            "washingtonpost.com",  # The Washington Post
            "thehill.com",         # The Hill
            "time.com"             # TIME
        ]
    },
    "me": {
        "name": "Middle East (English)",
        "sources": [
            "al-monitor.com",   # Al-Monitor
            "arabnews.com",     # Arab News
            "haaretz.com",      # Haaretz
            "tehrantimes.com"   # Tehran Times (EN)
        ]
    }
}

# Get all topics from all categories
def get_all_topics():
    """Get a flat list of all available topics"""
    all_topics = []
    for category_data in TOPIC_CATEGORIES.values():
        all_topics.extend(category_data["topics"])
    return all_topics

# Get all sources from all categories
def get_all_sources():
    """Get a flat list of all available sources"""
    all_sources = []
    for category_data in SOURCE_CATEGORIES.values():
        all_sources.extend(category_data["sources"])
    return all_sources

# Get topic by name
def get_topic_category(topic_name):
    """Get the category for a given topic name"""
    for cat_id, cat_data in TOPIC_CATEGORIES.items():
        if topic_name in cat_data["topics"]:
            return cat_id
    return None

# Get source by domain
def get_source_category(source_domain):
    """Get the category for a given source domain"""
    for cat_id, cat_data in SOURCE_CATEGORIES.items():
        if source_domain in cat_data["sources"]:
            return cat_id
    return None 