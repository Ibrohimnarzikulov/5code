"""Suhbat va chat endpoint'lari (SSE streaming bilan)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import ClaudeError, history_to_api, stream_reply
from app.ai.tools import ToolContext
from app.database import SessionLocal
from app.deps import CurrentUser, DbSession
from app.models import Conversation, Message
from app.schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationOut,
    MessageOut,
)

router = APIRouter(prefix="/api", tags=["chat"])

TITLE_MAX_LEN = 60


async def _owned_conversation(
    db: AsyncSession, conversation_id: int, user_id: int
) -> Conversation:
    """Suhbatni oladi va egaligini tekshiradi."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suhbat topilmadi"
        )
    return conversation


def _make_title(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= TITLE_MAX_LEN:
        return cleaned or "Yangi suhbat"
    return cleaned[:TITLE_MAX_LEN].rsplit(" ", 1)[0] + "…"


# --- Suhbatlar CRUD ---------------------------------------------------------


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(db: DbSession, user: CurrentUser) -> list[ConversationOut]:
    """Foydalanuvchining suhbatlari (yangisi birinchi)."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return [ConversationOut.model_validate(c) for c in result.scalars()]


@router.post(
    "/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate, db: DbSession, user: CurrentUser
) -> ConversationOut:
    """Yangi bo'sh suhbat yaratadi."""
    conversation = Conversation(user_id=user.id, title=payload.title)
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return ConversationOut.model_validate(conversation)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
)
async def list_messages(
    conversation_id: int, db: DbSession, user: CurrentUser
) -> list[MessageOut]:
    """Suhbat xabarlari tarixi."""
    await _owned_conversation(db, conversation_id, user.id)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id)
    )
    messages: list[MessageOut] = []
    for row in result.scalars():
        try:
            content = json.loads(row.content_json)
        except json.JSONDecodeError:
            content = row.content_json
        messages.append(
            MessageOut(
                id=row.id, role=row.role, content=content, created_at=row.created_at
            )
        )
    return messages


@router.delete(
    "/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_conversation(
    conversation_id: int, db: DbSession, user: CurrentUser
) -> None:
    """Suhbatni xabarlari bilan birga o'chiradi."""
    conversation = await _owned_conversation(db, conversation_id, user.id)
    await db.delete(conversation)


# --- Chat streaming ---------------------------------------------------------


def _sse(event: dict) -> str:
    """Hodisani SSE formatiga o'raydi."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(payload: ChatRequest, user: CurrentUser) -> StreamingResponse:
    """Xabar yuboradi va Claude javobini SSE oqim sifatida qaytaradi.

    Oqimdagi hodisa turlari:
    `start`, `thinking`, `text`, `tool_use`, `tool_result`, `error`, `done`.
    """
    user_id = user.id
    ai_in_pc = user.ai_in_pc
    provider_name = user.ai_provider
    model_name = user.ai_model
    conversation_id = payload.conversation_id
    user_text = payload.message

    async def generator() -> AsyncIterator[str]:
        # Streaming davomida alohida sessiya — so'rov dependency'si yopilib
        # ketishidan qat'i nazar ishlaydi.
        async with SessionLocal() as db:
            try:
                if conversation_id is None:
                    conversation = Conversation(
                        user_id=user_id, title=_make_title(user_text)
                    )
                    db.add(conversation)
                    await db.flush()
                else:
                    conversation = await _owned_conversation(
                        db, conversation_id, user_id
                    )

                history_rows = await db.execute(
                    select(Message.role, Message.content_json)
                    .where(Message.conversation_id == conversation.id)
                    .order_by(Message.id)
                )
                history = history_to_api(list(history_rows.all()))

                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role="user",
                        content_json=json.dumps(user_text, ensure_ascii=False),
                    )
                )
                await db.commit()

                yield _sse({"type": "start", "conversation_id": conversation.id})

                ctx = ToolContext(
                    ai_in_pc=ai_in_pc,
                    user_id=user_id,
                    conversation_id=conversation.id,
                    db=db,
                )

                async for event in stream_reply(
                    history=history,
                    user_message=user_text,
                    ctx=ctx,
                    provider_name=provider_name,
                    model_name=model_name,
                ):
                    if event["type"] == "assistant_message":
                        for msg in event["messages"]:
                            db.add(
                                Message(
                                    conversation_id=conversation.id,
                                    role=msg["role"],
                                    content_json=json.dumps(
                                        msg["content"], ensure_ascii=False
                                    ),
                                )
                            )
                        await db.commit()
                        continue
                    yield _sse(event)

                yield _sse({"type": "done", "conversation_id": conversation.id})

            except ClaudeError as exc:
                yield _sse({"type": "error", "message": str(exc)})
            except HTTPException as exc:
                yield _sse({"type": "error", "message": exc.detail})
            except Exception as exc:  # noqa: BLE001 — oqim uzilmasligi kerak
                yield _sse({"type": "error", "message": f"Server xatosi: {exc!r}"})

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
