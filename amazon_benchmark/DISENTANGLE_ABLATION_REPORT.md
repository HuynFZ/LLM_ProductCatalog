# BÁO CÁO THỰC NGHIỆM BÓC TÁCH TOÀN DIỆN (DISENTANGLEMENT ABLATION REPORT)
**Mô hình nghiên cứu:** `Qwen2.5:3B` (Chạy local trên Ollama, Seed = 42, Temperature = 0.0)  
**Tập dữ liệu độc lập:** `Dev Set 130 mẫu` (`data/dev_test_130.json`: 70 Standard + 20 $C_{neg}$ + 40 Out-of-Catalog)  
**Tính cô lập dữ liệu:** 0 query trùng lặp, 0 user trùng lặp, 0 ASIN trùng lặp với tập test 500 mẫu.  
**Thước đo thống kê:** Toàn bộ tỷ lệ phần trăm được báo cáo kèm **Khoảng tin cậy Wilson 95% CI** `[lower, upper]`.

---

## 1. Bối cảnh & Khắc phục Sai số Phương pháp luận (Methodological Fixes)

Sau đợt phản biện vòng 2, bốn điểm sai sót nghiêm trọng trong thiết kế thực nghiệm đã được phát hiện và xử lý dứt điểm:

1. **Rò rỉ nhãn kiểm thử trong Verifier (Label Leakage):**
   - *Vấn đề:* Ở phiên bản v2/v3, hàm `detect_correction_need` kiểm tra `sample["test_type"] == "out_of_catalog_adversarial"`. Đây là điều kiện "Oracle" bất khả thi trong môi trường triển khai thực tế vì hệ thống không biết trước nhãn kiểm thử.
   - *Khắc phục:* Phân tách rõ ràng hai cơ chế:
     - **Observable Verifier (Khả năng quan sát thực tế):** Chỉ dựa vào xung đột nội bộ giữa văn bản và cờ (`is_out_of_catalog_rejected` vs `recommended_item_id`), từ khóa từ chối trong văn bản, và tín hiệu RAG tại runtime (`neg_n > 0` nhưng `cons` rỗng hoặc mang placeholder).
     - **Oracle Verifier (Cận trên lý thuyết):** Dùng nhãn `test_type` và metadata ẩn để xác lập trần hiệu năng tối đa của LLM lượt 2.
2. **Khử rò rỉ trong Bộ sửa lỗi theo luật (Rule-Based Parser Repair):**
   - Loại bỏ hoàn toàn đối số `sample` khỏi hàm `rule_based_repair`. Mọi quyết định sửa cờ, khôi phục ASIN, trích xuất pros/cons đều chỉ dựa vào nội dung văn bản suy luận (thought/response) và ngữ cảnh danh mục RAG được cấp (`ctx_asins`, `kb`, `ctx_neg_n`).
3. **Phân rã chi tiết 4 luật con (Rule Deconstruction):**
   - Thay vì báo cáo một con số gộp "sửa luật 12.4%", hệ thống phân rã và đo lường độc lập 4 luật: (L1) Cứu ASIN, (L2) Sửa cờ OOC, (L3) Trích xuất pros/cons từ thought, (L4) Điền brand/price từ KB.
4. **Phân tích Cons 3 trạng thái (Tri-State Cons):**
   - Không gộp mảng rỗng `[]` vào "placeholder". Phân loại rạch ròi: `cons_real` (nhược điểm thật có căn cứ), `cons_placeholder` (chuỗi giữ chỗ chuẩn), và `cons_empty` (bỏ trống). Đo lường tác dụng phụ làm gia tăng "nhược điểm tự suy luận" trên mẫu Standard.
5. **Thực nghiệm cấu hình phối hợp (Cascaded Pipeline):**
   - Đánh giá đầy đủ mô hình phối hợp: Prompt v1.2 + Rule Repair (xử lý cú pháp 0ms) + Verifier (chỉ can thiệp trên lỗi còn sót lại).

---

## 2. Bảng Tổng Hợp Kết Quả Bóc Tách Thực Nghiệm

