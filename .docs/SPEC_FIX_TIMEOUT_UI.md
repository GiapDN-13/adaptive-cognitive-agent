# SPEC — Fix Timeout lặp lại + 2 lỗi UI

**Session gặp lỗi:** `a0dc58c1` — task "RAG 1k user", fail sau 34 iterations với message
`"Đã gặp lỗi timeout khi xử lý context lớn..."`.

---

## Root cause (đã xác minh trong code)

### RC1 — Timeout: context windowing KHÔNG bao giờ bỏ message cũ
`loop.py::_apply_context_window` chỉ **trim nội dung block lớn** (toolResult/toolUse → 2000 chars),
nhưng **không bao giờ giảm SỐ LƯỢNG message**. Sau 34 iterations ≈ 68 messages, dù mỗi block
đã trim, tổng vẫn vượt 80K và số message khổng lồ → Bedrock xử lý chậm →
`converse_stream` stall ở 120s (`client.py:117`) → retry 1 lần (trim 50K vẫn không giảm count)
→ stall tiếp → trả fallback. Đúng pattern `12s→117s→reset→12s→116s` trong ảnh.

### RC2 — Activity panel spam "Thinking... (Xs)"
`useWebSocket.ts:158` mỗi `agent_heartbeat` (8s/lần) gọi `setAgentStatus('Thinking... (Xs)')`.
`RightPanel.tsx::ActivityTimeline` useEffect fire trên **mọi** thay đổi `agentStatus` → tạo
**1 entry mới mỗi 8s**. Heartbeat là keepalive, không phải hoạt động → không nên vào timeline.

### RC3 — Tin nhắn trùng / bubble rỗng
`useWebSocket.ts:65` `agent_message` chỉ dedup với **message cuối**, và `chatStore.finalizeStream`
tạo bubble cả khi content chỉ toàn whitespace → bubble status rỗng + duplicate khi
stream-finalize và agent_message lệch nhẹ.

---

## Giải pháp

### FIX 1 (backend, critical) — `_apply_context_window` drop message cũ
Sau khi trim block, nếu VẪN vượt budget → giữ `messages[0]` (task gốc) + một **suffix liên tục**
các message gần nhất vừa với budget. Đảm bảo hợp lệ với Bedrock:
- Suffix liên tục → giữ nguyên cặp `toolUse → toolResult` (chúng luôn kề nhau).
- Bỏ các message `user` ở đầu suffix (tránh orphan toolResult + tránh user-user kề `messages[0]`).
- Luôn giữ message cuối (active turn).
- **Test:** dựng hội thoại 70 messages giả → assert tổng giảm < 80K, bắt đầu = user,
  không có 2 user liên tiếp, không orphan toolResult.

### FIX 2 (frontend) — heartbeat KHÔNG vào timeline
- `useWebSocket.ts`: heartbeat cập nhật field riêng `agentElapsed` (số giây), KHÔNG đụng `agentStatus`.
- `ActivityTimeline`: chỉ log tool activity thật; dòng "Working..." hiển thị kèm `agentElapsed`.

### FIX 3 (frontend) — dedup chặt + bỏ bubble rỗng
- `chatStore.finalizeStream`: bỏ qua nếu `streamingContent.trim()` rỗng.
- `useWebSocket.ts agent_message`: bỏ qua content rỗng; dedup với 3 message gần nhất.

---

## Verification
1. `python test_context_window.py` (mới) — PASS toàn bộ assertion.
2. Chạy lại task RAG 1k user trên UI → không còn fallback timeout, Activity panel sạch,
   không bubble trùng/rỗng.

---

# CẬP NHẬT — Lỗi lần 2 (session 94f498a9, fail sau 9 iterations)

## Đây là lỗi KHÁC, không phải RC1 ở trên.
Log backend cho thấy:
```
08:42:07  _call_llm: 21 messages, ~39613 chars   ← context CHỈ 39K, KHÔNG lớn
08:44:11  LLM stalled, retrying...                 ← Bedrock im lặng 120s, 0 token
08:44:11  _call_llm: 21 messages, ~39613 chars     ← retry GỬI Y HỆT (no-op trim)
08:46:16  Retry also failed: stalled no data 120s  ← fallback
```

### Root cause thật (3 yếu tố)
- **RC-A — Bedrock first-token latency / throttle:** context nhỏ (39K) nhưng model định sinh
  output khổng lồ ("rebuild hoàn toàn frontend") với `max_tokens=64000`. maxTokens lớn khiến
  Bedrock reserve/queue nhiều capacity → first-token > 120s → stream stall "no data for 120s".
- **RC-B — Retry vô nghĩa:** code cũ retry bằng `_apply_context_window(50000)`, nhưng 39K < 50K
  → no-op → gửi lại ĐÚNG request cũ → stall đúng như cũ → chỉ thử 1 lần rồi bỏ cuộc.
- **RC-C — boto3 không bật adaptive retry** → ThrottlingException/5xx transient không được backoff.

### Fix
| Fix | File | Nội dung |
|-----|------|----------|
| A | `config.py`, `client.py`, `streaming.py` | `bedrock_max_tokens=16384` (từ 64000). Giảm capacity reservation → giảm stall. Giữ 16K (không thấp hơn) vì write_file ghi file lớn = output token; cắt giữa toolUse sẽ hỏng JSON. |
| B | `loop.py` | `_retry_after_stall()`: backoff 2/4/8s, thử 3 lần request Y HỆT (stall transient → thử lại thường thành công). CHỈ trim context khi >120K (nhỏ thì trim vô ích). Tôn trọng cancel flag. |
| C | `client.py` | boto3 `Config(retries={"max_attempts":4,"mode":"adaptive"})` — backoff tự động cho throttle. |

### Bằng chứng test
```
test_retry_stall.py:
[1] stall x2 then success: PASS (3 attempts)
[2] stall forever -> None (graceful): PASS
[3] small context NOT trimmed: PASS (21 msgs preserved)
[4] cancel aborts retries: PASS
test_context_window.py: ALL PASS (no regression)
Container live: bedrock_max_tokens=16384, _retry_after_stall present, adaptive retry True
```
