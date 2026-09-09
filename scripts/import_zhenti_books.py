"""Import missing English-I reading passages from the bundled exam-prep scans.

The books are image-only PDFs. This script renders only the known Part A page
ranges, OCRs them with Tesseract, asks the configured LLM to reconstruct the
passage/questions and translations, validates the result, and writes the same
JSON shape used by the application.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from services.pdf_service import _call_llm  # noqa: E402


POPPLER = Path(r"C:\Users\Chen\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe")
TESSERACT = Path(r"D:\Tesseract-OCR\tesseract.exe")
OUTPUT_DIR = BACKEND / "data" / "zhenti"
CACHE_DIR = ROOT / "tmp" / "pdfs" / "zhenti-import"

BOOKS = {
    "base": Path(r"D:\Downloads\历年考研英语真题解析及复习思路(基础版)（2007-2013）.pdf"),
    "recent": Path(r"D:\Downloads\历年考研英语真题解析及复习思路(精编版)  (2022-2026) .pdf"),
}

# Inclusive source-page ranges. The older detailed edition uses eight pages per
# Text; the recent detailed edition uses seven. The new 2026 paper is compact.
PAGE_RANGES: dict[int, list[tuple[int, int]]] = {}
for year, block_start in {
    2007: 115, 2008: 163, 2009: 215, 2010: 267,
    2011: 319, 2012: 371, 2013: 423,
}.items():
    PAGE_RANGES[year] = [
        (block_start + 11 + 7 * i, block_start + 20 + 7 * i)
        for i in range(4)
    ]
for year, block_start in {2022: 67, 2023: 119, 2024: 171, 2025: 223}.items():
    PAGE_RANGES[year] = [
        (block_start + 13 + 7 * i - (2 if i else 0), block_start + 19 + 7 * i)
        for i in range(4)
    ]


SYSTEM_PROMPT = """You reconstruct Chinese postgraduate English-I exam reading data from noisy OCR of a bilingual study guide.

The OCR contains the original English passage, five original multiple-choice questions, Chinese translations, and extensive teaching commentary. Extract ONLY the original passage and the five questions. Correct obvious OCR errors using grammar and repeated quotations in the commentary, but never invent content. Ignore all teaching commentary.

Return ONLY one valid JSON object:
{"paragraphs":[{"sentences":["..."],"translations":["..."]}],"questions":[{"en":"number. stem\\nA. ...\\nB. ...\\nC. ...\\nD. ...","zh":"number. Chinese stem\\nA. ...\\nB. ...\\nC. ...\\nD. ..."}]}

