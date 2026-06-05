import json
from datetime import datetime
from pathlib import Path

import aiofiles

SESSIONS_DIR = Path("./data/sessions")
SESSION_INDEX_PATH = Path("./data/session_index.json")


async def save_session_messages(session_id: str, messages: list[dict]) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{session_id}.json"
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(messages, ensure_ascii=False, indent=2))


async def load_session_messages(session_id: str) -> list[dict]:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return []
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        content = await f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return []


async def delete_session_messages(session_id: str) -> None:
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
    await _remove_from_index(session_id)


async def save_session_meta(session_id: str, title: str, created_at: str) -> None:
    index = await _load_index()
    index[session_id] = {
        "id": session_id,
        "title": title,
        "created_at": created_at,
        "updated_at": datetime.utcnow().isoformat(),
    }
    await _save_index(index)


async def update_session_title(session_id: str, title: str) -> None:
    index = await _load_index()
    if session_id in index:
        index[session_id]["title"] = title
        index[session_id]["updated_at"] = datetime.utcnow().isoformat()
        await _save_index(index)


async def list_session_history() -> list[dict]:
    index = await _load_index()
    sessions = sorted(index.values(), key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


async def _load_index() -> dict:
    if not SESSION_INDEX_PATH.exists():
        return {}
    async with aiofiles.open(SESSION_INDEX_PATH, "r", encoding="utf-8") as f:
        content = await f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


async def _save_index(index: dict) -> None:
    SESSION_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(SESSION_INDEX_PATH, "w", encoding="utf-8") as f:
        await f.write(json.dumps(index, ensure_ascii=False, indent=2))


async def _remove_from_index(session_id: str) -> None:
    index = await _load_index()
    index.pop(session_id, None)
    await _save_index(index)
