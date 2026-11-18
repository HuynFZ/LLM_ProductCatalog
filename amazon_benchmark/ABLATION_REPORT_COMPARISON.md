# BÁO CÁO THỰC NGHIỆM ABLATION STUDY: SO SÁNH CLOUD (GPT-4o-mini) VÀ LOCAL (Qwen2.5:3B)
**Tiêu chuẩn:** `ablation_spec v1.1`  
**Quy mô:** 7.000 lượt kiểm thử (500 mẫu $\times$ 7 cấu hình A0 $\rightarrow$ A6 $\times$ 2 mô hình)  
**Tập dữ liệu:** Amazon Beauty Catalog (350 Standard, 100 $C_{neg}$, 50 Out-of-Catalog OOC)  
**Phương pháp đánh giá:** LLM-Judge độc lập `gpt-4o-mini` cho $C_{neg}$, kiểm tra logic tự động cho SKU & thuộc tính, khoảng tin cậy Wilson 95%.

---

## 1. Bảng Đối chiếu Trực tiếp (Markdown Table)

### Panel A: GPT-4o-mini (Cloud Proprietary)

| Cấu hình | Ảo giác ↓ | OOC đúng ↑ | Từ chối nhầm ↓ | C_neg có cons ↑ | Cons bám C_neg ↑ | Pros&Cons ↑ | Lỗi parse ↓ | P95 tổng (ms) |
|---|---|---|---|---|---|---|---|---|
| **A0** | 37.8% [33.7–42.1] | 64.0% [50.1–75.9] | 60.9% [56.3–65.3] | 100.0% [96.3–100.0] | 71.0% [61.5–79.0] | 59.3% [54.7–63.8] | 0.0% [0.0–0.8] | 4,731 ms |
| **A1** | 4.6% [3.1–6.8] | 100.0% [92.9–100.0] | 94.9% [92.4–96.6] | 90.0% [82.6–94.5] | 81.1% [71.8–87.9] | 22.9% [19.2–27.0] | 0.0% [0.0–0.8] | 4,881 ms |
| **A2** | 6.6% [4.7–9.1] | 100.0% [92.9–100.0] | 3.8% [2.4–6.0] | 99.0% [94.6–99.8] | 69.7% [60.0–77.9] | 96.4% [94.3–97.8] | 0.0% [0.0–0.8] | 4,847 ms |
| **A3** | 7.2% [5.2–9.8] | 100.0% [92.9–100.0] | 2.9% [1.7–4.9] | 100.0% [96.3–100.0] | 94.0% [87.5–97.2] | 54.4% [49.8–59.0] | 0.0% [0.0–0.8] | 3,660 ms |
| **A4** | 6.8% [4.9–9.4] | 100.0% [92.9–100.0] | 5.8% [4.0–8.3] | 99.0% [94.6–99.8] | 93.9% [87.4–97.2] | 24.4% [20.7–28.6] | 0.0% [0.0–0.8] | 5,433 ms |
| **A5** | 6.8% [4.9–9.4] | 100.0% [92.9–100.0] | 5.6% [3.8–8.1] | 98.0% [93.0–99.4] | 92.9% [86.0–96.5] | 22.2% [18.6–26.3] | 0.0% [0.0–0.8] | 5,286 ms |
| **A6** | 6.2% [4.4–8.7] | 100.0% [92.9–100.0] | 7.3% [5.3–10.1] | 99.0% [94.6–99.8] | 96.0% [90.1–98.4] | 22.2% [18.6–26.3] | 0.0% [0.0–0.8] | 5,540 ms |

### Panel B: Qwen2.5:3B (Local Open-Weights)

