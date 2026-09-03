from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from services.auth_service import (
    verify_login, get_user_by_token, get_user_info,
    toggle_checkin, get_checkin_status, save_avatar, get_avatar_path,
    require_admin_token, list_users, create_user, update_user, delete_user
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserUpdateRequest(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None


def _require_admin(token: str):
    try:
        return require_admin_token(token)
    except PermissionError as exc:
        status = 401 if str(exc) == "请重新登录" else 403
        raise HTTPException(status_code=status, detail=str(exc))


@router.post("/login")
async def login(req: LoginRequest):
    token = verify_login(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    info = get_user_info(req.username) or {}
    return {"token": token, "name": req.username, "role": info.get("role", "viewer")}


@router.get("/me")
async def me(token: str = Query(...)):
    username = get_user_by_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="无效的登录状态")
    info = get_user_info(username)
    return {"name": username, **(info or {})}


@router.get("/users")
async def users_list(token: str = Query(...)):
    _require_admin(token)
    return {"users": list_users()}


@router.post("/users")
async def users_create(req: UserCreateRequest, token: str = Query(...)):
    _require_admin(token)
    try:
        return {"user": create_user(req.username, req.password, req.role)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/users/{username}")
async def users_update(username: str, req: UserUpdateRequest, token: str = Query(...)):
    _require_admin(token)
    try:
        return {"user": update_user(username, req.password, req.role)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/users/{username}")
async def users_delete(username: str, token: str = Query(...)):
    admin = _require_admin(token)
    if username == admin:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    try:
        delete_user(username)
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/checkin/{article_id}")
async def checkin(article_id: str, token: str = Query(...)):
    username = get_user_by_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="请重新登录")
    result = toggle_checkin(username, article_id)
    return result


@router.get("/checkin-status/{article_id}")
async def checkin_status(article_id: str):
    return {"checkins": get_checkin_status(article_id)}


@router.post("/avatar")
async def upload_avatar(token: str = Query(...), file: UploadFile = File(...)):
    username = get_user_by_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="请重新登录")
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片不能超过2MB")
    save_avatar(username, content)
    return {"success": True}


@router.get("/avatar/{username}")
async def get_avatar(username: str):
    path = get_avatar_path(username)
    if path:
        return FileResponse(path, media_type="image/jpeg")
    default = Path(__file__).resolve().parent.parent.parent / "frontend" / "default-avatar.svg"
    return FileResponse(str(default), media_type="image/svg+xml")
