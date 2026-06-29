import asyncio
import io
import tarfile
from typing import AsyncGenerator

import docker
from docker.errors import NotFound

from app.models.session import ContainerConfig


class DockerManager:
    def __init__(self):
        self._client = docker.from_env()
        self._verify_connection()

    def _verify_connection(self):
        try:
            self._client.ping()
        except Exception as e:
            raise RuntimeError(f"Cannot connect to Docker: {e}")

    async def list_sandbox_containers(self) -> list[dict]:
        """List RUNNING sandbox containers (label smartagent.session) so SessionManager
        can rehydrate sessions after a backend restart (sessions live in-memory, but
        the containers survive). Returns [{session_id, container_id, app_port}]."""
        def _list():
            out = []
            for c in self._client.containers.list(filters={"label": "smartagent.session", "status": "running"}):
                sid = c.labels.get("smartagent.session")
                if not sid:
                    continue
                port = None
                try:
                    b = (c.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}).get("8080/tcp")
                    if b:
                        port = int(b[0]["HostPort"])
                except Exception:
                    pass
                out.append({"session_id": sid, "container_id": c.id, "app_port": port})
            return out
        return await asyncio.to_thread(_list)

    async def create_container(
        self, session_id: str, config: ContainerConfig
    ) -> tuple[str, int | None]:
        """Create a sandbox container. Publishes container port 8080 to a random
        host port so apps the agent builds (e.g. a RAG web UI) are reachable from
        the browser. Returns (container_id, host_port)."""
        def _create():
            container = self._client.containers.run(
                image=config.image,
                name=f"smartagent-{session_id}",
                detach=True,
                tty=True,
                stdin_open=True,
                mem_limit=config.mem_limit,
                nano_cpus=int(config.cpu_count * 1e9),
                network_mode=config.network_mode,
                working_dir="/workspace",
                volumes={
                    f"smartagent-uploads-{session_id}": {
                        "bind": "/uploads",
                        "mode": "rw",
                    },
                    # Shared pip cache across ALL sessions — a second install of the
                    # same package is near-instant (no re-download), removing a major
                    # source of pip timeouts that pushed the agent toward shortcuts.
                    "smartagent-pip-cache": {
                        "bind": "/root/.cache/pip",
                        "mode": "rw",
                    },
                },
                # Publish container's 8080 → random free host port
                ports={"8080/tcp": None},
                labels={"smartagent.session": session_id},
            )
            container.reload()
            host_port = None
            try:
                bindings = container.attrs["NetworkSettings"]["Ports"].get("8080/tcp")
                if bindings:
                    host_port = int(bindings[0]["HostPort"])
            except (KeyError, IndexError, TypeError, ValueError):
                host_port = None
            return container.id, host_port

        return await asyncio.to_thread(_create)

    async def destroy_container(self, container_id: str) -> None:
        def _destroy():
            try:
                container = self._client.containers.get(container_id)
                container.stop(timeout=5)
                container.remove(force=True)
            except NotFound:
                pass

        await asyncio.to_thread(_destroy)

    async def restart_stopped_sandbox(self, session_id: str) -> tuple[str, int | None] | None:
        """Nếu container sandbox của session_id còn TỒN TẠI nhưng đã dừng (Exited) —
        START LẠI nó (giữ nguyên /workspace, không mất sản phẩm) thay vì tạo mới (tránh
        409 name-conflict). Trả (container_id, host_port) nếu start được, None nếu không
        còn container nào để khôi phục."""
        def _restart():
            try:
                c = self._client.containers.get(f"smartagent-{session_id}")
            except NotFound:
                return None
            try:
                c.start()
            except Exception:
                pass
            c.reload()
            host_port = None
            try:
                b = c.attrs["NetworkSettings"]["Ports"].get("8080/tcp")
                if b:
                    host_port = int(b[0]["HostPort"])
            except (KeyError, IndexError, TypeError, ValueError):
                host_port = None
            return c.id, host_port

        return await asyncio.to_thread(_restart)

    async def exec_command(
        self, container_id: str, command: str, timeout: int = 60
    ) -> AsyncGenerator[str, None]:
        def _exec():
            container = self._client.containers.get(container_id)
            exec_instance = container.exec_run(
                ["bash", "-c", command],
                stream=True,
                demux=True,
            )
            return exec_instance

        result = await asyncio.to_thread(_exec)
        output_stream = result.output

        async def _stream():
            def _read_chunks():
                chunks = []
                for stdout_chunk, stderr_chunk in output_stream:
                    if stdout_chunk:
                        chunks.append(("stdout", stdout_chunk.decode("utf-8", errors="replace")))
                    if stderr_chunk:
                        chunks.append(("stderr", stderr_chunk.decode("utf-8", errors="replace")))
                return chunks

            chunks = await asyncio.to_thread(_read_chunks)
            for stream_type, content in chunks:
                yield f"{stream_type}:{content}"

        async for chunk in _stream():
            yield chunk

    async def exec_command_simple(
        self, container_id: str, command: str
    ) -> tuple[int, str]:
        def _exec():
            container = self._client.containers.get(container_id)
            exit_code, output = container.exec_run(
                ["bash", "-c", command],
                demux=False,
            )
            return exit_code, output.decode("utf-8", errors="replace")

        return await asyncio.to_thread(_exec)

    async def exec_command_capture(
        self, container_id: str, command: str, timeout: int = 60
    ) -> tuple[int, str, bool]:
        """Run a command and capture (exit_code, combined_output, timed_out).

        Enforces a real wall-clock timeout by wrapping the command in coreutils
        `timeout`. `timeout` exits 124 when the deadline is hit — we surface that
        as timed_out=True so callers (verify_work, shell_exec, pipeline steps)
        can report it instead of treating a hung command as success.

        Unlike exec_command (streaming, for live UX), this returns the exit code,
        which is the ground truth for "did it work".
        """
        # `timeout -k 5 <secs> bash -c <cmd>` — send TERM at deadline, KILL 5s later.
        # The inner command is passed as a single argv element so the user's command
        # is not re-parsed by an extra shell layer.
        def _exec():
            container = self._client.containers.get(container_id)
            exit_code, output = container.exec_run(
                ["timeout", "-k", "5", str(int(timeout)), "bash", "-c", command],
                demux=False,
            )
            text = output.decode("utf-8", errors="replace") if output else ""
            timed_out = exit_code in (124, 137)  # 124 = TERM at deadline, 137 = KILL
            return exit_code, text, timed_out

        return await asyncio.to_thread(_exec)

    async def exec_command_stream(
        self, container_id: str, command: str, timeout: int = 900,
        cancel_check=None,
    ):
        """Stream a command's output live AND return its exit code.

        Best of both worlds vs the other two helpers:
          - yields (stream_type, chunk) tuples as output arrives (live UX), then
          - yields a final ("__exit__", "<code>|<timed_out>") sentinel.

        Uses the low-level Docker exec API: exec_create → exec_start(stream=True)
        drained in a background thread into an asyncio.Queue, then exec_inspect to
        read the real ExitCode. The command is wrapped in coreutils `timeout` so a
        hung process is actually killed (exit 124/137) and we don't block forever.
        `cancel_check` is an optional callable returning True to abort early.
        """
        import queue as _queue

        api = self._client.api
        loop = asyncio.get_event_loop()

        def _create_and_run(q: _queue.Queue):
            try:
                exec_id = api.exec_create(
                    container_id,
                    ["timeout", "-k", "5", str(int(timeout)), "bash", "-c", command],
                )["Id"]
                stream = api.exec_start(exec_id, stream=True, demux=True)
                for stdout_chunk, stderr_chunk in stream:
                    if stdout_chunk:
                        q.put(("stdout", stdout_chunk.decode("utf-8", errors="replace")))
                    if stderr_chunk:
                        q.put(("stderr", stderr_chunk.decode("utf-8", errors="replace")))
                info = api.exec_inspect(exec_id)
                code = info.get("ExitCode", -1)
                q.put(("__exit__", f"{code}"))
            except Exception as e:
                q.put(("__error__", str(e)))
            finally:
                q.put((None, None))  # end-of-stream marker

        q: _queue.Queue = _queue.Queue()
        worker = loop.run_in_executor(None, _create_and_run, q)

        exit_code = -1
        try:
            while True:
                if cancel_check is not None and cancel_check():
                    yield ("__cancelled__", "")
                    return
                try:
                    item = await asyncio.to_thread(q.get, True, 0.3)
                except _queue.Empty:
                    continue
                stype, chunk = item
                if stype is None:
                    break
                if stype == "__exit__":
                    exit_code = int(chunk) if str(chunk).lstrip("-").isdigit() else -1
                    continue
                if stype == "__error__":
                    yield ("__error__", chunk)
                    return
                yield (stype, chunk)
        finally:
            try:
                await worker
            except Exception:
                pass
        timed_out = exit_code in (124, 137)
        yield ("__done__", f"{exit_code}|{int(timed_out)}")

    async def copy_file_to(
        self, container_id: str, content: bytes, remote_path: str
    ) -> None:
        import posixpath

        def _copy():
            container = self._client.containers.get(container_id)
            filename = posixpath.basename(remote_path)
            parent_dir = posixpath.dirname(remote_path)
            container.exec_run(["mkdir", "-p", parent_dir])
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                file_info = tarfile.TarInfo(name=filename)
                file_info.size = len(content)
                tar.addfile(file_info, io.BytesIO(content))
            tar_stream.seek(0)
            container.put_archive(parent_dir, tar_stream)

        await asyncio.to_thread(_copy)

    async def copy_file_from(
        self, container_id: str, remote_path: str
    ) -> bytes:
        def _copy():
            container = self._client.containers.get(container_id)
            bits, _ = container.get_archive(remote_path)
            tar_stream = io.BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)
            with tarfile.open(fileobj=tar_stream, mode="r") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        f = tar.extractfile(member)
                        return f.read() if f else b""
            return b""

        return await asyncio.to_thread(_copy)

    async def update_resources(
        self, container_id: str, mem_limit: str | None = None, cpu_count: float | None = None
    ) -> None:
        def _update():
            container = self._client.containers.get(container_id)
            kwargs = {}
            if mem_limit:
                kwargs["mem_limit"] = mem_limit
            if cpu_count:
                kwargs["nano_cpus"] = int(cpu_count * 1e9)
            if kwargs:
                container.update(**kwargs)

        await asyncio.to_thread(_update)

    async def get_container_status(self, container_id: str) -> dict:
        def _status():
            try:
                container = self._client.containers.get(container_id)
                container.reload()
                stats = container.stats(stream=False)
                cpu_pct = 0.0
                mem_mb = 0.0
                if stats.get("cpu_stats", {}).get("cpu_usage"):
                    cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                                stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                    system_delta = stats["cpu_stats"].get("system_cpu_usage", 0) - \
                                   stats.get("precpu_stats", {}).get("system_cpu_usage", 0)
                    if system_delta > 0:
                        num_cpus = stats["cpu_stats"].get("online_cpus", 1)
                        cpu_pct = (cpu_delta / system_delta) * num_cpus * 100.0
                if stats.get("memory_stats", {}).get("usage"):
                    mem_mb = stats["memory_stats"]["usage"] / (1024 * 1024)
                return {
                    "status": container.status,
                    "running": container.status == "running",
                    "cpu_percent": round(cpu_pct, 1),
                    "memory_mb": round(mem_mb, 1),
                }
            except NotFound:
                return {"status": "not_found", "running": False, "cpu_percent": 0, "memory_mb": 0}

        return await asyncio.to_thread(_status)

    async def cleanup(self):
        def _cleanup():
            containers = self._client.containers.list(
                filters={"label": "smartagent.session"}, all=True
            )
            for c in containers:
                try:
                    c.stop(timeout=3)
                    c.remove(force=True)
                except Exception:
                    pass

        await asyncio.to_thread(_cleanup)
