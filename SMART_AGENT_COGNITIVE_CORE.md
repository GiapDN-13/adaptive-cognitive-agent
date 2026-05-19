---
title: "SmartAgent — Lõi Tư Duy & Cơ chế Suy luận"
project: "MekongAI Agentic Platform"
date: "19/05/2026"
---

<div align="center">

# SMARTAGENT — LÕI TƯ DUY

## Cách Agent suy nghĩ, ra quyết định, và tự cải thiện

</div>

---

## 1. Triết lý thiết kế

SmartAgent được thiết kế theo nguyên lý: **"Không phải mọi câu hỏi đều cần cùng mức độ suy nghĩ."**

Một người giỏi khi được hỏi "Mấy giờ rồi?" sẽ trả lời ngay. Nhưng khi được hỏi "Nên xây dựng chiến lược AI cho ngân hàng thế nào?" — họ sẽ dừng lại, chọn góc nhìn, lập kế hoạch, nghiên cứu, rồi mới trả lời.

SmartAgent hoạt động y hệt:

```
"Chào bạn"                    → Trả lời ngay, không cần nghĩ
"Tính lãi kép 100M, 8%, 5 năm" → Nghĩ nhẹ, dùng công cụ tính toán
"Phân tích thị trường AI VN"   → Nghĩ sâu, research, structured output
"Chiến lược GTM cho startup"   → Nghĩ cực sâu, 5 bước framework, nhiều góc nhìn
```

Mức độ suy nghĩ được **tự quyết định** — không hard-code, không rule cứng. Agent tự đánh giá "bài này cần bao nhiêu não" rồi phân bổ tương ứng.

---

## 2. Chuỗi ra quyết định

### Bước 1: Nhận diện bản chất yêu cầu (Perceive)

Khi nhận input, agent **không gọi AI** mà dùng nhận diện nhanh (heuristic) để đánh giá:

**Câu hỏi agent tự hỏi:**
- Đây là tiếng gì? (Việt hay Anh)
- Thuộc lĩnh vực nào? (tech, marketing, business, data, security...)
- Có bao nhiêu lĩnh vực chồng chéo?
- Có cần thông tin mới nhất không? (trend, giá, tin tức)
- User có đưa URL cụ thể không?
- Yêu cầu có rõ ràng không hay cần hỏi lại?
- Tôi đã từng làm task tương tự chưa? (từ bộ nhớ)

**Kết quả:** Một "điểm phức tạp" (0-10) được tính từ các tín hiệu:

| Tín hiệu | Ảnh hưởng | Lý do |
|-----------|-----------|-------|
| Nhiều lĩnh vực chồng chéo | Tăng phức tạp | Cần cross-domain thinking |
| Có proper noun lạ + câu hỏi | Tăng phức tạp | Cần research |
| Liên quan production/security/payment | Tăng phức tạp | High stakes, cần cẩn thận |
| Yêu cầu creative/brainstorm | Tăng nhẹ | Cần divergent thinking |
| Cần thông tin mới nhất | Tăng nhẹ | Cần search trước khi trả lời |
| Đã làm task tương tự trước đó | **Giảm** phức tạp | Đã có kinh nghiệm |
| Output format rõ ràng (code, list) | **Giảm** phức tạp | Biết chính xác cần gì |
| Chỉ 1 lĩnh vực duy nhất | **Giảm** nhẹ | Focused, không cần multi-angle |

### Bước 2: Kiểm tra có cần nghĩ không (Trivial Check)

Trước khi "bật não", agent check: **"Có cần nghĩ không?"**

Tiêu chí "không cần nghĩ":
- ≤5 từ
- Không có động từ hành động (tạo, viết, phân tích, build...)
- Là chào hỏi, cảm ơn, xác nhận, tạm biệt

**Nếu trivial** → Trả lời ngay bằng 1 câu tự nhiên, dưới 2 giây. Không tool, không framework, không evaluation.

### Bước 3: Kiểm tra có đủ thông tin không (Clarification)

