"""Test LLM-judge của cổng pre-build (T10): phân loại đúng chất lượng tư duy chưa?

Đây là cách đo SẠCH nhất cho gate (khác đo-qua-loop bị cắt thinking giữa chừng):
cho judge chấm 3 mẫu thinking đã biết nhãn — XẤU/TB/TỐT — và kỳ vọng:
  - XẤU (chọn bừa "cho đơn giản")            -> CHUA_DAT (chặn)
  - TB  (có quy mô nhưng THIẾU đa nhánh)     -> CHUA_DAT (chặn) — chính là ca D4/D6 fail
  - TỐT (đủ quy mô + ≥2 nhánh + chấm điểm)   -> DAT (cho qua)

Gate chặn đúng mẫu thiếu đa nhánh => ép agent rethink => nâng D4/D6 (việc heuristic
từ khóa KHÔNG làm được vì mẫu TB có chữ 'tách trục' sẽ lọt).

Chạy trong container (cần Bedrock): python /app/test_prebuild_judge.py
"""
import asyncio, sys
sys.path.insert(0, "/app"); sys.path.insert(0, ".")
import app.agent.loop as loop

SAMPLES = [
    ("XAU", "CHUA_DAT", "Tôi sẽ dùng ChromaDB cho đơn giản, FastAPI, xong build luôn."),
    ("TB", "CHUA_DAT",
     "Doanh nghiệp ~1000 người, 4 phòng × 15 người × nhiều file → corpus nghìn+ tài liệu, "
     "tách trục đồng thời (30-50) khỏi khối lượng. Dùng ChromaDB."),
    ("TOT", "DAT",
     "Quy mô: 4 phòng × 15 người × ~vài chục file/người → nghìn+ tài liệu (tách khỏi 30-50 "
     "đồng thời). Chọn vector store: Nhánh A ChromaDB in-process (dễ cài nhưng concurrent-write "
     "yếu, scale kém khi nghìn+ doc); Nhánh B Qdrant server (mạnh scale + filter metadata, tốn "
     "vận hành); Nhánh C pgvector (tái dùng Postgres). Tiêu chí ưu tiên: scale theo khối lượng > "
     "đơn giản. Chấm: B thắng vì recall+scale cao nhất cho nghìn+ doc. Chọn Qdrant."),
]

async def main():
    ok = 0
    for label, expect, txt in SAMPLES:
        v, fb = await loop._prebuild_quality_gate(txt, "judgetest")
        passed = (v == expect)
        ok += passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}: got {v}, want {expect}")
    print(f"\n{'='*44}\nKET QUA: {ok}/{len(SAMPLES)}")
    print("RESULT:", "ALL PASS" if ok == len(SAMPLES) else "FAIL")
    sys.exit(0 if ok == len(SAMPLES) else 1)

asyncio.run(main())
