# 🛠️ H&M Product Catalog - Hướng Dẫn Cài Đặt & Vận Hành Backend

Tài liệu này hướng dẫn chi tiết cách cài đặt và chạy toàn bộ dịch vụ **Backend** (FastAPI, MySQL, Qdrant Vector DB, Ollama AI và đồng bộ dữ liệu thời trang H&M) trên một máy tính mới từ đầu.

---

## 📋 1. Yêu cầu hệ thống (Prerequisites)

Trước khi bắt đầu, hãy đảm bảo máy tính đã cài đặt các công cụ sau:

| Công cụ | Phiên bản khuyến nghị | Mục đích |
| :--- | :--- | :--- |
| **Python** | 3.10 trở lên | Chạy API FastAPI và script đồng bộ dữ liệu |
| **Docker & Docker Desktop** | Bản mới nhất | Khởi chạy MySQL 8.0 và Qdrant Vector DB |
| **Ollama** | Bản mới nhất | Chạy mô hình ngôn ngữ lớn (LLM) để suy luận Graph-CoT |
| **Git** | Bản mới nhất | Quản lý mã nguồn |

---

## 🚀 2. Hướng dẫn cài đặt từng bước cho máy mới

### Bước 2.1: Khởi động cơ sở dữ liệu (MySQL & Qdrant) bằng Docker

Từ thư mục gốc dự án (`LLM_ProductCatalog`), khởi chạy các container:

```bash
# Khởi chạy MySQL (cổng 3307) và Qdrant (cổng 6333) chạy ngầm
docker compose up -d db qdrant
```

Kiểm tra trạng thái container đang hoạt động:
```bash
docker compose ps
```
> **Thông tin kết nối mặc định:**
> - **MySQL Cổng máy chủ (Host):** `127.0.0.1:3307` (hoặc `3306` bên trong mạng Docker)
> - **Tài khoản:** `root` | **Mật khẩu:** `rootpassword` | **Database:** `ecommerce_db`
> - **Qdrant Vector DB:** `http://localhost:6333` (Dashboard web: `http://localhost:6333/dashboard`)

---

### Bước 2.2: Thiết lập môi trường Python ảo (Virtual Environment)

Di chuyển vào thư mục `backend`:
```bash
cd backend
```

Tạo và kích hoạt môi trường ảo:
- **Trên Windows (PowerShell/CMD):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
- **Trên Linux/macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

Cài đặt toàn bộ thư viện cần thiết:
```bash
pip install -r requirements.txt
```

> **Lưu ý:** Thư viện `datasets==2.19.1` được cố định phiên bản để tương thích hoàn toàn khi xử lý dữ liệu.

---

### Bước 2.3: Chuẩn bị dữ liệu hình ảnh & Metadata

Toàn bộ dữ liệu thô của H&M được gom gọn gàng trong thư mục `backend/data/`:
1. **`backend/data/articles.csv`**: File chứa thông tin chi tiết về sản phẩm H&M (tên, danh mục, màu sắc, mô tả, phòng ban...).
2. **`backend/data/images/`**: Thư mục chứa các ảnh sản phẩm thực tế theo cấu trúc thư mục con:
   ```
   backend/
   ├── data/                   # Thư mục gom toàn bộ dữ liệu CSDL H&M
   │   ├── articles.csv        # Metadata sản phẩm
   │   └── images/             # Toàn bộ ảnh sản phẩm thực tế
   │       ├── 010/
   │       │   ├── 0108775015.jpg
   │       │   ├── 0108775044.jpg
   │       │   └── 0108775051.jpg
   │       ├── 011/
   │       └── ...
   ├── main.py
   └── ...
   ```

---

### Bước 2.4: Đồng bộ dữ liệu vào MySQL & Qdrant

Hệ thống có sẵn script đồng bộ 2 chiều thông minh `import_all_hm_data.py`. Script này sẽ:
- Quét toàn bộ ảnh thực tế có trong thư mục `images/`.
- Tạo bảng `products` (Master) và `product_variants` (SKU theo màu, giá, tồn kho).
- Đẩy vector vào Qdrant collection `hm_products`.
- Tự động xóa các dữ liệu cũ không còn file ảnh trên đĩa.

