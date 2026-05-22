# SmartAgent V2 — Project Context

## What is this?
AI agent platform: user sends task → agent researches (web search, shell exec) → returns comprehensive analysis. Built for security research, code audit, data analysis.

## Architecture
```
v2/frontend (React + Vite + Zustand) → WebSocket → v2/backend (FastAPI + uvicorn) → Agent Loop → LLM (AWS Bedrock Claude Sonnet) + Docker sandbox
```

- Each session = 1 Docker container (python:3.11-slim)
- Agent executes commands inside container, streams output to user
- ReACT loop: LLM → tool_use → execute → observe → repeat (max 25 iterations)

## Running locally
```bash
# Backend
cd v2/backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd v2/frontend && npm run dev
```
Requires: Docker Desktop running, `.env` files in `v2/backend/.env` with AWS credentials.

## Key files
- `v2/backend/app/agent/loop.py` — Main agent loop, tool execution, continuation logic
- `v2/backend/app/llm/client.py` — Bedrock streaming client with cancel support
- `v2/backend/app/llm/streaming.py` — Stream chunks to frontend + heartbeat
- `v2/backend/app/agent/tools.py` — Tool definitions + output truncation
- `v2/backend/app/api/routes_ws.py` — WebSocket endpoint, ping loop, cancel
- `v2/frontend/src/hooks/useWebSocket.ts` — WS message handling
- `v2/frontend/src/store/chatStore.ts` — Zustand state
- `v2/frontend/src/components/Chat/` — Chat UI components

## Current design decisions
- **No hard timeout on agent loop** — agent can run as long as needed (tools like apt-get take minutes)
- **Only timeout LLM calls** — 180s first token, 60s per chunk, dynamic total based on context size
- **Auto-continuation** — when LLM hits max_tokens (64K), automatically continues up to 5 times
- **Context windowing** — when input > 180K chars, trim old tool results (keep recent 6 messages intact)
- **Cancel via threading.Event** — instant cancel even when boto3 thread is blocked
- **Generation counter** — prevents stale agent loops from sending messages after cancel

## WebSocket protocol
Client → Server: `user_message`, `approval_response`, `user_response`, `cancel`
Server → Client: `agent_chunk`, `agent_message`, `agent_status`, `agent_heartbeat`, `terminal_output`, `approval_request`, `plan_proposal`, `error`

## Conventions
- Vietnamese UI, English code
- Never add `Co-Authored-By` in git commits
- Commit style: `feat(v2):`, `fix(v2):`, etc.
- Prefer research depth over speed — quality results matter more than response time
