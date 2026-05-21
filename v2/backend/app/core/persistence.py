import json
import aiofiles
from pathlib import Path

SESSIONS_DIR = Path("./data/sessions")


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
