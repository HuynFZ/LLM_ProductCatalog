# Bảng So Sánh Đánh Giá Các Mô Hình (4-Pillar Conversational E-Commerce Framework)

| Mô hình | N | Độ trễ TB (ms) | P95 (ms) | JSON Hợp lệ (%) | Tỷ lệ Ảo giác (%) | Chặn Ngoại lai OOC (%) | Vi phạm C_neg (%) | Cân bằng Pros/Cons (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| gemini-1.5-flash-lite | 500 | 3233.1 | 3921.5 | 99.6 | 0.4 | 98.0 | 0.0 | 90.2 |
| gpt-4o-mini | 500 | 4875.0 | 6033.8 | 99.8 | 0.2 | 98.0 | 0.0 | 89.8 |
| gemma2:2b | 500 | 6880.8 | 9172.2 | 92.6 | 7.6 | 96.0 | 0.0 | 65.6 |
| qwen2.5:3b | 500 | 6940.8 | 9000.1 | 98.6 | 2.6 | 100.0 | 0.0 | 55.4 |
| llama3.2:3b | 500 | 9172.0 | 12780.8 | 100.0 | 4.0 | 100.0 | 2.0 | 32.8 |
| gemini-1.5-flash | 210 | 9447.8 | 13046.7 | 100.0 | 0.0 | 100.0 | 0.0 | 90.0 |

*Ghi chú: Tỷ lệ Ảo giác và Vi phạm C_neg càng thấp càng tốt; Chặn OOC và Cân bằng Pros/Cons càng cao càng tốt.*
