#!/usr/bin/env python3
"""Test RSS crawling for 5 English publications.

Usage:
    python3 backend/test_crawler.py

Output: crawled_articles/<source>/<index>_<title_slug>.txt
"""

import feedparser
import requests
import re
import os
import sys
from bs4 import BeautifulSoup
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "crawled_articles")

SOURCES = {
    "The Economist": "https://www.economist.com/rss",
    "The Atlantic": "https://www.theatlantic.com/feed/all/",
    "Scientific American": "https://www.scientificamerican.com/platform/syndication/rss/",
    "Aeon": "https://aeon.co/feed.rss",
    "Nautilus": "https://nautil.us/feed/",
}

EXCLUDED_CATEGORIES = {"politics", "sports", "entertainment"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TIMEOUT = 15


def slugify(title):
    s = re.sub(r"[^\w\s-]", "", title.lower())
    s = re.sub(r"[\s_]+", "_", s)
    return s[:60]


def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "aside"]):
        t.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return text


def count_words(text):
    return len(text.split())


def has_excluded_category(tags):
    for tag in tags:
        label = tag.get("term", "").lower() if hasattr(tag, "get") else str(tag).lower()
        if label in EXCLUDED_CATEGORIES:
            return True, label
    return False, None


def fetch_article_content(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        return None


def slug_from_url(url):
    m = re.search(r"/([^/]+?)(?:\.html|/)?$", url)
    return m.group(1) if m else "article"


def run():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for name, feed_url in SOURCES.items():
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"  Feed: {feed_url}")
        print(f"{'='*60}")

        folder = os.path.join(OUTPUT_DIR, name.replace(" ", "_"))
        os.makedirs(folder, exist_ok=True)

        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"  ❌ Feed fetch FAILED: {e}")
            continue

        if feed.bozo and not feed.entries:
            print(f"  ❌ Feed parse FAILED: {feed.bozo_exception}")
            continue

        print(f"  ✓ Feed OK — {len(feed.entries)} items")

        saved = 0
        for i, entry in enumerate(feed.entries):
            if saved >= 5:
                break

            title = entry.get("title", "Untitled")
            link = entry.get("link", "")
            tags = entry.get("tags", [])

            # Check category exclusion
            excluded, ex_label = has_excluded_category(tags)
            cat_labels = [t.get("term", "?") if hasattr(t, "get") else str(t) for t in tags]
            cat_str = ", ".join(cat_labels[:5]) if cat_labels else "(none)"

            print(f"\n  [{i+1}] {title}")
            print(f"       Link: {link}")
            print(f"       Tags: {cat_str}")
            if excluded:
                print(f"       ⛔ Excluded: {ex_label}")
                continue

            # Fetch full article
            html = fetch_article_content(link)
            if not html:
                print(f"       ⚠  Content fetch FAILED")
                # Save at least the RSS excerpt
                text = (entry.get("summary") or entry.get("description") or "")
                wc = count_words(text)
                print(f"       Words: {wc}  (RSS excerpt only)")
                continue

            text = extract_text(html)
            wc = count_words(text)

            status = ""
            if wc < 500:
                status = f"⛔ too short ({wc})"
            elif wc > 900:
                status = f"⛔ too long ({wc})"
            else:
                status = f"✓ {wc} words"

            print(f"       Words: {status}")

            # Save to file
            fname = f"{i+1:02d}_{slugify(title)}.txt"
            fpath = os.path.join(folder, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(f"Source: {name}\n")
                f.write(f"Title: {title}\n")
                f.write(f"URL: {link}\n")
                f.write(f"Date: {datetime.now().isoformat()}\n")
                f.write(f"Word Count: {wc}\n")
                f.write(f"Categories: {cat_str}\n")
                f.write(f"{'='*60}\n\n")
                f.write(text)

            saved += 1
            print(f"       💾 Saved: {fname}")

        if saved == 0:
            print(f"  No articles saved (all excluded or failed)")

    print(f"\n{'='*60}")
    print(f"  Done. Files saved to: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    run()
