# SPEC: Universal Critical Thinking — Phản biện cho MỌI domain

**Vấn đề:** Agent claim suông ("ChromaDB scale tốt cho 1k user" — sai). Fix trước hard-code ví dụ ChromaDB → chỉ đúng 1 domain. Cần framework tổng quát áp dụng pentest, ML, data, infra, security...

**Giải pháp:** 3 lớp kết hợp.

---

## Lớp 1: Framework gốc (3 câu hỏi — mọi domain)

Mọi quyết định/claim kỹ thuật, agent tự hỏi:
1. **Bằng chứng?** — Claim ("đủ nhanh/an toàn/scale được") phải có số liệu/doc/benchmark, hoặc đánh dấu rõ "giả định cần verify".
2. **Khớp con số requirement?** — Đối chiếu giới hạn thực tế của công cụ với con số cụ thể (1k user, 10GB, 100 req/s).
3. **Cái gì có thể SAI?** — Chủ động tìm failure mode, edge case, giả định ngầm.

→ Đưa vào prompt như nguyên tắc, KHÔNG kèm ví dụ domain cụ thể (tránh over-fit).

## Lớp 2: Critic Agent chuyên trách (trung tâm)

Tool mới `spawn_critic` — subagent chuyên DUY NHẤT việc phản biện:
- Input: quyết định/thiết kế/claim cần phản biện + context (requirement, domain)
- Critic tự nhận diện domain → áp 3 câu hỏi gốc + research (web_search) để verify
- Output: structured findings (mỗi claim: VALID / QUESTIONABLE / WRONG + evidence + đề xuất)
- Agent PHẢI spawn_critic trước khi finalize quyết định kiến trúc/quan trọng

Khác `spawn_subagent` chung: critic có system prompt chuyên phản biện, bắt buộc research, output structured.

## Lớp 3: Self-extend critique skills (tích lũy)

Khi critic phản biện 1 domain mới → tự `create_skill` lưu "checklist phản biện domain đó" (vd `critique-pentest`, `critique-ml`). Lần sau gặp domain đó → `load_skill` dùng lại checklist đã tích lũy.

---

## Implementation

| # | File | Thay đổi |
|---|------|----------|
| 1 | `prompts.py` | Thay phần "Architecture Review" hard-code bằng 3-câu-hỏi framework tổng quát (mọi domain) |
| 2 | `builtin_tools.py` | Tool `spawn_critic` — critic subagent chuyên phản biện + structured output |
| 3 | `prompts.py` | Critic system prompt (khi is_critic): research bắt buộc, áp 3 câu hỏi, structured verdict |
| 4 | `builtin_tools.py` | Critic tự create_skill checklist domain sau khi phản biện (khuyến khích trong prompt) |
| 5 | Frontend | `agent_critique` block đã có — critic findings hiện inline |

---

## Verdict format (structured)
```
CRITIQUE [domain: <auto-detected>]
- Claim: "..." → VERDICT: WRONG/QUESTIONABLE/VALID
  Evidence: <từ research>
  Fix: <đề xuất>
```

## Verification
Test 2-3 domain khác nhau (vector DB, pentest payload, data tool choice) — agent phải spawn_critic, research, đưa verdict có bằng chứng, KHÔNG claim suông. Không hard-code domain nào.
