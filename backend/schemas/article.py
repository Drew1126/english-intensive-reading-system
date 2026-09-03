from pydantic import BaseModel
from typing import List


class TranslateRequest(BaseModel):
    article_id: str
    sentences: List[str]


class TranslateResponse(BaseModel):
    translations: List[str]
