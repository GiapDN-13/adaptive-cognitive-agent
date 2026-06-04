# SmartAgent V2 — Codebase Weakness Report

**Date**: 2026-05-30
**Author**: Claude Code Audit
**Scope**: Full codebase review — v2/backend + v2/frontend

---

## Executive Summary

Phân tích toàn bộ codebase phát hiện **18 điểm yếu** được phân loại theo mức độ nghiêm trọng:
- **CRITICAL (4)**: Có thể bị exploit ngay lập tức, gây rò rỉ credentials hoặc RCE
- **HIGH (5)**: Ảnh hưởng nghiêm trọng tới security/stability nhưng cần điều kiện cụ thể
- **MEDIUM (6)**: Architectural weaknesses, có thể gây sự cố khi scale
- **LOW (3)**: Code quality, maintainability issues

---

## CRITICAL

### C1. Hardcoded API Keys trong Source Code
**File**: `v2/backend/app/config.py:22-25`
**Vấn đề**:
```python
azure_openai_api_key: str = "CywSY3nXq9IvpNqRdnl6ljjiaNJQMK2159Ai19VWANEZxgBpU0GGJQQJ99CEACHYHv6XJ3w3AAAAACOGJ1aY"
cursor_api_key: str = "crsr_ebfefd9f128472e33e5e838547ebe6ebd7a09f3d5760a7713e04bbb72e980fb3"
```
**Impact**: Bất kỳ ai clone repo đều thấy API keys. Keys này hoạt động và có thể bị abuse (Azure billing, unauthorized LLM access). Cũng xuất hiện trong `docker-compose.yml:15-16`.
**Fix**: Xóa default values, chỉ load từ `.env`. Rotate keys ngay lập tức.

---

### C2. Không có Authentication/Authorization
**Files**: `v2/backend/app/api/routes_http.py`, `v2/backend/app/api/routes_ws.py`
**Vấn đề**: Toàn bộ API endpoints (HTTP + WebSocket) không có bất kỳ authentication nào:
- Ai cũng có thể tạo session → spawn Docker container
- Ai cũng có thể connect WebSocket → điều khiển agent
- Ai cũng có thể xóa session của người khác (session_id dễ đoán: 12 hex chars)
- Ai cũng có thể download files từ container

**Impact**: Nếu expose ra internet → resource exhaustion (spawn vô số containers), data theft (đọc files người khác), unauthorized compute usage.
**Fix**: Thêm authentication middleware (JWT/API key), rate limiting, session ownership validation.

---

### C3. Command Injection qua `write_file` tool
**File**: `v2/backend/app/agent/loop.py:399-407`
**Vấn đề**:
```python
escaped_content = content.replace("'", "'\\''")
await _docker_manager.exec_command_simple(
    session.container_id,
    f"mkdir -p $(dirname '{path}') && printf '%s' '{escaped_content}' > '{path}'"
)
```
- Chỉ escape single quotes trong `content`, KHÔNG escape `path`
- Path có thể chứa: `'; rm -rf / #` → shell injection
- Content escape không đầy đủ: không handle `%` (printf format specifier), backslash sequences

**Impact**: LLM agent (hoặc attacker qua prompt injection) có thể thực thi arbitrary commands ngoài sandbox isolation boundary.
**Fix**: Sử dụng Docker API `put_archive` thay vì shell command, hoặc validate+escape path riêng.

---

### C4. Path Traversal trong File Download
**File**: `v2/backend/app/api/routes_http.py:82-100`
**Vấn đề**:
```python
@router.get("/sessions/{session_id}/files/{path:path}")
async def download_file(session_id: str, path: str, ...):
    content = await fm.download_from_container(session.container_id, f"/{path}")
```
- Không validate path — attacker có thể request `/sessions/abc/files/etc/passwd` hoặc `../../../etc/shadow`
- Container sandbox giới hạn phạm vi nhưng nếu container chạy privileged thì rò rỉ host files

**Impact**: Đọc bất kỳ file nào trong container (bao gồm `/proc`, `/etc`, env vars).
**Fix**: Whitelist allowed directories (`/workspace`, `/uploads`, `/tmp`), reject paths with `..`.

---

## HIGH

