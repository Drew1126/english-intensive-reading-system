from fastapi import APIRouter
from services.translate_service import translate_sentences
from schemas.article import TranslateRequest, TranslateResponse
from storage import read_json, write_json
from config import ARTICLES_DIR

router = APIRouter(prefix="/data/translate", tags=["translate"])


@router.post("", response_model=TranslateResponse)
def translate(req: TranslateRequest):
    translations = translate_sentences(req.sentences)

    # Cache translations back to article file — only for the first paragraph that is missing them
    article_path = str(ARTICLES_DIR / f"{req.article_id}.json")
    article = read_json(article_path, None)
    if article:
        for para in article.get("paragraphs", []):
            if not para.get("translations") or len(para.get("translations", [])) != len(para.get("sentences", [])):
                para["translations"] = translations
                break
        write_json(article_path, article)

    return TranslateResponse(translations=translations)
