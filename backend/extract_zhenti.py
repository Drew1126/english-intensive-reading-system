#!/usr/bin/env python3
"""Extract 考研英语一 reading passages from LaTeX source and save as articles."""

import re
import os
from pathlib import Path

REPO_DIR = Path("/tmp/EN201-kaoyan/1")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "zhenti_articles"

# Exclude cloze (\cloze) and translation (\transnum) sections
SKIP_BEFORE = ["\\section{Writing}", "\\section{Writing Part"]
STOP_AT_ENUMS = ["\\begin{enumerate}", "\\begin{listmatch}", "\\begin{listwrite}"]


def clean_text(text: str) -> str:
    """Clean LaTeX text: remove commands, normalize whitespace."""
    # Remove \cloze{...} and \cloze
    text = re.sub(r"\\cloze(?:\{[^}]*\})?", "______", text)
    # Remove \uline{...} but keep content
    text = re.sub(r"\\uline\s*\{([^}]*)\}", r"\1", text)
    # Remove \transnum
    text = re.sub(r"\\transnum", "", text)
    # Remove \TiGanSpace
    text = re.sub(r"\\TiGanSpace", "", text)
    # Remove \textbf{} but keep content
    text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
    # Remove \emph{} but keep content
    text = re.sub(r"\\emph\{([^}]*)\}", r"\1", text)
    # Remove \textit{} but keep content
    text = re.sub(r"\\textit\{([^}]*)\}", r"\1", text)
    # Remove \newpage, \vfil, \vspace, \phantom
    text = re.sub(r"\\newpage", "\n", text)
    text = re.sub(r"\\vfil", "", text)
    text = re.sub(r"\\vspace\{[^}]*\}", "", text)
    text = re.sub(r"\\phantom\{[^}]*\}", "", text)
    # Remove linefill
    text = re.sub(r"\\linefill", "", text)
    # Remove standalone braces and LaTeX commands
    text = re.sub(r"\\[a-zA-Z]+(?:\{[^}]*\})?", "", text)
    # Remove % comments
    text = re.sub(r"(?<!\\)%.*", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_texts_from_tex(content: str) -> list[dict]:
    """Extract reading passages from a LaTeX exam file."""
    articles = []

    # Cut off anything after Writing section
    for skip in SKIP_BEFORE:
        pos = content.find(skip)
        if pos != -1:
            content = content[:pos]

    # Pattern 1: modern format \subsection{Text N} (2002+)
    pattern1 = re.compile(
        r"\\subsection\{Text (\d+)\}\s*\n(.*?)(?=\\subsection\{Text|\\section|\\newpage)",
        re.DOTALL,
    )

    # Pattern 2: old format \section*{Passage N} (1994-2001)
    pattern2 = re.compile(
        r"\\(?:section|subsection)\*?\{Passage (\d+)\}(.*?)(?=\\section|\\subsection|\\newpage)",
        re.DOTALL,
    )

    matches = list(pattern1.finditer(content))
    if not matches:
        matches = list(pattern2.finditer(content))

    for match in matches:
        text_num = match.group(1)
        body = match.group(2).strip()

        # Stop at the first enumerate/listmatch (questions)
        for stop in STOP_AT_ENUMS:
            pos = body.find(stop)
            if pos != -1:
                body = body[:pos]

        # Remove leading \n and extra whitespace
        body = body.strip()
        if not body:
            continue

        # Clean LaTeX commands
        cleaned = clean_text(body)
        if len(cleaned.split()) < 50:
            continue

        # Split into sentences (by period + space or newline)
        # First split by double newline to get paragraphs
        raw_paragraphs = re.split(r"\n\s*\n", body)
        paragraphs = []
        for para in raw_paragraphs:
            para = clean_text(para)
            if not para or len(para.split()) < 10:
                continue
            # Split into sentences
            sentences = re.split(r"(?<=[.?!])\s+", para)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip().split()) > 3]
            if sentences:
                paragraphs.append({
                    "index": len(paragraphs),
                    "sentences": sentences,
                    "translations": [],
                })

        if paragraphs:
            total_words = sum(len(s.split()) for p in paragraphs for s in p["sentences"])
            articles.append({
                "title": f"考研英语一 阅读 Text {text_num}",
                "source": "考研英语一真题",
                "word_count": total_words,
                "paragraphs": paragraphs,
            })

    return articles


def extract_part_b(content: str) -> list[dict]:
    """Extract Part B (matching/排序) paragraphs."""
    articles = []
    
    # Find Part B section
    pb_match = re.search(r"\\textbf\{Part B\}.*?\\begin\{listmatch\}(.*?)\\end\{listmatch\}", content, re.DOTALL)
    if not pb_match:
        return articles
    
    body = pb_match.group(1)
    # Split by \item
    items = re.split(r"\\item\s*", body)
    
    paragraphs = []
    for i, item in enumerate(items):
        item = item.strip()
        if not item:
            continue
        cleaned = clean_text(item)
        if len(cleaned.split()) < 20:
            continue
        sentences = re.split(r"(?<=[.?!])\s+", cleaned)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip().split()) > 3]
        if sentences:
            paragraphs.append({
                "index": len(paragraphs),
                "sentences": sentences,
                "translations": [],
            })
    
    if paragraphs:
        total_words = sum(len(s.split()) for p in paragraphs for s in p["sentences"])
        articles.append({
            "title": "考研英语一 阅读 Part B (排序)",
            "source": "考研英语一真题",
            "word_count": total_words,
            "paragraphs": paragraphs,
        })
    
    return articles


def main():
    tex_files = sorted(REPO_DIR.glob("*.tex"))
    print(f"Found {len(tex_files)} LaTeX files")

    total_articles = 0
    for tex_path in tex_files:
        year_match = re.search(r"(\d{4})年", tex_path.stem)
        year = year_match.group(1) if year_match else "unknown"

        with open(tex_path, "r", encoding="utf-8") as f:
            content = f.read()

        year_dir = OUTPUT_DIR / year
        articles = extract_texts_from_tex(content)
        articles.extend(extract_part_b(content))

        for art in articles:
            title_slug = re.sub(r"[^\w]", "_", art["title"]).strip("_").lower()
            fname = f"{year}_{title_slug}.json"
            fpath = year_dir / fname

            year_dir.mkdir(parents=True, exist_ok=True)
            
            import json
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(art, f, ensure_ascii=False, indent=2)
            
            total_articles += 1
            print(f"  {year}  {art['title']:40s}  {art['word_count']:>4}w  -> {fpath.name}")

    print(f"\nTotal: {total_articles} articles extracted")


if __name__ == "__main__":
    main()
