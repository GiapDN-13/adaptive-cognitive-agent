"""#16-17 (A)+(B): load_skill / load_agent.
(A) load dung skill/agent, not-found bao ro, khong path-traversal.
(B) agent co goi load_skill khi task khop mot skill co san khong (goi LLM that)."""
import asyncio, json, sys
sys.path.insert(0, '/app')
from app.agent.skill_manager import skill_manager
from app.agent.agent_manager import agent_manager


def section(t): print(f"\n{'='*60}\n{t}\n{'-'*60}")


async def part_A():
    section("(A) load_skill / load_agent — correctness + safety")
    sids = list(skill_manager.skills.keys())
    print(f"  #skills discovered: {len(sids)} (vd: {sids[:4]})")
    if sids:
        c = skill_manager.load_skill_content(sids[0])
        print(f"  load '{sids[0]}': {'OK noi dung '+str(len(c))+' ky tu' if c and not c.startswith('Error') else 'LOI: '+c[:60]}")
    nf = skill_manager.load_skill_content("khong-ton-tai-xyz")
    print(f"  not-found skill: {'bao ro' if 'not found' in nf else 'KHONG ro'} -> {nf[:70]}")
    pt = skill_manager.load_skill_content("../../../etc/passwd")
    print(f"  path-traversal '../../../etc/passwd': {'CHAN (not found)' if 'not found' in pt or 'Error' in pt else 'BUG: doc duoc!'} -> {pt[:60]}")
    aids = list(agent_manager.agents.keys())
    print(f"  #agents discovered: {len(aids)} (vd: {aids[:4]})")
    naf = agent_manager.load_agent_content("khong-ton-tai")
    print(f"  not-found agent: {'bao ro + liet ke' if 'not found' in naf else 'KHONG ro'}")


async def part_B():
    section("(B) agent co goi load_skill khi task khop skill co san?")
    from app.llm.client import create_llm_client
    from app.agent.prompts import build_system_prompt
    from app.agent.tool_registry import tool_registry
    from app.agent.builtin_tools import register_all_builtins
    register_all_builtins(tool_registry)
    WANT = ("load_skill", "load_agent", "shell_exec", "think", "write_file")
    TOOLS = [{"toolSpec": e.schema} for e in tool_registry._tools.values() if e.name in WANT]

    async def first(q):
        c = create_llm_client()
        r = await c.converse(messages=[{"role": "user", "content": [{"text": q}]}],
                             system=build_system_prompt(False), tools=TOOLS, max_tokens=500)
        blocks = r.get("output", {}).get("message", {}).get("content", [])
        return next((b["toolUse"] for b in blocks if "toolUse" in b), None)

    tu = await first("Truoc khi build, hay nap huong dan ky nang 'systematic-debugging' de lam theo dung quy trinh debug.")
    name = tu["name"] if tu else "(text)"
    ok = name in ("load_skill", "think")
    print(f"  yeu cau nap skill cu the -> {name} {json.dumps(tu.get('input',{}),ensure_ascii=False)[:60] if tu else ''}  >> {'OK' if ok else 'xem lai'}")


async def main():
    await part_A()
    try:
        await part_B()
    except Exception as e:
        print(f"  (B) SKIP — {type(e).__name__}: {str(e)[:80]} (co the creds het han)")

asyncio.run(main())
