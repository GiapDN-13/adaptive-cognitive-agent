---
name: shell-mastery
description: Viết lệnh shell/bash chuẩn & an toàn trong sandbox. Dùng khi task cần pipeline shell phức tạp, quản lý process nền, hoặc nhiều bước phụ thuộc nhau (cd/venv/env).
origin: smartagent
---

# Shell Mastery — viết bash chuẩn trong sandbox

## Khi nào dùng
Task có: nhiều lệnh phụ thuộc nhau, quản lý virtualenv/env var, chạy server nền, xử lý nhiều file, parse output có cấu trúc, hoặc bất kỳ lúc nào một lệnh shell sai làm hỏng bước sau.

## Luật 1 — Mỗi `shell_exec` là một shell RIÊNG (quan trọng nhất)
Không có trạng thái nào được giữ giữa các lần gọi `shell_exec`: `cd`, `source`, `export`, biến shell đều RESET.

❌ SAI (2 lần gọi tách rời):
```
shell_exec: cd /workspace/proj && python3 -m venv venv && . venv/bin/activate
shell_exec: pip install fastapi   # ← pip này là pip HỆ THỐNG, KHÔNG phải của venv!
```
✅ ĐÚNG — cách A: gộp vào 1 lệnh:
```
cd /workspace/proj && python3 -m venv venv && ./venv/bin/pip install fastapi && ./venv/bin/python -c "import fastapi"
```
✅ ĐÚNG — cách B: đường dẫn tuyệt đối, không cần activate:
```
/workspace/proj/venv/bin/python app.py
```

## Luật 2 — Fail-fast, biết exit code
- Chuỗi bước phụ thuộc → nối bằng `&&` (dừng ngay khi fail). KHÔNG dùng `;` (chạy tiếp dù lỗi).
- Script nhiều dòng → mở đầu `set -euo pipefail` (lỗi/biến chưa set/pipe-fail đều dừng).
- `shell_exec` trả `[exit_code=N]` = exit code của **lệnh CUỐI cùng** trong chuỗi. Muốn cả chuỗi fail khi 1 bước giữa fail → dùng `&&` hoặc `set -e`.
- Bẫy `A && B || C`: nếu B fail thì C cũng chạy. Khi cần phân nhánh chính xác, dùng `if ... then ... else ... fi`.

## Luật 3 — Quote & xử lý file an toàn
- Luôn bọc đường dẫn/biến: `"$path"`, `"$(dirname "$f")"`.
- Lặp qua file: `find ... -print0 | xargs -0 ...` hoặc `while IFS= read -r -d '' f; do ...; done < <(find ... -print0)` — xử lý đúng tên có khoảng trắng/ký tự lạ.
- KHÔNG `for f in $(ls)` (vỡ với space). Dùng glob `for f in *.py` hoặc find.

## Luật 4 — Process nền & chờ sẵn sàng
- Chạy nền: `nohup <cmd> > /tmp/log 2>&1 &` (redirect log để không treo).
- Chờ server sẵn sàng (KHÔNG `sleep` mò): `until curl -sf http://localhost:8080/health; do sleep 1; done` — nhưng nhớ `shell_exec` đã có timeout bọc ngoài nên vòng này không treo vĩnh viễn.
- Kiểm tra cổng đang nghe: `curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/`.

## Luật 5 — Cài đặt deps đáng tin cậy
- `pip install` đã có cache + retry sẵn (env của sandbox). Cài lib NHẸ phù hợp RAM 512MB (xem skill research-first-design).
- Cài rồi xác nhận import được ngay trong cùng lệnh: `pip install X && python -c "import X"`.

## Checklist trước khi gửi lệnh phức tạp
- [ ] Các bước phụ thuộc có nằm trong CÙNG một lệnh (nối `&&`) không?
- [ ] Có dùng `;` chỗ đáng lẽ phải `&&` không?
- [ ] Đường dẫn/biến đã quote chưa?
- [ ] Server nền có redirect log + có bước chờ-sẵn-sàng chưa?
- [ ] Sau khi chạy, đã đọc `[exit_code=N]` để xác nhận thành công chưa?
