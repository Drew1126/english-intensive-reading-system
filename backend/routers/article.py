from fastapi import APIRouter, HTTPException
from services.article_service import get_or_create_current, advance_to_next
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data/article", tags=["article"])


@router.get("/current")
async def get_current():
    """Return current article. Creates session if none exists."""
    try:
        article = await get_or_create_current()
        return {"article": article}
    except Exception as e:
        logger.error(f"Failed to get current article: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get article: {str(e)}")


@router.post("/next")
async def next_article():
    """Advance: swap slots, prefetch becomes current. Returns current."""
    try:
        result = await advance_to_next()
        return result
    except Exception as e:
        logger.error(f"Failed to advance article: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to advance: {str(e)}")
