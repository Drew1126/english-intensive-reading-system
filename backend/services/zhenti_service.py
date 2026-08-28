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

_TRANSLATE_SYSTEM = """You are processing a single English reading passage for the Chinese graduate entrance exam (考研英语阅读).

The text you receive is a READING PASSAGE ONLY. It does NOT contain any questions.

Your ONLY task is:
1. Split the passage into individual sentences accurately.
2. When text before and after a line break / image boundary together form ONE grammatical sentence, merge them into a SINGLE sentence. Only treat them as two sentences if each side is grammatically complete on its own.
3. Assign each sentence its paragraph number (starting at 0).
4. Translate each sentence into Chinese.

STRICT RULES:
- Output ONLY sentences that appear VERBATIM in the passage text provided.
- NEVER generate, add, invent, or fabricate any multiple-choice questions, question stems, options, titles, or any content NOT present in the passage.
- The passage contains ONLY the article text. There are NO questions after it.
- Do NOT append anything after the last passage sentence.

Output ONLY a valid JSON array. Each element: {"en": "English sentence", "zh": "Chinese translation", "para": 0}"""

_TRANSLATE_USER = """Return ONLY a valid JSON array. No other text. Each element: {{"en": "English sentence", "zh": "Chinese translation", "para": 0}}

Reading passage (may contain artificial line breaks inside sentences caused by scanning). Output sentences ONLY from this passage:
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


# OCR often reads the question number with a colon (e.g. "21:") or misreads
# the period as "z"/"l"/"I" (e.g. "21z"), so tolerate trailing noise characters.
_NUM_NOISE = r'[\s\.\)\],zlI:]*'
_NUM_ONLY_RE = re.compile(r'^(\d{1,2})' + _NUM_NOISE + r'$')
_NUM_PREFIX_RE = re.compile(r'^(\d{1,2})' + r'[\s\.\)\],zlI:]+' + r'\s*(.*)$')
_OPTION_RE = re.compile(r'^\s*[A-Da-d][\.\)、]\s*')


def _split_passage_and_questions(text: str) -> tuple[str, list[str]]:
    """Split OCR text into (passage, questions[]).

    The questions section starts at the first question-number line or stem
    that is followed within a few lines by an option line (A. B. C. D.).
    """
    lines = text.split("\n")

    question_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not (_NUM_ONLY_RE.match(s) or _NUM_PREFIX_RE.match(s)):
            continue
        for j in range(i + 1, min(i + 20, len(lines))):
            if _OPTION_RE.match(lines[j].strip()):
                question_start = i
                break
        if question_start is not None:
            break

    if question_start is None:
        return text, []

    passage = "\n".join(lines[:question_start])
    q_text = "\n".join(lines[question_start:])
    return passage, _extract_questions(q_text)


def _extract_questions(text: str) -> list[str]:
    """Group question text into individual questions.

    Each question = stem line(s) + 4 option lines (A./B./C./D.).
    OCR often puts all question numbers ("36." "37." ...) as isolated lines
    BEFORE the actual stems; those are collected separately and re-attached
    in order to the detected questions.
    """
    nums = []
    clean = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        m = _NUM_ONLY_RE.match(s)
        if m:
            nums.append(int(m.group(1)))
            continue
        m = _NUM_PREFIX_RE.match(s)
        if m:
            nums.append(int(m.group(1)))
            clean.append(m.group(2))
            continue
        clean.append(s)

    questions = []
    cur = []
    option_count = 0
    for s in clean:
        if _OPTION_RE.match(s):
            cur.append(s)
            option_count += 1
            if option_count >= 4:
                questions.append(cur)
                cur = []
                option_count = 0
        else:
            if option_count > 0:
                if cur:
                    questions.append(cur)
                cur = [s]
                option_count = 0
            else:
                cur.append(s)
    if cur:
        questions.append(cur)

    result = []
    for i, q in enumerate(questions):
        if i < len(nums):
            num = nums[i]
        elif nums:
            num = nums[-1] + (i - len(nums) + 1)
        else:
            num = None
        qtext = "\n".join(_clean_question_lines(q))
        if num is not None:
            qtext = f"{num}. " + qtext
        result.append(qtext)

    return result


def _clean_question_lines(lines: list[str]) -> list[str]:
    out = []
    for l in lines:
        l = re.sub(r'^\s*([A-Da-d])[\.\)、]\s*', lambda m: m.group(1).upper() + ". ", l)
        out.append(l)
    return out


_QUESTION_SYSTEM = """You are a translator for the Chinese graduate entrance exam (考研英语). Translate the given English multiple-choice question into Chinese.

Rules:
- KEEP the question number (e.g. 36.) at the beginning of the translation.
- KEEP each option label (A. B. C. D.) and put each option on its OWN line.
- Translate the stem and each option accurately.
- Output ONLY the translated text, no extra commentary."""

_QUESTION_USER = """Translate this multiple-choice question into Chinese. Keep the question number, and keep each option on its own line:

{text}"""


async def _translate_question(text: str) -> str:
    prompt = _QUESTION_USER.format(text=text)
    for attempt in range(3):
        try:
            content = await _call_llm(_QUESTION_SYSTEM, prompt)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            if content:
                return content
            logger.warning(f"Question translate empty (attempt {attempt + 1})")
        except Exception as e:
            logger.warning(f"Question translate failed (attempt {attempt + 1}): {e}")
            await asyncio.sleep(1)
    return ""


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

    # Split out multiple-choice questions first (keep them intact with number + options).
    passage_text, questions = _split_passage_and_questions(full_text)

    # ── Passage: sentence split + translation (one LLM call) ──
    if passage_text.strip():
        result = await _translate_passage(passage_text)
        if result:
            cur_para = None
            cur_en = []
            cur_zh = []

            def flush():
                if cur_en:
                    article["paragraphs"].append({
                        "index": len(article["paragraphs"]),
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
        else:
            # Fallback: per-paragraph split + translate (old behavior)
            paragraphs = _split_raw_paragraphs(passage_text)
            for i, para_text in enumerate(paragraphs):
                r = await _translate_paragraph(para_text)
                article["paragraphs"].append({
                    "index": i,
                    "sentences": [item["en"] for item in r] if r else [para_text],
                    "translations": [item["zh"] for item in r] if r else [""],
                })

    # ── Questions: keep original text (number + options on separate lines), translate as unit ──
    for q in questions:
        zh = await _translate_question(q)
        article["paragraphs"].append({
            "index": len(article["paragraphs"]),
            "sentences": [q],
            "translations": [zh],
        })

    total_wc = sum(len(s.split()) for p in article["paragraphs"] for s in p["sentences"])
    article["word_count"] = total_wc

    return save_article(year, text_num, article)
