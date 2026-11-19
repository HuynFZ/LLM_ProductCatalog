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

## 2. Diễn Giải Khoa Học Có Căn Cứ & Bằng Chứng Giải Phẫu Mẫu Thô

1. **Ảo giác thuộc tính có cấu trúc trong điều kiện ngữ cảnh đúng sẵn (Oracle Context):**
   - **Phạm vi kiểm tra:** Chỉ số ảo giác ở đây chỉ kiểm tra các trường có cấu trúc (`recommended_item_id`, `brand`, `price_usd`). Chưa bao hàm kiểm định tính trung thực của văn bản tự do `response_to_user` (nơi mô hình vẫn có thể bịa công dụng hoặc thành phần).
   - **Vai trò của A0 và A1:** Ở A0 và A1, hệ thống không cung cấp danh mục sản phẩm nhưng schema JSON vẫn bắt buộc điền mã ASIN. Mô hình không thể biết trước mã ASIN nội bộ của kho, do đó tỷ lệ ảo giác cao ở A0 (37.8%–64.1%) là hệ quả tất yếu do thiết kế đối chứng không có tri thức (Zero-knowledge control).
   - **Kết luận:** **Trong điều kiện ngữ cảnh đúng sẵn** (ngữ cảnh đã chứa sản phẩm đích + 4 sản phẩm gây nhiễu), ảo giác về các trường có cấu trúc gần như bằng 0 (GPT-4o-mini: 0.0%, Qwen2.5:3B: 0.4%, LLaMA-3.2:3B: 0.8%). Kết quả này chưa phản ánh hiệu năng của một hệ thống RAG đầy đủ ngoài thực tế (nơi module truy xuất có thể trả về tập ứng viên thiếu sản phẩm đích).

2. **Tác động của Persona phòng thủ khi không có ngữ cảnh (A1):**
   - Khi đưa vào Persona và quy tắc ràng buộc (A1), khả năng chặn câu hỏi ngoài danh mục OOC tăng mạnh lên 82.0%–100.0%.
   - Tuy nhiên, do không có dữ liệu danh mục để đối soát, mô hình bị rơi vào tình trạng từ chối nhầm gần như toàn bộ (GPT-4o-mini từ chối nhầm 94.9%, LLaMA từ chối 79.5%). 
   - Ảo giác thấp ở A1 của GPT (4.6%) thực chất là do mẫu số trả lời chỉ còn 23/450 mẫu; và trong 23 mẫu đó, 100% đều là ảo giác.

3. **Hiện tượng nén khóa Schema (Schema Key Substitution) ở Qwen CoT (A4):**
   - Chuỗi suy luận 4 bước trong cấu hình A4 (`thought_1` đến `thought_4`) khiến mô hình 3B hiểu nhầm trường văn bản `thought_3_pros_cons` đã thay thế hai mảng `pros` và `cons`.
   - Đọc mẫu thô xác nhận mô hình vẫn phân tích ưu nhược điểm chi tiết trong thought, nhưng lược bỏ hoàn toàn hai khóa mảng ở JSON gốc. 
   - Verifier lượt 2 (A6) đóng vai trò bộ sửa cấu trúc (Structural Repair), phát hiện trường cons rỗng và bổ sung lại đúng schema JSON (sửa 41/41 ca $C_{neg}$).

4. **Phân tích hành vi từ chối ở mô hình Edge (Qwen và LLaMA):**
   - Theo [analysis_refusal.md](file:///d:/LLM_ProductCatalog/amazon_benchmark/results_ablation/analysis_refusal.md), tỷ lệ từ chối nhầm ở cấu hình A6 của Qwen là **54.2%** (243/448) và LLaMA là **40.4%** (182/450).
   - Bóc tách theo bản chất hành vi:
     - **Trên 100 mẫu $C_{neg}$:** Qwen có **90.0%** (90/100) bật cờ từ chối phạm vi `is_out_of_catalog_rejected`, và **7.0%** (7/100) không bật cờ nhưng để `recommended_item_id = null`. Tổng cộng có **97.0%** (97/100) mẫu $C_{neg}$ không đưa ra đề xuất. Việc mô hình từ chối gợi ý khi sản phẩm có đánh giá tiêu cực thực tế có thể là lời khuyên thận trọng và hợp lý của một trợ lý tư vấn; tuy nhiên việc bật cờ OOC cho thấy mô hình nhầm lẫn ngữ nghĩa giữa "ngoài phạm vi ngành hàng" và "sản phẩm không phù hợp do có nhược điểm".
     - **Trên 348 mẫu Standard:** Qwen có **23.3%** (81/348) bật cờ OOC và **18.7%** (65/348) không gợi ý (tổng từ chối: **42.0%**).
   - Tỷ lệ từ chối cao này là rào cản lớn nhất ngăn cản việc triển khai SLM nguyên bản ra thực tế thương mại, khẳng định SLM chưa thể đạt mức độ vận hành tin cậy tương đương Cloud LLM.

5. **Đánh đổi về Độ trễ và Vi phạm SLA 10 giây ở Mô hình Edge:**
   - GPT-4o-mini đáp ứng tốt ngưỡng tương tác thời gian thực ở toàn bộ cấu hình (P95: 3.66s – 5.54s).
   - Mô hình Local chỉ đạt SLA ở các cấu hình tinh gọn A0–A3 (3.4s – 6.9s).
   - Cấu hình đầy đủ A6 vi phạm nghiêm trọng SLA 10 giây: Qwen P95 đạt **13.5s** (23.8% yêu cầu > 10s) và LLaMA P95 đạt **15.8s** (61.4% yêu cầu > 10s). Quá trình gọi suy luận lần hai của Verifier trên phần cứng Edge tạo ra gánh nặng độ trễ quá lớn.
