"""Validate the structure and basic integrity of imported zhenti JSON files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "backend" / "data" / "zhenti"


def validate(years: list[int]) -> tuple[int, list[str], list[str]]:
    total = 0
    missing: list[str] = []
    bad: list[str] = []
    fingerprints: dict[str, str] = {}
    for year in years:
        for text_num in range(1, 5):
            label = f"{year}-T{text_num}"
            path = DATA_DIR / str(year) / f"text_{text_num}.json"
            if not path.exists():
                missing.append(label)
                continue
            total += 1
            errors: list[str] = []
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                bad.append(f"{label}: invalid JSON ({exc})")
                continue
            paragraphs = data.get("paragraphs", [])
            passage = paragraphs[:-5]
            if not passage:
                errors.append("no passage")
            else:
                first = passage[0].get("sentences", [""])[0].lstrip()
                if not re.match(r'''[A-Z"'“‘(]''', first):
                    errors.append("invalid passage start")
            for index, paragraph in enumerate(paragraphs):
                if len(paragraph.get("sentences", [])) != len(paragraph.get("translations", [])):
                    errors.append(f"paragraph {index} translation mismatch")
            expected = 21 + (text_num - 1) * 5
            questions = paragraphs[-5:]
            if len(questions) != 5:
                errors.append("question count")
            for offset, question in enumerate(questions):
                en = (question.get("sentences") or [""])[0]
                number = expected + offset
                if not re.match(rf"{number}[.、)]", en):
                    errors.append(f"question {number} number")
                if any(not re.search(rf"(?m)^{label_}[.)、]", en) for label_ in "ABCD"):
                    errors.append(f"question {number} options")
            body = " ".join(sentence for paragraph in passage for sentence in paragraph.get("sentences", []))
            fingerprint = re.sub(r"\W+", " ", body.lower())[:180]
            if fingerprint in fingerprints:
                errors.append(f"duplicate of {fingerprints[fingerprint]}")
            fingerprints[fingerprint] = label
            word_count = data.get("word_count", 0)
            if not 350 <= word_count <= 500:
                errors.append(f"unusual word count {word_count}")
            if errors:
                bad.append(f"{label}: " + "; ".join(errors))
    return total, missing, bad


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="*", type=int, default=list(range(2007, 2014)) + list(range(2022, 2026)))
    args = parser.parse_args()
    total, missing, bad = validate(args.years)
    print(f"FILES={total}/{len(args.years) * 4}")
    print("MISSING=" + (", ".join(missing) if missing else "none"))
    print("BAD=" + (" | ".join(bad) if bad else "none"))
    raise SystemExit(1 if missing or bad else 0)


if __name__ == "__main__":
    main()
