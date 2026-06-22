"""ĐO CHIỀU SÂU TƯ DUY — N LẦN (tách tín hiệu prompt khỏi nhiễu giữa các lần chạy).

Vì sao: chấm 1 trace duy nhất bị nhiễu nặng (mỗi lần LLM suy khác nhau) — điểm
nhảy 5/7→3/7 phần lớn là may rủi, không phải prompt. Cách đúng: chạy N lần rồi lấy
TỈ LỆ PASS mỗi tiêu chí.

Để rẻ + nhanh + không phụ thuộc build/sandbox: thay vì chạy agent loop đầy đủ (20'/lần,
Docker hay sập), ta gọi LLM với ĐÚNG system prompt thật + bài toán, yêu cầu agent PHÂN
TÍCH (Bước 0 đào sâu + Bước 1.5 chọn công nghệ đa nhánh) bằng think — KHÔNG build. D1-D7
đều chấm THINKING nên cách này đo đúng phần tư duy, chỉ bỏ phần thực thi.

Chạy:  python /app/eval_depth_multi.py [N]   (mặc định N=3)
In tỉ lệ PASS từng tiêu chí D1-D7 + điểm trung bình.
"""
import asyncio, sys, re
sys.path.insert(0, "/app"); sys.path.insert(0, ".")
from app.llm.client import create_llm_client
from app.agent.prompts import build_system_prompt
from app.config import settings

TASK = (
    "Phân tích bài toán sau (CHƯA cần build, chỉ tư duy bằng think): Xây chatbot RAG cho "
    "doanh nghiệp MekongAI — khoảng 1000 nhân viên, 4 phòng ban (HR/Finance/Engineering/"
    "Admin), mỗi phòng nhiều người và mỗi người nhiều tài liệu công việc. Tài liệu đa định "
    "dạng (PDF, Word, Excel). Phân quyền theo phòng ban. Hãy thực hiện ĐẦY ĐỦ Bước 0 (tự "
    "phát triển/đào sâu bài toán: quy mô, đặc tính dữ liệu, phân rã + phần khó nhất) và "
    "Bước 1.5 (chọn các công nghệ kiến trúc lõi — vector store, embedding, retrieval — theo "
    "tư duy đa nhánh, chấm điểm). Dùng think để trình bày toàn bộ suy nghĩ. KHÔNG gọi tool "
    "khác, KHÔNG viết code, KHÔNG hỏi lại — đây là bài tư duy."
)

RUBRIC = """Chấm CHIỀU SÂU TƯ DUY của AI agent (phân tích bài RAG doanh nghiệp 1000 nhân
viên). Mỗi tiêu chí PASS chỉ khi agent THỰC SỰ đạt (khắt khe), kèm bằng chứng trích dẫn.

[D1] Suy luận QUY MÔ định lượng: tự nhân tổng khối lượng dữ liệu từ ngữ cảnh (người ×
file × phòng → nghìn+ tài liệu), tách trục "đồng thời" khỏi trục "khối lượng dữ liệu".
FAIL nếu phán "corpus nhỏ/vài file" hoặc dùng số đồng thời để chọn kích thước DB.

[D2] Đào sâu XỬ LÝ NỘI DUNG: với Excel/CSV đào tới ngữ nghĩa hàng/cột, header, cách chunk
giữ ngữ nghĩa. FAIL nếu chỉ "đọc được file" / "pandas" hời hợt.

[D3] Phân rã + phần KHÓ NHẤT trước: chia bài toán con, xếp độ khó, đào phần khó trước.

[D4] Đa nhánh (Tree-of-Thoughts): sinh ≥2-3 nhánh cho ≥1 quyết định, so trade-off, chọn
có lý do. FAIL nếu nêu 1 phương án / liệt kê không so sánh để chọn.

[D5] Tự phản chiếu (Wait/Aha): tự nghi ngờ giả định của chính mình & đảo hướng ít nhất 1
lần. FAIL nếu mạch khẳng định thẳng tắp.

[D6] Chấm điểm CÓ TRỌNG SỐ khi chọn nhánh: nêu tiêu chí (recall/độ trễ/chi phí/scale...),
gán ưu tiên tiêu chí quan trọng nhất, chọn nhánh thắng vì điểm trọng số cao hơn. FAIL nếu
chỉ kể ưu/nhược định tính.

[D7] Biết khi mình KHÔNG biết: đánh dấu rõ giả định cần verify (model ID, giới hạn lib,
benchmark) + chủ trương kiểm chứng thay vì khẳng định từ trí nhớ.

TRẢ ĐÚNG ĐỊNH DẠNG:
D1: PASS|FAIL — <bằng chứng>
D2: PASS|FAIL — <bằng chứng>
D3: PASS|FAIL — <bằng chứng>
D4: PASS|FAIL — <bằng chứng>
D5: PASS|FAIL — <bằng chứng>
D6: PASS|FAIL — <bằng chứng>
D7: PASS|FAIL — <bằng chứng>
"""