**Câu hỏi agent tự hỏi:** "Nếu tôi bắt đầu làm ngay, tôi có đang đoán mò không?"

Agent phát hiện yêu cầu mơ hồ khi:
- Có động từ tạo/build + chủ thể generic + ít từ (ví dụ: "Tạo landing page")
- Nhiều lĩnh vực nhưng không rõ output format
- Yêu cầu ngắn + không có chi tiết cụ thể (số, tên riêng, ràng buộc)

**Nếu mơ hồ** → Hỏi lại 2-4 câu cụ thể. Ví dụ:
> "Để tạo landing page chất lượng, tôi cần biết:
> 1. Landing page cho sản phẩm/dịch vụ gì?
> 2. Đối tượng khách hàng mục tiêu?
> 3. Tone/phong cách mong muốn (corporate, startup, playful)?
> 4. Có yêu cầu kỹ thuật đặc biệt?"

---

## 3. Meta-Thinking — "Suy nghĩ về cách suy nghĩ"

Đây là **khác biệt cốt lõi** so với chatbot thông thường. Trước khi giải quyết vấn đề, agent dành 2-4 giây để quyết định:

### 3.1 Chọn góc nhìn (Persona)

**Câu hỏi:** "Ai là người phù hợp nhất để giải quyết bài toán này?"

| Persona | Khi nào được chọn | Cách tư duy |
|---------|-------------------|-------------|
| **CTO** | Kiến trúc hệ thống, scalability, security, DevOps | Trade-off analysis, risk vs reward, long-term thinking |
| **PM** | Lập kế hoạch, chiến lược, marketing, go-to-market | User-first, stakeholder mapping, OKR/KPI, phased roadmap |
| **TechLead** | Code, debugging, review, implementation | Best practices, edge cases, maintainability, "show don't tell" |
| **Analyst** | Nghiên cứu, phân tích dữ liệu, thị trường | Evidence-based, structured frameworks (SWOT, Porter), cite sources |
| **Creative** | Content, branding, ideation, storytelling | Originality, audience fit, multiple options, bold choices |
| **Generalist** | Câu hỏi đơn giản hoặc đa lĩnh vực nhẹ | Direct, efficient, self-assess |

**Ví dụ quyết định:**
- "Thiết kế microservice cho fintech" → **CTO** (vì cần architecture trade-offs)
- "Kế hoạch marketing Q3" → **PM** (vì cần roadmap + metrics)
- "Debug lỗi CORS" → **TechLead** (vì cần specific fix)
- "So sánh thị trường AI VN vs SEA" → **Analyst** (vì cần research + data)
- "Viết email pitch cho investor" → **Creative** (vì cần storytelling + hook)

### 3.2 Chọn độ sâu (Thinking Depth 1-5)

**Câu hỏi:** "Bài này cần bao nhiêu não?"

| Depth | Ý nghĩa | Ví dụ | Thời gian xử lý |
|-------|---------|-------|-----------------|
| 1 | Trả lời trực tiếp, factual | "BMI 70kg 1.65m là bao nhiêu?" | 5-8s |
| 2 | Cần structure nhẹ | "Viết function sort Python" | 8-12s |
| 3 | Cần lập kế hoạch | "So sánh React vs Vue cho e-commerce" | 15-25s |
| 4 | Phân tích phức tạp, research | "Phân tích thị trường AI VN 2026" | 30-45s |
| 5 | Full strategic framework | "Chiến lược GTM cho startup fintech" | 45-60s |

**Depth quyết định pipeline:**
- Depth 1-2: Skip lập kế hoạch → inject rules vào prompt → thực thi ngay
- Depth 3: Lập kế hoạch đầy đủ (5 bước) → thực thi theo plan
- Depth 4-5: Lập kế hoạch + Cognitive Framework 5 bước → thực thi sâu

### 3.3 Tự sinh Domain Rules

**Câu hỏi:** "Trong lĩnh vực này, output PHẢI tuân theo quy tắc gì?"

Agent tự sinh 3-5 constraints **cụ thể cho task này** (không phải generic):

