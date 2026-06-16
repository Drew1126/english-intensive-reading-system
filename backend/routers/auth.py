from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from services.auth_service import (
    verify_login, get_user_by_token, get_user_info,
    toggle_checkin, get_checkin_status, save_avatar, get_avatar_path
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    name: str


@router.post("/login")
async def login(req: LoginRequest):
    token = verify_login(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": token, "name": req.username}


@router.get("/me")
async def me(token: str = Query(...)):
    username = get_user_by_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="无效的登录状态")
    info = get_user_info(username)
    return {"name": username, **(info or {})}


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
