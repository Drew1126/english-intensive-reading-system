import asyncio
import httpx
import json
import re
import logging
import threading
from pathlib import Path
from typing import Optional

from config import LLM_API_KEY, LLM_MODEL, LLM_API_BASE
from vocab_checker import VocabChecker

logger = logging.getLogger(__name__)

_api_limiter = threading.Semaphore(2)

# ══════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCES_PRIORITY = {
    "The_Economist": 1,
    "The_Guardian": 1,
    "Scientific_American": 1,
    "The_Atlantic": 2,
    "Wired": 2,
    "ScienceMag": 3,
    "Nature": 3,
    "Nautilus": 3,
    "The_New_Yorker": 3,
}

# Acceptable article-body word counts (source article length)
SOURCE_WC_MIN = 350
SOURCE_WC_MAX = 5000

# Target rewrite standards
TARGET_WC_MIN = 340
TARGET_WC_MAX = 550
TARGET_PARAS_MIN = 3
TARGET_PARAS_MAX = 5
TARGET_CONCESSIVE_MIN = 1
TARGET_OOV_RATIO_MAX = 0.05
TARGET_SHORT_SENT_MIN = 0       # 6–15 word sentences (optional, encouraged in prompt)
TARGET_LONG_SENT_MIN = 1        # 35–55 word sentences

# Retry limits
MAX_REPLACE_ATTEMPTS = 2
MAX_REWRITE_ATTEMPTS = 3

CONCESSIVE_MARKERS = [
    "while", "although", "even though", "though", "admittedly",
    "despite", "in spite of", "however", "nevertheless",
    "nonetheless", "notwithstanding", "granted", "albeit", "yet",
]

SYSTEM_PROMPT = """You are an expert editor specializing in rewriting English journal articles into academic reading passages for the Chinese graduate entrance exam (考研英语一 / 英语二).

Your rewrites must match the authentic style, sentence complexity, and logical structure of real 考研 reading passages. You do NOT generate questions. You output only the rewritten passage."""

USER_PROMPT_TEMPLATE = """Rewrite the following journal article excerpt into a 考研英语一 reading comprehension passage. Follow ALL rules below strictly.

## Format Rules
- Total length: 340–550 words
- Paragraphs: 3–5, each 80–120 words
- Output: English body text only — no title, no author, no source, no Chinese, no extra commentary

## Content Rules
1. DELETE: lengthy background setup, excessive examples, specific names of minor figures, institutions, and closing policy recommendations or future outlooks
2. PRESERVE: the core argument, key evidence, and the author's original stance — do not alter the viewpoint
3. REWRITE all sentences in your own words — do not copy phrases verbatim from the source
4. DO NOT fabricate facts, data, or claims not present in the source

## Sentence Rhythm Rules
考研 passages use deliberate sentence rhythm — short sentences create emphasis or transition; long sentences carry argument and evidence. Do NOT write all sentences at the same length.

Follow this rhythm pattern within each paragraph:

  [SHORT: 6–15 words] → [LONG: 35–55 words] → [MEDIUM: 18–30 words]

- Short sentences (6–15 words): use 2–4 per passage. Role: open a paragraph, mark a turn, or land a conclusion.
- Long sentences (35–55 words): use 3–5 per passage. Role: carry the core argument with subordinate clauses, relative clauses, or participial phrases embedded. These are the primary reading difficulty points.
- Medium sentences (18–30 words): the default; fill the rest. Role: provide supporting detail, connect ideas.

HARD LIMIT: No more than 2 consecutive sentences of the same length tier.

## Style Rules
1. Use formal academic English — no colloquialisms, no simplified "plain English" style
2. Include at least one concessive structure (e.g., "While researchers agree that..., the evidence suggests...")
3. Paragraph structure: vary between these logical patterns — do NOT force every passage into the same mold:
   - Phenomenon → Cause → Author evaluation
   - Claim → Counterargument → Rebuttal
   - Problem → Research findings → Broader implications
   - Contrast between two perspectives → Author's positioning

## Vocabulary Rules
Use only common academic English vocabulary. Avoid rare technical jargon, low-frequency academic terms, and discipline-specific terminology. When a concept requires a specialized term, rephrase it using accessible vocabulary.

## Source Article
{{article_text}}"""

OOY_REPLACE_PROMPT = """The following words in the passage are outside the allowed vocabulary list. Replace each one with a simpler, more common synonym that preserves the meaning. Do not change any other part of the passage.

Words to replace: {{oov_list}}

Passage:
{{article_text}}

Output the revised passage only."""

FORMAT_FIX_PROMPT = """The passage below does not meet the required format specifications. Fix ALL of the following issues precisely:

{{format_errors}}

Requirements (current value → target):
- Total length: 340–550 words (count the words carefully)
- Paragraphs: 3–5
- Include 0–4 short sentences (6–15 words) and 1–5 long sentences (35–55 words)
- Vary sentence length rhythm — no uniform-length sentences
- Include at least one concessive structure (while, although, etc.)
- Output: English body text only — no title, no author, no source

Passage:
{{article_text}}

Output the revised passage only. Do NOT include any title."""

