"""P5 — Phép thử nghiệm thu năng lực TỰ CHỦ của SmartAgent.

Giao task "build RAG chatbot" mà KHÔNG hand-feed cách làm. Capture mọi event
để chấm các tiêu chí tự chủ: agent có TỰ research → build → verify_webapp → đúc kết không.

Chạy headless (không qua WebSocket UI). In log + dump JSON trajectory.
"""
import asyncio
import json
import sys
import time

# ensure deps wired like the app lifespan does
import app.deps as deps
from app.core.docker_manager import DockerManager
from app.core.session_manager import SessionManager
from app.models.session import ContainerConfig

# CRITICAL: register tools exactly like app.main lifespan does — otherwise the
# tool_registry singleton is EMPTY in this standalone process and the agent has
# no tools to call (it will hallucinate tool-use as plain text).
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
from app.agent.meta_tools import register_meta_tools
from app.agent.extension_loader import load_all_extensions
register_all_builtins(tool_registry)
register_meta_tools(tool_registry)
load_all_extensions()
print(f"[P5] tool_registry ready: {tool_registry.count} tools", flush=True)

TASK = (
    "Xây cho tôi một RAG chatbot chạy được trên web. "
    "Tôi sẽ cung cấp tài liệu, người dùng hỏi và bot trả lời DỰA TRÊN tài liệu đó, "
    "câu hỏi ngoài phạm vi tài liệu thì phải từ chối (không bịa). "
    "Phục vụ trên cổng 8080 với giao diện chat dùng được. "
    "Tự quyết định công nghệ phù hợp; nhớ môi trường chỉ có 512MB RAM."
)

# Signals of genuine autonomy (the acceptance bar)
SIGNALS = {
    "web_search": 0,        # C0 — researched before building
    "think": 0,             # reasoned / compared options
    "spawn_critic": 0,      # adversarial check of design
    "load_skill": [],       # which skills it pulled (research-first / debugging / ui)
    "write_file": 0,        # actually built something
    "shell_exec": 0,        # ran commands (install/run)
    "verify_work": 0,       # self-verified criteria
    "verify_webapp": 0,     # C3 — proved usable via real HTTP
    "create_skill": 0,      # C5 — distilled a blueprint (self-extension)
    "ask_user": 0,
}

events = []
chunks_text = []


async def main():
    dm = DockerManager()
    deps._docker_manager = dm
    sm = SessionManager(dm)
    deps._session_manager = sm

    print("[P5] creating session + sandbox container...", flush=True)
    session = await sm.create(ContainerConfig())
    print(f"[P5] session={session.id[:8]} container={session.container_id[:12]} app_port={session.app_port}", flush=True)

    t0 = time.monotonic()

    async def ws_send(msg: dict):
        mtype = msg.get("type")
        tool = msg.get("tool")
        # record
        events.append({"t": round(time.monotonic() - t0, 1), **{k: v for k, v in msg.items() if k != "content" or mtype != "agent_chunk"}})
        # count tool signals from agent_status
        if mtype == "agent_status" and tool:
            if tool in SIGNALS and tool != "load_skill":
                SIGNALS[tool] += 1
            detail = str(msg.get("detail", ""))
            if tool == "load_skill":
                SIGNALS["load_skill"].append(detail[:40])
            ts = round(time.monotonic() - t0)
            print(f"[{ts:4d}s] TOOL {tool}: {str(msg.get('detail',''))[:90]}", flush=True)
        elif mtype == "agent_message":
            print(f"\n[AGENT MESSAGE]\n{(msg.get('content') or '')[:1500]}\n", flush=True)
        elif mtype == "agent_chunk" and not msg.get("done"):
            chunks_text.append(msg.get("content", ""))
        elif mtype == "error":
            print(f"[ERROR EVENT] {msg.get('message','')[:300]}", flush=True)

    from app.agent.loop import run_agent_loop, handle_user_response, handle_approval

    # The agent may block on ask_user OR propose_plan (approval). Auto-respond to
    # both so the headless run doesn't hang — answer "tự quyết định" to test autonomy.
    async def auto_answer_watchdog():
        from app.agent.loop import _pending_responses, _pending_approvals
        while True:
            await asyncio.sleep(4)
            for sid in list(_pending_responses.keys()):
                print(f"[P5] auto-answering ask_user for {sid[:8]}", flush=True)
                await handle_user_response(sid, "Bạn tự quyết định phương án tốt nhất. Nếu cần tài liệu, hãy tự tạo một corpus mẫu nhỏ để demo.")
            for rid in list(_pending_approvals.keys()):
                print(f"[P5] auto-approving plan/approval {rid}", flush=True)
                await handle_approval(rid, {"request_id": rid, "approved": True})

    watchdog = asyncio.create_task(auto_answer_watchdog())
    try:
        await asyncio.wait_for(run_agent_loop(session, TASK, ws_send), timeout=1800)  # 30 min cap
    except asyncio.TimeoutError:
        print("[P5] TIMEOUT 30min — capturing partial trajectory", flush=True)
    except Exception as e:
        print(f"[P5] loop error: {type(e).__name__}: {e}", flush=True)
    finally:
        watchdog.cancel()

    elapsed = round(time.monotonic() - t0)
    # Acceptance scoring
    print("\n" + "=" * 60, flush=True)
    print("[P5] ACCEPTANCE SIGNALS", flush=True)
    print("=" * 60, flush=True)
    for k, v in SIGNALS.items():
        print(f"  {k:16s}: {v}", flush=True)
    print(f"  elapsed         : {elapsed}s, total events: {len(events)}", flush=True)

    # Probe whether an app is actually listening on 8080 in the container
    try:
        code, out = await dm.exec_command_simple(session.container_id, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/ 2>/dev/null || echo 000")
        print(f"  app on :8080    : HTTP {out.strip()[-3:]}", flush=True)
    except Exception as e:
        print(f"  app probe failed: {e}", flush=True)

    # dump trajectory
    with open("/app/p5_trajectory.json", "w", encoding="utf-8") as f:
        json.dump({"task": TASK, "signals": SIGNALS, "elapsed_s": elapsed, "events": events[-400:]}, f, ensure_ascii=False, indent=2)
    print("[P5] trajectory saved to /app/p5_trajectory.json", flush=True)

    # leave container for inspection; print id
    print(f"[P5] DONE. container={session.container_id} (left running for inspection)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
