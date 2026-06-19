"""TRACE RUNNER (FULL) — như trace_run.py nhưng CẤP ĐỒ THẬT cho sandbox để agent
build THẬT (tạo tool, chạy, giám khảo) — vẫn KHÔNG mock:
  - Seed file tài liệu mẫu THẬT vào /workspace/docs (PDF text, CSV-as-Excel, TXT-as-Word
    + 1 file mỗi phòng ban để test phân quyền).
  - Bơm AWS creds THẬT vào sandbox (đọc từ /root/.aws đã mount) -> RAG gọi Bedrock thật.
  - Trả lời 5 câu hỏi dứt khoát để agent KHÔNG phải hỏi nữa -> tiến tới build.

Chạy detached trong backend:
  docker exec -d <backend> sh -c 'python -u /app/trace_run_full.py > /app/data/trace_full.log 2>&1'
Output: /app/data/trace_report_full.md + trace_events_full.json
"""
import asyncio, sys, json, time, os
sys.path.insert(0, '/app'); sys.path.insert(0, '.')

TASK = (
    "Xây cho MekongAI một chatbot RAG để nhân viên hỏi đáp tài liệu nội bộ, ~1000 users "
    "(đăng ký; cao điểm ~30-50 đồng thời). Tài liệu mẫu THẬT đã có sẵn ở /workspace/docs "
    "(gồm PDF text, file Excel CSV, file Word text — mỗi phòng ban một file). "
    "Phân quyền theo 4 phòng: HR, Finance, Engineering, Admin (Admin xem tất cả). "
    "AWS Bedrock credentials ĐÃ có trong môi trường sandbox (biến AWS_* + region us-east-1) — "
    "DÙNG Bedrock THẬT (Claude cho generate, Titan/Cohere cho embedding). KHÔNG mock. "
    "Hãy thiết kế, BUILD, tự verify, rồi gọi giám khảo mù nghiệm thu."
)

# Tài liệu mẫu THẬT cho 4 phòng ban (đủ để test retrieval + phân quyền + đa định dạng).
DOCS = {
    "hr_chinh_sach_nghi_phep.txt": (
        "PHÒNG HR — CHÍNH SÁCH NGHỈ PHÉP 2024\n"
        "Nhân viên chính thức được 12 ngày phép/năm. Nghỉ ốm có lương tối đa 30 ngày/năm "
        "(cần giấy bác sĩ nếu nghỉ quá 2 ngày liên tục). Phép năm không dùng hết được "
        "chuyển tối đa 5 ngày sang năm sau. Thai sản: 6 tháng theo luật.\n"
    ),
    "finance_dinh_muc_cong_tac.csv": (
        "Hạng mục,Định mức/tháng (VND),Ghi chú\n"
        "Công tác phí nội thành,2000000,Cần hóa đơn\n"
        "Công tác phí ngoại tỉnh,5000000,Bao gồm lưu trú\n"
        "Tiếp khách,3000000,Duyệt trước bởi trưởng phòng\n"
    ),
    "engineering_quy_trinh_deploy.txt": (
        "PHÒNG ENGINEERING — QUY TRÌNH DEPLOY\n"
        "Mọi thay đổi phải qua code review (tối thiểu 1 approver) trước khi merge vào main. "
        "Deploy production chỉ trong khung 9h-16h ngày làm việc. Rollback bằng tag phiên bản "
        "trước. Bắt buộc có health check sau deploy 5 phút.\n"
    ),
    "admin_noi_quy_chung.txt": (
        "PHÒNG ADMIN — NỘI QUY CHUNG\n"
        "Giờ làm việc 8h30-17h30, nghỉ trưa 12h-13h30. Tài liệu mật không được mang ra ngoài. "
        "Thẻ ra vào cá nhân, không cho mượn. Đỗ xe tại tầng hầm B1.\n"
    ),
}

# Câu hỏi -> trả lời dứt khoát (agent sẽ KHÔNG cần hỏi thêm).
def auto_answer(q: str) -> str:
    return (
        "Quyết hết để bạn build NGAY, không hỏi thêm: "
        "(1) Quy mô: 1000 đăng ký, peak ~30-50 đồng thời → ChromaDB persistent là đủ. "
        "(2) LLM/Embedding: DÙNG AWS Bedrock THẬT — creds đã có trong env sandbox (AWS_ACCESS_KEY_ID...), "
        "region us-east-1; generate bằng Claude (anthropic.claude-3-5-sonnet hoặc model có sẵn), "
        "embedding bằng Titan (amazon.titan-embed-text-v2:0) hoặc Cohere. KHÔNG mock. "
        "(3) File mẫu: ĐÃ có thật ở /workspace/docs (4 phòng, đa định dạng .txt/.csv). "
        "(4) Auth: tự build đơn giản, mỗi user 1 phòng, Admin xem tất cả, không cần SSO. "
        "(5) Scope: MVP production-ready, deploy bằng python (FastAPI port 8080), có phân quyền metadata. "
        "Build thật, tự verify bằng câu hỏi mỗi phòng + ca phân quyền (HR hỏi Finance phải bị chặn), rồi gọi giám khảo mù."
    )


