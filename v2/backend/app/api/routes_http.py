from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response

from app.deps import get_session_manager, get_file_manager
from app.core.session_manager import SessionManager
from app.core.file_manager import FileManager
from app.models.session import CreateSessionRequest, SessionResponse

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    body: CreateSessionRequest | None = None,
    sm: SessionManager = Depends(get_session_manager),
):
    config = body.container_config if body else None
    session = await sm.create(config)
    return SessionResponse(
        id=session.id,
        container_id=session.container_id,
        status=session.status,
        created_at=session.created_at,
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
):
    session = await sm.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return SessionResponse(
        id=session.id,
        container_id=session.container_id,
        status=session.status,
        created_at=session.created_at,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
):
    session = await sm.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    await sm.destroy(session_id)
    return {"status": "destroyed"}


@router.post("/sessions/{session_id}/files")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    sm: SessionManager = Depends(get_session_manager),
    fm: FileManager = Depends(get_file_manager),
):
    session = await sm.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if not session.container_id:
        raise HTTPException(400, "Container not ready")

    content = await file.read()
    remote_path = await fm.upload_to_container(
        session.container_id, file.filename, content
    )
    return {"path": remote_path, "size": len(content)}


@router.get("/sessions/{session_id}/files/{path:path}")
async def download_file(
    session_id: str,
    path: str,
    sm: SessionManager = Depends(get_session_manager),
    fm: FileManager = Depends(get_file_manager),
):
    session = await sm.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if not session.container_id:
        raise HTTPException(400, "Container not ready")

    try:
        content = await fm.download_from_container(session.container_id, f"/{path}")
    except Exception as e:
        raise HTTPException(404, f"File not found: {e}")

    return Response(content=content, media_type="application/octet-stream")