# ══════════════════════════════════════════════════════════════
# Tokenization & helpers
# ══════════════════════════════════════════════════════════════

def tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text)


def count_words(text: str) -> int:
    return len(tokenize(text))


def split_paragraphs(text: str) -> list[str]:
    raw = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in raw if p.strip() and len(tokenize(p)) >= 10]


_ABBREVIATIONS = r"\b(?:U\.S|U\.K|Mr|Mrs|Ms|Dr|Prof|St|Ave|Blvd|Dept|vs|inc|ltd|co|etc|e\.g|i\.e|al|fig|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec|approx|dept|est|govt|mtn)"

def split_sentences(text: str) -> list[str]:
    protected = re.sub(_ABBREVIATIONS, lambda m: m.group(0).replace(".", "\x00"), text)
    raw = re.split(r"(?<=[.?!])\s+(?=[A-Z\"'(])", protected)
    return [s.strip().replace("\x00", ".") for s in raw if s.strip()]


def detect_concessive(text: str) -> list[str]:
    found = []
    lower = text.lower()
    for marker in CONCESSIVE_MARKERS:
        if marker in lower:
            found.append(marker)
    return found


def validate_format(text: str) -> dict:
    wc = count_words(text)
    paragraphs = split_paragraphs(text)
    sentences = split_sentences(text)

    para_count = len(paragraphs)
    concessive = detect_concessive(text)

    short_sents = [s for s in sentences if 6 <= len(tokenize(s)) <= 15]
    long_sents = [s for s in sentences if 35 <= len(tokenize(s)) <= 55]

    errors = []
    if wc < TARGET_WC_MIN or wc > TARGET_WC_MAX:
        errors.append(f"Word count {wc} (target {TARGET_WC_MIN}–{TARGET_WC_MAX})")
    if para_count < TARGET_PARAS_MIN or para_count > TARGET_PARAS_MAX:
        errors.append(f"Paragraphs {para_count} (target {TARGET_PARAS_MIN}–{TARGET_PARAS_MAX})")
    if len(short_sents) < TARGET_SHORT_SENT_MIN:
        errors.append(f"Short sentences {len(short_sents)} (target ≥{TARGET_SHORT_SENT_MIN})")
    if len(long_sents) < TARGET_LONG_SENT_MIN:
        errors.append(f"Long sentences {len(long_sents)} (target ≥{TARGET_LONG_SENT_MIN})")
    if len(concessive) < TARGET_CONCESSIVE_MIN:
        errors.append(f"Concessive structures {len(concessive)} (target ≥{TARGET_CONCESSIVE_MIN})")

    return {
        "passed": len(errors) == 0,
        "word_count": wc,
        "paragraph_count": para_count,
        "short_sentences": len(short_sents),
        "long_sentences": len(long_sents),
        "concessive_count": len(concessive),
        "errors": errors,
    }

# ══════════════════════════════════════════════════════════════
# LLM call
# ══════════════════════════════════════════════════════════════

