# 🛍️ H&M AI Product Catalog & Hybrid Search (Graph Chain-of-Thought)

Hệ thống tìm kiếm lai (**Hybrid Search**) kết hợp suy luận chuỗi tư duy đồ thị (**Graph Chain-of-Thought - Graph-CoT**) với cơ sở dữ liệu quan hệ (**MySQL 8.0**), cơ sở dữ liệu vector (**Qdrant**) và mô hình ngôn ngữ lớn cục bộ (**Ollama LLM**) trên tập dữ liệu thời trang thực tế H&M.

---

## 🏗️ 1. Kiến trúc tổng thể hệ thống (System Architecture)

```
                                  ┌────────────────────────┐
                                  │  CLIENT / FRONTEND     │
                                  │  Vue 3 + Vite          │
                                  └───────────┬────────────┘
                                              │ HTTP REST API (port 8080)
                                              ▼
                    ┌────────────────────────────────────────────────────────┐
                    │                   BACKEND SERVICE (FastAPI)            │
                    │  - API Gateway: /api/products, /api/chat, /images      │
                    │  - Static Image File Server (images/ mount)            │
                    └───────┬───────────────────┬───────────────────┬────────┘
                            │                   │                   │
               1. Intent &  │      2. Hybrid    │      3. Vector    │
               Graph-CoT    │      SQL Queries  │      Similarity   │
                            ▼                   ▼                   ▼
                     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                     │   OLLAMA    │     │    MySQL    │     │   QDRANT    │
                     │  (Qwen 2.5) │     │    (8.0)    │     │  Vector DB  │
                     │  Port 11434 │     │  Port 3307  │     │  Port 6333  │
                     └─────────────┘     └─────────────┘     └─────────────┘
```

### Các thành phần chính trong kiến trúc:
1. **Frontend Layer (Vue 3, Vite, Tailwind CSS):**
   - Đóng vai trò Client giao tiếp với Backend qua RESTful API.
   - Gửi truy vấn ngôn ngữ tự nhiên từ người dùng và render danh mục sản phẩm, kết quả tìm kiếm cùng các bước suy luận CoT.
2. **Backend API Layer (FastAPI, Python 3.10+):**
   - Đóng vai trò Controller trung tâm điều phối dữ liệu.
   - Tích hợp động cơ tìm kiếm lai `hybrid_search.py` kết nối trực tiếp với Ollama, MySQL và Qdrant.
   - Quản lý và phục vụ kho ảnh sản phẩm thực tế từ đĩa cứng qua StaticFiles mount.
3. **Database Layer (MySQL 8.0):**
   - Quản lý dữ liệu có cấu trúc quan hệ:
     - Bảng `products`: Lưu trữ thông tin Master Product (ID, tên, danh mục, nhóm ngành hàng, giới tính, phong cách, họa tiết, mô tả chi tiết).
     - Bảng `product_variants`: Lưu trữ từng biến thể SKU theo mã `article_id` 10 số (màu sắc, kích cỡ, đơn giá, số lượng tồn kho).
4. **Vector Database Layer (Qdrant):**
   - Lưu trữ và index vector đặc trưng sản phẩm trong collection `hm_products` phục vụ tìm kiếm tương đồng vector.
5. **AI Reasoning Engine (Ollama - Qwen 2.5):**
   - Thực thi mô hình LLM tại chỗ (Local Inference) để bóc tách ý định người dùng và phân tích đồ thị quan hệ danh mục thời trang.

---

## 🧠 2. Luồng xử lý tìm kiếm lai Graph Chain-of-Thought (Graph-CoT Workflow)

Khi người dùng gửi câu hỏi (ví dụ: *"tìm áo sơ mi nam màu trắng size L giá dưới 50$"*), hệ thống thực thi luồng suy luận 4 giai đoạn:

