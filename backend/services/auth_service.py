import secrets
import logging
import hashlib
import hmac
from typing import Optional
from config import DATA_DIR
from storage import read_json, write_json

logger = logging.getLogger(__name__)

USERS_FILE = str(DATA_DIR / "users.json")
SESSIONS_FILE = str(DATA_DIR / "auth_sessions.json")
AVATARS_DIR = DATA_DIR / "avatars"

INITIAL_USERS = {
    "root": {"password_hash": "pbkdf2_sha256$120000$6506c0f65838c78ad95835ab0ce1c098$7bc96947d0623004f9a6ed869f04abb7dbdfb927faf39abfba73849d02045f04", "role": "admin"},
    "游客": {"password_hash": "pbkdf2_sha256$120000$9f2dbe299e9a7187235937a9737efae7$66b6aa5990e9feb887f8614d8cd6a39335a5852e43a0d7b4fe134b17a90055c3", "role": "viewer"},
    "陈征广": {"password_hash": "pbkdf2_sha256$120000$30685e2f123a44e3fa3a47f3f494bcdb$f50b3884d557de79f232b2a11f9e0024e94f1e8b467b3112e5123e85065d0856", "role": "viewer"},
    "张晓雯": {"password_hash": "pbkdf2_sha256$120000$293fedf22ffa2babeaace1ff6a9eba73$7ac4fb0c3d41c7e0cc7976d85566ccc2c85d48d440c95e50a4f8b85a2839291c", "role": "viewer"},
}

AVATARS_DIR.mkdir(parents=True, exist_ok=True)


def _init_users():
    data = read_json(USERS_FILE, {}) or {}
    changed = False
    for name, info in INITIAL_USERS.items():
        if name not in data:
            data[name] = {
                "name": name, "password_hash": info["password_hash"],
                "role": info["role"], "avatar": None, "checkins": {},
            }
            changed = True
    for name, user in data.items():
        if "role" not in user:
            user["role"] = "admin" if name == "root" else "viewer"
            changed = True
        if "password_hash" not in user and name in INITIAL_USERS:
            user["password_hash"] = INITIAL_USERS[name]["password_hash"]
            changed = True
    if changed:
        write_json(USERS_FILE, data)
        logger.info("User accounts initialized or migrated")


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def _get_users() -> dict:
    return read_json(USERS_FILE, {})


def _save_users(data: dict):
    write_json(USERS_FILE, data)


def verify_login(username: str, password: str) -> Optional[str]:
    user = _get_users().get(username)
    if not user or not _verify_password(password, user.get("password_hash", "")):
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
        "role": user.get("role", "viewer"),
    }


def is_admin(username: str) -> bool:
    user = _get_users().get(username, {})
    return user.get("role") == "admin"


def require_admin_token(token: str) -> str:
    username = get_user_by_token(token)
    if not username:
        raise PermissionError("请重新登录")
    if not is_admin(username):
        raise PermissionError("仅管理员可以执行此操作")
    return username


def list_users() -> list[dict]:
    return [{"username": name, "name": data.get("name", name), "role": data.get("role", "viewer")}
            for name, data in sorted(_get_users().items())]


def create_user(username: str, password: str, role: str = "viewer") -> dict:
    username = username.strip()
    if not username or len(username) > 40:
        raise ValueError("账号名不能为空且不能超过40个字符")
    if len(password) < 6:
        raise ValueError("密码至少需要6个字符")
    if role != "viewer":
        raise ValueError("root 是唯一管理员，新账号只能是普通用户")
    users = _get_users()
    if username in users:
        raise ValueError("账号已存在")
    users[username] = {"name": username, "password_hash": _hash_password(password), "role": role, "avatar": None, "checkins": {}}
    _save_users(users)
    return {"username": username, "name": username, "role": role}


def update_user(username: str, password: Optional[str] = None, role: Optional[str] = None) -> dict:
    users = _get_users()
    if username not in users:
        raise ValueError("账号不存在")
    if role and ((username == "root" and role != "admin") or (username != "root" and role != "viewer")):
        raise ValueError("root 是唯一管理员，其他账号只能是普通用户")
    if password is not None:
        if len(password) < 6:
            raise ValueError("密码至少需要6个字符")
        users[username]["password_hash"] = _hash_password(password)
    if role is not None:
        if role not in ("admin", "viewer"):
            raise ValueError("无效的账号角色")
        users[username]["role"] = role
    _save_users(users)
    return {"username": username, "name": users[username].get("name", username), "role": users[username].get("role", "viewer")}


def delete_user(username: str):
    if username == "root":
        raise ValueError("不能删除 root 管理员")
    users = _get_users()
    if username not in users:
        raise ValueError("账号不存在")
    del users[username]
    _save_users(users)
    sessions = read_json(SESSIONS_FILE, {})
    sessions = {token: name for token, name in sessions.items() if name != username}
    write_json(SESSIONS_FILE, sessions)


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
