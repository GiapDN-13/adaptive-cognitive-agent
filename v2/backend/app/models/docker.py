from pydantic import BaseModel


class ExecResult(BaseModel):
    exec_id: str
    exit_code: int
    output: str
    truncated: bool = False
    full_output_path: str | None = None


class ContainerStatus(BaseModel):
    container_id: str
    status: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_seconds: int = 0
