from pydantic import BaseModel
from typing import List


class Paragraph(BaseModel):
    index: int
    sentences: List[str]
    translations: List[str] = []


class ArticleResponse(BaseModel):
    id: str
    date: str
    title: str
    source: str
    category: str = ""
    level: str
    word_count: int = 0
    paragraphs: List[Paragraph]


class ArticleHistoryItem(BaseModel):
    id: str
    date: str
    title: str
    level: str
    source: str


class ArticleHistoryResponse(BaseModel):
    total: int
    items: List[ArticleHistoryItem]


class TranslateRequest(BaseModel):
    article_id: str
    sentences: List[str]


class TranslateResponse(BaseModel):
    translations: List[str]
