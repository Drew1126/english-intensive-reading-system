from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers.article import router as article_router
from routers.agent import router as agent_router
from routers.translate import router as translate_router
from services.article_service import init_session_on_startup
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(title="考研英语精读练习系统", version="1.0")

app.include_router(article_router)
app.include_router(agent_router)
app.include_router(translate_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


@app.on_event("startup")
def on_startup():
    init_session_on_startup()
