from pathlib import Path
from filelock import FileLock, Timeout as FileLockTimeout
from config import DATA_DIR
from storage import read_json
import json
import logging

logger = logging.getLogger(__name__)

SESSION_FILE = "session.json"
SLOTS = [0, 1]


def get_session_path() -> str:
    return str(DATA_DIR / SESSION_FILE)


def load_session() -> dict | None:
    return read_json(get_session_path(), None)


def _write_session(path: str, data: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_session(data: dict) -> None:
    path = get_session_path()
    lock_path = path + ".lock"
    try:
        with FileLock(lock_path, timeout=5):
            _write_session(path, data)
    except FileLockTimeout:
        logger.error("save_session: Timeout acquiring lock")


def create_session(current_slot: int, prefetch_slot: int) -> dict:
    session = {
        "current_slot": current_slot,
        "prefetch_slot": prefetch_slot,
    }
    save_session(session)
    logger.info(f"Session created: current={current_slot}, prefetch={prefetch_slot}")
    return session


def advance_session() -> dict | None:
    """Swap current ↔ prefetch. Thread-safe with FileLock."""
    path = get_session_path()
    lock_path = path + ".lock"
    try:
        with FileLock(lock_path, timeout=10):
            session = read_json(path, None)
            if not session:
                logger.error("advance_session: No session found")
                return None
            old_current = session["current_slot"]
            old_prefetch = session["prefetch_slot"]

            session["current_slot"] = old_prefetch
            session["prefetch_slot"] = old_current

            _write_session(path, session)
            logger.info(f"Session advanced: current={session['current_slot']}, prefetch={session['prefetch_slot']}")
            return session
    except FileLockTimeout:
        logger.error("advance_session: Timeout acquiring lock")
        return None
