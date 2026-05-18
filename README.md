# 考研英语精读练习系统

AI-driven English reading practice for Chinese grad-school exam prep (考研英语一).

## Quick Start

```bash
cd backend
cp .env.example .env    # set LLM_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# → http://localhost:8000  (dev only)
```

### Production Access

The app is served at **`/english`** on port 80 via a reverse proxy:

```
http://<server-ip>/english
```

This coexists with other services on port 80 (e.g. `/baidu.com`).

Or use the startup script:

```bash
bash start.sh
```

On Windows: double-click `start_backend.bat`.

## Requirements

- Python 3.10+
- An LLM API key (DeepSeek-compatible) in `backend/.env`

```
LLM_API_KEY=sk-your_key_here
```

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + Uvicorn, Python 3 |
| AI | LangChain + langchain-open → DeepSeek `deepseek-chat` |
| Frontend | Vanilla HTML/CSS/JS — no build step |
| Storage | JSON files (`backend/data/`), `filelock` for write safety |

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Config & data dir paths
│   ├── routers/             # API routes (article, agent, translate)
│   ├── services/            # Business logic
│   ├── agents/              # LLM agent & article processor
│   ├── storage/             # JSON file I/O
│   ├── schemas/             # Pydantic models
│   ├── vocab_checker.py     # 5500-word vocabulary filter
│   ├── crawl_all.py         # Multi-source article crawler
│   ├── extract_zhenti.py    # 考研真题 LaTeX → JSON extractor
│   └── data/                # Runtime data (auto-created, gitignored)
├── frontend/
│   ├── index.html
│   ├── css/
│   └── js/
├── crawled_articles/        # Raw crawled source articles
├── processed_articles/      # LLM-rewritten article samples
├── vocabulary_data/         # 5500 考研词汇
├── zhenti_articles/         # 144 真题 articles (1994–2023)
└── start.sh                 # Linux startup script
```

## Architecture

- **Session-based**: 2 articles max on disk (current + prefetch)
- **Articles** generated on-demand from crawled journal sources (Economist, Guardian, SciAm, Atlantic, Wired, New Yorker, Nature, Nautilus)
- **No database**: all data persisted as JSON files
- **Frontend** served by backend at `/` — no CORS, no separate dev server

## Deployment (systemd)

```bash
# English app (port 8000)
sudo systemctl status english-reader
sudo systemctl restart english-reader
sudo journalctl -u english-reader -f

# Reverse proxy (port 80, serves /english)
sudo systemctl status deepseek-proxy
sudo systemctl restart deepseek-proxy
```

Port 80 is managed by `deepseek-proxy.service` which:
- Serves the baidu.com app at `/` and `/baidu.com`
- Proxies DeepSeek API at `/v1/*`
- Forwards all unmatched requests (including `/english/*`) to the English app on port 8000

### Architecture

```
Port 80 (deepseek-proxy)                    Port 8000 (english-reader)
├── /              → baidu.com               ├── /api/article/*  → article API
├── /baidu.com     → baidu.com               ├── /api/translate  → translate API
├── /v1/*          → DeepSeek API proxy      ├── /api/agent/*    → agent API
└── /english/*     → port 8000 ────────────▶ └── /*              → static frontend
```

## Testing

```bash
cd backend
python3 test_server.py
```
