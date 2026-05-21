from pydantic import BaseModel


# --- Client → Server ---

class UserMessage(BaseModel):
    type: str = "user_message"
    content: str
    attachments: list[str] | None = None


class ApprovalResponse(BaseModel):
    type: str = "approval_response"
    request_id: str
    approved: bool
    modified_command: str | None = None


class UserResponse(BaseModel):
    type: str = "user_response"
    content: str


class CancelRequest(BaseModel):
    type: str = "cancel"


class ResourceUpdate(BaseModel):
    type: str = "resource_update"
    cpu: float
    memory_mb: int


# --- Server → Client ---

class AgentChunk(BaseModel):
    type: str = "agent_chunk"
    content: str
    done: bool = False


class AgentMessage(BaseModel):
    type: str = "agent_message"
    content: str
    metadata: dict | None = None


class TerminalOutput(BaseModel):
    type: str = "terminal_output"
    exec_id: str
    content: str
    stream: str = "stdout"
    done: bool = False


class ApprovalRequest(BaseModel):
    type: str = "approval_request"
    request_id: str
    action: str
    command: str
    estimated_time: str | None = None
    risk_level: str = "low"


class PlanProposal(BaseModel):
    type: str = "plan_proposal"
    plan_id: str
    title: str
    steps: list[dict]


class StepProgress(BaseModel):
    type: str = "step_progress"
    plan_id: str
    step_id: str
    status: str


class AgentQuestion(BaseModel):
    type: str = "agent_question"
    question: str
    options: list[str] | None = None


class FileReady(BaseModel):
    type: str = "file_ready"
    path: str
    download_url: str
    size_bytes: int


class ErrorMessage(BaseModel):
    type: str = "error"
    message: str
    recoverable: bool = True