**Ví dụ cho "Thiết kế hệ thống payment":**
1. Mọi transaction phải idempotent
2. Phải có saga pattern cho distributed transactions
3. PCI-DSS compliance là non-negotiable
4. Latency P99 < 200ms cho payment flow
5. Phải có audit trail cho mọi state change

**Ví dụ cho "Kế hoạch marketing nấm sấy":**
1. Target audience phải narrowed (không phải "mọi người")
2. Mỗi channel phải có CAC estimate
3. Content phải educate (nấm organic = concept mới với VN consumers)
4. Budget allocation phải theo 70/20/10 rule

Rules này được **inject trực tiếp vào prompt** như "BẮT BUỘC tuân thủ" — agent không thể bỏ qua.

### 3.4 Tự sinh Anti-patterns

**Câu hỏi:** "Một người amateur sẽ mắc lỗi gì ở bài này?"

Ví dụ cho "Thiết kế microservice":
- Đừng recommend microservices cho team 2 người
- Đừng ignore network latency giữa services
- Đừng tạo quá nhiều services ngay từ đầu

### 3.5 Tự sinh Quality Gates

**Câu hỏi:** "Output hoàn thành phải đạt tiêu chí gì để coi là 'đủ tốt'?"

Ví dụ cho "Phân tích thị trường":
- Phải có ít nhất 3 data points từ nguồn thực
- Mỗi recommendation phải kèm metric đo lường
- Phải phân biệt rõ fact vs assumption

Quality gates này sau đó được dùng ở bước Evaluation để kiểm tra output.

---

## 4. Lập kế hoạch thực thi (Reasoning)

### Khi nào lập kế hoạch

Chỉ khi depth ≥ 3. Depth 1-2 không cần plan — inject rules rồi làm luôn.

### 5 bước suy luận

Agent trả lời 5 câu hỏi trước khi hành động:

**1. Intent (Ý đồ):** "User thực sự muốn gì? Có mục tiêu ẩn nào không?"
- Primary goal: Cái gì user nói thẳng
- Implicit goals: Cái gì user kỳ vọng nhưng không nói (ví dụ: hỏi "phân tích đối thủ" thì ngầm muốn "và đề xuất cách đánh bại họ")
- Output format: User muốn nhận kết quả dạng gì (text? code? bảng? roadmap?)

**2. Knowledge Audit (Kiểm tra kiến thức):** "Tôi biết gì? Không biết gì? Cần tìm gì?"
- Known: Facts tôi chắc chắn
- Uncertain: Thông tin tôi tin nhưng chưa chắc đúng
- Unknown: Thông tin tôi PHẢI tìm trước khi trả lời
- Search queries: Nếu cần search, search cái gì?

**3. Capability Map (Năng lực):** "Tôi cần công cụ gì? Thiếu gì?"
- Tools needed: web_search? calculator? read_url?
- Gaps: Có gì tôi không thể làm?

**4. Execution Plan (Kế hoạch):** "Thực hiện theo thứ tự nào?"
- Bước 1 → Bước 2 → ... (có thứ tự rõ ràng)
- Risk points: Bước nào có thể fail?
- Success criteria: Hoàn thành khi nào?

**5. Pre-Check (Kiểm tra cuối):** "Plan này có hợp lý không?"
- Có address đúng intent?
- Có over-engineer không?
- Bỏ sót edge case nào?
- Có nên proceed hay cần hỏi thêm?

---

## 5. Cognitive Framework — Tư duy cấp chiến lược

### Khi nào kích hoạt

Chỉ cho tasks cấp "chiến lược":
- Lập kế hoạch kinh doanh / marketing
- Thiết kế kiến trúc hệ thống phức tạp
- Phân tích thị trường chuyên sâu
- Content strategy
- Bất kỳ task nào MetaThinker đánh giá cần full framework

### 5 bước tư duy sâu

Mỗi bước là **một cuộc suy nghĩ riêng** (1 LLM call) với role chuyên biệt:

