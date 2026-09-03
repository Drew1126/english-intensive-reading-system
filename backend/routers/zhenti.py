import os
import tempfile
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from services.zhenti_service import list_years, get_article, process_upload, delete_article
from services.auth_service import require_admin_token
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data/zhenti", tags=["zhenti"])

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
PDF_EXT = {".pdf"}
ALLOWED_EXT = IMAGE_EXT | PDF_EXT


def _require_admin(token: str):
    try:
        return require_admin_token(token)
    except PermissionError as exc:
        status = 401 if str(exc) == "请重新登录" else 403
        raise HTTPException(status_code=status, detail=str(exc))


@router.get("/list")
async def zhenti_list():
    return {"years": list_years()}


@router.get("/{year}/{text_num}")
async def zhenti_article(year: int, text_num: int):
    if text_num not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="text_num must be 1-4")
    article = get_article(year, text_num)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return {"article": article}


@router.delete("/{year}/{text_num}")
async def zhenti_delete(year: int, text_num: int, token: str = Query(...)):
    _require_admin(token)
    if text_num not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="text_num must be 1-4")
    if not delete_article(year, text_num):
        raise HTTPException(status_code=404, detail="文章不存在")
    return {"success": True}


@router.post("/{year}/{text_num}/upload")
async def zhenti_upload(year: int, text_num: int, files: List[UploadFile] = File(...), token: str = Query(...)):
    _require_admin(token)
    if text_num not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="text_num must be 1-4")

    tmp_files = []
    try:
        for f in files:
            ext = os.path.splitext(f.filename or "")[1].lower()
            if ext not in ALLOWED_EXT:
                raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            tmp.write(f.file.read())
            tmp.close()
            tmp_files.append(tmp.name)

        article = await process_upload(year, text_num, tmp_files)
        return {"article": article}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Zhenti upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")
    finally:
        for p in tmp_files:
            try:
                os.unlink(p)
            except:
                pass
