from app.core.docker_manager import DockerManager
from app.core.file_manager import FileManager
from app.core.session_manager import SessionManager

_docker_manager: DockerManager | None = None
_session_manager: SessionManager | None = None
_file_manager: FileManager | None = None


def init_managers():
    global _docker_manager, _session_manager, _file_manager
    _docker_manager = DockerManager()
    _session_manager = SessionManager(_docker_manager)
    _file_manager = FileManager(_docker_manager)


def get_docker_manager() -> DockerManager:
    assert _docker_manager is not None
    return _docker_manager


def get_session_manager() -> SessionManager:
    assert _session_manager is not None
    return _session_manager


def get_file_manager() -> FileManager:
    assert _file_manager is not None
    return _file_manager