Dưới đây là kết quả của 8 cấu hình được chạy đồng nhất trên cùng tập Dev 130 mẫu với mô hình `qwen2.5:3b`:

| Cấu hình Thực nghiệm | Từ chối nhầm (Type I) ↓ | Chặn OOC (1 - Type II) ↑ | Chọn Gold ASIN ↑ | $C_{neg}$ Cons thật ↑ | Pros&Cons cân bằng ↑ | Tỷ lệ sửa luật (%) | Tỷ lệ gọi Verifier (%) | Độ trễ P95 (ms) ↓ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **(1) v1.1 Thô (Raw)** | 57.8% `[47.5, 67.5]` | **100.0%** `[91.2, 100]` | 42.2% `[32.5, 52.5]` | 35.0% `[18.1, 56.7]` | 15.6% `[9.5, 24.4]` | 0.0% | 0.0% | 6,436 ms |
| **(2) v1.1 + Sửa luật (Rule)** | 7.8% `[3.8, 15.2]` | **100.0%** `[91.2, 100]` | 92.2% `[84.8, 96.2]` | 80.0% `[58.4, 91.9]` | 71.1% `[61.0, 79.5]` | 61.5% `[53.0, 69.5]` | 0.0% | 6,436 ms |
| **(3) v1.2 Thô (Raw)** | 10.1% `[5.4, 18.1]` | 85.0% `[70.9, 92.9]` | 87.6% `[79.2, 93.0]` | 80.0% `[58.4, 91.9]` | 71.9% `[61.8, 80.2]` | 0.0% | 0.0% | 7,385 ms |
| **(4) v1.2 + Sửa luật (Rule)** | **1.1%** `[0.2, 6.1]` | 92.5% `[80.1, 97.4]` | **96.6%** `[90.6, 98.8]` | 90.0% `[69.9, 97.2]` | 76.4% `[66.6, 84.0]` | 12.4% `[7.8, 19.2]` | 0.0% | 7,385 ms |
| **(5) v1.2 + Verifier Thực tế (Obs)** | 10.1% `[5.4, 18.1]` | 92.5% `[80.1, 97.4]` | 87.6% `[79.2, 93.0]` | **100.0%** `[83.9, 100]` | 73.0% `[63.0, 81.2]` | 0.0% | 5.4% `[2.7, 10.8]` | 7,616 ms |
| **(6) v1.2 + Verifier Lý thuyết (Oracle)** | 10.1% `[5.4, 18.1]` | **100.0%** `[91.2, 100]` | 87.6% `[79.2, 93.0]` | 95.0% `[76.4, 99.1]` | 71.9% `[61.8, 80.2]` | 0.0% | 7.0% `[3.7, 12.7]` | 7,538 ms |
| **(7) v1.2 + Phối hợp Thực tế (Cascaded Obs)** | 3.4% `[1.2, 9.4]` | 92.5% `[80.1, 97.4]` | 94.4% `[87.5, 97.6]` | **100.0%** `[83.9, 100]` | **77.5%** `[67.8, 85.0]` | 12.4% `[7.8, 19.2]` | 3.1% `[1.2, 7.7]` | 7,563 ms |
| **(8) v1.2 + Phối hợp Lý thuyết (Cascaded Oracle)** | **1.1%** `[0.2, 6.1]` | **100.0%** `[91.2, 100]` | **96.6%** `[90.6, 98.8]` | 95.0% `[76.4, 99.1]` | 76.4% `[66.6, 84.0]` | 12.4% `[7.8, 19.2]` | 3.1% `[1.2, 7.7]` | 7,418 ms |

> *Ghi chú:* Chỉ số ảo giác tổng hợp ở tất cả các cấu hình sau khi có RAG đều duy trì ở mức 0.0% [0.0%, 2.9%].

---

## 3. Phân Rã 4 Luật Con (Rule Deconstruction Analysis)

Bảng dưới đây bóc tách chính xác tỷ lệ các mẫu được can thiệp bởi từng luật con:

| Cấu hình | Tổng can thiệp luật | L1: Khôi phục ASIN | L2: Sửa cờ OOC | L3: Trích xuất Pros/Cons | L4: Điền Brand/Price KB |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **v1.1 + Sửa luật** | 61.5% (80/130) | 34.6% (45/130) | 21.5% (28/130) | 55.4% (72/130) | 33.8% (44/130) |
| **v1.2 + Sửa luật** | 12.4% (16/129) | 6.2% (8/129) | 4.7% (6/129) | 4.7% (6/129) | 7.0% (9/129) |
| **v1.2 + Phối hợp (Cascaded)** | 12.4% (16/129) | 6.2% (8/129) | 4.7% (6/129) | 4.7% (6/129) | 7.0% (9/129) |

### Nhận xét & Đánh giá khách quan về Bộ sửa luật:
1. **L1 (Khôi phục ASIN) & L2 (Sửa cờ OOC):** Đây là hai luật đóng góp lớn nhất trong việc giảm tỷ lệ từ chối nhầm từ 10.1% xuống 1.1% ở v1.2 (và từ 57.8% xuống 7.8% ở v1.1). Kiểm tra log cho thấy mô hình SLM đã suy luận và đưa ra tên sản phẩm đúng trong phần văn bản, nhưng định dạng JSON ở đầu ra bị khuyết khóa ngoài. Bộ luật hoạt động đúng nghĩa là một parser cứu dữ liệu cú pháp.
2. **L4 (Điền Brand/Price từ KB):** Đóng góp trực tiếp vào việc đảm bảo 0% sai lệch thuộc tính. Tuy nhiên, cần thừa nhận thẳng thắn: **0% sai lệch brand/price sau khi qua L4 là hệ quả cơ học của việc truy vấn từ KB, không còn phản ánh năng lực sinh text nguyên bản của mô hình.**
3. **Mức độ phụ thuộc vào luật giảm 5 lần:** Ở v1.1, hệ thống phụ thuộc nặng nề vào luật (61.5% mẫu phải sửa). Ở v1.2, prompt đã định hướng tư duy tốt hơn nên số mẫu cần luật can thiệp giảm xuống chỉ còn 12.4%.

---

## 4. Phân Tích Cons 3 Trạng Thái & Tác Dụng Phụ (Side Effects)

Khi bóc tách tri-state (`cons_real` vs `cons_placeholder` vs `cons_empty`), bức tranh thực tế về năng lực cân bằng ưu/nhược điểm được làm sáng tỏ:

| Cấu hình | $C_{neg}$: Nhược điểm thật (Đạt) ↑ | $C_{neg}$: Placeholder (Chưa đạt) ↓ | $C_{neg}$: Bỏ trống (Hỏng) ↓ | Standard: Placeholder (Chuẩn) | Standard: Bỏ trống | Standard: Bịa nhược điểm (Tác dụng phụ) ↓ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **v1.1 Thô (Raw)** | 35.0% (7/20) | 0.0% (0/20) | 65.0% (13/20) | 15.7% (11/70) | 82.9% (58/70) | **1.4% (1/70)** |
| **v1.1 + Sửa luật** | 80.0% (16/20) | 0.0% (0/20) | 20.0% (4/20) | 70.0% (49/70) | 4.3% (3/70) | **25.7% (18/70)** |
| **v1.2 Thô (Raw)** | 80.0% (16/20) | 5.0% (1/20) | 15.0% (3/20) | 71.0% (49/69) | 4.3% (3/69) | **24.6% (17/69)** |
| **v1.2 + Sửa luật** | 90.0% (18/20) | 5.0% (1/20) | 5.0% (1/20) | 72.5% (50/69) | 0.0% (0/69) | **27.5% (19/69)** |
| **v1.2 + Verifier Thực tế** | **100.0% (20/20)** | 0.0% (0/20) | 0.0% (0/20) | 71.0% (49/69) | 4.3% (3/69) | **24.6% (17/69)** |
| **v1.2 + Phối hợp Thực tế** | **100.0% (20/20)** | 0.0% (0/20) | 0.0% (0/20) | 72.5% (50/69) | 0.0% (0/69) | **27.5% (19/69)** |