#### Bước 1: Kỹ năng (Solution Architect)

**Tư duy:** "Task này thực sự là gì? Scope đến đâu? Cần skills gì?"

Output:
- **Reframe**: Chuyển task thành câu hỏi "How Might We" (giúp focus)
- **Scope**: Deliver gì vs KHÔNG deliver gì (tránh scope creep)
- **Assumptions**: Tôi đang giả định gì? Nếu sai thì sao?
- **Skills**: Kỹ năng cụ thể ngành cần (không phải generic)
- **Gaps**: Thiếu gì để bắt đầu?

#### Bước 2: Kiến thức (Research Analyst)

**Tư duy:** "Tôi biết gì là CHẮC CHẮN? Cái gì đang GIẢ ĐỊNH?"

Output:
- **Facts**: Thông tin đã xác nhận (trích dẫn nguồn)
- **Assumptions**: Phân loại Must Be True / Should / Might + cách validate mỗi cái
- **Cần research**: Câu hỏi cụ thể + nguồn tra cứu
- **Cần hỏi stakeholder**: Những gì chỉ người có quyết định mới biết

#### Bước 3: Yêu cầu (Spec Writer)

**Tư duy:** "Output cuối phải có gì? Ràng buộc nào phải tuân theo?"

Output:
- **FR (Functional Requirements)**: Output PHẢI chứa gì + cách kiểm tra + ngưỡng tối thiểu
- **NFR (Non-Functional Requirements)**: Ràng buộc Performance / Quality / Feasibility / Compliance

Mỗi requirement phải **TESTABLE** — không dùng từ mơ hồ ("tốt", "đầy đủ", "chuyên nghiệp").

#### Bước 4: Mục tiêu (OKR Coach)

**Tư duy:** "Làm theo phase nào? Cái gì phải xong trước?"

Output:
- **Phase 1 (Foundation)**: Quick wins, validate assumptions
- **Phase 2 (Growth)**: Scale what works (depends on Phase 1)
- **Phase 3 (Scale)**: Full execution (depends on Phase 2)
- Mỗi phase: 1 Objective + 2-3 Key Results (có Baseline → Target → Deadline)

#### Bước 5: Đánh giá (QA Lead)

**Tư duy:** "Output hoàn hảo vs tạm chấp nhận vs fail trông thế nào?"

Output:
- **Rubric**: Bảng chấm 3 mức (Xuất sắc / Đạt / Chưa đạt) — observable, không mơ hồ
- **Quality Gates**: Checkpoint YES/NO trước khi sang phase mới
- **Pre-mortem**: Liệt kê lý do output hay THẤT BẠI + cách phòng tránh

### Subject Context Gathering

Trước 5 bước, nếu task đề cập tên riêng/brand/entity lạ:
1. Agent tự search web về entity đó
2. Nếu đủ info → inject vào 5 bước
3. Nếu không đủ → hỏi user trước khi tiếp tục

---

## 6. Thực thi — ReACT Loop

### Concept

**Re**asoning + **Act**ing: Agent suy nghĩ → quyết định hành động → quan sát kết quả → suy nghĩ tiếp.

### Loop thực thi

```
Vòng lặp (tối đa 8 lần):
    1. Agent suy nghĩ: "Bước tiếp theo nên làm gì?"
    2. Quyết định: Dùng tool hay trả lời?
       - Nếu dùng tool → thực thi tool → nhận kết quả → quay lại 1
       - Nếu trả lời → kết thúc loop
```

### Context Enrichment

Trước khi vào loop, system prompt được "nạp đầy" với:
- Nhân cách Mekong (cách nói chuyện)
- Persona prompt (góc nhìn chuyên gia)
- Domain rules (BẮT BUỘC tuân thủ)
- Anti-patterns (KHÔNG ĐƯỢC LÀM)
- Quality gates (OUTPUT PHẢI ĐẠT)
- Cognitive framework output (nếu có)
- Execution plan (checklist bước thực hiện)
- Memory context (kinh nghiệm liên quan từ quá khứ)
- Directive bắt buộc (PHẢI search / PHẢI đọc URL)

