from datetime import datetime

from pydantic import BaseModel, Field


class ContainerConfig(BaseModel):
    image: str = "smartagent-sandbox:latest"
    mem_limit: str = "512m"
    cpu_count: float = 1.0
    network_mode: str = "bridge"


class Session(BaseModel):
    id: str
    container_id: str | None = None
    container_config: ContainerConfig = Field(default_factory=ContainerConfig)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)
    messages: list[dict] = Field(default_factory=list)
    status: str = "active"


class CreateSessionRequest(BaseModel):
    container_config: ContainerConfig | None = None


class SessionResponse(BaseModel):
    id: str
    container_id: str | None
    status: str
    created_at: datetime
