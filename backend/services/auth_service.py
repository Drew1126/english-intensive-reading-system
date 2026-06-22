import os
import json
import secrets
import logging
import shutil
from pathlib import Path
from typing import Optional
from config import DATA_DIR
from storage import read_json, write_json

logger = logging.getLogger(__name__)

USERS_FILE = str(DATA_DIR / "users.json")
SESSIONS_FILE = str(DATA_DIR / "auth_sessions.json")
AVATARS_DIR = DATA_DIR / "avatars"

USERS = {
    "陈征广": {"password": "czghhh", "name": "陈征广"},
    "张晓雯": {"password": "zxwhhh", "name": "张晓雯"},
}

AVATARS_DIR.mkdir(parents=True, exist_ok=True)


def _init_users():
    data = read_json(USERS_FILE, None)
    if data is None:
        data = {}
        for name, info in USERS.items():
            data[name] = {
                "name": name,
                "avatar": None,
                "checkins": {},
            }
        write_json(USERS_FILE, data)
        logger.info("Users initialized")


def _get_users() -> dict:
    return read_json(USERS_FILE, {})


def _save_users(data: dict):
    write_json(USERS_FILE, data)


def verify_login(username: str, password: str) -> Optional[str]:
    if username not in USERS:
        return None
    if USERS[username]["password"] != password:
        return None
    token = secrets.token_hex(16)
    sessions = read_json(SESSIONS_FILE, {})
    sessions[token] = username
    write_json(SESSIONS_FILE, sessions)
    return token


def get_user_by_token(token: str) -> Optional[str]:
    sessions = read_json(SESSIONS_FILE, {})
    return sessions.get(token)


def get_user_info(username: str) -> Optional[dict]:
    users = _get_users()
    user = users.get(username)
    if not user:
        return None
    return {
        "name": user["name"],
        "has_avatar": user.get("avatar") is not None,
    }


def get_user_checkins(username: str) -> set:
    users = _get_users()
    user = users.get(username, {})
    return set(user.get("checkins", {}).keys())


def toggle_checkin(username: str, article_id: str) -> dict:
    users = _get_users()
    user = users.setdefault(username, {"name": username, "avatar": None, "checkins": {}})
    checkins = user.setdefault("checkins", {})
    if article_id in checkins:
        del checkins[article_id]
        status = False
    else:
        checkins[article_id] = True
        status = True
    _save_users(users)
    return {"checked_in": status}


def get_checkin_status(article_id: str) -> list[dict]:
    users = _get_users()
    result = []
    for username, data in users.items():
        checkins = data.get("checkins", {})
        if article_id in checkins:
            result.append({
                "name": data["name"],
                "has_avatar": data.get("avatar") is not None,
            })
    return result


_AVATAR_MAP = {"陈征广": "chen", "张晓雯": "zhang"}

def save_avatar(username: str, content: bytes) -> str:
    fname = _AVATAR_MAP.get(username, username)
    path = AVATARS_DIR / f"{fname}.jpg"
    with open(path, "wb") as f:
        f.write(content)
    users = _get_users()
    user = users.setdefault(username, {"name": username, "avatar": None, "checkins": {}})
    user["avatar"] = str(path)
    _save_users(users)
    return str(path)


def get_avatar_path(username: str) -> Optional[str]:
    fname = _AVATAR_MAP.get(username, username)
    for ext in [".jpg", ".png", ".gif"]:
        path = AVATARS_DIR / f"{fname}{ext}"
        if path.exists():
            return str(path)
    return None


_init_users()
