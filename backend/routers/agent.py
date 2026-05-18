from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from services.agent_service import stream_agent_response

router = APIRouter(prefix="/data/agent", tags=["agent"])


@router.get("/ask")
async def ask_agent(sentence: str, question: str, article_id: str = "", focus: str = ""):
    return StreamingResponse(
        stream_agent_response(question, sentence, article_id, focus),
        media_type="text/event-stream"
    )
