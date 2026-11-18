# ablation_spec v1.1 — Thực nghiệm Ablation Khung Prompt 4 Trụ cột (Chatbot TMĐT)

**Trạng thái:** đề xuất v1.1, dựa trên bản v1.0 của Ngọc, cần Ngọc xác nhận các quyết định ở Mục 2.
**Runner:** `amazon_benchmark/benchmark_runner_ablation_v3.py` (đặt cạnh `benchmark_runner_4pillars_v2.py`).
**Phạm vi:** Bộ 1 (500 mẫu: 350 thường, 100 C_neg, 50 OOC). Chưa gồm ESCI.

---

## 1. Mục tiêu

Đo đóng góp của từng thành phần trong khung 4 trụ cột bằng chuỗi cấu hình **cộng dồn** A0 → A6, trên các chỉ số về ảo giác, chặn OOC, cân bằng Pros/Cons và độ trễ. Mỗi chỉ số báo cáo kèm số mẫu (k/n) và khoảng tin cậy 95%.

## 2. Nhật ký quyết định (v1.0 → v1.1)

| # | Vấn đề ở v1.0 | Quyết định v1.1 | Lý do |
|---|---|---|---|
| D1 | RAG thật: k=5 sản phẩm truy xuất + r=10 review/sản phẩm | **Ngữ cảnh = sản phẩm đúng + (k−1)=4 sản phẩm gây nhiễu ngẫu nhiên** (`--k 5`). C_neg mặc định = review của mẫu test (`--neg_r 1`); `--neg_r 10` nạp thêm review 1–2 sao từ `reviews_Beauty_5` | Kịp lịch 5 ngày; vẫn buộc mô hình *chọn* sản phẩm. Truy xuất thật (BM25) để Phase 2 |
| D2 | A0–A4 văn bản tự do, chỉ A5 trả JSON → M3/M4 của A0–A4 bằng 0 do không parse được; M1 của A0/A1 ≈ 0 vì không in ASIN | **Một schema JSON thống nhất cho mọi cấu hình** (Mục 5) | Schema là thước đo, không phải biến thí nghiệm. Ngữ nghĩa hành vi chỉ đến từ các khối prompt |
| D3 | A5 bỏ hiển thị CoT của A4 và đổi định dạng → A4→A5 đổi nhiều thứ cùng lúc | **Cấu hình cộng dồn thuần** A0…A6 (Mục 4) | Ablation hợp lệ chỉ khi mỗi bước thêm đúng một thành phần |
| D4 | "Verifier" = checklist trong prompt, nhưng slide/repo dùng lượt gọi thứ hai | **Tách đôi:** A5 = checklist tự kiểm tra trong prompt; A6 = + lượt gọi Verifier (khung đầy đủ, khớp slide) | Bài mô tả đúng cái được chạy |
| D5 | M4 Type-I là phần bù của M3 (θ=0.5 vs 1−θ=0.5); Type-II dựa từ khóa quá nhiễu; "vi phạm C_neg" mang hai nghĩa | **Bỏ Type-I/II.** Giữ `cons_missing` (thiếu cons), `cons_grounded` (judge), và đổi tên thống nhất | Tránh chỉ số thừa và trùng tên |
| D6 | `all-MiniLM-L6-v2` (tiếng Anh) so cons tiếng Việt với review tiếng Anh, ngưỡng 0.35 chưa hiệu chuẩn | **LLM-judge** (`--judge_model`, khác mô hình đang test). Hiệu chuẩn bằng ~50 mẫu chấm tay (độ đồng thuận mục tiêu ≥ 80%) | Đa ngôn ngữ, không cần ngưỡng tùy ý |
| D7 | Type-B kiểm tra `ingredients`, `rating` | KB chỉ có title/brand/categories/price/description → **chỉ kiểm tra `brand` và `price`** (khớp mềm brand; giá lệch > 20%) | Dữ liệu không có trường khác |
| D8 | Tập "100 truy vấn hợp lệ" riêng | Dùng 450 mẫu trong danh mục có sẵn (350 + 100) để đo từ chối nhầm | Không cần tạo thêm dữ liệu |
| D9 | Mẫu OOC trong prompt nhận thông báo "0 kết quả" | **Mẫu OOC nhận k sản phẩm nhiễu** (`--ooc_context decoy`) | Thông báo "0 kết quả" làm lộ đáp án |
| D10 | Ánh xạ trường | Runner đọc `sample_id`, `user_query`, `test_type`, `ground_truth_target`, `negative_constraints` | Khớp repo |

