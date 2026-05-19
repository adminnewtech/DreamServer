"""AI Assistant - chat UI + streamed plain-text response backed by 9Router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from ..auth import require_admin
from ..integrations.assistant import chat_stream

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.get("/assistant", response_class=HTMLResponse)
async def page_assistant(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/assistant.html",
        {"request": request, "active_page": "assistant"},
    )


@router.post("/assistant/chat")
async def assistant_chat(
    body: ChatRequest,
    actor: str = Depends(require_admin),
):
    """Stream plain UTF-8 chunks. Client reads via fetch + ReadableStream."""

    async def gen():
        async for chunk in chat_stream(body.message):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