### H1. Docker Socket Mounting — Container Escape Risk
**File**: `v2/docker-compose.yml:17`
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```
**Vấn đề**: Backend container có full Docker socket access → có thể tạo privileged containers, mount host filesystem, effectively gaining root trên host.
**Impact**: Nếu backend bị compromise (qua C2 hoặc C3), attacker có full host access.
**Fix**: Sử dụng Docker-in-Docker hoặc rootless Docker. Hoặc abstract qua remote Docker API với limited permissions.

---

### H2. Session ID Prediction / No Session Isolation
**File**: `v2/backend/app/core/session_manager.py:16`
```python
session_id = uuid.uuid4().hex[:12]
```
**Vấn đề**:
- 12 hex chars = 48 bits entropy — có thể brute force (2^48 possibilities nhưng với known timing)
- Không validate session ownership tại WebSocket layer — biết session_id = full access
- Session list endpoint có thể expose active session IDs

**Impact**: Session hijacking, unauthorized access to other users' agent sessions.
**Fix**: Longer session IDs (UUID full), session-bound auth tokens, ownership validation.

---

### H3. Unbounded Resource Consumption
**Files**: `v2/backend/app/agent/loop.py:27`, `v2/backend/app/api/routes_http.py:20-30`
**Vấn đề**:
- `MAX_ITERATIONS = 150` — mỗi iteration gọi LLM ($) + có thể exec commands
- Không limit số sessions per user (vì không có auth)
- Không limit file upload size
- Không limit concurrent agent loops per session
- web_search limit = 10 per loop, nhưng vẫn tốn ~10 external requests
- Container memory 512MB * unlimited sessions = OOM host

**Impact**: Financial DoS (LLM costs), resource exhaustion (Docker containers, memory).
**Fix**: Rate limiting, per-user quotas, max concurrent sessions cap, file size limits.

---

### H4. Memory Leak — Global Dicts Never Cleaned
**File**: `v2/backend/app/agent/loop.py:38-45`
```python
_pending_approvals: dict[str, asyncio.Event] = {}
_approval_results: dict[str, dict] = {}
_pending_responses: dict[str, asyncio.Event] = {}
_response_results: dict[str, str] = {}
_cancel_flags: dict[str, bool] = {}
_session_pending_ids: dict[str, list[str]] = {}
_session_generation: dict[str, int] = {}
_cancel_events: dict[str, threading.Event] = {}
```
**Vấn đề**: Không có cleanup mechanism. Entries tích lũy vô tận khi sessions được tạo/destroy. `_cancel_flags`, `_session_generation`, `_cancel_events` KHÔNG bao giờ bị xóa.
**Impact**: Memory leak → OOM crash sau đủ lâu. Zombie entries có thể interfere với new sessions nếu ID collision.
**Fix**: Cleanup khi session destroy, hoặc sử dụng WeakRef/TTL dict.

---

### H5. LLM Client Singleton — Not Thread-Safe
**File**: `v2/backend/app/agent/loop.py:30-35`
```python
_llm_client = None

def _get_llm():
    global _llm_client
    if _llm_client is None:
        _llm_client = create_llm_client()
    return _llm_client
```
**Vấn đề**: Race condition khi multiple concurrent requests đồng thời check `_llm_client is None` — có thể tạo multiple clients. Với asyncio single-thread thì ít rủi ro nhưng nếu dùng uvicorn workers > 1 thì sẽ crash.
**Impact**: Potential duplicate boto3 client creation, connection pool exhaustion.
**Fix**: Sử dụng module-level initialization trong `lifespan`, hoặc `asyncio.Lock`.

---

## MEDIUM

### M1. In-Memory Session Storage — No Persistence Across Restarts
**File**: `v2/backend/app/core/session_manager.py:12`
```python
self._sessions: dict[str, Session] = {}
```
**Vấn đề**: Sessions chỉ tồn tại trong memory. Server restart = mất toàn bộ active sessions. Messages được save ra file nhưng session objects (container_id mapping) thì không.
**Impact**: Mỗi lần deploy mới → orphan Docker containers (không ai cleanup), users mất session.
**Fix**: Persist session state to disk/DB, reconcile containers on startup.

---

### M2. Blocking Docker Operations trong Async Loop
**File**: `v2/backend/app/core/docker_manager.py:80-95`
**Vấn đề**: `exec_command` reads ALL chunks into memory (`_read_chunks`) trước khi yield. Với large outputs (e.g., `find /` hoặc compile log), toàn bộ output buffer trong memory trước khi stream.
```python
async def _stream():
    def _read_chunks():
        chunks = []
        for stdout_chunk, stderr_chunk in output_stream:
            ...
        return chunks  # ALL at once
    chunks = await asyncio.to_thread(_read_chunks)
    for stream_type, content in chunks:
        yield f"{stream_type}:{content}"
```
**Impact**: Memory spike, delayed streaming (user thấy output chậm), potential OOM với very large outputs.
**Fix**: True streaming — yield từng chunk qua queue thay vì collect all.

---

### M3. `_build_messages` Silently Truncates History
**File**: `v2/backend/app/agent/loop.py:447-448`
```python
for msg in session.messages[-20:]:
```
**Vấn đề**: Hard-coded limit 20 messages gần nhất. Không có cảnh báo khi context bị cắt. Long conversations mất context quan trọng từ đầu.
**Impact**: Agent mất ngữ cảnh quan trọng, trả lời sai hoặc lặp lại công việc đã làm.
**Fix**: Dynamic windowing dựa trên token count, không hard-coded. Summarize older messages.

---

### M4. File Persistence Race Condition
**File**: `v2/backend/app/core/persistence.py`
**Vấn đề**: Multiple async tasks có thể đồng thời `_load_index()` + `_save_index()` — last writer wins. Ví dụ: 2 sessions save cùng lúc → session_index.json mất 1 entry.
```python
async def save_session_meta(session_id: str, title: str, created_at: str) -> None:
    index = await _load_index()  # <-- read
    index[session_id] = {...}
    await _save_index(index)     # <-- write (may overwrite concurrent change)
