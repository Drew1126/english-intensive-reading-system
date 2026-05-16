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
CHECKINS_FILE = DATA_DIR / "checkins.json"
CHAT_HISTORY_DIR = DATA_DIR / "chat_history"

ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

ARTICLE_WORD_RANGE = "350-450"

DAILY_TOPICS = [
    "社会伦理 / 文化教育",
    "经济商业 / 职场趋势",
    "科技发展 / 人工智能",
    "生态环境 / 公共健康",
    "法律政治简版",
]