## 3. Tham số cố định

| Tham số | Giá trị |
|---|---|
| temperature | 0.0 |
| seed | 42 (OpenAI `seed`, Ollama `options.seed`, Gemini `seed`) |
| max_tokens | 1024 (A0–A3), 1500 (A4–A6, có CoT) |
| k (số sản phẩm trong ngữ cảnh) | 5 |
| neg_r | 1 (mặc định) |
| timeout | 60 s (SLA 10 s đo bằng độ trễ, không ngắt request) |
| judge | mô hình khác mô hình đang test (ví dụ judge gpt-4o-mini cho mô hình local) |

Ghi trong mỗi dòng log: model ID thực tế do API trả về, temperature, max_tokens, seed, `prompt_version`, `prompt_hash`.

## 4. Cấu hình A0–A6 (cộng dồn)

| Cấu hình | Thành phần | Khác biệt so với bước trước |
|---|---|---|
| **A0** | không có gì | **Không có system prompt.** Chỉ câu hỏi + schema JSON |
| **A1** | + `profile` | Persona BeautyAdvisor, phạm vi ngành, luật chống bịa, luật cân bằng ưu/nhược |
| **A2** | + `rag` | Khối `[DANH MỤC SẢN PHẨM]` (gold + nhiễu) và luật chỉ dùng danh mục |
| **A3** | + `cneg` | Khối `[ĐÁNH GIÁ TIÊU CỰC TỪ NGƯỜI DÙNG]` và luật nhược điểm phải bám đánh giá |
| **A4** | + `cot` | Quy trình 4 bước, ghi vào các trường `thought_1..4` của JSON |
| **A5** | + `selfcheck` | Checklist tự kiểm tra trong system prompt (một lượt gọi) |
| **A6** | + `verifier` | Lượt gọi sửa lỗi thứ hai, kích hoạt theo luật (Mục 6.5). **= khung đầy đủ** |

`--config A6 --no_verifier` cho kết quả trùng A5 (cùng tập thành phần) và dùng chung file kết quả.

### Giả thuyết (giữ H0–H4 của v1.0, tách H5 thành H5/H6)

- **H0:** không có kỹ thuật nào → ảo giác, lỗi OOC và thiếu nhược điểm cao nhất (điểm xuất phát).
- **H1:** Persona + ràng buộc (A1) giảm OOC pass-through và từ chối nhầm, nhưng chưa giảm được ảo giác SKU vì chưa có dữ liệu.
- **H2:** Ngữ cảnh danh mục (A2) giảm mạnh ảo giác ASIN/thuộc tính, nhưng vẫn thiên về mặt tích cực.
- **H3:** Ngữ cảnh C_neg (A3) tăng tỷ lệ có cons và cons bám đánh giá thật.
- **H4:** CoT 4 bước (A4) giảm thêm ảo giác và cải thiện lập luận, đánh đổi bằng độ trễ và token.
- **H5:** Checklist tự kiểm tra (A5) cải thiện nhẹ OOC và thiếu cons ở mô hình đủ lớn; ít hiệu quả ở mô hình ≤3B.
- **H6:** Verifier lượt hai (A6) khắc phục phần lớn ca OOC lọt và thiếu cons, đánh đổi bằng độ trễ tăng.

## 5. Schema đầu ra (giống nhau ở mọi cấu hình)

