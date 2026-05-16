# AGENTS.md

## Project

考研英语精读练习系统 — AI-driven English reading practice for Chinese grad-school exam prep.

Single FastAPI service (port 8000) serving both the backend API **and** frontend static files. No CORS needed. No database — all data persisted as JSON files in `backend/data/`.

## Quick start

```bash
cd backend
cp .env.example .env    # set LLM_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# → http://localhost:8000
```

On Windows: double-click `start_backend.bat` (uses `py`, not `python3`).

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + Uvicorn, Python 3 |
| AI | LangChain + langchain-openai → DeepSeek `deepseek-chat` (OpenAI-compatible endpoint) |
| Frontend | Vanilla HTML/CSS/JS — **no build step** |
| Storage | JSON files (`backend/data/`), `filelock` for write safety |
| Article Generation | On-demand — 2 articles max on disk at any time (current + prefetch), generated only when user reads or advances |

## Architecture (key facts)

- **Entry point**: `backend/main.py` — registers 4 routers, mounts `frontend/` as static files at `/`, starts APScheduler on startup.
- **Config**: `backend/config.py` — loads `LLM_API_KEY` from `.env`, defines `DATA_DIR` paths and `DAILY_TOPICS` rotation (5-day cycle via `tm_yday % 5`).
- **Frontend is served by backend**: `app.mount("/", StaticFiles(..., html=True))`. Frontend JS calls APIs via relative paths `/api/*`. No separate dev server.
- **Modules**: `routers/` → `services/` → `agents/` + `storage/`. `schemas/` has Pydantic models.
- **Articles**: Session-based system — 2 articles max on disk at any time: current (displayed) + prefetch (generating in background). Single `data/session.json` tracks `{prev_index, current_index, prefetch_index}`. History limited to 1 level (can only go back one article). `POST /api/article/next` atomically advances session and returns both current + prev article data for instant client-side navigation.
- **Translations**: auto-preloaded on article load, cached back into the article JSON file.
- **Chat history**: one JSON file per day in `data/chat_history/`.

## Conventions

- All LLM calls go through `langchain-openai` with base URL `https://api.deepseek.com/v1/`.
- Articles are 4 paragraphs × 5 sentences × 18–28 words each (~350–450 words total).
- Topics rotate daily across 5 categories defined in `config.py`.
- Frontend has zero build tooling — edit files directly.

## Testing

`backend/test_server.py` is a manual integration test script (not pytest). It starts the server on port 8765, hits article endpoints, then tears down. Hardcoded to `/home/drew/English/backend` — **update line 9 if working from a different machine**. Run with `python3 test_server.py` from the `backend/` directory.

## Deployment

`english-reader.service` — systemd unit running in production (user `admin`, WorkingDirectory `/home/admin/English/backend`). Common ops from the `order` file:

```bash
sudo systemctl status english-reader
sudo systemctl restart english-reader
sudo journalctl -u english-reader -f          # tail logs
sudo journalctl -u english-reader --since "today"
```

## Gotchas

- `.env` **must exist** in `backend/` before starting, otherwise `start.sh` exits with error. The server itself won't crash but LLM calls will fail without a key.
- The `data/` directory is auto-created by `config.py` on import. Don't recreate it manually.
- `test_server.py` has an absolute path (`/home/drew/English/backend`) — **update line 9 if working from a different machine**.
- No linter, formatter, or type-checker is configured. Follow existing code style.
