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

## Luật 6 — Kill process / giải phóng cổng (sandbox SLIM — KHÔNG có lsof/pkill/fuser/ps)
Sandbox là `python:3.11-slim` — **KHÔNG có** `lsof`, `pkill`, `fuser`, `ps`, `netstat`. Gọi chúng sẽ "command not found" hoặc no-op âm thầm → nếu cố kill server cũ bằng các lệnh này bạn sẽ LẶP VÔ HẠN mà cổng vẫn bị giữ ("address already in use").

**Phòng ngừa (làm ngay từ đầu — TỐT NHẤT):** khi start server nền, LƯU PID rồi kill theo PID trước mỗi lần restart — KHÔNG đi "săn" cổng:
```
# start: lưu PID
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > /tmp/srv.log 2>&1 & echo $! > /tmp/srv.pid
# restart: kill instance cũ theo PID đã lưu, rồi start lại
kill "$(cat /tmp/srv.pid)" 2>/dev/null; sleep 1
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > /tmp/srv.log 2>&1 & echo $! > /tmp/srv.pid
```

**Khi đã lỡ mất PID + cổng bị giữ:** tìm & kill qua `/proc` (không cần lsof), KHÔNG thử pkill/fuser nữa:
```
python3 - <<'PY'
import os, glob
PORT_HEX = format(8080, '04X')           # 8080 -> '1F90'
ino = {l.split()[9] for l in open('/proc/net/tcp')
       if l.split()[1].endswith(':'+PORT_HEX) and l.split()[3] == '0A'}  # 0A = LISTEN
for fd in glob.glob('/proc/[0-9]*/fd/*'):
    try:
        t = os.readlink(fd)
        if t.startswith('socket:') and t.split('[')[1].rstrip(']') in ino:
            os.kill(int(fd.split('/')[2]), 9); print('killed', fd.split('/')[2])
    except Exception: pass
PY
```
**Đơn giản hơn cả:** nếu chỉ cần app chạy, đừng cố tái dùng đúng cổng cũ khi đang kẹt — kill theo PID đã lưu là đủ. Thấy "address already in use" lặp lại ≥2 lần → DỪNG thử lệnh kill khác, chuyển sang cách `/proc` ở trên ngay.

## Checklist trước khi gửi lệnh phức tạp
- [ ] Các bước phụ thuộc có nằm trong CÙNG một lệnh (nối `&&`) không?
- [ ] Có dùng `;` chỗ đáng lẽ phải `&&` không?
- [ ] Đường dẫn/biến đã quote chưa?
- [ ] Server nền có redirect log + có bước chờ-sẵn-sàng chưa?
- [ ] Sau khi chạy, đã đọc `[exit_code=N]` để xác nhận thành công chưa?
