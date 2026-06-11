# Báo cáo — Hardening 17 Tools của SmartAgent V2

**Ngày:** 2026-06-10 | **Mục tiêu:** hoàn thiện chất lượng từng tool để "hoạt động hoàn hảo nhất có thể".

## Nguyên tắc
- Giữ quyền red-team: KHÔNG lọc nội dung lệnh — hardening = robustness, không hạn chế tấn công.
- Exit code là ground truth (theo quyết định user) — giữ chế độ cũ qua param opt-in.
- Mỗi tool có test thực tế chạy được không cần LLM.

## Phát hiện cốt lõi
Codebase **đã có sẵn primitive an toàn** (`exec_command_simple` trả exit code, `copy_file_to` ghi file qua tar) nhưng handlers phớt lờ → nhiều lỗi nghiêm trọng (path injection, nghiệm thu bằng keyword, không có timeout).

## Thay đổi theo phase (mỗi mục đã TEST PASS)

| Phase | Tool | Trước | Sau |
|-------|------|-------|-----|
| **P0.1** | loop dispatch | `cancel_event` chỉ tới web_search | tới MỌI tool |
| **P0.2** | docker_manager | — | `exec_command_capture()` → (exit_code, output, timed_out), timeout thật |
| **P1.1** | **write_file** | `printf` qua shell → **path injection** (`$(...)` thực thi), không verify | `copy_file_to` (tar, không shell) + verify `stat` + cap 10MB |
| **P1.2** | **verify_work** | verdict bằng **keyword** ("error"/"traceback"), bỏ exit code | **exit code = ground truth** + `assert_mode` (exit_code/contains/regex) + timeout |
| **P1.3** | **shell_exec** | bỏ timeout, KHÔNG báo exit code, overflow heredoc dễ vỡ | timeout honored (default 900s) + `[exit_code=N]` + overflow qua tar + cancel |
| **P2.1** | read_file | head -n, không offset, không phân biệt missing/rỗng | offset+pagination, total lines, FILE NOT FOUND, line_numbers |
| **P2.2** | ask_user | timeout trả câu giả → agent loop | phân biệt timeout sentinel + match options |
| **P2.3** | propose_plan | hang autonomous, step success bằng keyword | thông báo no-approver, step success bằng exit code, tool-name step surfaced |
| **P3.1** | spawn_critic/subagent | nesting vô hạn, extraction "" khi last=toolResult | depth cap (≤3), budget 40 iter, `extract_last_agent_text`, pipeline loại khỏi subagent |
| **P3.2** | verify_webapp | curl -m 15 cứng, không retry | warmup/retry khi 000, timeout configurable, body cap 200KB, assert_json |
| **P3.3** | execute_pipeline | checkpoint theo index (vỡ khi reorder), không fail_fast | checkpoint theo hash(name,goal), fail_fast, findings cap 12KB |
| **P3.4** | web_search | cứng 3 kết quả, chỉ snippet, lỗi gộp | max_results 1-10, fetch_content, phân biệt network-error vs no-results |
| **P3.5** | meta_tools/tool_safety | safelist stdlib-only, không validate schema, hook crash | thêm requests/bs4/lxml, validate JSON Schema, overwrite guard, hook return-type fail-open |
| **P4.1** | truncate_output | was_truncated lệch line vs char | True khi BẤT KỲ hiding nào |
| — | think | (giữ nguyên — display-only đúng chủ ý) | — |

## Nghiệm thu
- **13 test suite ALL PASS**: 6 Docker-based (docker_exec, write_file, verify_work, read_file, shell_exec, verify_webapp) + 7 pure-unit (ask_user, plan_steps, subagent_limits, pipeline, web_search, meta_tools, truncate).
- Backend restart sạch sau mỗi phase, 17 tools, HTTP 200, Bedrock LIVE.

## Breaking changes (ghi PR)
- write_file: shell→tar (bytes trung thực hơn, không newline ẩn).
- verify_work + propose_plan step: verdict theo exit code thay keyword (có assert_mode cho kiểu cũ).
- subagent: budget 40 iter thay vì share 150.
- pipeline: checkpoint key theo tên (checkpoint index cũ → coi như fresh run).
- tool_safety: cho phép requests/bs4/lxml (os/subprocess vẫn cấm).
