#!/usr/bin/env python3
"""Test downloading and parsing Atlantic + Wired epubs from GitHub API."""

import requests
import ebooklib
import time
import re
import os
from bs4 import BeautifulSoup
from ebooklib import epub

GITHUB_API = "https://api.github.com/repos/hehonghui/awesome-english-ebooks/contents"
HEADERS = {"Accept": "application/vnd.github.v3.raw"}

EXCLUDED_KEYWORDS = [
    "politics", "sports", "entertainment", "football", "election",
    "trump", "biden", "nfl", "nba", "soccer", "baseball",
    "olympic", "movie", "film", "celebrity", "hollywood",
    "tv show", "netflix", "disney+", "oscar",
]

SOURCES = [
    {"name": "Atlantic", "api_path": "04_atlantic/2026.05.02/Atlantic_2026.05.02.epub"},
    {"name": "Wired",    "api_path": "05_wired/2026.05.02/wired_2026.05.02.epub"},
]

# Items to skip by filename
SKIP_NAMES = {
    "nav.xhtml", "nav.html", "cover.xhtml", "cover.html",
    "book_toc.html", "ad_page.html.html", "toc.html",
    "titlepage.xhtml", "titlepage.html",
    "index_u8.html", "index_u7.html",
}


def download_epub(api_path: str, dest: str) -> tuple[float, int]:
    url = f"{GITHUB_API}/{api_path}"
    start = time.time()
    resp = requests.get(url, headers=HEADERS, stream=True, timeout=120)
    resp.raise_for_status()
    size = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            size += len(chunk)
    elapsed = time.time() - start
    return elapsed, size


def extract_title(soup: BeautifulSoup, filename: str) -> str:
    """Extract article title from html. Try multiple strategies."""
    h1 = soup.find("h1")
    if h1:
        # Skip "| Next | Section menu |" style nav
        text = h1.get_text(strip=True)
        if text and "|" not in text[:20]:
            return text
    h2 = soup.find("h2")
    if h2:
        text = h2.get_text(strip=True)
        if text and "|" not in text[:20]:
            return text
    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.get_text(strip=True)
        if text:
            return text
    return os.path.splitext(os.path.basename(filename))[0]


def extract_body_text(soup: BeautifulSoup) -> str:
    """Extract readable text from article HTML."""
    # Remove unwanted elements
    for tag in soup(
        ["script", "style", "nav", "header", "footer", "aside", "noscript"]
    ):
        tag.decompose()

    # Remove elements with common navigation class/id
    for selector in [
        ".nav", ".navbar", ".menu", ".header", ".footer",
        "#nav", "#navbar", "#menu", "#header", "#footer",
        '[role="navigation"]', '[role="nav"]',
    ]:
        for el in soup.select(selector):
            el.decompose()

    text = soup.get_text(separator=" ", strip=True)
    # Clean up navigation artifacts
    text = re.sub(r"\| Next \|.*?\| Previous \|", "", text)
    text = re.sub(r"\| Next \|", "", text)
    text = re.sub(r"\| Previous \|", "", text)
    text = re.sub(r"\| Section menu \|", "", text)
    text = re.sub(r"\| Main menu \|", "", text)
    text = re.sub(r"Next section.*?(?:Previous section)?", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def has_excluded_keywords(title: str, text_preview: str) -> bool:
    combined = (title + " " + text_preview).lower()
    return any(kw in combined for kw in EXCLUDED_KEYWORDS)


def clean_title(title: str) -> str:
    t = re.sub(r"\s+", " ", title).strip().rstrip("|").strip()
    return t[:120]


def parse_epub(epub_path: str) -> list[dict]:
    """Parse epub and return articles (type 0 or 9, .html, not nav/cover)."""
    book = epub.read_epub(epub_path)
    articles = []

    for item in book.get_items():
        item_type = item.get_type()
        item_name = item.get_name()
        basename = os.path.basename(item_name).lower()

        # Accept both type 0 (Economist) and type 9 ITEM_DOCUMENT (Atlantic/Wired)
        if item_type not in (0, 9):
            continue
        if not item_name.lower().endswith(".html"):
            continue
        if basename in SKIP_NAMES:
            continue

        content = item.get_content()
        soup = BeautifulSoup(content, "lxml")
        text = extract_body_text(soup)
        word_count = len(text.split())

        if word_count < 80:
            continue

        title = clean_title(extract_title(soup, item_name))

        # Skip index/section pages (have many | separators, short text)
        if "|" in title and "|" in text[:300]:
            continue
        if title.lower().startswith("feed_"):
            continue

        articles.append({
            "title": title,
            "word_count": word_count,
            "text_preview": text[:300],
        })

    return articles


def run():
    for src in SOURCES:
        name = src["name"]
        api_path = src["api_path"]
        dest = f"/tmp/{name.lower()}_latest.epub"

        print(f"\n{'='*65}")
        print(f"  {name}")
        print(f"{'='*65}")

        # 1. Download
        print(f"\n  [1/3] Downloading ...")
        try:
            elapsed, size = download_epub(api_path, dest)
            size_mb = size / 1024 / 1024
            print(f"        ✓ {elapsed:.1f}s, {size_mb:.1f} MB ({size:,} bytes)")
        except Exception as e:
            print(f"        ❌ Download FAILED: {e}")
            continue

        # 2. Parse
        print(f"  [2/3] Parsing epub ...")
        try:
            articles = parse_epub(dest)
        except Exception as e:
            print(f"        ❌ Parse FAILED: {e}")
            continue

        total = len(articles)
        in_range = [a for a in articles if 500 <= a["word_count"] <= 900]
        filtered = [
            a
            for a in in_range
            if not has_excluded_keywords(a["title"], a["text_preview"])
        ]

        print(f"        ✓ Total articles: {total}")
        print(f"        ✓ 500-900 words: {len(in_range)}")
        print(f"        ✓ After keyword exclusion: {len(filtered)}")

        # 3. Show top articles
        print(f"  [3/3] Qualified article previews:")
        if filtered:
            shown = sorted(filtered, key=lambda x: x["word_count"])[:5]
            for i, a in enumerate(shown, 1):
                print(f"        {i}. \"{a['title']}\" ({a['word_count']} words)")
        else:
            shown = sorted(in_range, key=lambda x: x["word_count"])[:5]
            for i, a in enumerate(shown, 1):
                reason = (
                    "EXCLUDED"
                    if has_excluded_keywords(a["title"], a["text_preview"])
                    else "OK"
                )
                print(f"        {i}. \"{a['title']}\" ({a['word_count']} words) [{reason}]")

        # Cleanup
        os.remove(dest)
        print(f"        🗑  Temp file removed")

    print(f"\n{'='*65}")
    print(f"  Done.")
    print(f"{'='*65}")


if __name__ == "__main__":
    run()
