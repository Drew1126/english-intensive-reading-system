import os
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from services.pdf_service import process_uploaded_pdf, get_latest_article, get_article_by_index, get_article_list, delete_article
from services.auth_service import get_user_by_token
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data/article", tags=["article"])

ALLOWED_EXTENSIONS = {".pdf"}


@router.get("/current")
async def get_current():
    article = get_latest_article()
    if not article:
        return {"article": None}
    return {"article": article}


@router.get("/list")
async def list_articles():
    return {"articles": get_article_list()}


@router.get("/{index}")
async def get_article(index: int):
    article = get_article_by_index(index)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"article": article}


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        content = await file.read()
        tmp.write(content)
        tmp.close()

        article = await process_uploaded_pdf(tmp.name)

        if not article:
            raise HTTPException(status_code=422, detail="Failed to parse PDF: no valid content found")

        return {"article": article}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except:
                pass


@router.delete("/{index}")
async def remove_article(index: int, token: str = Query(...)):
    username = get_user_by_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="请重新登录")
    ok = delete_article(index)
    if not ok:
        raise HTTPException(status_code=404, detail="文章不存在")
    return {"success": True}