### Phát hiện quan trọng về Tác dụng phụ:
1. **v1.1 Thô ít bịa cons nhất (1.4%), nhưng thất bại ở $C_{neg}$ (65% bỏ trống):** Ở v1.1 thô, mô hình gần như bỏ trống toàn bộ trường cons (82.9% ở Standard và 65% ở $C_{neg}$). Do đó, nó hầu như không bịa đặt nhược điểm trên Standard, nhưng lại không cảnh báo được rủi ro trên $C_{neg}$.
2. **Tác dụng phụ của việc ép nêu nhược điểm:**
   - Khi chuyển sang prompt v1.2 (bắt buộc phân tích ưu/nhược điểm trong CoT), tỷ lệ phát hiện nhược điểm thật trên $C_{neg}$ tăng vọt lên **80.0% - 90.0%**.
   - Tuy nhiên, cái giá phải trả là trên các mẫu Standard (sản phẩm không có review xấu), tỷ lệ mô hình tự ngoại suy các câu cảnh báo chung chung (ví dụ: *"chú ý test phản ứng nếu da quá nhạy cảm"*, *"có mùi hương nhẹ có thể không hợp ai dị ứng mùi"*) tăng từ **1.4% lên 24.6% (v1.2 thô) và 27.5% (sau sửa luật)**.
   - Khi bộ sửa luật can thiệp (L3), việc quét các từ khóa cảnh báo trong phần suy luận nháp (`thought_3_balance`) đã vô tình chuyển các phán đoán cẩn trọng của mô hình thành các mục trong trường `cons`, làm tăng nhẹ hiện tượng này (+2.9%).

---

## 5. So Sánh Chi Tiết: Verifier Thực Tế (Observable) vs Lý Thuyết (Oracle)

| Tiêu chí | Verifier Thực tế (Observable) | Verifier Lý thuyết (Oracle) | Đánh giá & Rút kinh nghiệm |
| :--- | :---: | :---: | :--- |
| **Tín hiệu kích hoạt (Triggers)** | Mâu thuẫn text vs boolean, RAG có review xấu nhưng cons thiếu | Nhãn ẩn `sample["test_type"] == OOC`, `negative_constraints` | Observable hoàn toàn khả thi khi deploy production. Oracle chỉ là trần lý thuyết. |
| **Tỷ lệ kích hoạt (Tập Dev 130)** | **5.4%** (7/129 mẫu) | **7.0%** (9/129 mẫu) | Observable nhận diện được 7/9 ca lỗi thực sự mà không cần nhãn kiểm thử. |
| **Báo động nhầm (False Alarms)** | **0.0%** (0/69 mẫu Standard đúng) | **0.0%** (0/69 mẫu Standard đúng) | Observable không kích hoạt nhầm trên bất kỳ mẫu nào đã đúng sẵn. |
| **Tỷ lệ sửa thành công** | **100.0%** (7/7 ca) | **100.0%** (9/9 ca) | Cả hai đều đạt 100% sửa đúng khi đã kích hoạt. |
| **Chặn OOC sau Verifier** | **92.5%** (37/40) | **100.0%** (40/40) | Oracle chặn được 100% vì luôn ép từ chối nếu là nhãn OOC. Observable chặn 92.5% (bỏ sót 3 ca không lộ từ khóa). |
| **$C_{neg}$ Cons thật sau Verifier** | **100.0%** (20/20) | **95.0%** (19/20) | Observable phát hiện hoàn hảo dựa vào `ctx_neg_n > 0`. |
| **Độ trễ P95 gia tăng** | **+231.6 ms** (7,385 → 7,616 ms) | **+153.1 ms** (7,385 → 7,538 ms) | Chi phí độ trễ của Verifier là cực nhỏ vì chỉ kích hoạt trên 5.4% mẫu. |

---

## 6. Đường Cong Đánh Đổi (Trade-off Curve & Pareto Frontier)

Đồ thị đường cong đánh đổi giữa **Lỗi loại I (Từ chối nhầm yêu cầu hợp lệ)** và **Lỗi loại II (Bỏ lọt yêu cầu ngoài danh mục)** đã được vẽ và lưu tại `amazon_benchmark/tradeoff_curve_qwen.png`:

