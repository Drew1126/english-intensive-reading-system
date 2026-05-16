import json
import logging
from pathlib import Path
from typing import Any
from filelock import FileLock, Timeout as FileLockTimeout

logger = logging.getLogger(__name__)


def ensure_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def read_json(path: str, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default if default is not None else []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading {path}: {e}")
        return default if default is not None else []


def write_json(path: str, data: Any) -> None:
    lock_path = path + ".lock"
    ensure_dir(path)
    try:
        logger.info(f"write_json: Acquiring lock for {path}")
        with FileLock(lock_path, timeout=5) as lock:
            logger.info(f"write_json: Lock acquired for {path}")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"write_json: Lock released for {path}")
    except FileLockTimeout:
        logger.error(f"write_json: Timeout acquiring lock for {path}")
        raise
    except Exception as e:
        logger.error(f"write_json: Error writing {path}: {e}")
        raise


def append_to_list(path: str, item: dict) -> None:
    lock_path = path + ".lock"
    ensure_dir(path)
    try:
        with FileLock(lock_path, timeout=5):
            data = read_json(path, [])
            data.append(item)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except FileLockTimeout:
        logger.error(f"append_to_list: Timeout acquiring lock for {path}")
        raise
    except Exception as e:
        logger.error(f"append_to_list: Error writing {path}: {e}")
        raise
