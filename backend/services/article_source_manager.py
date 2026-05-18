import json
import logging
import re
from datetime import datetime
from pathlib import Path
from filelock import FileLock, Timeout as FileLockTimeout

logger = logging.getLogger(__name__)

CRAWLED_DIR = Path(__file__).resolve().parent.parent.parent / "crawled_articles"
TRACKING_FILE = CRAWLED_DIR / "processed_sources.json"

PRIORITY = {
    "The_Economist": 1,
    "The_Guardian": 1,
    "Scientific_American": 1,
    "Shanbay": 2,
    "The_Atlantic": 3,
    "Wired": 3,
    "Nature": 4,
    "Nautilus": 4,
    "The_New_Yorker": 4,
    "ScienceMag": 4,
}


def _parse_article_file(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return None

    body_start = content.find("=" * 60)
    if body_start != -1:
        header_lines = content[:body_start].strip().split("\n")
        body = content[body_start + 60:].strip()
        header = {}
        for line in header_lines:
            m = re.match(r"^(\w[\w\s]+):\s*(.*)", line)
            if m:
                header[m.group(1).strip()] = m.group(2).strip()
        source = header.get("Source", path.parent.name)
        title = header.get("Title", path.stem)
        wc_str = header.get("Word Count", "0")
        try:
            wc = int(wc_str)
        except ValueError:
            wc = len(body.split())
    else:
        body = content.strip()
        if not body:
            return None
        source = path.parent.name
        title = path.stem.replace("_", " ").title()
        wc = len(body.split())

    return {"source": source, "title": title, "word_count": wc, "body": body, "path": str(path)}


def _priority_key(article: dict) -> tuple:
    p = PRIORITY.get(article["source"], 99)
    return (p, -article["word_count"])


def _read_tracking() -> dict:
    p = Path(TRACKING_FILE)
    if not p.exists():
        return {"used": [], "last_reset": None}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"used": [], "last_reset": None}


def _write_tracking(data: dict):
    p = Path(TRACKING_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_next_source() -> dict | None:
    """Atomically pick and reserve the next unused source article.
    Returns {source, title, word_count, body, path} or None if exhausted.
    """
    lock_path = str(TRACKING_FILE) + ".lock"
    try:
        with FileLock(lock_path, timeout=10):
            tracking = _read_tracking()
            used_paths = set(tracking.get("used", []))

            candidates = []
            for folder in sorted(CRAWLED_DIR.iterdir()):
                if not folder.is_dir() or folder.name == "__pycache__":
                    continue
                for f in sorted(folder.glob("*.txt")):
                    if str(f) in used_paths:
                        continue
                    parsed = _parse_article_file(f)
                    if parsed:
                        candidates.append(parsed)

            if not candidates:
                logger.info("All source articles exhausted, resetting pool")
                tracking["used"] = []
                tracking["last_reset"] = datetime.now().isoformat()
                for folder in sorted(CRAWLED_DIR.iterdir()):
                    if not folder.is_dir() or folder.name == "__pycache__":
                        continue
                    for f in sorted(folder.glob("*.txt")):
                        parsed = _parse_article_file(f)
                        if parsed:
                            candidates.append(parsed)

            if not candidates:
                logger.warning("No source articles available at all")
                return None

            candidates.sort(key=_priority_key)
            chosen = candidates[0]
            tracking["used"].append(chosen["path"])
            _write_tracking(tracking)

            logger.info(f"Next source: [{chosen['source']}] {chosen['title'][:60]} ({chosen['word_count']}w)")
            return chosen
    except FileLockTimeout:
        logger.error("get_next_source: Timeout acquiring lock")
        return None


def get_queue_status() -> dict:
    lock_path = str(TRACKING_FILE) + ".lock"
    try:
        with FileLock(lock_path, timeout=5):
            tracking = _read_tracking()
            used_paths = set(tracking.get("used", []))
            total = 0
            for folder in sorted(CRAWLED_DIR.iterdir()):
                if not folder.is_dir() or folder.name == "__pycache__":
                    continue
                total += len(list(folder.glob("*.txt")))
            return {"total": total, "used": len(used_paths), "remaining": total - len(used_paths)}
    except FileLockTimeout:
        logger.error("get_queue_status: Timeout acquiring lock")
        return {"total": 0, "used": 0, "remaining": 0}
