from typing import Optional
from pathlib import Path
from config import ARTICLES_DIR
from storage import read_json, write_json
import logging

logger = logging.getLogger(__name__)


def get_article_path(index: int) -> str:
    return str(ARTICLES_DIR / f"article_{index}.json")


def get_article(index: int) -> Optional[dict]:
    return read_json(get_article_path(index), None)


def save_article(index: int, data: dict) -> None:
    write_json(get_article_path(index), data)


def cleanup_old_articles() -> None:
    """Delete any article_*.json files outside the 2 slots (0,1) and the PDF upload slot (-1)."""
    keep = {0, 1, -1}
    for f in list(ARTICLES_DIR.glob("article_*.json")):
        try:
            idx = int(f.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        if idx not in keep:
            f.unlink()
            logger.info(f"Cleaned up article {idx}")