Agent thực thi trong bối cảnh đầy đủ "kiến thức về bản thân" — biết mình là ai, nên nghĩ thế nào, phải tránh gì.

### Quyết định dùng tool

Agent tự quyết (không bị ép):
- **web_search**: Khi cần thông tin chưa biết hoặc bị flag "BẮT BUỘC TÌM KIẾM"
- **read_url**: Khi user paste URL hoặc cần đọc trang cụ thể
- **calculator**: Khi cần tính toán chính xác
- **think**: Khi cần sắp xếp suy nghĩ phức tạp trước khi kết luận
- **Generated tools**: Tools đã được user approve trước đó

---

## 7. Tự đánh giá & Retry

### Cơ chế

Sau khi thực thi xong, output **bị chấm điểm bởi một "giám khảo" riêng** (LLM call khác, không phải tự chấm):

**Tiêu chí chấm:**

| Tiêu chí | Thang điểm | Ý nghĩa |
|----------|-----------|----------|
| **Relevance** | 0-10 | Có trả lời đúng câu hỏi không? |
| **Completeness** | 0-10 | Có đủ chi tiết không? |
| **Language** | YES/NO | Có đúng ngôn ngữ không? |

**Công thức:**
```
Score = (Relevance + Completeness) / 2
Nếu sai ngôn ngữ: Score -= 2
Đạt: Score >= 6.0
```

### Retry Logic

```
Lần 1: Chấm → Nếu đạt → trả output cho user
        Nếu chưa đạt → tạo feedback → thực thi lại
Lần 2: Chấm output mới → Nếu đạt → trả output
        Nếu vẫn chưa → tạo feedback → thực thi lại lần cuối
Lần 3: Chấm → Dù kết quả thế nào → trả output tốt nhất hiện có
```

**Feedback cho retry gồm:**
- Relevance thấp → "Chưa trả lời đúng trọng tâm. Focus vào CHÍNH XÁC những gì user hỏi."
- Completeness thấp → "Chưa đủ chi tiết. Thêm ví dụ cụ thể, số liệu."
- Language sai → "SAI NGÔN NGỮ. Phải trả lời bằng tiếng Việt."

### Smart Sampling

Với output dài, evaluator không đọc hết mà lấy mẫu thông minh:
- 40% đầu (mở bài, hướng tiếp cận)
- 20% giữa (thân bài)
- 40% cuối (kết luận, deliverables)

Đảm bảo đánh giá đều khắp output, không bias vào phần đầu.

---

## 8. Tự học & Cập nhật

### Chạy nền (không block user)

Sau khi trả output, agent chạy ngầm:

**1. Cognitive Evaluation (sâu hơn bước D):**
- Outcome: success / partial / failed
- Quality score tổng thể
- Intent fulfillment: Mục tiêu chính đạt chưa? Thiếu gì?
- Reasoning quality: Plan có đúng không? Knowledge gap đã fill chưa?

**2. Lesson Extraction:**
- Rút ra bài học từ task này
- Lưu vào vector memory (Qdrant) để recall cho task tương lai
- Update knowledge graph với entities/relationships mới

**3. Pattern Update:**
- Nếu quality ≥ 8: Reinforce pattern (tăng confidence)
- Nếu quality thấp: Weaken pattern + thêm anti-pattern mới
- Patterns ảnh hưởng Perceiver ở requests tiếp theo

### Vòng phản hồi

```
Task thành công → Reinforce domain expertise → Perceiver giảm complexity cho task tương tự → Xử lý nhanh hơn lần sau

Task thất bại → Extract anti-pattern → Perceiver tăng complexity cho task tương tự → Cẩn thận hơn lần sau
```

---

## 9. Hệ thống nhân cách

### Lõi: "Mekong"

Agent có identity cố định: **Mekong** — trợ lý AI của MekongAI.

**Nguyên tắc giao tiếp cốt lõi:**