Chạy lệnh đồng bộ:
```bash
python import_all_hm_data.py
```
*Thời gian chạy phụ thuộc vào số lượng ảnh (quá trình xử lý chia theo từng batch 500 bản ghi để tối ưu bộ nhớ).*

---

### Bước 2.5: Cài đặt & Khởi động Mô hình AI (Ollama)

Dự án sử dụng cơ chế suy luận lai **Graph Chain-of-Thought (Graph-CoT)** thông qua Ollama.

1. Tải và cài đặt Ollama từ [https://ollama.com](https://ollama.com).
2. Tải mô hình Qwen 2.5 (3 tỷ tham số - siêu nhanh và thông minh cho tiếng Việt):
   ```bash
   ollama pull qwen2.5:3b
   ```
3. Đảm bảo Ollama đang chạy tại cổng mặc định:
   ```bash
   ollama serve
   ```
   *(Nếu Ollama đã chạy ngầm trên Windows qua biểu tượng Taskbar, bạn có thể bỏ qua lệnh này).*

---

### Bước 2.6: Khởi chạy Backend API (FastAPI)

Kích hoạt môi trường ảo và chạy server qua Uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

Khi chạy thành công, console sẽ hiển thị:
```
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

- **Kiểm tra API Healthcheck:** [http://localhost:8080/](http://localhost:8080/)
- **Tài liệu Swagger UI tương tác:** [http://localhost:8080/docs](http://localhost:8080/docs)
- **Kiểm tra truy cập ảnh tĩnh:** [http://localhost:8080/images/010/0108775015.jpg](http://localhost:8080/images/010/0108775015.jpg)

---

## 📡 3. Danh sách các API chính (Endpoints)

| Phương thức | Đường dẫn | Chức năng | Dữ liệu trả về |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Kiểm tra trạng thái server & kết nối MySQL | `{"status": "success", "message": "..."}` |
| `GET` | `/api/products` | Lấy danh sách sản phẩm mặc định (kèm đầy đủ biến thể màu sắc, tồn kho, ảnh & thông số CSDL) | Danh sách JSON 1000 sản phẩm |
| `POST` | `/api/chat` | Chat tìm kiếm thông minh kết hợp Graph-CoT, suy luận đa bước & SQL | Câu trả lời AI, chuỗi CoT, câu truy vấn SQL & danh sách sản phẩm khớp |
| `GET` | `/images/{sub}/{file}` | Mount thư mục ảnh tĩnh phục vụ Frontend | Trực tiếp trả về file ảnh JPG/PNG |

---

## 🔧 4. Các biến môi trường (Environment Variables)

Bạn có thể tùy biến các biến môi trường khi triển khai qua file `.env` hoặc tham số dòng lệnh:

| Biến | Giá trị mặc định | Giải thích |
| :--- | :--- | :--- |
| `DATABASE_URL` | `mysql+pymysql://root:rootpassword@127.0.0.1:3307/ecommerce_db` | Chuỗi kết nối MySQL |
| `QDRANT_URL` | `http://localhost:6333` | Địa chỉ máy chủ Qdrant |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | API endpoint sinh văn bản Ollama |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Tên mô hình LLM sử dụng cho CoT |

---

## ❓ 5. Xử lý sự cố thường gặp (Troubleshooting)

1. **Lỗi `Can't connect to MySQL server on '127.0.0.1:3307'`:**
   - Hãy chắc chắn Docker Desktop đang bật và container `db` đang ở trạng thái `healthy`:
     ```bash
     docker compose ps
     docker compose restart db
     ```
2. **Lỗi `Failed to connect to Ollama`:**
   - Kiểm tra xem Ollama đã chạy chưa bằng cách mở trình duyệt vào `http://localhost:11434`.
   - Kiểm tra mô hình đã được tải: `ollama list`.
3. **Ảnh sản phẩm không hiển thị (Lỗi 404):**
   - Đảm bảo tên file ảnh có định dạng đúng 10 chữ số (ví dụ: `0108775015.jpg`) và nằm trong thư mục con tương ứng (`010/`).
