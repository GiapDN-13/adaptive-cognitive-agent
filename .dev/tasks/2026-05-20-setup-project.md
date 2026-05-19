# Task: Setup Project Structure

## 1. Task chuẩn bị làm là gì
Khởi tạo project Python với đầy đủ folder structure, dependencies, config, và LLM client wrapper. Đây là nền tảng để build toàn bộ SmartAgent pipeline.

## 2. Làm như thế nào
- Dùng `uv` để init project (nhanh hơn poetry)
- Tạo folder structure theo plan: `src/smart_agent/` với các sub-modules (graph, nodes, tools, prompts, memory, ui)
- Setup `pyproject.toml` với dependencies: langgraph, google-genai, pydantic, pydantic-settings, streamlit
- Tạo `.env.example` cho API key
- Tạo `config.py` (pydantic-settings)
- Tạo `llm.py` (Gemini Flash/Pro client wrapper)

## 3. Ảnh hưởng ra sao
- Đây là task đầu tiên, chưa có code nào → không ảnh hưởng gì
- Thiết lập convention cho toàn bộ project: naming, imports, config pattern
- LLM client wrapper sẽ được dùng bởi TẤT CẢ nodes sau này

## 4. Triển khai như thế nào
- Step 1: uv init + install deps
- Step 2: Tạo folder structure
- Step 3: Viết config.py
- Step 4: Viết llm.py
- Step 5: Viết .env.example
- Step 6: Test LLM client hoạt động

## 5. Kiểm thử ra sao
- Import thành công tất cả modules
- `config.py` load được settings từ .env
- `llm.py` gọi được Gemini Flash với 1 prompt đơn giản
- Folder structure đúng theo plan

## 6. Kết quả như thế nào
- [x] Project init thành công (uv init + hatchling build system)
- [x] Dependencies installed (82 packages: langgraph, google-genai, boto3, pydantic, streamlit...)
- [x] Config loads correctly (supports both Gemini + Bedrock providers)
- [x] LLM client connects and responds (Bedrock Claude Sonnet 4.6 verified)
- [x] All __init__.py files present
- [x] All module imports verified
- [x] Full pipeline test: 6 test cases passed
  - Trivial detection: 3/3 correct
  - Complex classification: domains, complexity, needs_search all accurate
  - Clarification detection: "Tạo landing page" + "Thiết kế microservice payment" correctly flagged
