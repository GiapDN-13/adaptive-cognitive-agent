---
name: ui-blueprint
description: 12 rule thiết kế UI web sạch & dùng được (rút từ DESIGN.md production của Claude/Airtable/Cal/Apple). Áp cho MỌI web app/chat UI để tránh "giao diện nhìn dở/chưa xong".
origin: research-awesome-design-md
---

# UI Blueprint — 12 rule cho UI sạch & dùng được

## Khi nào dùng
MỌI lúc build giao diện web (chat UI, dashboard, landing, form...). Tuân thủ để tránh UI "trông như chưa làm xong": thiếu trạng thái, màu lộn xộn, spacing tùy tiện.

## 12 Rule (encode được — kiểm tra output của mình theo từng rule)

1. **Một màu nhấn duy nhất** + neutral grays. 1 accent (vd `#FF5701` / `#0066cc` / brand). Nền dùng xám trung tính `#f5f5f5 / #e5e7eb / #6b7280`. KHÔNG thêm màu nhấn thứ 2.
2. **Canvas warm/off-white**, KHÔNG pure white. Nền trang `#faf9f5` hoặc `#f8fafc`, không `#ffffff` thuần (trông lạnh/clinical).
3. **Typography**: 1 font display (28-48px, `letter-spacing` âm -0.5 đến -2px) + 1 font body (humanist sans, 14-16px, `line-height: 1.5`) + monospace cho code (13-14px). Display KHÔNG cần bold (weight 400-600).
4. **Button** cao ≥40px, `border-radius` 8-12px, padding 12-16px ngang. Phân biệt rõ primary (nền accent, chữ trắng) vs secondary (nền surface, viền hairline). Không quá 2 kiểu button hiện cùng lúc.
5. **Chat bubble**: user phải-align (nền xám nhạt/accent@10%), agent trái-align (nền surface + viền hairline). Cả hai: `border-radius` 12px, padding 12-16px, `max-width` 70-85%.
6. **Spacing theo grid 8px**: 96px giữa section lớn, 24px giữa card, 16-32px bên trong card. Whitespace là công cụ chính tạo nhịp.
7. **Input** cao ≥44px, viền hairline `1px #e5e7eb`, radius 6-8px. Focus state: viền đổi sang accent + ring accent@20%. Có label (16px, weight 500) phía trên + help text (13px, muted) phía dưới.
8. **LUÔN có 3 trạng thái: loading / empty / error.** Đây là thứ hay bị quên khiến UI "trông chưa xong":
   - Loading: spinner/skeleton + nhãn ("Đang xử lý...").
   - Empty: icon + tiêu đề + 1-2 dòng mô tả + (tùy chọn) nút hành động.
   - Error: viền/nền đỏ nhạt `#fee2e2` + thông báo + nút "Thử lại".
9. **Card/surface**: radius nhất quán 8-12px. Độ nổi bằng **màu/viền**, KHÔNG shadow nặng. Nếu dùng shadow: blur ≤4-8px, opacity ≤12%.
10. **Dark mode**: chọn DỨT KHOÁT 1 trong 2 — full dark (surface tối `#181715`, chữ sáng) HOẶC light-only (ghi rõ). KHÔNG làm nửa vời (vỡ accessibility).
11. **Responsive**: mobile (<768px) 1 cột, card full-width, button 100% rộng. Code block cho phép scroll ngang (không wrap).
12. **Transition** 150-250ms `ease-out` (`cubic-bezier(0.23, 1, 0.32, 1)`). Enter ~200ms, exit ~140ms. KHÔNG dùng `ease-in` (chậm chạp). Hành động chính phản hồi tức thì.

## Checklist tự kiểm trước khi báo "xong UI"
- [ ] Chỉ 1 màu nhấn; nền off-white không pure white
- [ ] Mọi button ≥40px, radius 8-12px; input ≥44px có focus state
- [ ] Có ĐỦ loading + empty + error state
- [ ] Spacing theo bội số 8px; card radius nhất quán
- [ ] Responsive mobile 1 cột; transition 150-250ms ease-out
- [ ] (Chat) bubble user/agon đúng align, max-width ≤85%

## Lưu ý
"Có giao diện" ≠ "dùng được". UI phải vượt cả gate chức năng (`verify_webapp`) lẫn checklist thẩm mỹ này.
