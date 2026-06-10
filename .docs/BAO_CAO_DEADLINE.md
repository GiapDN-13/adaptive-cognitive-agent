# BÁO CÁO — Deadline Task "Kiến trúc Agentic Tối ưu cho SmartAgent"


---

## 1. Tóm tắt 
| | |
|---|---|
| **Mong muốn** | Đưa ra kiến trúc agentic tối ưu cho SmartAgent |
| **Bằng chứng** | SmartAgent **TỰ** thiết kế & build ra 1 RAG chatbot dùng được (RAG chỉ là phép thử năng lực tự chủ) |
| **🎯 Mốc 1 — Kiến trúc** | **Hết Thứ Ba 09/06/2026**  |
| **🎯 Mốc 2 — Triển khai + Demo** | **Hết Thứ Sáu 12/06/2026** |
| **Đệm rủi ro (nếu lỗi sâu)** | Tối đa Thứ Ba 16/06/2026 |


---

## 2. "Hoàn thành" nghĩa là gì? (định nghĩa rõ, đo được)

Task chỉ được tính **HOÀN THÀNH** khi đạt ĐỦ 2 mốc dưới đây — mỗi mốc có tiêu chí nghiệm thu cụ thể, không nói chung chung.

### 🎯 MỐC 1 — KIẾN TRÚC (deliverable để sếp duyệt)
**Hạn: hết Thứ Ba 09/06/2026.** Trạng thái: ✅ **ĐÃ HOÀN THÀNH** (tài liệu `.docs/ARCH_AGENTIC_OPTIMAL.md`).

Tiêu chí đạt:
- [x] Tài liệu kiến trúc 6 trụ cột, có sơ đồ, luận chứng root-cause (chỉ ra đúng vì sao bản cũ "có giao diện nhưng không dùng được").
- [x] Đối chiếu với **Nexus** — agent production của chính MekongAI — để port pattern đã kiểm chứng thay vì tự sáng chế (tăng độ chắc chắn, giảm rủi ro).
- [x] Tham khảo 17 repo nghiên cứu nội bộ + repo Nexus, ghi nguồn minh bạch.

### 🎯 MỐC 2 — TRIỂN KHAI + DEMO (bằng chứng năng lực)
**Hạn: hết Thứ Sáu 12/06/2026.**

Tính HOÀN THÀNH khi SmartAgent nhận task "build RAG chatbot" mà **KHÔNG được mớm lời giải**, và **tự** vượt qua các tiêu chí đo được:

| # | Tiêu chí nghiệm thu | Cách đo (khách quan) |
|---|---------------------|----------------------|
| C0 | Agent **tự nghiên cứu** trước khi build | Log có `web_search` + đối chiếu yêu cầu TRƯỚC khi viết code |
| C1 | Chạy không lỗi | `python eval.py` chạy xong, exit 0 |
| C2 | Chất lượng truy hồi đạt ngưỡng | Hit Rate@4 ≥ 0.8 (số đo in ra) |
| C3 | **App dùng được THẬT** | Test HTTP thật: hỏi câu trong tài liệu → trả lời đúng; hỏi ngoài phạm vi → từ chối (không bịa) |
| C4 | Bền với input hiểm | Input rỗng/dài/sai định dạng không làm sập app |
| C5 | Agent **tự đúc kết** | Sau khi xong, agent tự lưu lại phương pháp để lần sau khá hơn |
| C6 | Trung thực | Báo cáo có số liệu thật, nêu rõ hạn chế |

> **Thước đo cốt lõi:** không phải "RAG đẹp tới đâu", mà là **agent có TỰ CHỦ thật không** — làm được task nó chưa từng được dạy.

---

## 3. Lịch chi tiết (cam kết theo ngày)

| Ngày | Phase | Nội dung | Kết quả |
|------|-------|----------|---------|
| **T3 09/06** | P0 | Tài liệu kiến trúc | ✅ Xong — **trình sếp duyệt** |
| **T4 10/06** | P1 + P2 | Kỷ luật "debug trước khi đập đi xây lại" + cơ chế kiểm chứng app dùng được | Test PASS |
| **T5 11/06** | P3 + P4 + P4b | Kỷ luật "nghiên cứu trước khi làm" + cài đặt đáng tin cậy + chuẩn UI | Test PASS |
| **T6 12/06** | P6 + P5 | Sửa gốc lỗi treo/timeout + **chạy demo nghiệm thu** | ✅ **Demo dùng được + báo cáo số liệu** |

**Nguyên tắc thực hiện (đã thống nhất với anh em kỹ thuật):**
- Mỗi phase **port pattern đã kiểm chứng từ Nexus** (sản phẩm production của MekongAI) → nhanh và chắc hơn tự viết.
- Mỗi phase có **test thực tế** mới tính xong (không "chắc chạy được").

---

## 4. Rủi ro & cam kết minh bạch

| Rủi ro | Khả năng | Phương án |
|--------|----------|-----------|
| Demo (P5) lòi lỗi cần sửa sâu | Trung bình | Đã chừa **đệm tới T3 16/06**. Nếu trượt sẽ báo sếp ngay, kèm lý do cụ thể. |
| Agent tự research ra giải pháp vẫn chưa tối ưu | Thấp | Có cơ chế phản biện + kiểm chứng buộc làm lại; báo cáo trung thực phần chưa đạt thay vì giả vờ hoàn hảo. |

**Cam kết:** Nếu đến mốc mà chưa đạt 100% tiêu chí, sẽ báo cáo **đúng phần đạt / chưa đạt + lý do**, không báo cáo "xong" khi chưa kiểm chứng.

---
