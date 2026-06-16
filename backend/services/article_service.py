import re
import asyncio
import threading
import logging
from datetime import date

from storage.article_store import get_article, save_article, cleanup_old_articles
from storage.session_store import load_session, create_session, advance_session
from agents.article_processor import ArticleProcessor
from services.translate_service import translate_sentences
from services.article_source_manager import get_next_source
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


_ABBREVIATIONS = r"\b(?:U\.S|U\.K|Mr|Mrs|Ms|Dr|Prof|St|Ave|Blvd|Dept|vs|inc|ltd|co|etc|e\.g|i\.e|al|fig|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec|approx|dept|est|govt|mtn)"

def _split_sentences(text: str) -> list[str]:
    # Protect abbreviations by replacing their periods with a placeholder
    protected = re.sub(_ABBREVIATIONS, lambda m: m.group(0).replace(".,", "\x00,").replace(".", "\x00"), text)
    raw = re.split(r"(?<=[.?!])\s+(?=[A-Z\"'(])", protected)
    return [s.strip().replace("\x00", ".") for s in raw if s.strip()]


def _parse_processor_output(text: str, title: str, source_name: str) -> dict:
    raw_paras = re.split(r"\n\s*\n", text.strip())
    paragraphs = []
    for i, block in enumerate(raw_paras):
        block = block.strip()
        if not block or len(block.split()) < 10:
            continue
        sentences = _split_sentences(block)
        if not sentences:
            continue
        paragraphs.append({
            "index": i,
            "sentences": sentences,
            "translations": [],
        })

    wc = sum(len(s.split()) for p in paragraphs for s in p["sentences"])

    return {
        "title": title,
        "source": source_name,
        "category": "",
        "word_count": wc,
        "paragraphs": paragraphs,
    }


async def _translate_all_paragraphs(article: dict) -> dict:
    for i, para in enumerate(article.get("paragraphs", [])):
        sentences = para.get("sentences", [])
        if not sentences:
            para["translations"] = []
            continue
        try:
            translations = await run_in_threadpool(translate_sentences, sentences)
            if len(translations) != len(sentences):
                logger.warning(f"Para {i}: translations {len(translations)} != sentences {len(sentences)}, fixing")
                translations = (translations + [""] * len(sentences))[:len(sentences)]
            para["translations"] = translations
            logger.info(f"Translated paragraph {i} of '{article.get('title')}'")
        except Exception as e:
            logger.error(f"Failed to translate paragraph {i}: {e}")
            para["translations"] = [""] * len(sentences)
    return article


async def _generate_and_save(slot: int) -> dict:
    """Try source articles until one succeeds. No LLM fallback."""
    today = date.today()
    max_attempts = 10

    for attempt in range(max_attempts):
        try:
            source = get_next_source()
        except Exception as e:
            logger.error(f"get_next_source failed (attempt {attempt + 1}): {e}")
            await asyncio.sleep(1)
            continue
        if not source:
            raise RuntimeError(f"No source article available after {attempt} attempts")

        logger.info(f"Generating from source: [{source['source']}] {source['title'][:60]}")
        processor = ArticleProcessor()
        try:
            result = await asyncio.wait_for(
                processor.process(source["body"], source["source"]),
                timeout=300.0
            )
        except Exception as e:
            logger.error(f"Processor pipeline failed (attempt {attempt + 1}): {e}")
            result = None

        if result:
            title = source.get("title") or source["title"]
            article = _parse_processor_output(result["text"], title, result["source"])
            article["id"] = f"article_{slot}"
            article["date"] = today.isoformat()
            article["article_index"] = slot

            article = await _translate_all_paragraphs(article)

            await run_in_threadpool(save_article, slot, article)
            logger.info(f"Source article saved: slot={slot}, '{article['title'][:60]}', {article['word_count']}w")
            return article

        logger.warning(f"Processor pipeline returned no result (attempt {attempt + 1}), trying next source")

    raise RuntimeError(f"Failed to generate article for slot {slot} after {max_attempts} source attempts")


def _start_bg_gen(slot: int) -> None:
    def _run():
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_generate_and_save(slot))
        except Exception as e:
            logger.error(f"Background generation failed for slot {slot}: {e}")
        finally:
            loop.close()
    threading.Thread(target=_run, daemon=True).start()


def init_session_on_startup() -> None:
    cleanup_old_articles()

    session = load_session()
    if session:
        c = get_article(session["current_slot"])
        p = get_article(session["prefetch_slot"])
        if not c:
            _start_bg_gen(session["current_slot"])
        if not p:
            _start_bg_gen(session["prefetch_slot"])
        if c and p:
            logger.info(f"Session OK: current=slot{session['current_slot']}, prefetch=slot{session['prefetch_slot']}")
        return

    logger.info("No session on startup, generating initial articles")
    def _run():
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_generate_and_save(0))
            loop.run_until_complete(_generate_and_save(1))
            create_session(0, 1)
            logger.info("Session created on startup")
        except Exception as e:
            logger.error(f"Failed to init session on startup: {e}")
        finally:
            loop.close()
    threading.Thread(target=_run, daemon=True).start()


async def get_or_create_current() -> dict:
    session = load_session()
    if session:
        for _ in range(30):
            article = await run_in_threadpool(get_article, session["current_slot"])
            if article:
                prefetch = get_article(session["prefetch_slot"])
                if not prefetch:
                    asyncio.create_task(_generate_and_save(session["prefetch_slot"]))
                return article
            await asyncio.sleep(2)
        logger.warning(f"Current article slot{session['current_slot']} not ready after polling, generating synchronously")
        article = await _generate_and_save(session["current_slot"])
        return article

    logger.warning("No session found on first request, generating synchronously")
    article = await _generate_and_save(0)
    create_session(0, 1)
    asyncio.create_task(_generate_and_save(1))
    return article


async def advance_to_next() -> dict:
    session = advance_session()
    if not session:
        raise RuntimeError("No session — cannot advance")

    current = await _generate_and_save(session["current_slot"])

    asyncio.create_task(_generate_and_save(session["prefetch_slot"]))

    return {"article": current}
