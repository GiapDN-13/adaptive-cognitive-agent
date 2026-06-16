"""VERIFY T3c — GIAM KHAO CO KHON KHONG? (ca gai loi)
Dung 1 san pham THIEU RO RANG: file that co text + BANG so, nhung 'san pham' chi doc text
(hoi so trong bang thi truot). Giam khao mu phai TU DIEU TRA va bat duoc VERDICT=THIEU."""
import asyncio, types, sys
sys.path.insert(0, '/app')
from app.core.docker_manager import DockerManager
from app.models.session import ContainerConfig
import app.deps as deps
from app.agent.builtin_tools import handle_spawn_evaluator
import app.agent.loop as loop

async def main():
    dm = DockerManager(); deps._docker_manager = dm
    cid, _ = await dm.create_container('eval-judge', ContainerConfig())
    sess = types.SimpleNamespace(container_id=cid, id='judge1')
    loop._subagent_depth.clear(); loop._session_generation['judge1']=0; loop._cancel_flags.clear()
    async def ws(m): pass

    # 1. File tai lieu THAT: co text + 1 bang so lieu
    doc = (
        "BAO CAO QUY 3/2024\n\n"
        "Phan thuyet minh: Cong ty tang truong on dinh trong quy 3.\n\n"
        "BANG DOANH THU THEO DON VI (trieu VND):\n"
        "Don vi | Doanh thu | Tam dinh chi\n"
        "Hai Ha | 1200 | 45\n"
        "Song Da | 980 | 12\n"
        "Bac Son | 1500 | 0\n"
    )
    await dm.copy_file_to(cid, doc.encode(), "/workspace/baocao.txt")

    # 2. 'San pham' RAG GIA: chi tra loi dua text, hoi so trong bang -> 'khong biet'
    product = (
        "import sys\n"
        "q = sys.argv[1] if len(sys.argv)>1 else ''\n"
        "text = open('/workspace/baocao.txt').read()\n"
        "# RAG gia: chi tim trong phan THUYET MINH (bo qua dong co dau | = bang)\n"
        "para = '\\n'.join(l for l in text.split('\\n') if '|' not in l)\n"
        "if 'tang truong' in q.lower():\n"
        "    print('Cong ty tang truong on dinh trong quy 3.')\n"
        "else:\n"
        "    print('Khong tim thay thong tin trong tai lieu.')\n"
    )
    await dm.copy_file_to(cid, product.encode(), "/workspace/rag.py")

    ti = {
        "original_request": "Làm chatbot RAG hỏi đáp tài liệu công ty (file /workspace/baocao.txt).",
        "product": "Script /workspace/rag.py — chạy: python3 /workspace/rag.py \"<câu hỏi>\". Trả lời dựa trên tài liệu.",
        "data_location": "/workspace/baocao.txt (tài liệu thật) + /workspace/rag.py (sản phẩm)",
    }
    out = await handle_spawn_evaluator(sess, ti, ws, None)
    print("="*70)
    print(out)
    print("="*70)
    verdict = "THIEU" if ("THIẾU" in out or "THIEU" in out) else ("ĐỦ" if "ĐỦ" in out else "?")
    print(f">> Giam khao phan: {verdict}  (ky vong THIEU — vi san pham khong doc duoc BANG)")
    await dm.destroy_container(cid)

asyncio.run(main())