```
              Tỷ lệ Bỏ lọt OOC (Type II Error = 100 - OOC Correct %)
     30% |
         |
     25% |
         |
     20% |
         |          (v1.2 Thô)
     15% |          [10.1%, 15.0%]
         |
     10% |  (v1.2+Rule)       (v1.2+Verifier Obs)
         |  [1.1%, 7.5%]      [10.1%, 7.5%]
      5% |        \             /
         |         (v1.2+Cascaded Obs)★ [3.4%, 7.5%]
      0% |----+---------------------------------------------------+--- (v1.1 Thô) [57.8%, 0.0%]
             0%     5%     10%    15%    20%    25%    30%   ... 60%
                     Tỷ lệ Từ chối nhầm In-Catalog (Type I Error %)
```

### Phân tích Đường biên Pareto:
1. **v1.1 Thô vs v1.2 Thô không phải hơn kém tuyệt đối, mà là hai cực đoan trên đường đánh đổi:**
   - **v1.1 Thô:** Đạt 0% bỏ lọt OOC (chặn 100%), nhưng phải trả giá bằng **57.8% từ chối nhầm** ("Hội chứng siêu cảnh giác").
   - **v1.2 Thô:** Nới lỏng định nghĩa cờ giúp từ chối nhầm giảm mạnh xuống **10.1%**, nhưng chấp nhận bỏ lọt **15.0% OOC**.
2. **Vai trò thực sự của Bộ sửa luật (Rule Repair):**
   - Bộ sửa luật giúp dịch chuyển toàn bộ điểm làm việc về phía gốc tọa độ tối ưu: kéo v1.1 từ (57.8%, 0%) về (7.8%, 0%), và kéo v1.2 từ (10.1%, 15.0%) về (1.1%, 7.5%).
3. **Cấu hình Tối ưu Triển khai Thực tế (Cascaded Observable):**
   - Điểm **v1.2 + Cascaded Obs**: Đạt **3.4% từ chối nhầm** và **7.5% bỏ lọt OOC**, đưa $C_{neg}$ cons lên **100%**, tỷ lệ chọn gold **94.4%**, và độ trễ P95 chỉ **7,563 ms** (thấp hơn nhiều ngưỡng SLA 10,000 ms).
   - Đây chính là cấu hình cân bằng nhất giữa an toàn hệ thống (Type II) và trải nghiệm mua sắm của người dùng (Type I).

---

## 7. Kết Luận & Khuyến Nghị cho Luận Văn / Bài Báo

1. **Rút lại kết luận "Verifier dư thừa":** Dữ liệu chứng minh Verifier không hề dư thừa. Dù bộ sửa luật giải quyết rất tốt lỗi cú pháp (0ms), Verifier là thành phần duy nhất có khả năng sinh lại ngôn ngữ để giải quyết dứt điểm các ca khuyết nhược điểm $C_{neg}$ phức tạp (đưa từ 90% lên 100%).
2. **Áp dụng mô hình Phối hợp (Cascaded Architecture):** Khuyến nghị mô hình phân tầng: *Prompt v1.2 -> Rule-Based Repair -> Observable Verifier (chỉ gọi theo điều kiện lọc)*. Kiến trúc này tối ưu cả về độ chính xác lẫn hiệu năng (chỉ 3.1% mẫu cần gọi thêm LLM, P95 giữ nguyên mức 7.5s).
3. **Minh bạch hóa các giới hạn:**
   - Nêu rõ 0% sai lệch brand/price là nhờ bước hậu kiểm từ KB (L4).
   - Thừa nhận việc nâng cao nhận thức về rủi ro ở $C_{neg}$ có tác dụng phụ làm tăng ~25% cảnh báo cẩn trọng chung trên mẫu Standard.
   - Khẳng định 100% chặn OOC trước đây của Verifier là cận trên lý thuyết (Oracle), trong khi hiệu năng triển khai thực tế bằng tín hiệu quan sát (Observable) đạt 92.5%.
