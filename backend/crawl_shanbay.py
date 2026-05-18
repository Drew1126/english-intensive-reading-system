import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "crawled_articles", "Shanbay")
os.makedirs(DATA_DIR, exist_ok=True)

BASE_URL = "https://apiv3.shanbay.com/news"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def fetch_json(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def list_articles(ipp=83, page=1):
    url = f"{BASE_URL}/retrieve/articles?ipp={ipp}&page={page}"
    return fetch_json(url)


def get_article(slug):
    url = f"{BASE_URL}/articles/{slug}?source=1"
    return fetch_json(url)


def parse_content(content_xml):
    if not content_xml or content_xml.strip() == "":
        return []
    paragraphs = []
    root = ET.fromstring(content_xml)
    for para in root.findall(".//para"):
        sents = para.findall(".//sent")
        if not sents:
            continue
        para_texts = []
        for s in sents:
            text = "".join(s.itertext()).strip()
            if text:
                para_texts.append(text)
        if para_texts:
            paragraphs.append(para_texts)
    return paragraphs


def slugify(title):
    s = re.sub(r"[^\w\s-]", "", title.lower())
    s = re.sub(r"[\s_]+", "_", s)
    return s[:60]


def clean_article_text(paragraphs):
    lines = []
    for para in paragraphs:
        lines.append(" ".join(para))
    return "\n\n".join(lines)


def main():
    print("Fetching article list...")
    data = list_articles()
    articles = data.get("objects", [])
    print(f"Total articles: {len(articles)}")

    level_order = {"六级/考研": 1, "四级": 2, "高考": 3, "雅思/托福/专四": 4}
    articles.sort(key=lambda a: level_order.get(a.get("exam_level", {}).get("name", ""), 99))

    results = []
    for i, art in enumerate(articles):
        slug = art.get("slug") or art.get("id", "")
        title = art.get("title_en", "unknown")
        src = art.get("source", {}).get("name_en", "")
        print(f"\n[{i+1}/{len(articles)}] {title} ({src})")

        try:
            detail = get_article(slug)
            content_xml = detail.get("content", "")
            paras = parse_content(content_xml)

            if not paras:
                print("  -> no content")
                continue

            clean_text = clean_article_text(paras)
            filename = f"{slugify(title)}.txt"
            filepath = os.path.join(DATA_DIR, filename)

            word_count = len(clean_text.split())
            meta = {
                "title": title,
                "source": src,
                "original_url": detail.get("original_url", ""),
                "word_count": word_count,
                "paragraphs": len(paras),
                "sentences": sum(len(p) for p in paras),
                "exam_level": detail.get("exam_level", {}).get("name", ""),
                "grade": detail.get("grade", ""),
                "slug": slug,
            }

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(clean_text)

            results.append(meta)
            print(f"  -> saved ({word_count} words, {len(paras)} paras)")

            time.sleep(0.3)
        except Exception as e:
            print(f"  -> error: {e}")
            time.sleep(1)

    meta_path = os.path.join(DATA_DIR, "articles_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {len(results)} articles saved to {DATA_DIR}")


if __name__ == "__main__":
    main()
