from datetime import date
import httpx
import json
import random
import logging
import asyncio
import threading
from config import LLM_API_KEY, LLM_MODEL, LLM_API_BASE, DAILY_TOPICS

logger = logging.getLogger(__name__)

_api_limiter = threading.Semaphore(2)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KAOYAN_SOURCES = [
    "The Economist",
    "The Guardian",
    "The Atlantic",
    "The New Yorker",
    "Scientific American",
    "The New York Times",
    "Newsweek",
]

ARTICLE_SYSTEM = """You are an expert writer producing English reading comprehension passages for Chinese graduate school entrance exams (考研英语).

Output ONLY a valid JSON object with EXACTLY this structure. Do NOT include any text before or after the JSON. Do NOT use markdown code blocks.

STRUCTURE:
{
  "title": "English article title (6-12 words)",
  "paragraphs": [
    {
      "sentences": ["sentence 1", "sentence 2", "sentence 3", "sentence 4", "sentence 5"],
    }
  ]
}

HARD REQUIREMENTS:
1. "paragraphs" MUST contain EXACTLY 5 objects.
2. Each paragraph's "sentences" MUST contain EXACTLY 5 strings.
3. Each sentence MUST be 18-28 words long.
4. Total word count across all 5 paragraphs: 500-600 words.

STYLE:
- Formal written English, editorial style of The Economist or The Atlantic.
- Use relative clauses, participial phrases, appositives, and subordinating conjunctions.
- Paragraph 1 introduces the thesis; paragraphs 2-4 develop it with evidence or contrast; paragraph 5 concludes.
- Do NOT use first-person or address the reader directly.

MOST COMMON FAILURE: fewer than 5 paragraphs. You MUST output all 5."""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_json(raw: str) -> str:
    """Strip markdown fences that some models emit despite instructions."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if s.startswith("json"):
        s = s[4:].strip()
    return s

# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

async def _call_llm(user_prompt: str) -> str:
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY is not set. Please check your .env file.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": ARTICLE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.85,
        "response_format": {"type": "json_object"},
    }

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _api_limiter.acquire)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
            try:
                logger.info(f"Calling LLM: {LLM_API_BASE}chat/completions, model={LLM_MODEL}")
                resp = await client.post(LLM_API_BASE + "chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()
                logger.info(f"LLM response length={len(content)}")
                return content
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text[:500]}")
                raise
            except Exception as e:
                logger.error(f"LLM call failed: {e}", exc_info=True)
                raise
    finally:
        _api_limiter.release()

# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

async def _try_generate_article(topic: str, source: str) -> dict:
    user_prompt = (
        f"Topic: {topic}\n"
        f"Simulated source style: {source}\n\n"
        "Produce exactly 5 paragraphs, 5 sentences each, 500-600 words total."
    )

    raw = await _call_llm(user_prompt)
    data = json.loads(_clean_json(raw))

    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response type: {type(data).__name__}")
    if "paragraphs" not in data:
        raise ValueError(f"Missing 'paragraphs'. Keys: {list(data.keys())}")

    paragraphs = []
    total_words = 0

    for i, p in enumerate(data["paragraphs"]):
        sentences = [s.strip() for s in p.get("sentences", []) if s.strip()]
        if len(sentences) < 4:
            raise ValueError(f"Paragraph {i} has only {len(sentences)} sentences (need >= 4)")

        word_count = sum(len(s.split()) for s in sentences)
        total_words += word_count
        logger.info(f"Paragraph {i}: {len(sentences)} sentences, {word_count} words")

        paragraphs.append({
            "index": i,
            "sentences": sentences,
            "translations": [],
        })

    if len(paragraphs) < 4:
        raise ValueError(f"Only {len(paragraphs)} paragraphs returned (need >= 4)")
    if total_words < 420:
        raise ValueError(f"Only {total_words} words (minimum 420)")

    title = data.get("title", "Untitled")
    logger.info(f"Article OK — '{title}', {len(paragraphs)} paragraphs, {total_words} words")

    return {
        "title": title,
        "source": source,
        "category": topic,
        "word_count": total_words,
        "paragraphs": paragraphs,
    }


async def generate_article(d: date, topic: str | None = None) -> dict:
    """Generate a 考研-style reading article with retry logic.

    Args:
        d:     Reference date (unused for topic, kept for API compatibility).
        topic: Override the topic. If None, a random topic is chosen.

    Returns:
        Dict with keys: title, source, category, word_count, paragraphs.
    """
    resolved_topic = topic if topic else random.choice(DAILY_TOPICS)
    source = random.choice(KAOYAN_SOURCES)
    logger.info(f"Generating article — date={d}, topic='{resolved_topic}', source='{source}'")

    last_error = None
    for attempt in range(3):
        try:
            return await _try_generate_article(resolved_topic, source)
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            logger.warning(f"Attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                source = random.choice(KAOYAN_SOURCES)
                logger.info(f"Retrying with source='{source}'")

    logger.error(f"All 3 attempts failed.")
    raise last_error