async def one_run(idx):
    """1 lần: agent phân tích -> lấy thinking -> giám khảo chấm. Trả dict {D1:bool,...}."""
    c = create_llm_client()
    sysp = build_system_prompt(False)
    # ép think nhiều: max_tokens cao
    r = await c.converse(
        messages=[{"role": "user", "content": [{"text": TASK}]}],
        system=sysp, max_tokens=6000, temperature=0.7,  # temp cao để thấy variance thật
    )
    blocks = r.get("output", {}).get("message", {}).get("content", [])
    # gom mọi text + tool think input
    parts = []
    for b in blocks:
        if "text" in b:
            parts.append(b["text"])
        if "toolUse" in b and isinstance(b["toolUse"].get("input"), dict):
            parts.append(b["toolUse"]["input"].get("thought", ""))
    blob = "\n".join(p for p in parts if p)
    if len(blob) < 200:
        return None, blob  # không đủ thinking (agent có thể đòi gọi tool)
    heavy = getattr(settings, "bedrock_heavy_model", "") or "us.anthropic.claude-opus-4-7"
    j = await c.converse(
        messages=[{"role": "user", "content": [{"text": RUBRIC + "\n\n=== THINKING ===\n" + blob}]}],
        system="Giám khảo kỹ thuật khắt khe, chỉ PASS khi có bằng chứng rõ.",
        max_tokens=1500, model=heavy,
    )
    out = "".join(b.get("text", "") for b in j.get("output", {}).get("message", {}).get("content", []))
    v = dict(re.findall(r"(D[1-7]):\s*(PASS|FAIL)", out))
    return {k: v.get(k) == "PASS" for k in [f"D{i}" for i in range(1, 8)]}, blob

async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    dims = [f"D{i}" for i in range(1, 8)]
    tally = {d: 0 for d in dims}
    valid = 0
    for i in range(n):
        try:
            res, blob = await one_run(i)
        except Exception as e:
            print(f"  run {i+1}: ERROR {type(e).__name__}: {str(e)[:80]}"); continue
        if res is None:
            print(f"  run {i+1}: SKIP (thinking quá ngắn, {len(blob)} ký tự)"); continue
        valid += 1
        for d in dims:
            tally[d] += 1 if res[d] else 0
        print(f"  run {i+1}: " + " ".join(f"{d}={'P' if res[d] else 'F'}" for d in dims))
    print(f"\n{'='*56}")
    if valid == 0:
        print("KHÔNG có run hợp lệ."); sys.exit(1)
    print(f"TỈ LỆ PASS qua {valid} lần chạy:")
    total = 0
    for d in dims:
        rate = tally[d] / valid
        total += rate
        bar = "█" * round(rate * 10)
        print(f"  {d}: {tally[d]}/{valid} ({rate*100:.0f}%) {bar}")
    print(f"\nĐIỂM TRUNG BÌNH: {total:.1f}/7")
    sys.exit(0)

asyncio.run(main())