class Tracer:
    def __init__(self):
        self.events = []; self.t0 = time.time(); self._sid = None
    def bind(self, sid): self._sid = sid
    async def __call__(self, msg: dict):
        msg = dict(msg or {})
        self.events.append({"t": round(time.time()-self.t0, 1), **msg})
        if msg.get("type") == "agent_question" and self._sid:
            from app.agent.loop import handle_user_response
            ans = auto_answer(msg.get("question", ""))
            self.events.append({"t": round(time.time()-self.t0,1), "type":"user_answer","content":ans})
            await asyncio.sleep(0.3)
            await handle_user_response(self._sid, ans)


def _read_host_creds():
    """Đọc creds từ /root/.aws/credentials (đã mount) để bơm vào sandbox."""
    import configparser
    p = "/root/.aws/credentials"
    if not os.path.exists(p): return {}
    cp = configparser.ConfigParser(); cp.read(p)
    s = cp["default"] if cp.has_section("default") else {}
    out = {}
    if s.get("aws_access_key_id"): out["AWS_ACCESS_KEY_ID"] = s.get("aws_access_key_id").strip()
    if s.get("aws_secret_access_key"): out["AWS_SECRET_ACCESS_KEY"] = s.get("aws_secret_access_key").strip()
    if s.get("aws_session_token"): out["AWS_SESSION_TOKEN"] = s.get("aws_session_token").strip()
    out["AWS_REGION"] = "us-east-1"; out["AWS_DEFAULT_REGION"] = "us-east-1"
    return out


async def main():
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
    cid = session.container_id

    # 1) Seed tài liệu mẫu THẬT
    await dm.exec_command_simple(cid, "mkdir -p /workspace/docs")
    for name, content in DOCS.items():
        await dm.copy_file_to(cid, content.encode(), f"/workspace/docs/{name}")

    # 2) Bơm AWS creds THẬT vào /etc/profile + 1 file env sandbox đọc được
    creds = _read_host_creds()
    if creds.get("AWS_ACCESS_KEY_ID"):
        env_lines = "\n".join(f'export {k}="{v}"' for k, v in creds.items())
        await dm.copy_file_to(cid, (env_lines + "\n").encode(), "/workspace/.awsenv")
        # ghi vao /root/.bashrc de moi shell_exec deu co (shell_exec chay bash -c)
        await dm.exec_command_simple(cid, "cat /workspace/.awsenv >> /root/.bashrc")
        # cung ghi /etc/environment cho chac
        plain = "\n".join(f'{k}={v}' for k, v in creds.items())
        await dm.copy_file_to(cid, (plain + "\n").encode(), "/etc/environment")
        print(f"[trace-full] injected AWS creds ({creds['AWS_ACCESS_KEY_ID'][:4]}...) into sandbox", flush=True)
    else:
        print("[trace-full] WARNING: no host creds found — agent sẽ vẫn phải hỏi", flush=True)

    tr = Tracer(); tr.bind(session.id)
    print(f"[trace-full] session={session.id} starting build...", flush=True)
    t_start = time.time()
    try:
        await asyncio.wait_for(run_agent_loop(session, TASK, tr), timeout=3000)
    except asyncio.TimeoutError:
        tr.events.append({"t": round(time.time()-tr.t0,1),"type":"trace_note","content":"TRACE: chạm trần 50 phút."})
    finally:
        try:
            _c, ls = await dm.exec_command_simple(cid,
                "find /workspace -type f -not -path '*/node_modules/*' -not -path '*/__pycache__/*' 2>/dev/null | head -80")
        except Exception:
            ls = ""
        from trace_run import render  # tái dùng renderer
        report = render(TASK, session, tr.events, ls, round(time.time()-t_start,1))
        os.makedirs("/app/data", exist_ok=True)
        with open("/app/data/trace_report_full.md","w",encoding="utf-8") as f: f.write(report)
        with open("/app/data/trace_events_full.json","w",encoding="utf-8") as f:
            json.dump(tr.events, f, ensure_ascii=False, indent=1)
        print(f"[trace-full] wrote report ({len(tr.events)} events)", flush=True)
        try: await dm.destroy_container(cid)
        except Exception: pass

asyncio.run(main())
