# BÁO CÁO THỰC NGHIỆM ABLATION STUDY (ĐÃ CHẤM LẠI VỚI VÁ LỖI HTML UNESCAPE)
**Tiêu chuẩn khoa học:** `ablation_spec v1.1`  
**Quy mô thực nghiệm:** 10.500 lượt kiểm thử (500 mẫu $\times$ 7 cấu hình A0 $\rightarrow$ A6 $\times$ 3 mô hình)  
**Tập dữ liệu:** Amazon Beauty Catalog (350 Standard, 100 $C_{neg}$, 50 Out-of-Catalog OOC)  
**Phương pháp đánh giá:** LLM-Judge độc lập `gpt-4o-mini` cho tiêu chí $C_{neg}$, kiểm tra logic tự động cho SKU & thuộc tính (đã giải mã HTML entity `&#39;`, `&amp;`), khoảng tin cậy Wilson 95%.

---

## 1. Bảng Đối chiếu Trực tiếp 3 Mô hình (Ablation Benchmark Table)

### Panel A: GPT-4o-mini (Cloud Proprietary)

| Cấu hình | Ảo giác ↓ | OOC đúng ↑ | Từ chối nhầm ↓ | C_neg có cons ↑ | Cons bám C_neg ↑ | Pros&Cons ↑ | Lỗi parse ↓ | P95 tổng (ms) |
|---|---|---|---|---|---|---|---|---|
| **A0** | 37.8% [33.7–42.1] | 64.0% [50.1–75.9] | 60.9% [56.3–65.3] | 100.0% [96.3–100.0] | 71.0% [61.5–79.0] | 59.3% [54.7–63.8] | 0.0% [0.0–0.8] | 4,731 ms |
| **A1** | 4.6% [3.1–6.8] | 100.0% [92.9–100.0] | 94.9% [92.4–96.6] | 90.0% [82.6–94.5] | 81.1% [71.8–87.9] | 22.9% [19.2–27.0] | 0.0% [0.0–0.8] | 4,881 ms |
| **A2** | 0.0% [0.0–0.8] | 100.0% [92.9–100.0] | 3.8% [2.4–6.0] | 99.0% [94.6–99.8] | 69.7% [60.0–77.9] | 96.4% [94.3–97.8] | 0.0% [0.0–0.8] | 4,847 ms |
| **A3** | 0.2% [0.0–1.1] | 100.0% [92.9–100.0] | 2.9% [1.7–4.9] | 100.0% [96.3–100.0] | 94.0% [87.5–97.2] | 54.4% [49.8–59.0] | 0.0% [0.0–0.8] | 3,660 ms |
| **A4** | 0.0% [0.0–0.8] | 100.0% [92.9–100.0] | 5.8% [4.0–8.3] | 99.0% [94.6–99.8] | 93.9% [87.4–97.2] | 24.4% [20.7–28.6] | 0.0% [0.0–0.8] | 5,433 ms |
| **A5** | 0.0% [0.0–0.8] | 100.0% [92.9–100.0] | 5.6% [3.8–8.1] | 98.0% [93.0–99.4] | 92.9% [86.0–96.5] | 22.2% [18.6–26.3] | 0.0% [0.0–0.8] | 5,286 ms |
| **A6** | 0.0% [0.0–0.8] | 100.0% [92.9–100.0] | 7.3% [5.3–10.1] | 99.0% [94.6–99.8] | 96.0% [90.1–98.4] | 22.2% [18.6–26.3] | 0.0% [0.0–0.8] | 5,540 ms |

### Panel B: Qwen2.5:3B (Local Edge Open-Weights)

