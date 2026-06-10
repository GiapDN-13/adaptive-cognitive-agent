---
name: systematic-debugging
description: Debug-trước-rewrite. 4 phase tìm root cause TRƯỚC khi sửa; cấm đập-đi-xây-lại; chỉ hỏi user khi muốn rewrite lớn. Dùng cho MỌI lỗi/bug.
origin: ported-from-nexus
---

# Systematic Debugging (Debug trước — KHÔNG đập đi xây lại)

## Nguyên tắc tối thượng (Iron Law)

```
KHÔNG SỬA KHI CHƯA TÌM RA ROOT CAUSE.
KHÔNG REBUILD/REWRITE TOÀN BỘ KHI MỚI GẶP LỖI.
```

Một lỗi là bằng chứng của một **defect cụ thể**, KHÔNG phải bằng chứng "kiến trúc sai". Vá triệu chứng hoặc đập đi xây lại đều là thất bại. Nếu chưa hoàn thành Phase 1, bạn KHÔNG được đề xuất fix.

## Khi nào dùng

MỌI lỗi kỹ thuật: test fail, bug, hành vi lạ, app không chạy, build lỗi, layout/CSS vỡ, server trả lỗi. ĐẶC BIỆT khi: đang gấp, "chỉ một fix nhanh thôi" nghe có vẻ hiển nhiên, đã thử vài fix mà chưa được.

## 4 Phase (PHẢI hoàn thành phase trước khi sang phase sau)

### Phase 1 — Điều tra Root Cause (BẮT BUỘC trước mọi fix)
1. **Đọc kỹ thông báo lỗi** — đọc hết stack trace, ghi lại file/dòng/mã lỗi. Dùng `read_file` mở đúng file lỗi.
2. **Tái hiện ổn định** — chạy lại đúng lệnh/luồng gây lỗi bằng `shell_exec`. Lỗi xảy ra mỗi lần không? Không tái hiện được → thu thập thêm dữ liệu, KHÔNG đoán.
3. **Kiểm tra thay đổi gần đây** — `shell_exec` chạy `git log --oneline -10`, `git diff`. Cái gì vừa đổi có thể gây lỗi?
4. **Thu thập bằng chứng (hệ nhiều thành phần)** — thêm log tại mỗi ranh giới (API→service→DB). Chạy 1 lần để thấy CHÍNH XÁC chỗ nào gãy.
5. **Truy vết dòng dữ liệu** — giá trị xấu phát sinh từ đâu? Truy ngược lên nguồn. **Fix tại nguồn, không tại triệu chứng.**

**Checklist Phase 1 (STOP nếu chưa đủ):**
- [ ] Đã đọc & hiểu thông báo lỗi
- [ ] Đã tái hiện ổn định
- [ ] Đã xem thay đổi gần đây
- [ ] Đã cô lập về 1 thành phần/đoạn code cụ thể
- [ ] Đã có **giả thuyết root cause** ("Tôi nghĩ X là nguyên nhân vì Y")

### Phase 2 — Phân tích pattern
- Tìm code tương tự ĐANG CHẠY ĐÚNG trong codebase (`shell_exec grep`/`read_file`).
- So sánh working vs broken, liệt kê MỌI khác biệt (đừng giả định "cái đó không quan trọng").

### Phase 3 — Giả thuyết & kiểm chứng
- Phát biểu **1 giả thuyết** rõ ràng.
- Thử thay đổi **NHỎ NHẤT có thể** để kiểm chứng — mỗi lần 1 biến.
- Được → Phase 4. Không được → giả thuyết MỚI (đừng chồng thêm fix).
- Không hiểu → nói "tôi chưa hiểu X", `web_search` hoặc `ask_user`. Đừng giả vờ biết.

### Phase 4 — Triển khai
1. Tạo test/lệnh tái hiện lỗi (dùng `verify_work`).
2. Sửa **1 thay đổi** đúng root cause — KHÔNG "tiện tay" refactor, KHÔNG mở rộng phạm vi.
3. `verify_work` lại đúng tiêu chí đó: lỗi RED → GREEN.

## Quy tắc Số 3 (Rule of Three) — chống đập đi xây lại
Nếu fix KHÔNG chạy:
- **DỪNG.** Đếm: đã thử mấy fix?
- < 3 → quay lại Phase 1, phân tích lại với thông tin mới.
- **≥ 3 → DỪNG, KHÔNG thử fix #4. Đây mới là lúc nghi ngờ kiến trúc.**

## Khi nào được REWRITE LỚN / đổi kiến trúc / đổi công nghệ
CHỈ khi: (a) đã thử ≥3 fix có phương pháp mà vẫn fail, VÀ (b) có bằng chứng thiết kế là root cause. Khi đó **PHẢI dùng `ask_user` hỏi TRƯỚC** (kèm 2-4 options: "Debug tiếp bản hiện tại (khuyến nghị)", "Rewrite module X", "Để tôi tự quyết") rồi DỪNG chờ trả lời. TUYỆT ĐỐI không tự ý đập đi xây lại.

## Plateau detection
Nếu cùng một LỚP lỗi lặp lại ≥3 lần trong một task → DỪNG retry mù, dùng `spawn_critic` phân tích tại sao kẹt, hoặc `ask_user`.

## Lưu ý red-team
Kỷ luật này áp cho *thay đổi kỹ thuật trên bản build của agent*. KHÔNG hạn chế thực thi lệnh, sinh exploit/payload, command injection, security testing.
