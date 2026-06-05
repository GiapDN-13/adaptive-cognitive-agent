import uuid
from datetime import datetime

from app.config import settings
from app.core.docker_manager import DockerManager
from app.core.persistence import delete_session_messages, save_session_meta
from app.models.session import ContainerConfig, Session


class SessionManager:
    def __init__(self, docker_manager: DockerManager):
        self._docker = docker_manager
        self._sessions: dict[str, Session] = {}

    async def create(self, config: ContainerConfig | None = None) -> Session:
        session_id = uuid.uuid4().hex[:12]
        container_config = config or ContainerConfig(image=settings.sandbox_image)

        container_id, app_port = await self._docker.create_container(session_id, container_config)

        session = Session(
            id=session_id,
            container_id=container_id,
            container_config=container_config,
            app_port=app_port,
        )
        self._sessions[session_id] = session

        await save_session_meta(
            session_id,
            title="New Session",
            created_at=session.created_at.isoformat(),
        )

        return session

    async def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def destroy(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session and session.container_id:
            await self._docker.destroy_container(session.container_id)
        await delete_session_messages(session_id)
        # Clean up agent-loop global state to prevent memory leak
        try:
            from app.agent.loop import cleanup_session_state
            cleanup_session_state(session_id)
        except Exception:
            pass

    async def touch(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.last_active = datetime.utcnow()

    async def list_sessions(self) -> list[Session]:
        return list(self._sessions.values())

    async def cleanup_idle(self) -> int:
        now = datetime.utcnow()
        idle_ids = []
        for sid, session in self._sessions.items():
            idle_min = (now - session.last_active).total_seconds() / 60
            if idle_min > settings.container_idle_timeout_min:
                idle_ids.append(sid)

        for sid in idle_ids:
            await self.destroy(sid)

        return len(idle_ids)

    @property
    def active_count(self) -> int:
        return len(self._sessions)
