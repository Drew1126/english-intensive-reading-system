from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers.article import router as article_router
from routers.agent import router as agent_router
from routers.translate import router as translate_router
from routers.auth import router as auth_router
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(title="考研英语精读练习系统", version="2.0")

app.include_router(article_router)
app.include_router(agent_router)
app.include_router(translate_router)
app.include_router(auth_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
