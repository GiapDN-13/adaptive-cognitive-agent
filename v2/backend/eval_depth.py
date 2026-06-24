"""EVAL CHIỀU SÂU TƯ DUY (rubric D1/D2/D3) — đo "tư duy đủ rộng/sâu" theo feedback sếp.

Lỗi sếp chỉ ra trên bài RAG-1k-users:
  D1 — Suy luận QUY MÔ định lượng: agent phải TỰ NHÂN tổng tải từ ngữ cảnh nghiệp vụ
       (users × files/người × xử lý), tách trục "đồng thời" khỏi trục "khối lượng dữ
       liệu". LỖI baseline: agent phán "corpus nhỏ ~chục file" — bịa, anchor sai vào
       số đồng thời, bỏ qua "4 phòng × ~15 người × nhiều file".
  D2 — Đào sâu XỬ LÝ NỘI DUNG: mỗi định dạng phải đào tới xử lý nội dung thật (cấu
       trúc bảng/ngữ nghĩa cột/quan hệ), không dừng ở "đọc được file".
  D3 — PHÂN RÃ + làm phần KHÓ NHẤT trước: chia bài toán con, gán độ khó, đào phần khó
       nhất trước thay vì "nhích" phần dễ.

Cách đo: đưa THINKING THẬT của agent (từ 1 trace) cho giám khảo Opus chấm từng tiêu
chí PASS/FAIL kèm bằng chứng trích dẫn. Có assertion + exit code.

Chạy trong container backend:
  python /app/eval_depth.py <duong_dan_trace_events.json>
Mặc định đọc /app/data/trace_events_full.json (trace build đầy đủ).
"""
import asyncio, sys, json
sys.path.insert(0, '/app'); sys.path.insert(0, '.')
from app.llm.client import create_llm_client
from app.config import settings