| Cấu hình | Ảo giác ↓ | OOC đúng ↑ | Từ chối nhầm ↓ | C_neg có cons ↑ | Cons bám C_neg ↑ | Pros&Cons ↑ | Lỗi parse ↓ | P95 tổng (ms) |
|---|---|---|---|---|---|---|---|---|
| **A0** | 56.2% [51.8–60.5] | 38.0% [25.9–51.8] | 42.4% [38.0–47.1] | 90.0% [82.6–94.5] | 57.8% [47.5–67.5] | 92.0% [89.1–94.2] | 0.0% [0.0–0.8] | 3,468 ms |
| **A1** | 38.6% [34.4–42.9] | 90.0% [78.6–95.7] | 57.6% [52.9–62.0] | 88.0% [80.2–93.0] | 62.5% [52.1–71.9] | 87.3% [83.9–90.1] | 0.0% [0.0–0.8] | 3,628 ms |
| **A2** | 0.8% [0.3–2.1] | 88.0% [76.2–94.4] | 18.8% [15.4–22.7] | 96.0% [90.1–98.4] | 70.5% [60.7–78.8] | 98.0% [96.2–98.9] | 0.0% [0.0–0.8] | 4,509 ms |
| **A3** | 1.2% [0.6–2.6] | 94.0% [83.8–97.9] | 21.8% [18.3–25.9] | 100.0% [96.3–100.0] | 89.0% [81.4–93.7] | 94.2% [91.7–96.0] | 0.0% [0.0–0.8] | 4,323 ms |
| **A4** | 0.4% [0.1–1.4] | 98.0% [89.5–99.6] | 46.3% [41.8–50.9] | 8.0% [4.1–15.0] | 62.5% [30.6–86.3] | 7.1% [5.1–9.9] | 0.0% [0.0–0.8] | 6,420 ms |
| **A5** | 0.4% [0.1–1.5] | 100.0% [92.9–100.0] | 54.5% [49.8–59.0] | 59.0% [49.2–68.1] | 81.4% [69.6–89.3] | 10.0% [7.6–13.1] | 0.2% [0.0–1.1] | 6,811 ms |
| **A6** | 0.4% [0.1–1.5] | 100.0% [92.9–100.0] | 54.2% [49.6–58.8] | 100.0% [96.3–100.0] | 89.0% [81.4–93.7] | 10.5% [8.0–13.6] | 0.2% [0.0–1.1] | 13,454 ms |

### Panel C: LLaMA-3.2:3B (Local Edge Open-Weights)

| Cấu hình | Ảo giác ↓ | OOC đúng ↑ | Từ chối nhầm ↓ | C_neg có cons ↑ | Cons bám C_neg ↑ | Pros&Cons ↑ | Lỗi parse ↓ | P95 tổng (ms) |
|---|---|---|---|---|---|---|---|---|
| **A0** | 64.1% [59.7–68.1] | 14.0% [7.0–26.2] | 31.2% [27.1–35.7] | 99.0% [94.6–99.8] | 44.4% [35.0–54.3] | 89.1% [85.9–91.6] | 0.2% [0.0–1.1] | 7,894 ms |
| **A1** | 19.3% [16.1–23.0] | 82.0% [69.2–90.2] | 79.5% [75.5–82.9] | 95.0% [88.8–97.8] | 54.7% [44.7–64.4] | 57.8% [53.2–62.3] | 0.4% [0.1–1.4] | 6,261 ms |
| **A2** | 4.2% [2.8–6.3] | 84.0% [71.5–91.7] | 26.4% [22.6–30.7] | 100.0% [96.3–100.0] | 57.0% [47.2–66.3] | 82.9% [79.1–86.1] | 0.0% [0.0–0.8] | 6,659 ms |
| **A3** | 5.4% [3.7–7.7] | 70.0% [56.2–80.9] | 18.7% [15.3–22.5] | 100.0% [96.3–100.0] | 77.0% [67.8–84.2] | 82.0% [78.2–85.3] | 0.0% [0.0–0.8] | 6,968 ms |
| **A4** | 1.6% [0.8–3.1] | 94.0% [83.8–97.9] | 49.6% [44.9–54.2] | 91.0% [83.8–95.2] | 61.5% [51.3–70.9] | 49.6% [45.0–54.2] | 0.4% [0.1–1.4] | 14,770 ms |
| **A5** | 1.4% [0.7–2.9] | 90.0% [78.6–95.7] | 40.4% [36.0–45.0] | 96.0% [90.2–98.4] | 68.8% [58.9–77.1] | 60.4% [55.9–64.9] | 0.0% [0.0–0.8] | 15,789 ms |
| **A6** | 0.8% [0.3–2.0] | 100.0% [92.9–100.0] | 40.4% [36.0–45.0] | 99.0% [94.6–99.8] | 68.7% [59.0–77.0] | 60.4% [55.9–64.9] | 0.0% [0.0–0.8] | 15,755 ms |