```
**Impact**: Mất session history entries, corrupted index.
**Fix**: File locking (fcntl/msvcrt), hoặc switch to SQLite/proper DB.

---

### M5. No Input Validation on WebSocket Messages
**File**: `v2/backend/app/api/routes_ws.py:63-64`
```python
data = await websocket.receive_text()
message = json.loads(data)
```
**Vấn đề**:
- Không validate message schema — malformed messages silently fail hoặc crash
- Không limit message size — 1GB message = OOM
- `message["content"]` access without `.get()` → potential KeyError crash
- `resource_update` handler trusts client-provided `memory_mb`/`cpu` values completely

**Impact**: Server crash via malformed messages, resource manipulation.
**Fix**: Pydantic message validation, max message size, input bounds checking.

---

### M6. Web Search — Sync `requests` Library in Async Context
**File**: `v2/backend/app/agent/loop.py:277-284`
```python
import requests
resp = requests.post(url, headers=headers, data={'q': query}, timeout=10)
```
**Vấn đề**: Sử dụng synchronous `requests` library trong async function — blocks event loop cho 10s mỗi search. Với 10 searches liên tiếp = 100s blocking.
**Impact**: Tất cả WebSocket connections bị freeze trong khi search đang chạy.
**Fix**: Sử dụng `httpx` (đã có trong dependencies) hoặc `asyncio.to_thread(requests.post, ...)`.

---

## LOW

### L1. Inconsistent Error Handling in Frontend
**File**: `v2/frontend/src/hooks/useWebSocket.ts:51-52`
```typescript
case 'file_ready' as any:
  break
```
**Vấn đề**: Multiple `as any` type casts, unhandled message types, no TypeScript type safety cho server messages. `ServerMessage` type likely incomplete.
**Impact**: Runtime errors not caught at compile time, missed features.
**Fix**: Complete the `ServerMessage` discriminated union type.

---

### L2. No Graceful Degradation for LLM Provider Failures
**File**: `v2/backend/app/llm/client.py:256-261`
```python
def create_llm_client():
    if settings.llm_provider == "cursor":
        return CursorClient()
    if settings.llm_provider == "azure":
        return AzureOpenAIClient()
    return BedrockClient()
```
**Vấn đề**: Không có fallback mechanism — nếu provider chết thì toàn bộ hệ thống chết. Không có health check, circuit breaker, hoặc auto-switch.
**Impact**: Single point of failure cho toàn bộ agent functionality.
**Fix**: Health check + automatic fallback chain (primary → secondary → tertiary).

---

### L3. Frontend Auto-Starts Session Without User Intent
**File**: `v2/frontend/src/App.tsx:23-26`
```typescript
useEffect(() => {
  if (!sessionId && containerStatus === 'idle') {
    startSession()
  }
}, [sessionId, containerStatus, startSession])
```
**Vấn đề**: Mỗi lần load page → tạo Docker container ngay lập tức. Tab để mở 10 phút → wasted resources. Refresh page → session cũ orphaned + session mới tạo.
**Impact**: Resource waste, orphan containers.
**Fix**: Lazy session creation — chỉ tạo khi user thực sự gửi message đầu tiên.

---

## Architecture Concerns (Non-Bug)

| Concern | Description |
|---------|-------------|
| No test suite | Zero tests for backend/frontend. No CI/CD pipeline visible. |
| No logging aggregation | `logger.info` to stdout only. No structured logging, no metrics. |
| No container image registry | Sandbox image built at compose-up time, not versioned. |
| Single-process backend | No horizontal scaling strategy. All state in-memory. |
| No HTTPS/TLS termination | docker-compose exposes ports directly, no reverse proxy. |
| `lxml` dependency for scraping | Heavy C library for parsing HTML search results. Could use lighter alternatives. |
| Vendor directory not gitignored | 246 skill files + 61 agent files loaded at startup — impacts cold start time. |

---

## Prioritized Fix Roadmap

### Phase 1 — Immediate (Security Critical)
1. **Rotate + remove hardcoded API keys** (C1)
2. **Add auth middleware** (C2)
3. **Fix path injection in write_file/download** (C3, C4)

### Phase 2 — Short-term (Stability)
4. Fix memory leaks in global dicts (H4)
5. Add WebSocket message validation (M5)
6. Fix blocking web_search (M6)
7. Add session cleanup on restart (M1)

### Phase 3 — Medium-term (Robustness)
8. Rate limiting + resource quotas (H3)
9. Docker socket isolation (H1)
10. True streaming in docker_exec (M2)
11. Dynamic context windowing (M3)
12. File persistence locking (M4)

### Phase 4 — Long-term (Quality)
13. Add test suite
14. LLM provider fallback (L2)
15. Lazy session creation (L3)
16. Structured logging + monitoring
17. CI/CD pipeline
18. HTTPS termination

---

## Methodology

- Full source reading of all `.py` and `.tsx/.ts` files in the application layer
- Cross-referenced tool definitions with execution handlers
- Traced data flow from WebSocket input → agent loop → Docker execution → response
- Checked for OWASP Top 10 patterns
- Evaluated architecture for scalability and resilience
