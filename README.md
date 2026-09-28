# 🛍️ H&M AI Product Catalog & Hybrid Search (Graph Chain-of-Thought)

Hệ thống danh mục sản phẩm thời trang thông minh H&M tích hợp công nghệ **Graph Chain-of-Thought (Graph-CoT)**, hỗ trợ tìm kiếm ngữ nghĩa đa tầng, tự động đồng bộ kho ảnh thực tế, chuyển đổi ảnh theo biến thể màu sắc thời gian thực và quản lý thông số CSDL chi tiết.

---

## 🏗️ Kiến trúc tổng thể hệ thống (System Architecture)

```
                            ┌──────────────────────────────────────────────┐
                            │            FRONTEND (Vue 3 + Vite)           │
                            │  - Thanh lọc Hamburger danh mục 62 loại      │
                            │  - Đổi màu & tráo ảnh thực tế theo SKU      │
                            │  - Chat tương tác AI & xem chuỗi CoT        │
                            └──────────────────────┬───────────────────────┘
                                                   │ HTTP / REST API (port 8080)
                                                   ▼
                            ┌──────────────────────────────────────────────┐
                            │            BACKEND (FastAPI API)             │
                            │  - /api/products : Lấy kho hàng & biến thể   │
                            │  - /api/chat     : Tìm kiếm lai Graph-CoT    │
                            │  - /images/...   : Phục vụ ảnh đĩa cứng      │
                            └──────┬───────────────┬───────────────┬───────┘
                                   │               │               │
                    SQL Queries    │  Vectors      │  Prompt       │
                                   ▼               ▼               ▼
                        ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
                        │    MySQL    │   │   Qdrant    │   │   Ollama    │
                        │    (8.0)    │   │  Vector DB  │   │  (Qwen 2.5) │
                        │  Port 3307  │   │  Port 6333  │   │  Port 11434 │
                        └─────────────┘   └─────────────┘   └─────────────┘
```

---

## ⚡ Hướng dẫn cài đặt nhanh cho máy mới (Quickstart)

Chỉ với **3 bước** đơn giản để khởi chạy toàn bộ dự án trên một máy tính mới:

### 1️⃣ Bước 1: Khởi động cơ sở dữ liệu (MySQL & Qdrant)

Yêu cầu máy đã cài **Docker & Docker Desktop**. Tại thư mục gốc dự án:

```bash
docker compose up -d db qdrant
```
*MySQL chạy trên cổng `3307` và Qdrant chạy trên cổng `6333`.*

---

### 2️⃣ Bước 2: Khởi động Backend (FastAPI & Ollama)

1. **Khởi động Ollama (AI Model):**
   ```bash
   ollama pull qwen2.5:3b
   ollama serve
   ```
2. **Cài đặt thư viện & chạy Backend:**
   ```bash
   cd backend
   python -m venv venv
   
   # Kích hoạt môi trường ảo:
   # Trên Windows: .\venv\Scripts\activate
   # Trên Linux/macOS: source venv/bin/activate
   
   pip install -r requirements.txt
   
   # (Tùy chọn) Đồng bộ dữ liệu ảnh nếu là lần đầu:
   python import_all_hm_data.py
   
   # Khởi chạy server FastAPI:
   uvicorn main:app --reload --port 8080
   ```
*Backend sẵn sàng tại `http://localhost:8080` (Tài liệu API Swagger: `http://localhost:8080/docs`).*

👉 **Xem hướng dẫn chi tiết Backend tại:** [backend/README.md](backend/README.md)

---

### 3️⃣ Bước 3: Khởi động Frontend (Vue 3 + Vite)

Mở một cửa sổ Terminal mới:

```bash
cd frontend
npm install
npm run dev
```

*Mở trình duyệt tại: **`http://localhost:5173/`** để bắt đầu trải nghiệm.*

👉 **Xem hướng dẫn chi tiết Frontend tại:** [frontend/README.md](frontend/README.md)

---

## 🌟 Các tính năng nổi bật của dự án