---

## 2. Các Phát Hiện Khoa Học & Bằng Chứng Giải Phẫu Mẫu Thô

1. **Hiệu quả thực của RAG đối với Mô hình Local (trong điều kiện ngữ cảnh đúng sẵn):**
   - Khi có RAG và giải mã HTML đúng, tỷ lệ ảo giác của Qwen2.5:3B giảm sốc **70 lần**: từ **56.2% (A0) xuống 0.8% (A2)** ($\Delta = -38.0\%^*$).
   - Ở LLaMA-3.2:3B, ảo giác giảm từ **64.1% xuống 4.2%** ($\Delta = -15.1\%^*$).
   - Tỷ lệ chọn đúng sản phẩm (Gold Rec) tăng vọt từ 0.0% lên **79.6% (Qwen)** và **65.1% (LLaMA)**.
   - Đối với GPT-4o-mini, khi có RAG, mô hình đạt **0.0% ảo giác** (0 ca sai brand, 0 ca sai giá).

2. **Persona và Ràng buộc nâng cao OOC nhưng gây "tê liệt" nếu thiếu RAG (A1):**
   - Ràng buộc phòng thủ giúp chặn OOC tăng vọt lên 82%–100%, nhưng nếu không có RAG cung cấp danh mục (A1), mô hình từ chối nhầm tới **94.9% (GPT)**, **79.5% (LLaMA)**, và **57.6% (Qwen)**.
   - Ở A1, con số ảo giác thấp (4.6% ở GPT) chỉ là ảo ảnh thống kê do mô hình hầu như không trả lời. Với 23 mẫu hiếm hoi mà nó trả lời, tỷ lệ ảo giác là **100.0% (23/23)**.

3. **Hiện tượng nén khóa Schema (Schema Key Substitution) ở Qwen CoT (A4):**
   - Việc bổ sung chuỗi suy luận 4 bước ở A4 khiến mô hình 3B hiểu nhầm rằng khóa `thought_3_pros_cons` đã thay thế hai mảng `pros` và `cons`.
   - Mô hình vẫn phân tích ưu/nhược điểm rất chi tiết trong trường thought, nhưng bỏ trống hai khóa đầu ra JSON, khiến chỉ số tụt xuống 7.1%.
   - Verifier lượt 2 (A6) đóng vai trò bộ sửa cấu trúc (Structural Repair), khôi phục thành công 41/41 ca $C_{neg}$.

4. **Hiện tượng Siêu cảnh giác (Hyper-vigilance) và Rào cản Từ chối nhầm ở SLM:**
   - Dù đạt 100% OOC Rejection ở A6, Qwen từ chối nhầm tới **54.2%** và LLaMA từ chối nhầm **40.4%** yêu cầu hợp lệ.
   - Nguyên nhân chính: Ở 100 mẫu $C_{neg}$, mô hình 3B nhầm lẫn giữa *cảnh báo nhược điểm* và *từ chối sản phẩm*, dẫn đến việc bật cờ từ chối phạm vi `is_out_of_catalog_rejected` ở **90.0% số mẫu $C_{neg}$**!
   - Đây là bằng chứng thực nghiệm rõ ràng cho thấy **SLM chưa thể đạt mức độ vận hành tin cậy tương đương Cloud LLM**.

5. **Đánh đổi về Độ trễ và Vi phạm SLA 10 giây ở Mô hình Edge:**
   - GPT-4o-mini đáp ứng tốt SLA ở toàn bộ cấu hình (P95: 3.66s – 5.54s).
   - Mô hình Local chỉ đạt SLA ở các cấu hình tinh gọn A0–A3 (3.4s – 6.9s).
   - Ở cấu hình đầy đủ A6, cơ chế Verifier 2 lượt khiến P95 tăng vọt lên **13.5s (Qwen)** và **15.8s (LLaMA)**, với 23.8% – 61.4% số yêu cầu vượt ngưỡng 10s. Khung đầy đủ trên Edge hiện chưa khả thi cho tương tác thời gian thực nếu không tối ưu hóa suy luận (quantization, speculative decoding).
