import asyncio
import uuid
from typing import AsyncGenerator, Callable

from app.core.docker_manager import DockerManager


class DockerExecutor:
    """Executes commands in containers with real-time streaming."""

    def __init__(self, docker_manager: DockerManager):
        self._docker = docker_manager
        self._active_execs: dict[str, bool] = {}

    async def exec_streaming(
        self,
        container_id: str,
        command: str,
        ws_send: Callable,
        timeout: int = 60,
    ) -> tuple[str, int]:
        """Execute command, stream output via WebSocket, return full output + line count."""
        exec_id = uuid.uuid4().hex[:8]
        self._active_execs[exec_id] = True

        output_lines = []

        try:
            async for chunk in self._docker.exec_command(container_id, command):
                if not self._active_execs.get(exec_id):
                    break

                sep_idx = chunk.index(":")
                stream_type = chunk[:sep_idx]
                content = chunk[sep_idx + 1:]
                output_lines.append(content)

                await ws_send({
                    "type": "terminal_output",
                    "exec_id": exec_id,
                    "content": content,
                    "stream": stream_type,
                    "done": False,
                })

        except asyncio.TimeoutError:
            await ws_send({
                "type": "terminal_output",
                "exec_id": exec_id,
                "content": f"\n[TIMEOUT after {timeout}s]\n",
                "stream": "stderr",
                "done": False,
            })
            output_lines.append(f"\n[TIMEOUT after {timeout}s]\n")
        except Exception as e:
            await ws_send({
                "type": "terminal_output",
                "exec_id": exec_id,
                "content": f"\n[ERROR: {e}]\n",
                "stream": "stderr",
                "done": False,
            })
            output_lines.append(f"\n[ERROR: {e}]\n")
        finally:
            self._active_execs.pop(exec_id, None)
            await ws_send({
                "type": "terminal_output",
                "exec_id": exec_id,
                "content": "",
                "stream": "stdout",
                "done": True,
            })

        full_output = "".join(output_lines)
        return full_output, len(full_output.splitlines())

    def cancel_exec(self, exec_id: str):
        self._active_execs[exec_id] = False

    def cancel_all(self):
        for exec_id in list(self._active_execs.keys()):
            self._active_execs[exec_id] = False
