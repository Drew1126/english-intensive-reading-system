#!/usr/bin/env python3
"""Run the full article processing pipeline on crawled articles.

Usage:
    python3 run_pipeline.py                    # process all sources
    python3 run_pipeline.py --source Economist  # specific source
    python3 run_pipeline.py --limit 5           # max 5 articles
"""

import asyncio
import json
import logging
import re
import sys
from pathlib import Path

from agents.article_processor import ArticleProcessor, pre_filter, count_words, tokenize, validate_format
from vocab_checker import VocabChecker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CRAWLED_DIR = Path(__file__).resolve().parent.parent / "crawled_articles"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "processed_articles"

# ── Helpers ──

def parse_article_file(path: Path) -> dict | None:
    """Parse a crawled article .txt file with metadata header."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"Failed to read {path}: {e}")
        return None

    # Parse metadata header (lines before ==== separator)
    header = {}
    body_start = content.find("=" * 60)
    if body_start == -1:
        return None
    header_lines = content[:body_start].strip().split("\n")
    body = content[body_start + 60:].strip()

    for line in header_lines:
        m = re.match(r"^(\w[\w\s]+):\s*(.*)", line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            header[key] = value

    source = header.get("Source", path.parent.name)
    title = header.get("Title", path.stem)
    wc_str = header.get("Word Count", header.get("Word_Count", "0"))

    try:
        wc = int(wc_str)
    except ValueError:
        wc = count_words(body)

    return {
        "source": source,
        "title": title,
        "word_count": wc,
        "body": body,
        "path": str(path),
    }


def save_result(article: dict, source_name: str) -> Path | None:
    """Save processed article to output directory."""
    source_dir = OUTPUT_DIR / source_name
    source_dir.mkdir(parents=True, exist_ok=True)

    # Generate a short slug from first paragraph
    first_para = article["text"].split("\n\n")[0][:60]
    slug = re.sub(r"[^\w\s-]", "", first_para.lower())
    slug = re.sub(r"[\s_]+", "_", slug)[:50]

    fpath = source_dir / f"{slug}.json"
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)
    return fpath


# ── Main ──

async def run(source_filter: str | None = None, limit: int | None = None):
    processor = ArticleProcessor()

    # Collect all articles
    all_articles = []
    for folder in sorted(CRAWLED_DIR.iterdir()):
        if not folder.is_dir():
            continue
        if source_filter and source_filter.lower() not in folder.name.lower():
            continue
        for f in sorted(folder.glob("*.txt")):
            parsed = parse_article_file(f)
            if parsed:
                all_articles.append(parsed)

    logger.info(f"Found {len(all_articles)} articles in {CRAWLED_DIR}")

    # Pre-filter
    passed = []
    skipped = []
    for art in all_articles:
        ok, reason = pre_filter(art["source"], art["word_count"], art["title"])
        if ok:
            passed.append(art)
        else:
            skipped.append((art["source"], art["title"], reason))

    logger.info(f"Pre-filter: {len(passed)} passed, {len(skipped)} skipped")
    for s, t, r in skipped:
        logger.info(f"  SKIP [{s}] {t[:50]}: {r}")

    if limit:
        passed = passed[:limit]

    # Process
    results = {"passed": 0, "failed": 0, "skipped": len(skipped)}
    for i, art in enumerate(passed):
        source_label = f"[{i + 1}/{len(passed)}]"
        logger.info(f"{source_label} Processing: {art['source']} - {art['title'][:50]}")
        print(f"\n{'='*60}")
        print(f"  {source_label} {art['source']}")
        print(f"  Title: {art['title'][:60]}")
        print(f"  Source words: {art['word_count']}")
        print(f"{'='*60}")

        result = await processor.process(art["body"], art["source"])

        if result:
            fpath = save_result(result, art["source"])
            results["passed"] += 1
            print(f"  ✓ {result['word_count']}w/{result['paragraph_count']}p")
            print(f"    Short: {result['short_sentences']}, Long: {result['long_sentences']}, Concessive: {result['concessive_count']}")
            print(f"    Saved: {fpath}")
        else:
            results["failed"] += 1
            print(f"  ✗ Failed after all retries")

    # Summary
    print(f"\n{'='*60}")
    print(f"  Done: {results['passed']} passed, {results['failed']} failed, {results['skipped']} skipped")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    source_filter = None
    limit = None

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--source" and i + 1 < len(args):
            source_filter = args[i + 1]
        elif arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    asyncio.run(run(source_filter, limit))
