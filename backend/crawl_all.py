#!/usr/bin/env python3
"""Crawl articles from all available sources and save to crawled_articles/."""

import requests, ebooklib, feedparser, re, os, time, json
from bs4 import BeautifulSoup
from ebooklib import epub
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "crawled_articles"
MAX_PER_SOURCE = 5
EXCLUDED_KEYWORDS = [
    "politics", "sports", "entertainment", "football", "election",
    "trump", "biden", "nfl", "nba", "soccer", "baseball",
    "olympic", "movie", "film", "celebrity", "hollywood",
    "tv show", "netflix", "disney", "oscar", "kardashian",
    "fashion week", "reality tv", "box office",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT = 20

def slugify(title):
    s = re.sub(r"[^\w\s-]", "", title.lower())
    s = re.sub(r"[\s_]+", "_", s)
    return s[:60]

def has_excluded(title, text_preview):
    combined = (title + " " + text_preview).lower()
    for kw in EXCLUDED_KEYWORDS:
        if kw in combined:
            return True
    return False

def save_article(folder, title, source, url, text, word_count, extra_meta=None):
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{slugify(title)}.txt"
    fpath = folder / fname
    if fpath.exists():
        fpath = folder / f"{slugify(title)}_{int(time.time())}.txt"
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(f"Source: {source}\n")
        f.write(f"Title: {title}\n")
        f.write(f"URL: {url}\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Word Count: {word_count}\n")
        if extra_meta:
            for k, v in extra_meta.items():
                f.write(f"{k}: {v}\n")
        f.write("=" * 60 + "\n\n")
        f.write(text)
    return fpath

# ──────────────────────────────────────────────
# RSS sources
# ──────────────────────────────────────────────

RSS_SOURCES = {
    "Scientific_American": "https://www.scientificamerican.com/platform/syndication/rss/",
    "Nautilus": "https://nautil.us/feed/",
    "Nature": "https://www.nature.com/nature.rss",
    "ScienceMag": "https://www.science.org/rss/news_current.xml",
}

def crawl_rss(name, feed_url):
    folder = OUTPUT_DIR / name
    print(f"\n  [{name}] RSS: {feed_url}")
    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        print(f"    ❌ Feed failed: {e}")
        return
    if not feed.entries:
        print(f"    ❌ No entries")
        return

    saved = 0
    for entry in feed.entries:
        if saved >= MAX_PER_SOURCE:
            break

        title = entry.get("title", "Untitled")
        link = entry.get("link", "")

        # Get text
        html = None
        try:
            r = requests.get(link, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                html = r.text
        except Exception:
            pass

        if html:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
        else:
            text = (entry.get("summary") or entry.get("description") or "")

        wc = len(text.split())
        if wc < 100:
            continue
        if has_excluded(title, text[:500]):
            print(f"    ⛔ Excluded: {title} ({wc}w)")
            continue

        meta = {"Category": entry.get("tags", [{}])[0].get("term", "") if entry.get("tags") else ""}
        fpath = save_article(folder, title, name, link, text, wc, meta)
        print(f"    ✓ {wc:>5}w  {title[:50]}")
        saved += 1
        time.sleep(0.3)

    print(f"    → {saved} articles saved")

# ──────────────────────────────────────────────
# Guardian API
# ──────────────────────────────────────────────

def crawl_guardian():
    name = "The_Guardian"
    folder = OUTPUT_DIR / name
    print(f"\n  [{name}] Guardian API")

    sections = "technology|science|books|environment|global-development|business|lifeandstyle"
    url = "https://content.guardianapis.com/search"
    params = {
        "section": sections,
        "page-size": MAX_PER_SOURCE + 5,
        "show-fields": "bodyText,headline,wordCount,shortUrl",
        "show-tags": "all",
        "order-by": "newest",
        "api-key": "test",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
    except Exception as e:
        print(f"    ❌ API failed: {e}")
        return

    if data["response"]["status"] != "ok":
        print(f"    ❌ API error: {data}")
        return

    saved = 0
    for article in data["response"]["results"]:
        if saved >= MAX_PER_SOURCE:
            break

        title = article.get("webTitle", "Untitled")
        section = article.get("sectionName", "")
        fields = article.get("fields", {})
        body = fields.get("bodyText", "")
        wc = len(body.split())
        link = article.get("webUrl", "")

        if has_excluded(title, body[:500]):
            print(f"    ⛔ Excluded: {title} ({wc}w)")
            continue
        if wc < 100:
            continue

        meta = {"Section": section}
        fpath = save_article(folder, title, name, link, body, wc, meta)
        print(f"    ✓ {wc:>5}w  [{section:15s}] {title[:50]}")
        saved += 1
        time.sleep(0.3)

    print(f"    → {saved} articles saved")

# ──────────────────────────────────────────────
# Epub sources (GitHub API)
# ──────────────────────────────────────────────

EPUB_SOURCES = [
    {
        "name": "The_Economist",
        "api_path": "01_economist/te_2026.05.09/TheEconomist.2026.05.09.epub",
    },
    {
        "name": "The_Atlantic",
        "api_path": "04_atlantic/2026.05.02/Atlantic_2026.05.02.epub",
    },
    {
        "name": "Wired",
        "api_path": "05_wired/2026.05.02/wired_2026.05.02.epub",
    },
    {
        "name": "The_New_Yorker",
        "api_path": "02_new_yorker/2026.05.11/new_yorker.2026.05.11.epub",
    },
]

GITHUB_API = "https://api.github.com/repos/hehonghui/awesome-english-ebooks/contents"
GH_HEADERS = {"Accept": "application/vnd.github.v3.raw"}

SKIP_NAMES = {
    "nav.xhtml", "nav.html", "cover.xhtml", "cover.html",
    "book_toc.html", "ad_page.html.html", "toc.html",
    "titlepage.xhtml", "titlepage.html",
    "index_u8.html", "index_u7.html",
}

def extract_epub_title(soup, filename):
    for tag in ["h1", "h2"]:
        el = soup.find(tag)
        if el:
            t = el.get_text(strip=True)
            if t and "|" not in t[:20]:
                return t
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)
    return os.path.splitext(os.path.basename(filename))[0]

def extract_epub_text(soup):
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        tag.decompose()
    for sel in [".nav", ".navbar", ".menu", ".header", ".footer", '[role="navigation"]']:
        for el in soup.select(sel):
            el.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\| Next \|.*?\| Previous \|", "", text)
    text = re.sub(r"\| Next \||\| Previous \||\| Section menu \||\| Main menu \|", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def crawl_epub(src):
    name = src["name"]
    api_path = src["api_path"]
    folder = OUTPUT_DIR / name
    dest = f"/tmp/crawl_{name.lower()}.epub"

    print(f"\n  [{name}] GitHub API → epub: {api_path}")

    # Download
    url = f"{GITHUB_API}/{api_path}"
    try:
        resp = requests.get(url, headers=GH_HEADERS, stream=True, timeout=120)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
        print(f"    ✓ Downloaded ({os.path.getsize(dest)/1024/1024:.1f} MB)")
    except Exception as e:
        print(f"    ❌ Download failed: {e}")
        return

    # Parse
    try:
        book = epub.read_epub(dest)
    except Exception as e:
        print(f"    ❌ Parse failed: {e}")
        return

    articles = []
    for item in book.get_items():
        itype = item.get_type()
        iname = item.get_name()
        basename = os.path.basename(iname).lower()

        if itype not in (0, 9):
            continue
        if not iname.lower().endswith(".html"):
            continue
        if basename in SKIP_NAMES:
            continue

        content = item.get_content()
        soup = BeautifulSoup(content, "lxml")
        text = extract_epub_text(soup)
        wc = len(text.split())
        if wc < 100:
            continue

        title = extract_epub_title(soup, iname)
        title = re.sub(r"\s+", " ", title).strip()[:100]
        if not title or title.lower().startswith("feed_"):
            continue
        if "|" in title and "|" in text[:300]:
            continue

        articles.append({"title": title, "text": text, "word_count": wc})

    os.remove(dest)
    print(f"    ✓ Parsed: {len(articles)} total articles")

    # Filter, sort, save
    articles.sort(key=lambda a: a["word_count"])
    saved = 0
    for a in articles:
        if saved >= MAX_PER_SOURCE:
            break
        if has_excluded(a["title"], a["text"][:500]):
            continue
        fpath = save_article(folder, a["title"], name, api_path, a["text"], a["word_count"])
        print(f"    ✓ {a['word_count']:>5}w  {a['title'][:50]}")
        saved += 1

    print(f"    → {saved} articles saved")

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  Crawling all available sources")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 65)

    # RSS sources
    for name, feed_url in RSS_SOURCES.items():
        crawl_rss(name, feed_url)

    # Guardian API
    crawl_guardian()

    # Epub sources
    for src in EPUB_SOURCES:
        crawl_epub(src)

    print(f"\n{'=' * 65}")
    print("  Done. Files saved to:", OUTPUT_DIR)
    print("=" * 65)

if __name__ == "__main__":
    main()
