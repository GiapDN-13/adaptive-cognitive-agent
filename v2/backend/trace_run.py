"""TRACE RUNNER — chạy agent THẬT trên 1 bài toán, ghi lại MỌI event (thinking,
reasoning, tool calls + input/output, tool tự tạo, critic/giám khảo, báo cáo) rồi
render thành báo cáo markdown cho sếp.

KHÔNG mock gì — đây là trace thật từ 1 lần chạy thật (đúng nguyên tắc chống-mock).

Chạy trong container backend (có Docker socket + creds):
  docker compose exec -T backend python /app/trace_run.py
Hoặc tuỳ biến task:
  docker compose exec -T backend python /app/trace_run.py "Yêu cầu..."

Output: /app/data/trace_report.md  (đọc ra host: docker compose exec ...)
"""
import asyncio, sys, json, time

sys.path.insert(0, '/app')
sys.path.insert(0, '.')

DEFAULT_TASK = (
    "Xây cho MekongAI một chatbot RAG để nhân viên hỏi đáp tài liệu nội bộ, "
    "khoảng 1000 users. Tài liệu gồm nhiều định dạng (PDF, Word, Excel). "
    "Cần phân quyền theo phòng ban. Hãy thiết kế và xây dựng."
)

# Auto-trả lời ask_user: agent SẼ hỏi (làm rõ 1k đồng thời?, xin creds...).
# Trả lời như một "user thật" để trace chạy trọn vẹn — câu trả lời được GHI vào báo cáo.
def auto_answer(question: str) -> str:
    q = (question or "").lower()
    if "đồng thời" in q or "concurren" in q or "registered" in q or "đăng ký" in q:
        return "1000 user ĐĂNG KÝ, cao điểm khoảng 30-50 truy vấn ĐỒNG THỜI."
    if "cred" in q or "bedrock" in q or "token" in q or "aws" in q or "key" in q:
        return ("Hiện sandbox CHƯA có AWS credentials thật. Bạn cứ thiết kế kiến trúc "
                "đúng chuẩn production dùng Bedrock; phần gọi LLM thật để tôi cấp creds sau. "
                "TUYỆT ĐỐI không mock để 'demo chạy'.")
    if "phòng ban" in q or "rbac" in q or "phân quyền" in q:
        return "4 phòng: HR, Finance, Engineering, Admin. Admin xem tất cả; các phòng chỉ xem tài liệu của mình."
    return "Bạn tự quyết theo phương án tốt nhất cho production 1k users, miễn không mock phụ thuộc thật."


class Tracer:
    """Thu mọi ws_send event + tự trả lời ask_user, kèm timestamp tương đối."""
    def __init__(self):
        self.events = []
        self.t0 = time.time()
        self._session_id = None

    def bind(self, session_id):
        self._session_id = session_id

    async def __call__(self, msg: dict):
        msg = dict(msg or {})
        self.events.append({"t": round(time.time() - self.t0, 1), **msg})
        # Khi agent hỏi -> tự trả lời (mô phỏng user) để loop chạy tiếp.
        if msg.get("type") == "agent_question" and self._session_id:
            from app.agent.loop import handle_user_response
            ans = auto_answer(msg.get("question", ""))
            self.events.append({"t": round(time.time() - self.t0, 1),
                                "type": "user_answer", "content": ans})
            # tra loi sau 1 nhip de loop kip dang ky _pending_responses
            await asyncio.sleep(0.3)
            await handle_user_response(self._session_id, ans)


