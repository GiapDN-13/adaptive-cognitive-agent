# SPEC: Agent Transparency — Nhìn sâu vào tư duy Agent

**Mục tiêu:** User thấy rõ agent search gì, lấy gì, suy nghĩ ra sao, phản biện thế nào.
**Hiển thị:** Inline trong chat (collapse được).
**Date:** 2026-06-05

---

## Vấn đề hiện tại

Agent CÓ làm đầy đủ (search, reasoning, critique) nhưng UI chỉ hiện **trạng thái** (status nhấp nháy), không hiện **nội dung**. User không đọc được agent đang nghĩ gì.

---

## 4 Khía cạnh cần phơi bày

### 1. Search & Retrieval chi tiết
**Hiện tại:** `web_search` chỉ hiện query 60 ký tự, kết quả vào context ẩn.
**Cần:** Khi agent search →
- Hiện full query
- Hiện danh sách kết quả (title + URL + snippet)
- Khi agent dùng 1 nguồn → đánh dấu "đã chọn", vì sao

**Cơ chế:** `web_search` emit message `agent_retrieval`:
```json
{
  "type": "agent_retrieval",
  "query": "...",
  "results": [{"title","url","snippet","score"}],
  "selected": [indices]
}
```

### 2. Reasoning liên tục
**Hiện tại:** Chỉ có `agent_thinking` khi gọi tool `think`.
**Cần:** Khuyến khích agent verbalize reasoning thường xuyên hơn + hiển thị mọi text agent sinh ra giữa các tool call như reasoning (không chỉ câu trả lời cuối).

**Cơ chế:**
- Prompt: khuyến khích agent dùng `think` trước mỗi quyết định quan trọng
- Frontend: gom các `agent_thinking` thành 1 "reasoning thread" collapse được

### 3. Tư duy phản biện (Critique)
**Hiện tại:** `spawn_subagent` QA reviewer chỉ hiện "đang chạy".
**Cần:** Hiện rõ:
- Reviewer thử gì (adversarial inputs)
- Tìm thấy lỗi gì
- Agent chấp nhận/bác bỏ ra sao

**Cơ chế:** Sub-agent messages đã stream về (qua `agent_message` với prefix 🔨/✅). Cần:
- Đánh dấu rõ message nào của sub-agent (đã có visual ở MessageBubble)
- Thêm message `agent_critique` cho từng phát hiện

### 4. Decision Log (vì sao làm X)
**Hiện tại:** Tool call không kèm lý do.
**Cần:** Mỗi tool call quan trọng kèm 1 dòng "vì sao".

**Cơ chế:** Prompt yêu cầu agent thêm field `reason` ngắn khi gọi tool, hoặc dùng `think` ngay trước. Frontend hiện reason cạnh tool call trong activity.

---

## Thiết kế UI (Inline trong chat)

```
┌─ Chat ──────────────────────────────────────────────┐
│ 👤 Xây dựng RAG chatbot...                          │
│                                                     │
│ 🧠 ▾ Reasoning (3 bước)          [collapse]         │
│    • Cần phân tích yêu cầu: KB, retrieval, UI       │
│    • Sẽ dùng TF-IDF vì không cần API ngoài          │
│    • Ưu tiên xử lý out-of-scope vì user nhấn mạnh   │
│                                                     │
│ 🔍 ▾ Search: "TF-IDF python sklearn"   [collapse]   │
│    1. [chọn] scikit-learn docs — TfidfVectorizer    │
│    2. stackoverflow — cosine similarity             │
│    3. (bỏ) medium blog — quá cũ                     │
│                                                     │
│ ⚙️ shell_exec  →  vì: cài scikit-learn              │
│                                                     │
│ 🤖 [câu trả lời chính]                              │
│                                                     │
│ 🔬 ▾ QA Review (tìm 3 vấn đề)        [collapse]     │
│    ❌ "model runway" bị nhận nhầm in-scope          │
│    ❌ threshold quá thấp                            │
│    ✅ Đã sửa cả 2                                   │
└─────────────────────────────────────────────────────┘
```

Mỗi block là 1 component collapse được, màu riêng:
- 🧠 Reasoning — tím
- 🔍 Search — xanh dương
- ⚙️ Action + reason — xám
- 🔬 Critique — cam/đỏ

---

## Implementation Plan

### Backend (4 thay đổi)
| # | File | Thay đổi |
|---|------|----------|
| B1 | `builtin_tools.py` | `web_search` emit `agent_retrieval` (query + results + selected) |
| B2 | `builtin_tools.py` | `spawn_subagent` emit `agent_critique` cho QA findings |
| B3 | `prompts.py` | Khuyến khích agent verbalize reasoning + nêu lý do trước tool call |
| B4 | `loop.py` | Tool status kèm reason (nếu agent cung cấp) |

### Frontend (3 thay đổi)
| # | File | Thay đổi |
|---|------|----------|
| F1 | `messages.ts` + `chatStore.ts` | Type + state cho retrieval/critique/reasoning blocks |
| F2 | `useWebSocket.ts` | Handle `agent_retrieval`, `agent_critique` |
| F3 | New `components/Chat/ReasoningBlock.tsx`, `RetrievalBlock.tsx`, `CritiqueBlock.tsx` | Collapse-able inline blocks |

---

## Phạm vi & Thứ tự

1. **B1 + F (Search/Retrieval)** — giá trị cao nhất, dễ thấy ngay
2. **B3 (Reasoning prompt)** — agent nói nhiều hơn về tư duy
3. **B2 + Critique block** — phơi bày QA review
4. **Decision log** — reason cạnh mỗi tool

Mỗi phần test bằng cách chạy 1 task RAG và quan sát UI.

---

## Lưu ý

- KHÔNG làm chậm agent — chỉ thêm message stream, không thêm LLM call
- Block mặc định **collapsed** để chat không rối, click để mở
- Giữ nguyên flow hiện tại (thinking bubble, activity panel)
