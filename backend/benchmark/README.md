# 🧪 Framework Thực Nghiệm & Đánh Giá So Sánh LLM Cho Bài Báo Khoa Học

Framework này tự động hóa toàn bộ quy trình đo lường, kiểm thử cú pháp SQL dry-run trên MySQL 8.0 thực tế, phát hiện ảo giác (hallucination) và trực quan hóa dữ liệu phục vụ trực tiếp cho việc viết bài báo nghiên cứu.

---

## 🎯 1. Chiến Lược Lựa Chọn Mô Hình Theo Chuẩn Nghiên Cứu

| Nhóm tham số | Mô hình đại diện | Lệnh tải qua Ollama | Mục tiêu nghiên cứu |
| :--- | :--- | :--- | :--- |
| **Ultra-small (2B - 4B)** | `qwen2.5:3b` | `ollama pull qwen2.5:3b` | Mô hình nòng cốt của hệ thống (Hiểu tiếng Việt, sinh JSON chuẩn) |
| **Ultra-small (2B - 4B)** | `gemma2:2b` | `ollama pull gemma2:2b` | Mô hình đối trọng siêu nhẹ từ Google DeepMind |
| **Standard Baseline (7B - 9B)** | `llama3.1:8b` | `ollama pull llama3.1:8b` | **Mô hình chuẩn mực (tương đương bài báo TrustRec)** |
| **Standard Baseline (7B - 9B)** | `mistral:7b` | `ollama pull mistral:7b` | Đại diện kiến trúc sinh SQL / Code ổn định của Mistral AI |

---

## 📋 2. Cấu Trúc Thư Mục Thực Nghiệm

```
backend/benchmark/
├── README.md                      # Hướng dẫn chi tiết vận hành thực nghiệm
├── benchmark_queries.json         # Tập 100 câu hỏi test phân tầng thực tế (Direct, Context, Multi-attr, Out-of-stock...)
├── benchmark_runner.py            # Trình điều phối chạy benchmark tự động qua Ollama & Dry-run MySQL
├── benchmark_visualize.py         # Module vẽ 3 biểu đồ chuẩn học thuật (DPI 300) & xuất bảng LaTeX
├── benchmark_results.csv          # Dữ liệu chi tiết từng lượt chạy (Model, Prompt, Latency, SQL_Success...)
└── benchmark_summary.csv          # Bảng tổng hợp các độ đo học thuật
```

---

## 🚀 3. Hướng Dẫn Thực Hiện

### Bước 1: Khởi động Ollama & MySQL
Đảm bảo service Ollama đang chạy ngầm (`ollama serve`) và CSDL MySQL 8.0 qua Docker đang hoạt động.

### Bước 2: Tải các mô hình cần đánh giá
Mở terminal và chạy lệnh:
```bash
ollama pull qwen2.5:3b
ollama pull llama3.1:8b
ollama pull gemma2:2b
ollama pull mistral:7b
```

### Bước 3: Chạy thử nghiệm tự động
Mở terminal tại thư mục `backend/`:

* **Chạy thử nhanh 5 câu đầu tiên** để kiểm tra hệ thống:
  ```bash
  python benchmark/benchmark_runner.py --limit 5
  ```

* **Chạy thử nghiệm toàn diện (100 câu x 4 mô hình x 2 chiến lược Prompt = 800 lượt chạy)**:
  ```bash
  python benchmark/benchmark_runner.py --models qwen2.5:3b llama3.1:8b gemma2:2b mistral:7b
  ```

* **Chạy riêng với các mô hình hiện có** (ví dụ nếu chưa tải đủ 8B):
  ```bash
  python benchmark/benchmark_runner.py --models qwen2.5:3b
  ```

### Bước 4: Trực quan hóa dữ liệu và xuất bảng biểu cho bài báo
Sau khi chạy xong, sinh toàn bộ biểu đồ và bảng LaTeX:
```bash
python benchmark/benchmark_visualize.py
```

Các file kết quả sinh ra gồm:
1. `figure1_latency_vs_sql_success.png`: Scatter plot thể hiện sự đánh đổi giữa **Độ trễ (Latency)** và **Tỷ lệ thực thi SQL thành công**.
2. `figure2_prompt_comparison_bar.png`: Grouped bar chart so sánh sức mạnh vượt trội của **Graph-CoT** so với **Zero-shot**.
3. `figure3_hallucination_breakdown.png`: Biểu đồ phân rã các loại lỗi ảo giác (Schema hallucination, Column hallucination, JSON error).
4. `paper_summary_table.tex`: Bảng LaTeX chuẩn định dạng IEEE/ACM để đưa trực tiếp vào tài liệu Overleaf / TeX.
5. `paper_summary_table.md`: Bảng Markdown xem nhanh trên GitHub hoặc tài liệu báo cáo.