```json
{
  "[A4+] thought_1_context / thought_2_catalog_check / thought_3_pros_cons / thought_4_decision": "...",
  "response_to_user": "câu trả lời gửi khách hàng",
  "recommended_item_id": "ASIN hoặc null",
  "brand": "thương hiệu sản phẩm gợi ý hoặc null",
  "price_usd": "số hoặc null",
  "is_out_of_catalog_rejected": "true nếu từ chối vì ngoài phạm vi, ngược lại false",
  "pros": ["..."],
  "cons": ["..."]
}
```

Mô tả các trường trung tính (không gợi ý khi nào phải từ chối hay phải nêu nhược điểm). Phần gợi ý hành vi nằm ở các khối `profile/rag/cneg/cot/selfcheck`.

## 6. Chỉ số

**Quy ước mẫu số:** mẫu `api_error` bị loại khỏi mọi mẫu số (chạy lại bằng `--retry_errors`). Mẫu `parse_fail` (API OK nhưng không có JSON hợp lệ) được tính là *thất bại* ở các chỉ số đúng/sai (OOC đúng, có cons, Pros/Cons) nhưng **không** tính là ảo giác. Tên cột trong CSV nằm trong ngoặc.

### 6.1 Ảo giác (M1)

- **ASIN ảo** (`hallu_asin`): `recommended_item_id` khác null và không có trong KB. Mẫu số: mẫu trong danh mục, JSON hợp lệ.
- **Thuộc tính sai** (`hallu_attr`): sản phẩm gợi ý có trong KB nhưng `brand` không khớp mềm (chuẩn hóa chữ thường, chứa nhau) hoặc `price_usd` lệch > 20% so với giá KB (chỉ kiểm tra khi KB có giá).
- **Gợi ý không có căn cứ** (`unsupported_rec`): ASIN ảo, hoặc có trong KB nhưng không nằm trong ngữ cảnh đã cung cấp.
- **Chọn đúng sản phẩm đích** (`rec_is_gold`): gợi ý đúng sản phẩm mà câu hỏi nhắm tới.
- **Ảo giác tổng hợp** (`hallucination_any`) = ASIN ảo ∨ thuộc tính sai ∨ OOC gợi ý sai. Mẫu số: JSON hợp lệ.

### 6.2 OOC và từ chối nhầm (M2)

- **OOC đúng** (`ooc_correct`): `is_out_of_catalog_rejected = true` và `recommended_item_id = null`. Mẫu số: 50 mẫu OOC.
- **OOC gợi ý sai** (`ooc_wrong_rec`): có gợi ý sản phẩm ở mẫu OOC.
- **Từ chối nhầm** (`false_refusal`): ở mẫu trong danh mục mà mô hình từ chối hoặc không gợi ý gì.

### 6.3 Cân bằng ưu/nhược (M3)

- **Có cons** (`cons_nonempty`, `cons_nonempty_pre` trước Verifier): mảng `cons` không rỗng.
- **Thiếu cons** (`cons_missing`): mẫu C_neg mà `cons` rỗng. (Trước đây có tên "vi phạm C_neg".)
- **Cons bám C_neg** (`cons_grounded`): judge trả `covers = true`. Chỉ chấm mẫu C_neg có cons không rỗng; mẫu số là số mẫu được chấm.
- **Pros&Cons** (`pros_cons_balanced`): cả hai mảng không rỗng, **chỉ tính trên mẫu trong danh mục** (không tính 50 mẫu OOC, vì từ chối đúng thì mảng rỗng).

### 6.4 Độ trễ và chi phí (M5)

- `latency_ms` (lần gọi chính), `verifier_latency_ms`, `total_latency_ms` (cộng cả hai). Báo cáo trung bình và P95 của lần gọi chính và của tổng.
- `total_tokens` trung bình (khi API trả về).

### 6.5 Verifier (A6)

- Kích hoạt khi: (a) mẫu OOC mà có gợi ý hoặc không từ chối (`ooc_not_rejected`); (b) mẫu C_neg có review tiêu cực mà `cons` rỗng (`missing_cons`).
- Gộp các trường sửa vào JSON gốc (giữ các trường khác, như `pros`). Thành công khi: OOC → từ chối và `recommended_item_id = null`; thiếu cons → `cons` không rỗng.
- `needs_correction` luôn được ghi (kể cả khi tắt Verifier), nên chạy A5 cho biết sẵn tỷ lệ ca cần can thiệp.