async def _call_llm(system: str, user: str) -> str:
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY is not set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
    }

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _api_limiter.acquire)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
            try:
                resp = await client.post(LLM_API_BASE + "chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()
                return content
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                raise
    finally:
        _api_limiter.release()


async def rewrite_article(source_text: str) -> str:
    prompt = USER_PROMPT_TEMPLATE.replace("{{article_text}}", source_text[:4000])
    return await _call_llm(SYSTEM_PROMPT, prompt)


async def replace_oov(text: str, oov_words: list[str]) -> str:
    prompt = OOY_REPLACE_PROMPT.replace("{{oov_list}}", ", ".join(oov_words)).replace("{{article_text}}", text)
    return await _call_llm(SYSTEM_PROMPT, prompt)


async def fix_format(text: str, format_errors: list[str]) -> str:
    prompt = FORMAT_FIX_PROMPT.replace("{{format_errors}}", "\n".join(format_errors)).replace("{{article_text}}", text)
    return await _call_llm(SYSTEM_PROMPT, prompt)

# ══════════════════════════════════════════════════════════════
# Main pipeline
# ══════════════════════════════════════════════════════════════

def pre_filter(source_name: str, word_count: int, title: str = "") -> tuple[bool, str]:
    """Return (pass, reason)."""
    if source_name not in SOURCES_PRIORITY:
        return False, f"Source '{source_name}' not in priority list"

    priority = SOURCES_PRIORITY[source_name]
    if priority not in (1, 2, 3):
        return False, f"Source priority too low"

    if word_count < SOURCE_WC_MIN:
        return False, f"Word count {word_count} < minimum {SOURCE_WC_MIN}"
    if word_count > SOURCE_WC_MAX:
        return False, f"Word count {word_count} > maximum {SOURCE_WC_MAX}"

    return True, ""


class ArticleProcessor:
    def __init__(self):
        self.vocab = VocabChecker()

    def set_vocab_path(self, path: str | Path):
        self.vocab.vocab_path = Path(path)
        self.vocab._loaded = False

    async def process(self, source_text: str, source_name: str = "") -> Optional[dict]:
        """Process a source article through the full pipeline.
        Returns {text, word_count, paragraph_count, source} or None on failure.
        """
        self.vocab.load()

        # ── Step 1: Initial LLM rewrite ──
        logger.info(f"Step 1: LLM rewrite ({source_name})")
        try:
            rewritten = await rewrite_article(source_text)
        except Exception as e:
            logger.error(f"Rewrite failed: {e}")
            return None

        # ── Step 2: Vocab check + replace loop ──
        for replace_attempt in range(MAX_REPLACE_ATTEMPTS + 1):
            tokens = tokenize(rewritten)
            oov_words = self.vocab.detect_oov(tokens)
            oov_ratio = len(oov_words) / len(tokens) if tokens else 0

            logger.info(f"  Replace attempt {replace_attempt}: OOV ratio {oov_ratio:.1%} ({len(oov_words)}/{len(tokens)})")

            if oov_ratio <= TARGET_OOV_RATIO_MAX:
                break
            if replace_attempt >= MAX_REPLACE_ATTEMPTS:
                logger.warning(f"OOV ratio {oov_ratio:.1%} exceeds limit after {MAX_REPLACE_ATTEMPTS} replace attempts, dropping")
                return None

            oov_word_list = list(dict.fromkeys(o["word"] for o in oov_words))[:20]
            try:
                rewritten = await replace_oov(rewritten, oov_word_list)
            except Exception as e:
                logger.error(f"OOV replace failed: {e}")
                return None

        # ── Step 3: Format validation + rewrite loop ──
        for rewrite_attempt in range(MAX_REWRITE_ATTEMPTS + 1):
            fmt = validate_format(rewritten)

            if fmt["passed"]:
                logger.info(f"Format OK on attempt {rewrite_attempt}")
                return {
                    "text": rewritten,
                    "word_count": fmt["word_count"],
                    "paragraph_count": fmt["paragraph_count"],
                    "source": source_name,
                    "short_sentences": fmt["short_sentences"],
                    "long_sentences": fmt["long_sentences"],
                    "concessive_count": fmt["concessive_count"],
                }

            if rewrite_attempt >= MAX_REWRITE_ATTEMPTS:
                logger.warning(f"Format still failing after {MAX_REWRITE_ATTEMPTS} rewrites: {fmt['errors']}, accepting anyway")
                return {
                    "text": rewritten,
                    "word_count": fmt["word_count"],
                    "paragraph_count": fmt["paragraph_count"],
                    "source": source_name,
                    "short_sentences": fmt["short_sentences"],
                    "long_sentences": fmt["long_sentences"],
                    "concessive_count": fmt["concessive_count"],
                }

            logger.info(f"  Rewrite attempt {rewrite_attempt}: format errors: {fmt['errors']}")
            try:
                rewritten = await fix_format(rewritten, fmt["errors"])
            except Exception as e:
                logger.error(f"Format fix failed: {e}")
                return None

        return None


# ══════════════════════════════════════════════════════════════
# Standalone test
# ══════════════════════════════════════════════════════════════

async def test_single(source_text: str, source_name: str = "test"):
    proc = ArticleProcessor()
    result = await proc.process(source_text, source_name)
    if result:
        print(f"✓ {result['word_count']}w/{result['paragraph_count']}p  {source_name}")
        print(f"  Short: {result['short_sentences']}, Long: {result['long_sentences']}, Concessive: {result['concessive_count']}")
        print(f"\n--- OUTPUT ---\n{result['text']}")
    else:
        print(f"✗ FAILED: {source_name}")
    return result


if __name__ == "__main__":
    sample = """The weather in Texas may have cooled since the recent extreme heat, but the temperature will be high at the State Board of Education meeting in Austin this month as officials debate how climate change is taught in Texas schools. Pat Hardy, who sympathises with the views of the energy sector, is resisting proposed changes to science standards for pre-teen pupils. These would emphasise the primacy of human activity in recent climate change and encourage discussion of mitigation measures.

Most scientists and experts sharply dispute Hardy's views. 'They casually dismiss the career work of scholars and scientists as just another misguided opinion,' says Dan Quinn, senior communications strategist at the Texas Freedom Network. 'What millions of Texas kids learn in their public schools is determined too often by the political ideology of partisan board members, rather than facts and sound scholarship.'

Such debates reflect fierce discussions across the US and around the world, as researchers, policymakers, teachers and students step up demands for a greater focus on teaching about the facts of climate change in schools.

A study last year by the National Center for Science Education, a non-profit group of scientists and teachers, looking at how state public schools across the country address climate change in science classes, gave barely half of US states a grade B+ or higher. Among the 10 worst performers were some of the most populous states, including Texas."""
    asyncio.run(test_single(sample, "Scientific_American"))