async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TASK

    import app.deps as deps
    from app.core.docker_manager import DockerManager
    from app.core.session_manager import SessionManager
    from app.agent.tool_registry import tool_registry
    from app.agent.builtin_tools import register_all_builtins
    from app.agent.loop import run_agent_loop

    register_all_builtins(tool_registry)
    dm = DockerManager(); deps._docker_manager = dm
    sm = SessionManager(dm); deps._session_manager = sm

    session = await sm.create()
    tr = Tracer(); tr.bind(session.id)

    print(f"[trace] session={session.id} task={task[:60]}...", flush=True)
    t_start = time.time()
    try:
        await asyncio.wait_for(run_agent_loop(session, task, tr), timeout=2400)
    except asyncio.TimeoutError:
        tr.events.append({"t": round(time.time()-tr.t0,1), "type": "trace_note",
                          "content": "TRACE: chạm trần 40 phút, dừng ghi."})
    finally:
        # Snapshot trạng thái sản phẩm trong workspace để đưa vào báo cáo
        try:
            _c, ls = await dm.exec_command_simple(session.container_id,
                "find /workspace -type f -not -path '*/node_modules/*' 2>/dev/null | head -60")
        except Exception:
            ls = ""
        report = render(task, session, tr.events, ls, round(time.time()-t_start,1))
        out = "/app/data/trace_report.md"
        import os; os.makedirs("/app/data", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(report)
        # Cũng lưu raw events để soi lại
        with open("/app/data/trace_events.json", "w", encoding="utf-8") as f:
            json.dump(tr.events, f, ensure_ascii=False, indent=1)
        print(f"[trace] wrote {out} ({len(tr.events)} events)", flush=True)
        try:
            await dm.destroy_container(session.container_id)
        except Exception:
            pass


def _fmt_tool_input(inp):
    if not isinstance(inp, dict):
        return str(inp)[:800]
    parts = []
    for k, v in inp.items():
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        if len(s) > 1200:
            s = s[:1200] + f"\n…(+{len(s)-1200} ký tự)"
        parts.append(f"**{k}**:\n```\n{s}\n```")
    return "\n".join(parts)


def render(task, session, events, workspace_listing, elapsed):
    """Render trace -> báo cáo markdown đầy đủ cho sếp."""
    L = []
    A = L.append
    A("# Báo cáo Agentic — Trace thật một lần chạy\n")
    A(f"**Bài toán:** {task}\n")
    A(f"**Session:** `{session.id}` · **Thời gian chạy:** {elapsed}s · **Số event:** {len(events)}\n")
    A("> Đây là TRACE THẬT từ một lần agent chạy thật trên task này — không dàn dựng, "
      "không mock. Mọi bước thinking, reasoning, tool, phán quyết đều ghi nguyên trạng.\n")
    A("\n---\n")

    # --- Thống kê nhanh ---
    counts = {}
    tools_called = []
    for e in events:
        t = e.get("type")
        counts[t] = counts.get(t, 0) + 1
        if t == "agent_status" and e.get("tool") and e.get("tool") != "thinking":
            tools_called.append(e["tool"])
    A("## 1. Tổng quan\n")
    A(f"- Số bước thinking: **{counts.get('agent_thinking',0)//2 or counts.get('agent_thinking',0)}**")
    A(f"- Lượt gọi công cụ (status): **{len([e for e in events if e.get('type')=='agent_status' and e.get('tool')])}**")
    A(f"- Lần agent HỎI người dùng: **{counts.get('agent_question',0)}**")
    A(f"- Retrieval/QA: **{counts.get('agent_retrieval',0)}** · Critique: **{counts.get('agent_critique',0)}**")
    A(f"- Công cụ đã dùng: {', '.join(dict.fromkeys(tools_called)) or '—'}\n")
    A("\n---\n")

    # --- Dòng thời gian đầy đủ ---
    A("## 2. Toàn bộ dòng suy nghĩ & hành động (theo thứ tự)\n")
    step = 0
    stream_buf = []

    def flush_stream():
        nonlocal stream_buf
        if stream_buf:
            txt = "".join(stream_buf).strip()
            if txt:
                A(f"\n**💬 Agent (trả lời/stream):**\n\n{txt}\n")
            stream_buf = []

    for e in events:
        t = e.get("type")
        ts = e.get("t", "")
        if t == "agent_thinking":
            if e.get("done"):
                continue
            c = (e.get("content") or "").strip()
            if not c:
                continue
            flush_stream()
            step += 1
            A(f"\n### 🧠 [{ts}s] Bước {step} — THINKING\n\n> {c.replace(chr(10), chr(10)+'> ')}\n")
        elif t == "agent_status":
            tool = e.get("tool", ""); detail = e.get("detail", "")
            if tool and tool != "thinking":
                flush_stream()
                step += 1
                A(f"\n### 🔧 [{ts}s] Bước {step} — DÙNG CÔNG CỤ: `{tool}`\n")
                if detail:
                    A(f"\n_Chi tiết:_ {detail}\n")
        elif t == "agent_chunk":
            if not e.get("done"):
                stream_buf.append(e.get("content", ""))
        elif t == "agent_question":
            flush_stream()
            step += 1
            A(f"\n### ❓ [{ts}s] Bước {step} — AGENT HỎI NGƯỜI DÙNG\n\n**{e.get('question','')}**\n")
            opts = e.get("options")
            if opts:
                A("\nLựa chọn: " + " · ".join(opts) + "\n")
        elif t == "user_answer":
            A(f"\n**🧑 Người dùng trả lời:** {e.get('content','')}\n")
        elif t == "agent_retrieval":
            flush_stream()
            A(f"\n### 🔎 [{ts}s] RETRIEVAL — truy vấn: `{e.get('query','')}` "
              f"({e.get('count',0)} kết quả)\n")
            if e.get("error"):
                A(f"\n_Lỗi:_ {e['error']}\n")
        elif t == "agent_critique":
            flush_stream()
            A(f"\n### 🧪 [{ts}s] QA REVIEW (critic) — {'✅ resolved' if e.get('resolved') else '❌'}\n\n{e.get('finding','')}\n")
        elif t == "plan_proposal":
            flush_stream()
            A(f"\n### 📋 [{ts}s] ĐỀ XUẤT KẾ HOẠCH: {e.get('title','')}\n")
            for s in e.get("steps", []):
                A(f"- {s.get('description', s)}")
        elif t == "agent_message":
            flush_stream()
            c = (e.get("content") or "").strip()
            if c:
                A(f"\n### ✅ [{ts}s] AGENT — THÔNG ĐIỆP HOÀN CHỈNH\n\n{c}\n")
        elif t == "error":
            flush_stream()
            A(f"\n### ⚠️ [{ts}s] LỖI: {e.get('message','')}\n")
        elif t == "trace_note":
            A(f"\n_{e.get('content','')}_\n")
    flush_stream()

    A("\n---\n")
    A("## 3. Sản phẩm tạo ra trong workspace\n")
    files = [l for l in (workspace_listing or "").splitlines() if l.strip()]
    if files:
        A("```")
        for f in files:
            A(f)
        A("```")
    else:
        A("_(workspace trống hoặc không đọc được)_")
    A("\n")
    return "\n".join(L)


asyncio.run(main())