Requirements:
- Preserve the passage paragraph boundaries and split each paragraph into complete English sentences.
- Provide a faithful Chinese translation for every sentence; sentence and translation counts must match.
- Include exactly five questions, each with A-D options, and preserve the requested question numbers.
- Do not include analysis, answer keys, source notes, word counts, or headings.
- Do not require any minimum word count per paragraph."""


def book_for(year: int) -> Path:
    return BOOKS["base" if year <= 2013 else "recent"]


def ocr_image(path: Path) -> str:
    completed = subprocess.run(
        [str(TESSERACT), str(path), "stdout", "-l", "eng", "--psm", "11"],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return completed.stdout


def get_ocr(year: int, text_num: int) -> str:
    cache = CACHE_DIR / f"{year}_text_{text_num}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")

    first, last = PAGE_RANGES[year][text_num - 1]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"zhenti-{year}-{text_num}-", dir=CACHE_DIR) as tmp:
        prefix = Path(tmp) / "page"
        subprocess.run(
            [str(POPPLER), "-f", str(first), "-l", str(last), "-r", "180", "-jpeg", "-jpegopt", "quality=88", str(book_for(year)), str(prefix)],
            check=True,
        )
        images = sorted(Path(tmp).glob("page-*.jpg"))
        with ThreadPoolExecutor(max_workers=min(6, len(images))) as pool:
            page_texts = list(pool.map(ocr_image, images))
    raw = "\n\n".join(f"=== SOURCE PAGE {first + i} ===\n{text}" for i, text in enumerate(page_texts))
    cache.write_text(raw, encoding="utf-8")
    return raw


def parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(content[start:end + 1])


def validate(data: dict, year: int, text_num: int) -> list[str]:
    errors: list[str] = []
    paragraphs = data.get("paragraphs")
    questions = data.get("questions")
    if not isinstance(paragraphs, list) or len(paragraphs) < 3:
        errors.append("fewer than 3 passage paragraphs")
    else:
        for i, paragraph in enumerate(paragraphs):
            en, zh = paragraph.get("sentences"), paragraph.get("translations")
            if not isinstance(en, list) or not isinstance(zh, list) or not en or len(en) != len(zh):
                errors.append(f"paragraph {i + 1} sentence/translation mismatch")
    if not isinstance(questions, list) or len(questions) != 5:
        errors.append("question count is not 5")
    else:
        expected_first = 21 + (text_num - 1) * 5
        for i, question in enumerate(questions):
            en, zh = str(question.get("en", "")), str(question.get("zh", ""))
            expected = expected_first + i
            if not re.match(rf"^{expected}[.、)]", en.strip()):
                errors.append(f"missing question number {expected}")
            for label in "ABCD":
                if not re.search(rf"(?m)^{label}[.)、]", en):
                    errors.append(f"question {expected} missing option {label}")
            if not re.search(r"[\u4e00-\u9fff]", zh):
                errors.append(f"question {expected} missing Chinese translation")
    return errors


def build_article(data: dict, year: int, text_num: int) -> dict:
    paragraphs = []
    passage_words = 0
    for item in data["paragraphs"]:
        sentences = [re.sub(r"\s+", " ", s).strip() for s in item["sentences"] if str(s).strip()]
        translations = [re.sub(r"\s+", " ", s).strip() for s in item["translations"] if str(s).strip()]
        passage_words += sum(len(re.findall(r"\b[A-Za-z]+(?:['’-][A-Za-z]+)?\b", s)) for s in sentences)
        paragraphs.append({"index": len(paragraphs), "sentences": sentences, "translations": translations})
    for question in data["questions"]:
        paragraphs.append({
            "index": len(paragraphs),
            "sentences": [question["en"].strip()],
            "translations": [question["zh"].strip()],
        })
    return {
        "title": f"{year}年考研英语阅读 Text {text_num}",
        "source": f"考研真题 {year}",
        "category": "考研真题",
        "word_count": passage_words,
        "date": date.today().isoformat(),
        "paragraphs": paragraphs,
        "id": f"zhenti_{year}_{text_num}",
        "zhenti": {"year": year, "text": text_num},
    }


async def reconstruct(year: int, text_num: int, raw: str) -> dict:
    first_question = 21 + (text_num - 1) * 5
    target_header = re.search(rf"(?i)\bText\s*{text_num}\b", raw)
    if target_header:
        raw = raw[target_header.start():]
        if text_num < 4:
            next_header = re.search(rf"(?i)\bText\s*{text_num + 1}\b", raw[500:])
            if next_header:
                raw = raw[:500 + next_header.start()]
    user = f"Year: {year}; Text: {text_num}; expected questions: {first_question}-{first_question + 4}.\n\nOCR:\n{raw}"
    last_errors: list[str] = []
    last_exception: Exception | None = None
    for attempt in range(5):
        reminder = "" if not last_errors else "\n\nFix these validation failures from the prior result: " + "; ".join(last_errors)
        try:
            data = parse_json(await _call_llm(SYSTEM_PROMPT, user + reminder))
            last_errors = validate(data, year, text_num)
            if not last_errors:
                return data
        except Exception as exc:
            last_exception = exc
            await asyncio.sleep(min(2 ** attempt, 12))
    details = "; ".join(last_errors) if last_errors else repr(last_exception)
    raise RuntimeError(details)


async def import_one(year: int, text_num: int, overwrite: bool) -> tuple[int, int, str]:
    output = OUTPUT_DIR / str(year) / f"text_{text_num}.json"
    if output.exists() and not overwrite:
        return year, text_num, "skipped"
    raw = await asyncio.to_thread(get_ocr, year, text_num)
    data = await reconstruct(year, text_num, raw)
    article = build_article(data, year, text_num)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return year, text_num, f"saved ({article['word_count']} passage words)"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="*", type=int, default=sorted(PAGE_RANGES))
    parser.add_argument("--texts", nargs="*", type=int, default=[1, 2, 3, 4])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not POPPLER.is_file() or not TESSERACT.is_file():
        raise SystemExit("pdftoppm.exe or tesseract.exe is missing")
    for path in BOOKS.values():
        if not path.is_file():
            raise SystemExit(f"PDF missing: {path}")
    failures: list[str] = []
    for year in args.years:
        if year not in PAGE_RANGES:
            raise SystemExit(f"Unsupported year: {year}")
        for text_num in args.texts:
            if text_num not in (1, 2, 3, 4):
                raise SystemExit(f"Unsupported Text number: {text_num}")
            print(f"[{year} Text {text_num}] OCR + reconstruction...", flush=True)
            try:
                result = await import_one(year, text_num, args.overwrite)
                print(f"[{result[0]} Text {result[1]}] {result[2]}", flush=True)
            except Exception as exc:
                failure = f"{year} Text {text_num}: {exc}"
                failures.append(failure)
                print(f"FAILED: {failure}", file=sys.stderr, flush=True)
    if failures:
        raise SystemExit("Import failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    asyncio.run(main())
