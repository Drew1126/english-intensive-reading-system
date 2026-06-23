import re
import json
import asyncio
import time
import logging
import httpx
from typing import Optional
from datetime import date
from pathlib import Path

from pdfminer.high_level import extract_text
from storage.article_store import save_article
from storage import write_json, read_json
from fastapi.concurrency import run_in_threadpool
from config import LLM_API_KEY, LLM_MODEL, LLM_API_BASE, ARTICLES_DIR

logger = logging.getLogger(__name__)

_P_LABEL = re.compile(r'^P\d+$')
_API_LIMITER = asyncio.Semaphore(2)

TRANSLATE_SYSTEM_PROMPT = """You are an expert translator and English sentence segmenter. Given an English paragraph, split it into individual sentences and provide accurate Chinese translations.

Sentence splitting rules:
- Split at sentence-ending punctuation (. ! ?) followed by a space and an uppercase letter or opening quote
- NEVER split on periods inside abbreviations (Mr., Mrs., Dr., Ms., Prof., U.S., U.K., Inc., Ltd., etc.)
- NEVER split on periods in names or initials (Statham's, J. K. Rowling, etc.)
- NEVER split on decimal points (4.5, $3.14, 0.5%)
- Each output sentence must be a complete grammatical unit"""

TRANSLATE_USER_PROMPT = """Return ONLY a valid JSON array. No other text.

Each element: {{"en": "English sentence", "zh": "Chinese translation"}}

The number of elements must exactly match the number of sentences.

Paragraph:
{text}"""

INDEX_FILE = str(ARTICLES_DIR / "index.json")


def _is_p_label(line: str) -> bool:
    return bool(_P_LABEL.match(line.strip()))


def _merge_lines(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _has_chinese(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text))


