import logging
from config import ARTICLES_DIR, DATA_DIR
from storage import read_json, write_json
from services.translate_service import translate_sentences
from services.zhenti_service import _translate_question
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

ZHENTI_DIR = DATA_DIR / "zhenti"


def _locate(article_id: str):
    """Return (path, is_zhenti) for the given article id."""
    if article_id.startswith("zhenti_"):
        parts = article_id.split("_")
        year = int(parts[1])
        text = int(parts[2])
        return ZHENTI_DIR / str(year) / f"text_{text}.json", True
    idx = int(article_id.split("_")[1])
    return ARTICLES_DIR / f"article_{idx}.json", False


async def update_article(article_id: str, paragraphs: list, retranslate: bool = False) -> dict:
    """Update the English sentences of an article (外刊 or 考研真题).

    paragraphs: list of {index, sentences}. Translations are kept unless
    retranslate is True, in which case the LLM re-translates every paragraph.
    """
    path, is_zhenti = _locate(article_id)
    article = read_json(str(path), None)
    if not article:
        raise RuntimeError("Article not found")

    new_sentences = {p.index: p.sentences for p in paragraphs}
    for para in article["paragraphs"]:
        if para["index"] in new_sentences:
            para["sentences"] = new_sentences[para["index"]]

    article["word_count"] = sum(
        len(s.split()) for p in article["paragraphs"] for s in p["sentences"]
    )

    if retranslate:
        for para in article["paragraphs"]:
            sentences = para["sentences"]
            if len(sentences) == 1 and "\n" in sentences[0]:
                # 考研真题 question paragraph (stem + options as one unit)
                para["translations"] = [await _translate_question(sentences[0])]
            else:
                para["translations"] = await run_in_threadpool(
                    translate_sentences, sentences
                )
        logger.info(f"Retranslated article {article_id}")

    write_json(str(path), article)

    if not is_zhenti:
        # keep 外刊 index metadata in sync
        index_data = read_json(str(ARTICLES_DIR / "index.json"), {"next": 0, "articles": []})
        for meta in index_data.get("articles", []):
            if meta.get("id") == article_id:
                meta["word_count"] = article["word_count"]
        write_json(str(ARTICLES_DIR / "index.json"), index_data)

    return article
