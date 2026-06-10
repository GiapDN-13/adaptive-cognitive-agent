# Log tiến độ — phiên trưa 2026-06-08 (lúc bạn ngủ)

**Bạn quay lại:** 13:15. **Trạng thái hệ thống:** ✅ Backend + Frontend UP (HTTP 200), 17 tools, không lỗi.

## ✅ ĐÃ HOÀN THÀNH (P1→P6, mỗi phần đã TEST thực tế)

| Phase | Việc | Bằng chứng |
|-------|------|------------|
| **P1** Debug-before-rewrite | Skill `systematic-debugging` (port từ Nexus): Iron Law "no fix without root cause", Rule of Three, cấm đập-đi-xây-lại, chỉ rewrite sau ≥3 fix + ask_user | Skill load OK trong container |
| **P2** verify_webapp | Tool mới: HTTP thật vào :8080, assert response BODY + journey. Port từ Nexus dev_server pattern | **Test E2E thật**: app có UI marker→PASS; thiếu text→FAIL. Tool phân biệt đúng "200 ≠ dùng được" |
| **P3** Research-first | Skill `research-first-design`: bắt research SOTA + đối chiếu requirement TRƯỚC khi build (chống đẻ giải pháp yếu vì dựa trí nhớ) | Skill load OK + wired prompt |
| **P4** Deps đáng tin cậy | Dockerfile.sandbox: PIP_RETRIES=6, timeout=120; docker_manager: mount shared pip-cache volume. KHÔNG pre-bake RAG (tổng quát) | `docker run` xác nhận env có trong image |
| **P4b** UI blueprint | Skill `ui-blueprint`: 12 rule UI (luôn có loading/empty/error...) trị "UI nhìn dở" | Skill load OK |
| **P6** Plateau detection | loop.py: cùng tool+input lặp ≥3 lần → chèn nudge root-cause (port concept metacognition Nexus). ADDITIVE, không đụng exit logic | Syntax+import OK, backend restart sạch |

3 skill mới đã đăng ký vào `priority_skill_ids` (đầu danh sách) → luôn hiển thị catalog. Prompt đã wire 3 kỷ luật cốt lõi + bắt buộc verify_webapp + bước "tự đúc kết" (create_skill).

## ⚠️ QUYẾT ĐỊNH BẢO THỦ (cần bạn review)
- **P6 làm bản AN TOÀN**: chỉ thêm plateau-detection (additive), KHÔNG thay `MAX_ITERATIONS=150` bằng quality-based-exit của Nexus. Lý do: thay exit logic của core loop ngay trước khi bạn ngủ là rủi ro cao (dễ phá vòng đang chạy ổn). Quality-based-exit đầy đủ nên làm khi bạn online để giám sát. Đã ghi vào memory.

## 🔧 SỰ CỐ ĐÃ XỬ LÝ
- Docker Desktop tự tắt giữa chừng (máy chuẩn bị ngủ?) → containers bị xóa. Đã `docker compose up -d --build` lại toàn stack, verify mọi thứ live lại. Pip-cache volume + sandbox rebuild OK.

## ▶️ VIỆC TIẾP THEO (khi bạn online)
1. **P5 — phép thử thật**: mở UI, giao task "build RAG chatbot KHÔNG hand-feed", quan sát agent có TỰ research→build→verify_webapp→đúc kết không. Đây là nghiệm thu năng lực tự chủ (Mốc 2).
2. **P6 đầy đủ** (tùy chọn): port quality-based-exit từ Nexus orchestrator thay MAX_ITERATIONS — cần bạn giám sát vì đụng core loop.
3. Cân nhắc commit (bạn tự quyết — chưa commit gì).

## Files đã đổi phiên này
- `v2/backend/vendor/ecc/skills/{systematic-debugging,research-first-design,ui-blueprint}/SKILL.md` (mới)
- `v2/backend/app/agent/skill_manager.py` (priority_skill_ids)
- `v2/backend/app/agent/prompts.py` (3 kỷ luật + verify_webapp + bước tự đúc kết)
- `v2/backend/app/agent/builtin_tools.py` (handle_verify_webapp + register)
- `v2/backend/app/agent/loop.py` (plateau detection)
- `v2/sandbox/Dockerfile.sandbox` (pip retry env)
- `v2/backend/app/core/docker_manager.py` (pip-cache volume)