RUBRIC = """Bạn là giám khảo NGHIÊM KHẮC chấm CHIỀU SÂU TƯ DUY của một AI agent khi
phân tích bài toán "xây chatbot RAG cho doanh nghiệp ~1000 nhân viên, 4 phòng ban,
tài liệu đa định dạng, phân quyền". Dưới đây là TOÀN BỘ dòng suy nghĩ (thinking) thật
của agent đó. Chấm 3 tiêu chí, mỗi tiêu chí PASS chỉ khi agent THỰC SỰ đạt (khắt khe):

[D1] SUY LUẬN QUY MÔ ĐỊNH LƯỢNG:
  PASS nếu agent TỰ suy ra TỔNG KHỐI LƯỢNG DỮ LIỆU từ ngữ cảnh nghiệp vụ — tức nhân ra
  từ "doanh nghiệp / N phòng / nhiều người / nhiều file mỗi người" (vd ~15 người/phòng ×
  4 phòng × nhiều file = corpus LỚN, hàng nghìn+ tài liệu), VÀ tách bạch trục "số truy vấn
  đồng thời" KHỎI trục "khối lượng tài liệu cần index".
  FAIL nếu agent phán corpus "nhỏ / vài chục file / ~chục file" mà không suy từ số người ×
  số file, hoặc dùng số "đồng thời" để kết luận về kích thước vector DB.

[D2] ĐÀO SÂU XỬ LÝ NỘI DUNG (không chỉ đọc được file):
  PASS nếu với định dạng bảng (Excel/CSV) agent đào tới XỬ LÝ NỘI DUNG thật: ngữ nghĩa
  hàng/cột, header context, quan hệ dữ liệu, cách chunk giữ ngữ nghĩa — VÀ coi đây là
  phần KHÓ cần giải kỹ.
  FAIL nếu chỉ nói "đọc được .csv/.xlsx" hoặc "parse từng row" hời hợt mà không bàn
  ngữ nghĩa/cấu trúc nội dung.

[D3] PHÂN RÃ + ĐÀO PHẦN KHÓ NHẤT TRƯỚC:
  PASS nếu agent chia bài toán thành các phần con RÕ RÀNG, nhận diện phần KHÓ NHẤT, và
  chủ trương giải/đào phần khó trước (không để cuối).
  FAIL nếu agent liệt kê đều đều rồi đi xây phần dễ trước, hoặc không phân định độ khó.

[D4] TƯ DUY ĐA NHÁNH (Tree-of-Thoughts) — với ÍT NHẤT MỘT quyết định kiến trúc quan trọng:
  PASS nếu agent SINH ≥2 phương án/nhánh khác nhau cho cùng một quyết định (vd vector DB:
  Chroma vs Qdrant vs pgvector; hoặc retrieval: vector-only vs hybrid+rerank), SO SÁNH
  trade-off của TỪNG nhánh, rồi chọn có lý do dựa trên so sánh — KHÔNG cam kết 1 phương án
  ngay từ đầu.
  FAIL nếu agent chỉ nêu 1 phương án rồi đi luôn (kể cả có phản biện 1 phương án đó), hoặc
  liệt kê option mà không so sánh trade-off để chọn.

[D5] TỰ PHẢN CHIẾU / SỬA SAI GIỮA CHỪNG (Wait/Aha):
  PASS nếu agent tự nghi ngờ một giả định/quyết định của CHÍNH NÓ và điều chỉnh (dấu hiệu:
  "khoan/chờ đã/thực ra/nghĩ lại/điều này sai/tốt hơn nên..."), tức có ít nhất 1 lần đảo
  hướng dựa trên tự phê bình, không phải đi thẳng tắp.
  FAIL nếu toàn bộ thinking là một mạch khẳng định, không có chỗ nào tự sửa/tự nghi ngờ.

[D6] CHẤM ĐIỂM CÓ TRỌNG SỐ KHI CHỌN NHÁNH (reward-model — mục 3.1 tài liệu):
  PASS nếu khi so sánh các nhánh, agent KHÔNG chỉ kể trade-off định tính mà CHẤM theo các
  TIÊU CHÍ rõ ràng (vd recall, độ trễ, chi phí, độ phức tạp vận hành, khớp requirement) và
  nêu nhánh thắng vì điểm tổng cao hơn ở các tiêu chí QUAN TRỌNG NHẤT với bài này — tức có
  ưu tiên/trọng số, không cào bằng.
  FAIL nếu chỉ liệt kê ưu/nhược mỗi nhánh rồi chọn mà không nói tiêu chí nào quan trọng nhất
  / vì sao điểm nhánh thắng cao hơn.

[D7] BIẾT KHI MÌNH KHÔNG BIẾT (Self-RAG / ranh giới tri thức — mục 4.2 tài liệu):
  PASS nếu agent tự đánh dấu RÕ chỗ nào là GIẢ ĐỊNH chưa chắc / cần verify (model ID, giới
  hạn thư viện, con số benchmark, hành vi API) và chủ trương web_search/đọc doc/chạy thử để
  xác minh THAY VÌ khẳng định từ trí nhớ — phân biệt "điều mình chắc" vs "điều cần kiểm".
  FAIL nếu agent khẳng định mọi thứ chắc nịch từ trí nhớ, không đánh dấu giả định cần verify
  nào (kể cả những thứ dễ sai như model ID / version API).

[D8] CHIỀU SÂU TRIỂN KHAI ĐỊNH LƯỢNG (không dừng ở tên công nghệ — áp MỌI lĩnh vực):
  PASS nếu agent chốt THÔNG SỐ/CON SỐ cụ thể đủ để người khác bắt tay làm mà không phải tự
  đoán — đúng theo bản chất task (vd RAG: chunk size/overlap MỖI loại tài liệu + top-k + ngưỡng
  + embedding dim; data: ngưỡng outlier/null/encoding; API: rate-limit/timeout/retry; pentest:
  payload/scope/rate cụ thể), VÀ thông số có lý do gắn với đặc tính dữ liệu/quy mô.
  FAIL nếu chỉ nêu TÊN công nghệ/cách tiếp cận ("dùng chunking theo ngữ nghĩa", "có rerank")
  mà KHÔNG có con số cụ thể, hoặc đọc thiết kế xong vẫn phải tự đoán tham số để code.

[D9] BUILD KHỚP QUYẾT ĐỊNH (không "đúng trên giấy, làm trên tiện"):
  PASS nếu thứ agent THỰC SỰ build/dùng KHỚP phương án đã chấm thắng; HOẶC nếu cố tình lệch
  (dùng phương án tiện cho mẫu nhỏ) thì đã ask_user xác nhận rõ ràng.
  FAIL nếu agent chấm phương án X thắng nhưng build Y kèm tự bào chữa ("tạm dùng cho mẫu nhỏ",
  "migrate sau", "prototype nên...") mà KHÔNG hỏi người dùng.

[D10] VERIFY THAM SỐ ĐỊNH LƯỢNG (chứng minh con số ĐÚNG, không chỉ "chạy được"):
  PASS nếu các con số/tham số then chốt được chứng minh bằng ĐO ĐẠC — đo đặc tính dữ liệu thật
  trước khi chốt (vd đo độ dài tài liệu rồi mới chọn chunk size), HOẶC đo kết quả đầu ra trên
  ca có ground-truth (vd retrieve câu hỏi mẫu xem có lấy đúng đoạn không); hoặc nói RÕ "số này
  là giả định cần đo X" khi không đo được.
  FAIL nếu agent chốt con số CHỈ bằng lý lẽ ("chunk 600 vì văn bản ngắn") mà không đo gì, và
  coi "app chạy xanh" = tham số đúng (dù chạy xanh không phân biệt tham số tốt/xấu).

TRẢ ĐÚNG ĐỊNH DẠNG (không thêm gì ngoài khối này):
D1: PASS|FAIL — <bằng chứng: trích 1 câu agent đã viết>
D2: PASS|FAIL — <bằng chứng>
D3: PASS|FAIL — <bằng chứng>
D4: PASS|FAIL — <bằng chứng>
D5: PASS|FAIL — <bằng chứng>
D6: PASS|FAIL — <bằng chứng>
D7: PASS|FAIL — <bằng chứng>
D8: PASS|FAIL — <bằng chứng>
D9: PASS|FAIL — <bằng chứng>
D10: PASS|FAIL — <bằng chứng>
TỔNG: <x>/10
"""