### 🧠 1. Tìm kiếm lai bằng Graph Chain-of-Thought (Graph-CoT)
- Không chỉ tìm kiếm từ khóa thông thường, hệ thống sử dụng LLM suy luận theo chuỗi tư duy đa bước:
  1. **Bước 1 (Ý định):** Phân tích danh mục, màu sắc, kích cỡ, mức giá, giới tính người dùng muốn mua.
  2. **Bước 2 (Ánh xạ đồ thị):** Suy luận liên kết giữa các danh mục thời trang H&M.
  3. **Bước 3 (Chiến lược CSDL):** Sinh câu lệnh SQL tối ưu và kiểm tra tồn kho theo màu sắc.
  4. **Bước 4 (Minh bạch):** Hiển thị trực tiếp quá trình suy luận và câu lệnh SQL ngay trong khung chat.

### 🎨 2. Biến thể màu sắc & Đổi ảnh theo thời gian thực
- Mỗi sản phẩm có nhiều màu sắc khác nhau cùng mã SKU (`article_id`) và ảnh chụp thực tế riêng biệt.
- Người dùng chỉ cần click chọn màu trên thẻ sản phẩm hoặc trong modal chi tiết, **ảnh sản phẩm lập tức đổi sang góc chụp của màu đó**, đồng thời mã SKU, đơn giá và số lượng tồn kho tự động đồng bộ.

### 🍔 3. Thanh danh mục Hamburger thông minh
- Tích hợp nút **"Danh mục" (Hamburger Menu)** mở Slide-over Drawer sang trọng.
- Cho phép tìm kiếm tức thì qua toàn bộ 62 danh mục thời trang H&M.
- Tự động lọc và hiển thị Top 8 danh mục phổ biến nhất kèm số lượng sản phẩm.

### 🗄️ 4. Bảng thông số CSDL chi tiết (Database Schema Specs)
- Hiển thị đầy đủ 8 trường thông số từ CSDL MySQL trong cửa sổ xem chi tiết:
  - Mã Master Product (`id`), Mã SKU màu (`article_id`).
  - Loại sản phẩm (`product_type`), Nhóm ngành hàng (`product_group`).
  - Phân khúc khách hàng (`gender_group`), Phong cách (`department`), Họa tiết (`pattern`).
  - Tồn kho thời gian thực theo từng cặp màu & size.

---

## 📂 Cấu trúc thư mục dự án

```
LLM_ProductCatalog/
├── docker-compose.yml       # Cấu hình container MySQL & Qdrant
├── README.md                # Tài liệu tổng quan dự án
├── backend/                 # Mã nguồn Backend (FastAPI, Python)
│   ├── README.md            # Hướng dẫn chi tiết cài đặt Backend
│   ├── main.py              # Server FastAPI & API routes
│   ├── hybrid_search.py     # Động cơ tìm kiếm lai Graph-CoT & SQL
│   ├── llm_agent.py         # Module prompt suy luận Chain-of-Thought với Ollama
│   ├── db_models.py         # SQLAlchemy ORM models (Product, ProductVariant)
│   ├── database.py          # Kết nối CSDL MySQL
│   ├── import_all_hm_data.py# Script đồng bộ kho ảnh & dữ liệu vào MySQL/Qdrant
│   ├── requirements.txt     # Danh sách thư viện Python
│   └── data/                # Thư mục gom dữ liệu CSDL H&M
│       ├── articles.csv     # Dữ liệu thuộc tính sản phẩm H&M
│       └── images/          # Thư mục toàn bộ ảnh thực tế (010, 011, ...)
└── frontend/                # Mã nguồn Frontend (Vue 3, Vite, Tailwind CSS v4)
    ├── README.md            # Hướng dẫn chi tiết cài đặt Frontend
    ├── package.json         # Khai báo dependencies npm
    ├── vite.config.js       # Cấu hình Vite & Tailwind
    └── src/
        ├── App.vue          # Component gốc
        └── components/      # Các components giao diện (ProductCard, Chat, Grid...)
```

---

## 🤝 Hỗ trợ & Khắc phục lỗi

Nếu bạn gặp khó khăn trong quá trình cài đặt, vui lòng tham khảo mục **Troubleshooting** trong:
- [Hướng dẫn Backend](backend/README.md#5-xử-lý-sự-cố-thường-gặp-troubleshooting)
- [Hướng dẫn Frontend](frontend/README.md#5-xử-lý-sự-cố-thường-gặp-troubleshooting)
