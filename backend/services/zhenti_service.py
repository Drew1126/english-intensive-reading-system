import re
import os
import json
import asyncio
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from pdfminer.high_level import extract_text
from storage import read_json, write_json
from config import DATA_DIR, ARTICLES_DIR
from services.pdf_service import _translate_paragraph, _call_llm

logger = logging.getLogger(__name__)

ZHENTI_DIR = DATA_DIR / "zhenti"
ZHENTI_YEARS = list(range(2000, 2027))
ZHENTI_TEXTS = [1, 2, 3, 4]

_TRANSLATE_SYSTEM = """You are an expert at processing English passages for the Chinese graduate entrance exam (考研英语阅读).

The passage you receive was extracted from scanned images or PDFs by OCR, so it may contain artificial line breaks or image boundaries in the MIDDLE of a sentence. Your tasks:

1. Split the text into individual sentences accurately.
2. CRITICAL: when text before and after a line break / image boundary together form ONE grammatical sentence, merge them into a SINGLE sentence. Only treat them as two sentences if each side is grammatically complete on its own.
3. Preserve the passage's original paragraph structure: assign each sentence a paragraph number (starting at 0).
4. Translate each sentence accurately into Chinese.

Output ONLY a valid JSON array. Each element: {"en": "English sentence", "zh": "Chinese translation", "para": 0}
The number of elements must exactly match the number of sentences."""

_TRANSLATE_USER = """Return ONLY a valid JSON array. No other text. Each element: {{"en": "English sentence", "zh": "Chinese translation", "para": 0}}

Passage (may contain artificial line breaks inside sentences caused by scanning):
{text}"""


async def _translate_passage(text: str) -> Optional[list[dict]]:
    """One LLM call: sentence split (handling cross-image breaks) + paragraph grouping + translation."""
    prompt = _TRANSLATE_USER.format(text=text[:8000])
    for attempt in range(3):
        try:
            content = await _call_llm(_TRANSLATE_SYSTEM, prompt)
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(content)
            if isinstance(data, list) and all("en" in item and "zh" in item for item in data):
                return data
            logger.warning(f"Zhenti LLM invalid format (attempt {attempt + 1}): {content[:100]}")
        except Exception as e:
            logger.warning(f"Zhenti LLM failed (attempt {attempt + 1}): {e}")
            await asyncio.sleep(1)
    return None


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


def delete_article(year: int, text_num: int) -> bool:
    path = _article_path(year, text_num)
    if not path.exists():
        return False
    path.unlink()
    logger.info(f"Zhenti deleted: {year} text {text_num}")
    return True


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

    # Join with single newline so a sentence split across two images
    # stays contiguous for the LLM to correctly merge.
    full_text = "\n".join(t.strip() for t in texts if t.strip())
    if not full_text.strip():
        raise RuntimeError("No text extracted from files")

    article = {
        "title": f"{year}年考研英语阅读 Text {text_num}",
        "source": f"考研真题 {year}",
        "category": "考研真题",
        "word_count": 0,
        "date": date.today().isoformat(),
        "paragraphs": [],
    }

    result = await _translate_passage(full_text)

    if result:
        paragraphs = []
        cur_para = None
        cur_en = []
        cur_zh = []

        def flush():
            if cur_en:
                paragraphs.append({
                    "index": len(paragraphs),
                    "sentences": cur_en[:],
                    "translations": cur_zh[:],
                })

        for item in result:
            pnum = item.get("para", 0)
            if cur_para is None:
                cur_para = pnum
            if pnum != cur_para:
                flush()
                cur_en = []
                cur_zh = []
                cur_para = pnum
            cur_en.append(item["en"])
            cur_zh.append(item["zh"])
        flush()

        article["paragraphs"] = paragraphs
    else:
        # Fallback: per-paragraph split + translate (old behavior)
        paragraphs = _split_raw_paragraphs(full_text)
        for i, para_text in enumerate(paragraphs):
            r = await _translate_paragraph(para_text)
            article["paragraphs"].append({
                "index": i,
                "sentences": [item["en"] for item in r] if r else [para_text],
                "translations": [item["zh"] for item in r] if r else [""],
            })

    total_wc = sum(len(s.split()) for p in article["paragraphs"] for s in p["sentences"])
    article["word_count"] = total_wc

    return save_article(year, text_num, article)