async def _call_llm(system: str, user: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
    }

    async with _API_LIMITER:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
            resp = await client.post(LLM_API_BASE + "chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()


def _parse_llm_response(content: str) -> Optional[list[dict]]:
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(content)
        if isinstance(data, list) and all("en" in item and "zh" in item for item in data):
            return data
    except json.JSONDecodeError:
        pass
    return None


async def _translate_paragraph(para_text: str) -> Optional[list[dict]]:
    prompt = TRANSLATE_USER_PROMPT.format(text=para_text)
    for attempt in range(3):
        try:
            content = await _call_llm(TRANSLATE_SYSTEM_PROMPT, prompt)
            result = _parse_llm_response(content)
            if result and len(result) > 0:
                return result
            logger.warning(f"LLM invalid format (attempt {attempt + 1}): {content[:100]}")
        except Exception as e:
            logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
            await asyncio.sleep(1)
    return None


def _next_article_index() -> int:
    index_data = read_json(INDEX_FILE, {"next": 0})
    n = index_data["next"]
    index_data["next"] = n + 1
    write_json(INDEX_FILE, index_data)
    return n


def _add_to_index(meta: dict):
    index_data = read_json(INDEX_FILE, {"next": 0, "articles": []})
    if "articles" not in index_data:
        index_data["articles"] = []
    index_data["articles"].append(meta)
    write_json(INDEX_FILE, index_data)


def get_article_list() -> list[dict]:
    index_data = read_json(INDEX_FILE, {"next": 0, "articles": []})
    return list(reversed(index_data.get("articles", [])))


def get_article_by_index(index: int) -> Optional[dict]:
    return read_json(str(ARTICLES_DIR / f"article_{index}.json"), None)


def delete_article(index: int) -> bool:
    path = ARTICLES_DIR / f"article_{index}.json"
    if not path.exists():
        return False
    path.unlink()
    index_data = read_json(INDEX_FILE, {"next": 0, "articles": []})
    index_data["articles"] = [a for a in index_data.get("articles", []) if a.get("index") != index]
    write_json(INDEX_FILE, index_data)
    return True


def get_latest_article() -> Optional[dict]:
    articles = get_article_list()
    if not articles:
        return None
    return get_article_by_index(articles[0]["index"])


def parse_pdf(file_path: str) -> Optional[dict]:
    try:
        raw_text = extract_text(file_path)
    except Exception as e:
        logger.error(f"PDF extract failed: {e}")
        return None

    lines = raw_text.split("\n")

    source = "PDF"
    title = ""
    word_count = 0
    found_source = False

    body_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r'^\d+词$', stripped):
            m = re.search(r'(\d+)', stripped)
            if m:
                word_count = int(m.group(1))
            body_start = i + 1
            break
        if _has_chinese(stripped):
            if not found_source:
                m = re.match(r'^([A-Za-z\s]+)(?:[\u4e00-\u9fff]|$)', stripped)
                if m:
                    s = m.group(1).strip()
                    words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', s)
                    while len(words) >= 2 and len(words) % 2 == 0:
                        mid = len(words) // 2
                        if words[:mid] == words[mid:]:
                            words = words[:mid]
                        else:
                            break
                    s = " ".join(words)
                    if len(s) >= 3:
                        source = s
                        found_source = True
        else:
            if not found_source:
                cleaned = re.sub(r'^([A-Za-z]+)\1$', r'\1', stripped)
                words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', cleaned)
                while len(words) >= 2 and len(words) % 2 == 0:
                    mid = len(words) // 2
                    if words[:mid] == words[mid:]:
                        words = words[:mid]
                    else:
                        break
                if 1 <= len(words) <= 4:
                    source = " ".join(words)
                    found_source = True
                    continue
            if re.match(r"^[A-Za-z'\u2018\u2019][A-Za-z0-9\s'\"\u2019\u2018\-\:,\?\!]+$", stripped) and len(stripped) >= 3:
                title = (title + " " + stripped).strip()

    if body_start:
        while body_start < len(lines) and not lines[body_start].strip():
            body_start += 1

    if body_start is None or body_start >= len(lines):
        logger.error("Could not find article body in PDF")
        return None

    body_lines = lines[body_start:]

    raw_paras = []
    current = []

    def _flush():
        if current:
            merged = _merge_lines(" ".join(current))
            if merged and len(merged.split()) >= 5:
                raw_paras.append(merged)

    for i, line in enumerate(body_lines):
        stripped = line.strip()
        if not stripped:
            ahead = i + 1
            while ahead < len(body_lines) and not body_lines[ahead].strip():
                ahead += 1
            if ahead < len(body_lines) and _is_p_label(body_lines[ahead].strip()):
                continue
            _flush()
            current = []
            continue
        if _is_p_label(stripped):
            continue
        if re.match(r'^-\d+-$', stripped):
            continue
        current.append(stripped)

    _flush()

    article = {
        "title": title,
        "source": source,
        "category": "",
        "word_count": word_count,
        "date": date.today().isoformat(),
        "paragraphs": [],
    }

    for i, para_text in enumerate(raw_paras):
        article["paragraphs"].append({
            "index": i,
            "sentences": [para_text],
            "translations": [],
        })

    return article


async def process_uploaded_pdf(file_path: str) -> Optional[dict]:
    article = parse_pdf(file_path)
    if not article:
        return None

    index = _next_article_index()
    logger.info(f"PDF parsed: {article['title'][:50]}, {len(article['paragraphs'])} paragraphs, index={index}")

    for i, para in enumerate(article["paragraphs"]):
        para_text = para["sentences"][0]
        logger.info(f"Translating paragraph {i + 1}/{len(article['paragraphs'])} ({len(para_text.split())}w)")
        result = await _translate_paragraph(para_text)
        if result:
            para["sentences"] = [item["en"] for item in result]
            para["translations"] = [item["zh"] for item in result]
        else:
            para["translations"] = [""]

    total_wc = sum(len(s.split()) for p in article["paragraphs"] for s in p["sentences"])
    if not article["word_count"]:
        article["word_count"] = total_wc

    article["id"] = f"article_{index}"
    article["article_index"] = index

    await run_in_threadpool(save_article, index, article)

    _add_to_index({
        "id": article["id"],
        "index": index,
        "title": article["title"],
        "source": article["source"],
        "word_count": article["word_count"],
        "date": article["date"],
    })

    return article
