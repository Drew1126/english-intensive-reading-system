import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = "deepseek-chat"
LLM_API_BASE = "https://api.deepseek.com/v1/"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ARTICLES_DIR = DATA_DIR / "articles"
CHAT_HISTORY_DIR = DATA_DIR / "chat_history"

ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
