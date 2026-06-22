# Đo chiều sâu tư duy — 4 lần chạy (tách nhiễu) — prompt v4 (đã có D1-D7 rules)

Cùng 1 prompt, cùng 1 bài toán RAG doanh nghiệp, temperature 0.7:

| Run | D1 | D2 | D3 | D4 | D5 | D6 | D7 | Tổng |
|-----|----|----|----|----|----|----|----|------|
| 1 | F | F | F | F | F | F | F | 0/7 |
| 2 | P | P | P | P | P | F | F | 5/7 |
| 3 | P | P | P | F | F | F | P | 4/7 |
| 4 | F | F | F | F | F | F | F | 0/7 |
| **Tỉ lệ** | 50% | 50% | 50% | 25% | 25% | 0% | 25% | **TB 2.2/7** |

## Phát hiện quan trọng
- Biến thiên CỰC LỚN (0→5 cùng prompt). Các con số "1/3→5/5" báo cáo trước CHỈ LÀ 1 MẪU → bị nhiễu phóng đại, KHÔNG đáng tin làm bằng chứng prompt tốt lên.
- Gốc vấn đề KHÔNG phải thiếu luật/đề mục, mà là agent KHÔNG ỔN ĐỊNH thực thi chuỗi tư duy: lúc đào sâu (run 2), lúc làm hời hợt rớt sạch (run 1,4).
- Thêm luật vào prompt (D6 reward-scoring) KHÔNG nâng được — D6 vẫn 0/4.

## Hướng đề xuất (chờ user quyết — KHÔNG tự làm vì đụng kiến trúc loop)
Cần CƠ CHẾ CỨNG (hard-gate trong loop.py) ép agent đi đủ chuỗi Bước 0→1.5 (đào quy mô + đa nhánh + chấm điểm) TRƯỚC khi cho build — giống cách T7/T8 ép spawn_evaluator. Prompt-only đã chứng minh không đủ (giống bài học T7 trước đây).
