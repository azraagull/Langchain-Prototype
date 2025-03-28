import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_API_BASE_URL = "http://localhost:11434"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TELEGRAM_BOT_TOKEN= os.getenv("TELEGRAM_BOT_TOKEN")
UPLOAD_DIR_TG = "./uploads/Telegram"
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USERNAME_SCRAPER = os.getenv("DB_USERNAME_SCRAPER")
DB_PASSWORD_SCRAPER = os.getenv("DB_PASSWORD_SCRAPER")
DB_NAME_SCRAPER = os.getenv("DB_NAME_SCRAPER")
PAGINATION = os.getenv("PAGINATION", 5)