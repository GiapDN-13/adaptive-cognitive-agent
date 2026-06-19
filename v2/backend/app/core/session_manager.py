import uuid
from datetime import datetime

from app.config import settings
from app.core.docker_manager import DockerManager
from app.core.persistence import delete_session_messages, load_session_messages, save_session_meta
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

    async def rehydrate(self) -> int:
        """Sau khi backend restart (sessions in-memory mất), khôi phục lại session từ
        các container sandbox CÒN SỐNG. Container đặt tên smartagent-{id} + có label,
        nên ta map lại được — tránh lỗi 404 'session not found' khi frontend giữ id cũ.

        QUAN TRỌNG: phải nạp lại CẢ `messages` từ persistence. Nếu bỏ qua, agent loop
        chạy với history RỖNG → khi user gõ 'Tiếp tục' nó tưởng đây là phiên mới và
        hỏi 'tiếp tục cái gì' (dù container vẫn còn sản phẩm dở). Frontend được replay
        riêng để hiển thị, nhưng đó KHÔNG nạp vào session.messages của agent."""
        try:
            running = await self._docker.list_sandbox_containers()
        except Exception:
            return 0
        n = 0
        for c in running:
            sid = c["session_id"]
            if sid in self._sessions:
                continue
            try:
                messages = await load_session_messages(sid)
            except Exception:
                messages = []
            self._sessions[sid] = Session(
                id=sid,
                container_id=c["container_id"],
                container_config=ContainerConfig(image=settings.sandbox_image),
                app_port=c.get("app_port"),
                messages=messages,
            )
            n += 1
        return n

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