async def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/app/data/trace_events_full.json"
    events = json.load(open(path, encoding="utf-8"))
    thinking = [x.get("content", "") for x in events if x.get("type") == "agent_thinking" and x.get("content", "").strip()]
    blob = "\n\n---\n\n".join(thinking)
    if not blob.strip():
        print("RESULT: ERROR — trace không có thinking"); sys.exit(1)

    heavy = getattr(settings, "bedrock_heavy_model", "") or "us.anthropic.claude-opus-4-7"
    c = create_llm_client()
    r = await c.converse(
        messages=[{"role": "user", "content": [{"text": RUBRIC + "\n\n=== THINKING CỦA AGENT ===\n" + blob}]}],
        system="Bạn là giám khảo kỹ thuật khắt khe, chỉ PASS khi có bằng chứng rõ ràng.",
        max_tokens=1500, model=heavy,
    )
    out = "".join(b.get("text", "") for b in r.get("output", {}).get("message", {}).get("content", []))
    print(out)

    # Parse verdict (D1-D9) — parser linh hoạt (bỏ markdown)
    import re
    clean = out.replace("*", "").replace("`", "")
    verdicts = dict((k.upper(), v.upper()) for k, v in re.findall(r"(D1[0-9]|D[1-9])\s*[:\-—]*\s*(PASS|FAIL)", clean, re.IGNORECASE))
    npass = sum(1 for v in verdicts.values() if v == "PASS")
    total = len(verdicts)
    print(f"\n{'='*50}\nĐO ĐƯỢC: {npass}/{total} PASS  (verdicts={verdicts})")
    # Đo để so trước/sau khi sửa — KHÔNG assert pass.
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
