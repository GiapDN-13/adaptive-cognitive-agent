"""DEBUG T3c: in TOAN BO trace giam khao — moi iteration goi tool gi, tra gi.
Goi thang _run_loop voi prompt giam khao, ws in moi event."""
import asyncio, types, sys, json
sys.path.insert(0, '/app')
from app.core.docker_manager import DockerManager
from app.models.session import ContainerConfig
import app.deps as deps
import app.agent.loop as loop
from app.agent.prompts import build_blind_evaluator_prompt
from app.agent.tool_registry import tool_registry
from app.agent.builtin_tools import register_all_builtins
register_all_builtins(tool_registry)
from app.config import settings

async def main():
    dm = DockerManager(); deps._docker_manager = dm
    cid, _ = await dm.create_container('eval-trace', ContainerConfig())
    sess = types.SimpleNamespace(container_id=cid, id='trace1')
    loop._subagent_depth.clear(); loop._session_generation['trace1']=0; loop._cancel_flags.clear()

    doc = ("BAO CAO QUY 3/2024\nPhan thuyet minh: Cong ty tang truong on dinh.\n"
           "BANG DOANH THU:\nDon vi | Doanh thu | Tam dinh chi\nHai Ha | 1200 | 45\nSong Da | 980 | 12\n")
    await dm.copy_file_to(cid, doc.encode(), "/workspace/baocao.txt")
    rag = ("import sys\nq=sys.argv[1] if len(sys.argv)>1 else ''\nt=open('/workspace/baocao.txt').read()\n"
           "para='\\n'.join(l for l in t.split('\\n') if '|' not in l)\n"
           "print('Cong ty tang truong on dinh.' if 'tang truong' in q.lower() else 'Khong tim thay.')\n")
    await dm.copy_file_to(cid, rag.encode(), "/workspace/rag.py")

    async def ws(m):
        ty=m.get('type')
        if ty=='agent_status': print(f"  [status] tool={m.get('tool')} {str(m.get('detail',''))[:80]}")
        elif ty=='agent_message': print(f"  [msg] {str(m.get('content',''))[:120]}")
        # bo qua chunk/heartbeat cho gon

    task=("## YEU CAU GOC\nLam chatbot RAG hoi dap tai lieu (/workspace/baocao.txt).\n\n"
          "## SAN PHAM\nScript /workspace/rag.py — chay: python3 /workspace/rag.py \"<cau hoi>\".\n\n"
          "## DU LIEU THAT\n/workspace/baocao.txt + /workspace/rag.py\n\nDIEU TRA roi phan VERDICT.")
    msgs=[{"role":"user","content":[{"text":task}]}]
    await loop._run_loop(session=sess, messages=msgs, system_prompt=build_blind_evaluator_prompt(),
        tools_list=tool_registry.get_tool_specs(is_subagent=True), ws_send=ws,
        gen=0, is_subagent=True, max_iterations=15, force_model=settings.bedrock_heavy_model or None)

    print("\n===== FULL MESSAGES TRACE =====")
    for i,m in enumerate(msgs):
        role=m['role']
        for b in (m['content'] if isinstance(m['content'],list) else [{'text':m['content']}]):
            if 'text' in b: print(f"[{i}|{role}|text] {b['text'][:200]}")
            elif 'toolUse' in b: print(f"[{i}|{role}|TOOLUSE] {b['toolUse']['name']} {json.dumps(b['toolUse'].get('input',{}),ensure_ascii=False)[:150]}")
            elif 'toolResult' in b:
                tc=b['toolResult'].get('content',[{}])[0].get('text','')
                print(f"[{i}|{role}|toolResult] {tc[:150]}")
    await dm.destroy_container(cid)

asyncio.run(main())