### 6.6 Thống kê

Khoảng tin cậy Wilson 95% cho mọi tỷ lệ. So sánh hai cấu hình liền kề trên cùng 500 mẫu: bootstrap ghép cặp (10.000 lần) — bổ sung ở Ngày 3.

## 7. Log

Mỗi (mô hình, cấu hình) sinh ba file trong `results_ablation/`, tên dạng `<model>_<config>` (`:` và `/` thay bằng `-`):

- `.jsonl`: mỗi dòng gồm `sample_id, model, config, timestamp (UTC+7), prompt{system,user}, context{catalog_asins, gold_asin, neg_review_n}, raw_output, parsed_json, latency_ms, token_usage, status, error, verifier{reason, triggered, success, raw}`. `status` ∈ {success, json_parse_error, api_error, timeout, empty_response}. Chạy lại sẽ *thêm* dòng; khi đọc lấy dòng cuối theo `sample_id`.
- `.csv`: một dòng mỗi mẫu với toàn bộ cột chỉ số.
- `.summary.json`: tổng hợp (k/n, CI95, độ trễ, token).

## 8. Cách chạy

```bash
# Ngày 1: ablation cho mô hình Cloud (judge khác mô hình test)
for c in A0 A1 A2 A3 A4 A5 A6; do
  python benchmark_runner_ablation_v3.py --model gpt-4o-mini --config $c --judge_model gemini-3.5-flash-lite
done
# Ngày 2: mô hình local
for c in A0 A1 A2 A3 A4 A5 A6; do
  python benchmark_runner_ablation_v3.py --model qwen2.5:3b --config $c --judge_model gpt-4o-mini
done
# Chạy lại các mẫu lỗi API
python benchmark_runner_ablation_v3.py --model qwen2.5:3b --config A6 --retry_errors
# Xuất bảng ablation (Markdown, có CI95)
python benchmark_runner_ablation_v3.py --table --models gpt-4o-mini qwen2.5:3b
```

Chạy thử trước: thêm `--limit 10`. Muốn chạy lại từ đầu một cấu hình, xóa file `.csv` và `.jsonl` tương ứng.

## 9. Hạn chế đã biết (ghi vào bài)

1. Ngữ cảnh là **sản phẩm đúng + nhiễu ngẫu nhiên**, chưa phải truy xuất thật; kết quả ảo giác là *khi đã có ngữ cảnh đúng*. Phase 2: BM25 / embedding trên KB 259k SKU, đo Recall@k, so oracle với truy xuất thật.
2. Chỉ 50 mẫu OOC (CI rộng) và toàn truy vấn dễ nhận ra; chưa có ca OOC khó (mỹ phẩm không có trong kho, thương hiệu giả).
3. Judge là LLM nên có thiên lệch; cần hiệu chuẩn bằng nhãn tay và báo cáo độ đồng thuận.
4. Brand khớp mềm và nhiều SKU thiếu giá nên `hallu_attr` chỉ kiểm tra được một phần.
5. Mô hình local chạy một seed; độ lệch giữa các lần chạy chưa đo.

## 10. Checklist bàn giao

- [ ] Ngọc xác nhận D1–D10 (hoặc phản biện).
- [ ] Hiệu chuẩn judge trên ~50 mẫu chấm tay.
- [ ] Chạy thử `--limit 10` cho từng mô hình/đường API thật.
- [ ] A0–A6 xong cho gpt-4o-mini, rồi qwen2.5:3b.
- [ ] Bảng ablation (`--table`), bootstrap ghép cặp cho các cặp liền kề.
- [ ] Đánh giá bởi người (100 mẫu, hai người chấm độc lập, tính Cohen's kappa).
- [ ] Cập nhật slide 13, 15 và các câu mô tả chỉ số cho khớp định nghĩa ở Mục 6.