```
[Truy vấn người dùng]
         │
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Giai đoạn 1: Bóc tách ý định & Chuỗi tư duy CoT (Ollama)              │
│ - Intent Extraction: Category, Color, Size, Max Price, Gender          │
│ - Chuỗi suy luận: Phân tích yêu cầu và định hình tiêu chí tìm kiếm    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Giai đoạn 2: Ánh xạ đồ thị danh mục (Category Graph Mapping)           │
│ - Ánh xạ từ khóa về danh mục chuẩn H&M (Primary Category)              │
│ - Mở rộng đồ thị danh mục liên quan/thay thế (Related Categories)      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Giai đoạn 3: Thực thi truy vấn lai CSDL (Hybrid Retrieval & SQL)       │
│ - Sinh câu lệnh SQL động theo Primary Category & thuộc tính            │
│ - Kiểm tra trạng thái tồn kho theo màu sắc (Color in-stock / out-stock) │
│ - Truy vấn bổ sung danh mục phụ nếu danh mục chính thiếu sản phẩm      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Giai đoạn 4: Đóng gói kết quả & Xếp hạng (Scoring & Formatting)        │
│ - Điểm khớp 100%: Chuẩn danh mục & đúng màu yêu cầu                    │
│ - Điểm khớp 85%: Đúng danh mục chính nhưng hết màu (gợi ý màu khác)   │
│ - Điểm khớp 60-70%: Danh mục phụ kiện/đi kèm tương đồng               │
│ - Trả về: Lời giải thích CoT + Câu lệnh SQL minh bạch + Danh sách SP   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ 3. Hướng dẫn khởi chạy nhanh (Quick Start)

### 1️⃣ Khởi động cơ sở dữ liệu (MySQL & Qdrant)
Yêu cầu đã cài đặt **Docker & Docker Desktop**:
```bash
docker compose up -d db qdrant
```
- MySQL: cổng `3307` (database: `ecommerce_db`, user: `root`, pass: `rootpassword`)
- Qdrant: cổng `6333` (dashboard: `http://localhost:6333/dashboard`)

### 2️⃣ Khởi động AI & Backend (FastAPI)
1. **Khởi động Ollama:**
   ```bash
   ollama pull qwen2.5:3b
   ollama serve
   ```
2. **Chạy Backend:**
   ```bash
   cd backend
   python -m venv venv
   # Kích hoạt venv (Windows: .\venv\Scripts\activate | Linux/macOS: source venv/bin/activate)
   pip install -r requirements.txt
   
   # Đồng bộ dữ liệu vào MySQL & Qdrant (nếu có dữ liệu mới trong backend/data/):
   python import_all_hm_data.py
   
   # Chạy API server:
   uvicorn main:app --reload --port 8080
   ```
👉 **Xem chi tiết tài liệu Backend:** [backend/README.md](backend/README.md)

### 3️⃣ Khởi động Frontend (Vue 3)
Mở terminal mới:
```bash
cd frontend
npm install
npm run dev
```
Truy cập giao diện tại: **`http://localhost:5173/`**

👉 **Xem chi tiết tài liệu Frontend:** [frontend/README.md](frontend/README.md)

---

## 📂 4. Cấu trúc thư mục dự án (Project Structure)

```
LLM_ProductCatalog/
├── docker-compose.yml       # Cấu hình container Docker (MySQL 8.0 & Qdrant)
├── README.md                # Tài liệu kiến trúc tổng quan hệ thống
├── .gitignore               # Cấu hình loại trừ file rác & dữ liệu nặng
├── backend/                 # Mã nguồn Backend API & Động cơ AI
│   ├── README.md            # Hướng dẫn chi tiết Backend
│   ├── main.py              # Server FastAPI & REST endpoints
│   ├── hybrid_search.py     # Động cơ tìm kiếm lai Graph-CoT & SQL
│   ├── llm_agent.py         # Prompt engineering & tích hợp Ollama
│   ├── db_models.py         # SQLAlchemy ORM (Product, ProductVariant)
│   ├── database.py          # Cấu hình kết nối MySQL engine
│   ├── import_all_hm_data.py# Script đồng bộ 2 chiều MySQL & Qdrant
│   ├── requirements.txt     # Danh sách thư viện Python
│   └── data/                # Thư mục chứa dữ liệu thô CSDL H&M (không commit lên Git)
│       ├── README.md        # Hướng dẫn liên hệ Huy để lấy file dữ liệu
│       ├── articles.csv     # Metadata sản phẩm H&M
│       └── images/          # Thư mục ảnh thực tế (010, 011, ...)
└── frontend/                # Mã nguồn Frontend Client (Vue 3, Vite, Tailwind v4)
    ├── README.md            # Hướng dẫn chi tiết Frontend
    ├── package.json         # Danh sách dependencies npm
    ├── vite.config.js       # Cấu hình Vite & Tailwind plugin
    └── src/
        ├── App.vue          # Component gốc điều phối state
        └── components/      # Các components giao diện (ProductCard, Chat, Grid, Modal...)
```

---

## 📦 5. Lưu ý về dữ liệu (Data Source Notice)

Các file dữ liệu dung lượng lớn không được lưu trữ trực tiếp trên Git repository:
- `backend/data/articles.csv` (~36 MB metadata)
- `backend/data/images/` (~105,064 ảnh sản phẩm thực tế)

👉 Vui lòng liên hệ **Huy** để nhận các file dữ liệu này và đặt vào đúng vị trí `backend/data/` trước khi chạy script `import_all_hm_data.py`. Chi tiết xem tại [backend/data/README.md](backend/data/README.md).
