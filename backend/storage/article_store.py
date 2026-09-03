from typing import Optional
from config import ARTICLES_DIR
from storage import read_json, write_json


def get_article_path(index: int) -> str:
    return str(ARTICLES_DIR / f"article_{index}.json")


def get_article(index: int) -> Optional[dict]:
    return read_json(get_article_path(index), None)


def save_article(index: int, data: dict) -> None:
    write_json(get_article_path(index), data)