| Cấu hình | Ảo giác ↓ | OOC đúng ↑ | Từ chối nhầm ↓ | C_neg có cons ↑ | Cons bám C_neg ↑ | Pros&Cons ↑ | Lỗi parse ↓ | P95 tổng (ms) |
|---|---|---|---|---|---|---|---|---|
| **A0** | 56.2% [51.8–60.5] | 38.0% [25.9–51.8] | 42.4% [38.0–47.1] | 90.0% [82.6–94.5] | 57.8% [47.5–67.5] | 92.0% [89.1–94.2] | 0.0% [0.0–0.8] | 3,468 ms |
| **A1** | 38.6% [34.4–42.9] | 90.0% [78.6–95.7] | 57.6% [52.9–62.0] | 88.0% [80.2–93.0] | 62.5% [52.1–71.9] | 87.3% [83.9–90.1] | 0.0% [0.0–0.8] | 3,628 ms |
| **A2** | 4.6% [3.1–6.8] | 88.0% [76.2–94.4] | 18.8% [15.4–22.7] | 96.0% [90.1–98.4] | 70.5% [60.7–78.8] | 98.0% [96.2–98.9] | 0.0% [0.0–0.8] | 4,509 ms |
| **A3** | 3.8% [2.5–5.9] | 94.0% [83.8–97.9] | 21.8% [18.3–25.9] | 100.0% [96.3–100.0] | 89.0% [81.4–93.7] | 94.2% [91.7–96.0] | 0.0% [0.0–0.8] | 4,323 ms |
| **A4** | 3.8% [2.5–5.9] | 98.0% [89.5–99.6] | 46.3% [41.8–50.9] | 8.0% [4.1–15.0] | 62.5% [30.6–86.3] | 7.1% [5.1–9.9] | 0.0% [0.0–0.8] | 6,420 ms |
| **A5** | 3.0% [1.8–4.9] | 100.0% [92.9–100.0] | 54.5% [49.8–59.0] | 59.0% [49.2–68.1] | 81.4% [69.6–89.3] | 10.0% [7.6–13.1] | 0.2% [0.0–1.1] | 6,811 ms |
| **A6** | 3.0% [1.8–4.9] | 100.0% [92.9–100.0] | 54.2% [49.6–58.8] | 100.0% [96.3–100.0] | 89.0% [81.4–93.7] | 10.5% [8.0–13.6] | 0.2% [0.0–1.1] | 13,454 ms |

---

## 2. 4 Điểm Sáng Học thuật Rút ra từ So sánh Đối đầu:

1. **Hiệu ứng "Phép màu" của RAG đối với Mô hình Local 3B:**
   - Ở baseline A0, Qwen2.5:3B bị ảo giác tới **56.2%**. Khi nạp RAG (A2), tỷ lệ ảo giác giảm sốc 12 lần, rớt xuống chỉ còn **4.6%**! RAG chính là điều kiện tiên quyết để đưa mô hình nhỏ ra vận hành thực tế.
2. **Hiện tượng Quá tải Suy luận (Context Forgetting) ở Mô hình 3B:**
   - Khi áp dụng CoT (A4), do phải sinh thêm các trường suy luận dài (`thought_1..4`), mô hình 3B bị quên hướng dẫn ở cuối, khiến tỷ lệ sinh cons ở mẫu $C_{neg}$ tụt dốc từ **100% (ở A3) xuống còn 8.0% (ở A4)**!
3. **Giá trị Cốt lõi của Verifier lượt 2 (A6) — Bằng chứng khoa học quyết định:**
   - Checklist tự kiểm tra trong prompt (A5) chỉ cứu vãn được tỷ lệ có cons lên **59.0%** (khẳng định giả thuyết H5: SelfCheck ít tác dụng với mô hình nhỏ).
   - Nhưng khi có **Verifier lượt hai (A6)** can thiệp: Hệ thống phát hiện đúng 41 ca thiếu cons và sửa thành công **100.0% (41/41 ca)**, kéo chỉ số $C_{neg}$ có cons trở lại mức tuyệt đối **100.0%**!
   - Điều này chứng minh luận điểm trong luận văn: *Với mô hình nhỏ chạy Edge, cơ chế Verifier độc lập ở lượt hai là bắt buộc, không thể thay thế bằng prompt checklist đơn thuần.*
4. **Độ an toàn Zero-Hallucination về SKU:**
   - Cả hai mô hình khi chạy ở cấu hình A6 đều đạt **0.0% mã ASIN ảo ngoài KB** trên toàn bộ 450 mẫu trong danh mục.
