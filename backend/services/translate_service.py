import json
import re
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import LLM_API_KEY, LLM_MODEL, LLM_API_BASE
from typing import List

logger = logging.getLogger(__name__)


def translate_sentences(sentences: List[str]) -> List[str]:
    if not sentences:
        return []

    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_API_BASE,
        temperature=0.3,
    )

    count = len(sentences)
    sentence_list = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))
    prompt = (
        f"将以下 {count} 句英文逐句翻译成中文，保持准确流畅。\n\n"
        f"只返回 JSON 数组，包含恰好 {count} 个翻译。不要包含其他文字。\n"
        f"格式：[\"译文1\", \"译文2\", ..., \"译文{count}\"]\n\n"
        f"英文句子：\n{sentence_list}"
    )

    messages = [
        SystemMessage(content="你是一个专业中英翻译助手。只返回 JSON 格式的翻译数组，不包含其他文字。"),
        HumanMessage(content=prompt)
    ]

    for attempt in range(2):
        try:
            response = llm.invoke(messages)
            content = response.content.strip()

            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            translations = json.loads(content)

            if not isinstance(translations, list):
                logger.warning(f"Translate returned non-list, attempt {attempt + 1}")
                continue

            # Fix length mismatch
            if len(translations) > count:
                translations = translations[:count]
                logger.info(f"Truncated translations {len(translations)} -> {count}")
            elif len(translations) < count:
                translations.extend([""] * (count - len(translations)))
                logger.info(f"Padded translations {len(translations)} -> {count}")

            return translations

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Translate attempt {attempt + 1} failed: {e}")
            if attempt == 0:
                continue

    logger.error(f"All translate attempts failed for {count} sentences, returning originals")
    return sentences if count > 0 else []