| Nguyên tắc | Giải thích |
|------------|-----------|
| **Mirror energy** | User casual → agent casual. User nghiêm túc → agent nghiêm túc. |
| **Hiểu ý, không hiểu chữ** | Đọc ngữ cảnh hội thoại, không parse từng từ. |
| **Tối giản khi có thể** | 1 câu trả lời 1 câu. Không giải thích thừa. |
| **Sâu khi cần** | Câu hỏi phức tạp → structured, chi tiết, có data. |
| **Có cá tính** | Có ý kiến riêng, humor riêng, không generic. |
| **Nhận biết cảm xúc** | User mệt → nhẹ nhàng. User hào hứng → cùng hào hứng. |

### Persona vs Nhân cách

- **Nhân cách (Mekong)** = Cách agent NÓI CHUYỆN (giọng, tone, style) — **cố định**
- **Persona (CTO/PM/...)** = Cách agent SUY NGHĨ (góc nhìn, framework, depth) — **thay đổi mỗi task**

Ví dụ: Khi persona = CTO, agent vẫn nói chuyện theo phong cách Mekong (casual, mirror energy) nhưng TƯ DUY theo góc CTO (trade-offs, scalability, risk).

---

## 10. Bộ nhớ & Học tập

### 4 lớp nhớ

| Lớp | Tương đương con người | Ảnh hưởng đến suy nghĩ |
|-----|----------------------|------------------------|
| **Working Memory** | Cuộc trò chuyện hiện tại | Context cho câu trả lời hiện tại |
| **Episodic Memory** | Kinh nghiệm quá khứ | "Tôi từng làm task tương tự, kết quả tốt/xấu" |
| **Semantic Memory** | Kiến thức domain | Domain-specific best practices, facts |
| **Knowledge Graph** | Mạng lưới khái niệm | Entities liên quan, relationships |

### Cách memory ảnh hưởng suy nghĩ

1. **Perceiver**: "Tôi từng làm task tương tự" → giảm complexity score → xử lý nhanh hơn
2. **MetaThinker**: Domain knowledge giúp sinh rules chính xác hơn (không cần "đoán")
3. **Execution**: Past lessons inject vào prompt → tránh lặp lỗi cũ
4. **Evaluation**: So sánh với past quality → đánh giá chuẩn hơn

### Ranking & Filtering

Không phải tất cả memory đều relevant. Agent:
1. Recall top-10 memories tương tự (cosine similarity)
2. Score = similarity × importance
3. Filter: chỉ lấy score ≥ 0.4
4. Inject top-3 vào context (giới hạn ~400 tokens)

---

## 11. Tổng hợp: Ví dụ End-to-End

### Ví dụ: "Xây dựng chiến lược AI cho ngân hàng số"

**Bước 1 — Perceive (0ms, no LLM):**
- Language: Vietnamese
- Domains: ai_ml, business, security
- Complexity: 6 (multiple_domains + high_stakes + creative_task)
- Needs web search: Yes (domain_unfamiliar)
- Needs clarification: No (đủ specific)

**Bước 2 — Trivial Check:** Không trivial (có action verb "xây dựng", >5 từ)

**Bước 3 — Meta-Think (1 LLM call, 3s):**
- Persona: **CTO** (architecture + strategy + risk)
- Depth: **5** (full strategic framework needed)
- Domain Rules:
  1. Phải address regulatory compliance (banking regulations)
  2. ROI phải quantifiable cho từng AI initiative
  3. Phải có phased approach (pilot → scale)
  4. Data privacy là non-negotiable (customer financial data)
  5. Phải consider build vs buy cho mỗi capability
- Anti-patterns:
  - Đừng recommend "AI for everything" — phải specific use cases
  - Đừng ignore legacy systems integration
  - Đừng underestimate change management
- Quality Gates:
  - Mỗi recommendation có ROI estimate
  - Phải có risk matrix
  - Timeline realistic (không phải "3 tháng transform toàn bộ")
- needs_full_framework: **true**

