"""Artifact endpoint'lari — AI yaratgan saytlarni saqlash va ko'rsatish."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import Artifact
from app.schemas import ArtifactOut

router = APIRouter(tags=["artifacts"])

# Artifact HTML'i model tomonidan yaratiladi — unga ishonib bo'lmaydi.
# `sandbox` direktivasi sahifani alohida (opaque) origin'ga tushiradi, ya'ni
# u bizning localStorage/cookie/DOM'imizga umuman kira olmaydi.
SANDBOX_CSP = "sandbox allow-scripts allow-forms allow-popups allow-modals"


@router.get("/api/artifacts", response_model=list[ArtifactOut])
async def list_artifacts(db: DbSession, user: CurrentUser) -> list[ArtifactOut]:
    """Foydalanuvchining artifactlari (yangisi birinchi)."""
    result = await db.execute(
        select(Artifact)
        .where(Artifact.user_id == user.id)
        .order_by(Artifact.updated_at.desc())
    )
    return [ArtifactOut.model_validate(a) for a in result.scalars()]


@router.get("/api/artifacts/{artifact_id}", response_model=ArtifactOut)
async def get_artifact(
    artifact_id: int, db: DbSession, user: CurrentUser
) -> ArtifactOut:
    """Bitta artifact (HTML kodi bilan)."""
    artifact = await db.get(Artifact, artifact_id)
    if artifact is None or artifact.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifact topilmadi"
        )
    return ArtifactOut.model_validate(artifact)


@router.delete("/api/artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact(artifact_id: int, db: DbSession, user: CurrentUser) -> None:
    """Artifactni o'chiradi."""
    artifact = await db.get(Artifact, artifact_id)
    if artifact is None or artifact.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifact topilmadi"
        )
    await db.delete(artifact)


@router.get("/a/{token}", include_in_schema=False)
async def render_artifact(token: str, db: DbSession) -> Response:
    """Artifactni jonli HTML sahifa sifatida beradi.

    iframe Bearer header yubora olmaydi, shuning uchun kirish taxmin qilib
    bo'lmaydigan `token` orqali. Sahifa qattiq sandbox ostida ishlaydi.
    """
    result = await db.execute(select(Artifact).where(Artifact.token == token))
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifact topilmadi"
        )

    return Response(
        content=artifact.html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Security-Policy": SANDBOX_CSP,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )
