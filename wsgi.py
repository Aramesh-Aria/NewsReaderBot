import os
from dotenv import load_dotenv
from src.main import app

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    app.run(host=host, port=port) 