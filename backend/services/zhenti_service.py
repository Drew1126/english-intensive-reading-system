import re
import os
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from pdfminer.high_level import extract_text
from storage import read_json, write_json
from config import DATA_DIR, ARTICLES_DIR
from services.pdf_service import _translate_paragraph

logger = logging.getLogger(__name__)

ZHENTI_DIR = DATA_DIR / "zhenti"
ZHENTI_YEARS = list(range(2000, 2027))
ZHENTI_TEXTS = [1, 2, 3, 4]

_TEXT_PATTERNS = [
    r"Text\s*(\d+)",
    r"Passage\s*(\d+)",
    r"Section\s*II?\s*Part\s*A?\s*Text\s*(\d+)",
]


def _zhenti_dir(year: int) -> Path:
    return ZHENTI_DIR / str(year)


def _article_path(year: int, text_num: int) -> Path:
    return _zhenti_dir(year) / f"text_{text_num}.json"


def _exists(year: int, text_num: int) -> bool:
    return _article_path(year, text_num).exists()


def list_years() -> list[dict]:
    result = []
    for year in ZHENTI_YEARS:
        entry = {"year": year}
        for t in ZHENTI_TEXTS:
            entry[f"text{t}"] = _exists(year, t)
        result.append(entry)
    return result


def get_article(year: int, text_num: int) -> Optional[dict]:
    path = _article_path(year, text_num)
    if not path.exists():
        return None
    return read_json(str(path), None)


def save_article(year: int, text_num: int, article: dict) -> dict:
    path = _article_path(year, text_num)
    path.parent.mkdir(parents=True, exist_ok=True)
    article["id"] = f"zhenti_{year}_{text_num}"
    article["article_index"] = -1
    article["zhenti"] = {"year": year, "text": text_num}
    write_json(str(path), article)
    logger.info(f"Zhenti saved: {year} text {text_num} ({article.get('title')})")
    return article


def extract_from_pdf(file_path: str) -> str:
    return extract_text(file_path)


def extract_from_images(file_paths: list[str]) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as e:
        raise RuntimeError(f"OCR dependencies missing: {e}")

    parts = []
    for p in file_paths:
        img = Image.open(p)
        if img.mode != "RGB":
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img, lang="eng")
        parts.append(text.strip())
    return "\n\n".join(parts)


def _split_raw_paragraphs(text: str) -> list[str]:
    raw = re.split(r"\n\s*\n", text.strip())
    paras = []
    for block in raw:
        block = re.sub(r"\s+", " ", block).strip()
        if len(block.split()) >= 5:
            paras.append(block)
    return paras


async def process_upload(year: int, text_num: int, file_paths: list[str]) -> dict:
    """Process uploaded files (PDF or images) into a translated article."""
    if not file_paths:
        raise RuntimeError("No files provided")

    texts = []
    for p in file_paths:
        ext = os.path.splitext(p)[1].lower()
        if ext == ".pdf":
            texts.append(extract_from_pdf(p))
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
            texts.append(extract_from_images([p]))
        else:
            raise RuntimeError(f"Unsupported file type: {ext}")

    full_text = "\n\n".join(texts)
    if not full_text.strip():
        raise RuntimeError("No text extracted from files")

    paragraphs = _split_raw_paragraphs(full_text)

    article = {
        "title": f"{year}年考研英语阅读 Text {text_num}",
        "source": f"考研真题 {year}",
        "category": "考研真题",
        "word_count": 0,
        "date": date.today().isoformat(),
        "paragraphs": [],
    }

    for i, para_text in enumerate(paragraphs):
        result = await _translate_paragraph(para_text)
        if result:
            article["paragraphs"].append({
                "index": i,
                "sentences": [item["en"] for item in result],
                "translations": [item["zh"] for item in result],
            })
        else:
            article["paragraphs"].append({
                "index": i,
                "sentences": [para_text],
                "translations": [""],
            })

    total_wc = sum(len(s.split()) for p in article["paragraphs"] for s in p["sentences"])
    article["word_count"] = total_wc

    return save_article(year, text_num, article)
