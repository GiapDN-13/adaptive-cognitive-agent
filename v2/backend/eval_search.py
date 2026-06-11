import asyncio, types, sys
sys.path.insert(0, '/app')
import app.deps as deps
from app.agent.builtin_tools import handle_web_search


async def main():
    s = types.SimpleNamespace(container_id='none', id='x')
    async def ws(m): pass

    async def r(label, ti):
        out = await handle_web_search(s, ti, ws, None)
        print(f"\n=== {label} ===  INPUT: {ti}")
        print(f"RETURN (len={len(out)}):\n{out[:450]}" + ("...[CAT]" if len(out) > 450 else ""))

    await r("1. Search thuong (xem [engine: ...])", {"query": "FastAPI tutorial"})
    await r("2. Query vo nghia (loc rac)", {"query": "asdfqwerzxcv9988zzz gibberish xyz"})
    await r("3. FETCH URL truc tiep", {"url": "https://fastapi.tiangolo.com/"})
    await r("4. FETCH URL khong co scheme", {"url": "example.com"})
    await r("5. FETCH URL hong (domain khong ton tai)", {"url": "https://this-domain-zzz-9988.invalid/"})
    await r("6. Khong query khong url", {})

asyncio.run(main())