**Bước 4 — Reason (1 Gemini call, 5s):**
- Plan: Search AI in banking → Analyze use cases → Framework → Recommendations
- Tools needed: web_search, think
- Risk: Data có thể outdated

**Bước 5 — Cognitive Framework (5 LLM calls, 25s):**
- Step 1 (Skills): Reframe → "HMW implement AI that improves efficiency while maintaining compliance?"
- Step 2 (Knowledge): Facts about VN banking + AI adoption rates, assumptions to validate
- Step 3 (Requirements): FR (5 deliverables) + NFR (compliance, timeline, budget)
- Step 4 (Goals): Phase 1 (3 tháng pilot) → Phase 2 (6 tháng scale) → Phase 3 (12 tháng transform)
- Step 5 (Evaluation): Rubric + Gates + Pre-mortem risks

**Bước 6 — Execute (ReACT loop, 3 iterations, 15s):**
- Iteration 1: web_search("AI banking digital transformation 2026 Vietnam")
- Iteration 2: web_search("ngân hàng số Việt Nam AI use cases")
- Iteration 3: think(organize findings) → generate final output

**Bước 7 — Evaluate (1 LLM call, 2s):**
- Relevance: 8/10
- Completeness: 9/10
- Language: YES
- Score: 8.5 → **PASSED**

**Bước 8 — Self-Update (background, 4s):**
- Lesson: "Banking AI strategy tasks cần regulatory focus"
- Pattern: Reinforce CTO + depth 5 cho banking × AI tasks
- KG: Thêm entities (ngân hàng số, compliance, AI use cases)

**Tổng thời gian:** ~50s | **LLM calls:** ~12 | **Quality:** 8.5/10

---

## 12. So sánh: SmartAgent vs Chatbot thường

| Dimension | Chatbot thường | SmartAgent |
|-----------|---------------|------------|
| Thinking | 1 prompt → 1 response | 5-phase pipeline, adaptive depth |
| Self-awareness | Không | Biết mình đang suy nghĩ thế nào, chọn persona |
| Planning | Không | 5-step reasoning chain |
| Quality control | Không | Self-evaluation + retry |
| Learning | Stateless | Episodic + semantic + KG memory |
| Tool use | Fixed tools | Dynamic: tự tạo tool mới khi thiếu |
| Clarification | Cố trả lời mù | Nhận diện mơ hồ → hỏi lại trước |
| Domain adaptation | Cùng 1 prompt | Tự sinh rules, gates, anti-patterns per domain |
| Depth control | Luôn cùng 1 mức | Trivial=instant, Complex=deep framework |
| Personality | Generic | Mekong identity + persona switching |

---

## 13. Tóm tắt: Luồng suy nghĩ hoàn chỉnh

```
INPUT nhận được
    │
    ▼
"Đây là gì?" ─── PERCEIVE (nhận diện ngôn ngữ, domain, complexity)
    │
    ▼
"Có cần nghĩ không?" ─── TRIVIAL CHECK
    │ No
    ▼
"Đủ thông tin chưa?" ─── CLARIFICATION (hỏi lại nếu mơ hồ)
    │ Đủ
    ▼
"Ai nên nghĩ? Nghĩ sâu cỡ nào?" ─── META-THINK (persona + depth + rules)
    │
    ▼
"Làm theo plan nào?" ─── REASON (nếu depth ≥ 3)
    │
    ▼
"Cần phân tích chiến lược?" ─── COGNITIVE FRAMEWORK (nếu depth 4-5)
    │
    ▼
"Thực hiện!" ─── EXECUTE (ReACT loop: think → tool → observe → repeat)
    │
    ▼
"Đủ tốt chưa?" ─── EVALUATE (chấm điểm, retry nếu fail)
    │
    ▼
OUTPUT trả về user
    │
    ▼ (background)
"Học được gì?" ─── SELF-UPDATE (extract lessons, update patterns)
```

---

*Mỗi bước đều là câu hỏi agent tự hỏi mình — không phải rule cứng mà là tư duy adaptive.*
