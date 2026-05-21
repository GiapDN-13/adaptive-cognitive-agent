from pathlib import Path

from app.core.docker_manager import DockerManager


class FileManager:
    def __init__(self, docker_manager: DockerManager):
        self._docker = docker_manager

    async def upload_to_container(
        self, container_id: str, filename: str, content: bytes
    ) -> str:
        remote_path = f"/uploads/{filename}"
        await self._docker.copy_file_to(container_id, content, remote_path)
        return remote_path

    async def download_from_container(
        self, container_id: str, remote_path: str
    ) -> bytes:
        return await self._docker.copy_file_from(container_id, remote_path)
