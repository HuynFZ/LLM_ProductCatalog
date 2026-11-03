# 🛍️ H&M AI Product Catalog & Hybrid Search (Graph-CoT & Dense Vector Search)

Hệ thống tìm kiếm thời trang lai (**Hybrid Search**) thế hệ mới, kết hợp suy luận chuỗi tư duy đồ thị (**Graph Chain-of-Thought - Graph-CoT**), tìm kiếm ngữ nghĩa vector dày đặc (**Dense Vector Search**) cùng cơ sở dữ liệu quan hệ (**MySQL 8.0**), cơ sở dữ liệu vector (**Qdrant**) và các mô hình AI cục bộ (**Ollama LLM & Embeddings**) trên tập dữ liệu thời trang thực tế H&M.

---

## 🏗️ 1. Kiến trúc tổng thể hệ thống (System Architecture)

```
                                  ┌────────────────────────────────────────┐
                                  │           CLIENT / FRONTEND            │
                                  │   Vue 3 + Vite + Tailwind CSS v4      │
                                  │   - Real-time Color Swatches & Images  │
                                  │   - Slide-over Category Drawer         │
                                  │   - CoT AI Chat & Real SQL Inspector   │
                                  └───────────────────┬────────────────────┘
                                                      │ HTTP REST API (port 8080)
                                                      ▼
                      ┌────────────────────────────────────────────────────────┐
                      │              BACKEND SERVICE (FastAPI)                 │
                      │  - API Gateway: /api/products, /api/chat, /api/models  │
                      │  - Local Image Server (/images/{sub}/{file}.jpg)       │
                      │  - Dual-Engine Hybrid Retrieval & Re-ranking           │
                      └───────┬───────────────────┬───────────────────┬────────┘
                              │                   │                   │
                 1. Intent &  │      2. Hybrid    │      3. Dense     │
                 Graph-CoT    │      SQL Queries  │      Vector Sim   │
                 & Embeddings │                   │                   │
                              ▼                   ▼                   ▼
                      ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                      │   OLLAMA    │     │    MySQL    │     │   QDRANT    │
                      │  Local AI   │     │    (8.0)    │     │  Vector DB  │
                      │ Port 11434  │     │  Port 3307  │     │  Port 6333  │
                      │ ─────────── │     │ ─────────── │     │ ─────────── │
                      │• qwen2.5:3b │     │• products   │     │• collection │
                      │• nomic-embed│     │• variants   │     │  hm_products│
                      └─────────────┘     └─────────────┘     └─────────────┘
```

### Các thành phần chính trong kiến trúc:

1. **Frontend Layer (Vue 3, Vite, Tailwind CSS v4, Lucide Icons):**
   - **Giao diện danh mục:** Lưới sản phẩm tương tác cao, phân trang, lọc theo danh mục, sắp xếp theo giá và độ phổ biến.
   - **Slide-over Hamburger Drawer:** Tìm kiếm nhanh và duyệt toàn bộ 62 danh mục sản phẩm H&M kèm số lượng tồn thực tế.
   - **Real-time Color Swatches:** Chuyển đổi màu sắc trực tiếp trên từng thẻ sản phẩm — ảnh, mã SKU (`article_id`), giá niêm yết và tồn kho đổi theo tức thì.
   - **Product Detail Modal:** Xem chi tiết bảng thông số kỹ thuật CSDL MySQL đầy đủ và kiểm tra tồn kho theo từng kích cỡ.
   - **Graph-CoT Chat Interface:** Khung chat trợ lý AI hiển thị minh bạch 4 bước suy luận CoT, câu truy vấn SQL thực thi và danh sách sản phẩm đề xuất.

2. **Backend API Layer (FastAPI, Python 3.10+):**
   - **Bộ điều phối trung tâm:** Tích hợp bộ tìm kiếm lai `hybrid_search.py` kết nối trực tiếp với Ollama, MySQL và Qdrant.
   - **Static Image Server:** Phục vụ trực tiếp hơn 105,000+ file ảnh sản phẩm độ phân giải cao được phân nhóm theo thư mục tiền tố SKU 3 chữ số (`/images/010/...`).

3. **Database Layer (MySQL 8.0):**
   - **Quan hệ 1-N chuẩn hóa:**
     - Bảng `products`: Lưu trữ thông tin Master Product (`id`, `name`, `product_type`, `product_group`, `gender_group`, `department`, `pattern`, `detail_desc`).
     - Bảng `product_variants`: Lưu trữ từng biến thể SKU theo mã `article_id` 10 số (`color`, `size`, `price`, `stock_quantity`).

4. **Vector Database Layer (Qdrant):**
   - Collection `hm_products`: Lưu trữ và đánh chỉ mục vector 768 chiều sinh bởi mô hình `nomic-embed-text`.
   - Hỗ trợ **Filtered Vector Search**: Tìm kiếm tương đồng vector Cosine kết hợp lọc các trường thuộc tính cứng (`color`, `gender_group`, `price`).

5. **AI Reasoning Engine (Ollama Local AI):**
   - **LLM Reasoning (`qwen2.5:3b`):** Chạy cục bộ với độ trễ cực thấp, bóc tách ý định, phân tích ngữ cảnh, diễn giải sang truy vấn tiếng Anh (`semantic_query`) và lập chuỗi tư duy CoT 4 bước.
   - **Text Embedding (`nomic-embed-text`):** Vector hóa tài liệu sản phẩm và câu truy vấn người dùng thành vector 768 chiều.

---

## 🧠 2. Cơ chế tìm kiếm lai 2 trong 1 (Dual-Engine Hybrid Search)

Hệ thống kết hợp linh hoạt giữa **Tìm kiếm theo quy tắc / danh mục CoT** và **Tìm kiếm ngữ nghĩa Vector Search** tùy theo ngữ cảnh của câu truy vấn:

```
                              [Truy vấn người dùng]
                                        │
                                        ▼
      ┌──────────────────────────────────────────────────────────────────┐
      │  Giai đoạn 1: Bóc tách ý định & Chuỗi tư duy CoT (Ollama)        │
      │  - Phân tích ngữ cảnh, phong cách thời trang, giới tính          │
      │  - Sinh cụm từ ngữ nghĩa chuẩn tiếng Anh (semantic_query)        │
      │  - Trích xuất thuộc tính: Color, Size, Max Price, Gender         │
      │  - Lập chuỗi tư duy 4 bước (Thought 1 -> Thought 4)              │
      └─────────────────────────────────┬────────────────────────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 ▼                                             ▼
   [Có Danh mục cụ thể / Rõ ràng]               [Tìm kiếm phong cách / Tự do]
                 │                                             │
                 ▼                                             ▼
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│ Giai đoạn 2A: Hybrid SQL Search │           │ Giai đoạn 2B: Qdrant Vector     │
│ - Truy vấn MySQL theo Category  │           │ - Sinh vector 768d qua nomic    │
│ - Lọc biến thể theo màu & size  │           │ - Cosine Similarity trên Qdrant │
│ - Xử lý hết hàng màu sắc:       │           │ - Lọc thuộc tính (Color/Gender) │
│   + Đạt 100%: Khớp chuẩn màu   │           │ - Ánh xạ kết quả về CSDL MySQL  │
│   + Đạt 85%: Đúng loại, hết màu │           │ - Đạt 70% - 98%: Khớp ngữ nghĩa │
└────────────────┬────────────────┘           └────────────────┬────────────────┘
                 │                                             │
                 └──────────────────────┬──────────────────────┘
                                        ▼
      ┌──────────────────────────────────────────────────────────────────┐
      │  Giai đoạn 3: Đóng gói kết quả & Xếp hạng (Scoring & Re-ranking) │
      │  - Ưu tiên danh mục chính & sản phẩm đúng tiêu chí               │
      │  - Bổ sung phụ kiện / danh mục tương đồng (60% - 70%) nếu thiếu  │
      │  - Trả về: Lời giải thích CoT + Câu lệnh SQL minh bạch + DS SP   │
      └──────────────────────────────────────────────────────────────────┘
```

### Chi tiết các mức điểm khớp (Match Scores):
- **100% Khớp chuẩn xác:** Sản phẩm khớp hoàn toàn cả danh mục chính và màu sắc/size yêu cầu.
- **85% Đúng loại nhưng tạm hết màu:** Danh mục chính có sẵn sản phẩm nhưng màu sắc yêu cầu đang hết hàng. Hệ thống thông báo rõ ràng cho khách và gợi ý các màu khác có sẵn.
- **70% - 98% Khớp ngữ nghĩa Vector:** Dành cho các tìm kiếm mô tả ngữ cảnh tự do (ví dụ: *"trang phục dạo phố thoáng mát"*, *"đồ ấm giữ nhiệt mùa đông"*).
- **60% - 70% Gợi ý phụ kiện đi kèm:** Khi danh mục chính có ít sản phẩm, hệ thống mở rộng sang danh mục liên quan để hoàn thiện set đồ.

---

## ⚡ 3. Hướng dẫn khởi chạy nhanh (Quick Start)

### 1️⃣ Khởi động cơ sở dữ liệu (MySQL & Qdrant) bằng Docker
Yêu cầu đã cài đặt **Docker & Docker Desktop**:
```bash
docker compose up -d db qdrant
```
- **MySQL 8.0:** Cổng `3307` trên host (`localhost:3307`), Database: `ecommerce_db`, User: `root`, Pass: `rootpassword`
- **Qdrant Vector DB:** Cổng `6333` trên host, Web Dashboard: `http://localhost:6333/dashboard`

---

### 2️⃣ Cài đặt & Khởi động Mô hình AI Cục bộ (Ollama)
Cài đặt Ollama từ [https://ollama.com](https://ollama.com), sau đó mở terminal chạy:

```bash
# 1. Tải mô hình LLM suy luận chuỗi tư duy CoT (3B tham số, tiếng Việt xuất sắc)
ollama pull qwen2.5:3b

# 2. Tải mô hình Embedding để vector hóa 768 chiều cho Qdrant
ollama pull nomic-embed-text

# 3. Khởi chạy Ollama service (nếu chưa chạy ngầm)
ollama serve
```

---

### 3️⃣ Cài đặt và Nạp dữ liệu Backend (FastAPI)
Mở một terminal mới:

```bash
cd backend

# Tạo và kích hoạt môi trường ảo Python
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt

# Bước 3.1: Đồng bộ 2 chiều dữ liệu metadata & ảnh thực tế vào MySQL và Qdrant
python import_all_hm_data.py

# Bước 3.2: Vector hóa dữ liệu sản phẩm (768-dim) vào Qdrant phục vụ tìm kiếm ngữ nghĩa
python index_vectors.py

# Bước 3.3: Khởi chạy API Server
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

- **Kiểm tra API Healthcheck:** [http://localhost:8080/](http://localhost:8080/)
- **Swagger UI tài liệu API tương tác:** [http://localhost:8080/docs](http://localhost:8080/docs)
- **Kiểm tra truy cập ảnh tĩnh:** [http://localhost:8080/images/010/0108775015.jpg](http://localhost:8080/images/010/0108775015.jpg)

👉 Xem chi tiết cấu hình Backend: [backend/README.md](backend/README.md)

---

### 4️⃣ Khởi chạy Frontend (Vue 3 + Vite)
Mở một terminal khác:

```bash
cd frontend

# Cài đặt các gói thư viện npm
npm install

# Khởi chạy Vite Development Server
npm run dev
```

Truy cập giao diện ứng dụng tại: **`http://localhost:5173/`**

👉 Xem chi tiết cấu hình Frontend: [frontend/README.md](frontend/README.md)

---

## 📂 4. Cấu trúc thư mục dự án (Project Directory Structure)

```
LLM_ProductCatalog/
├── docker-compose.yml          # Cấu hình container Docker (MySQL 8.0 & Qdrant Vector DB)
├── README.md                   # Tài liệu kiến trúc & hướng dẫn tổng quan toàn hệ thống
├── .gitignore                  # Cấu hình loại trừ file rác, venv và dữ liệu nặng
│
├── backend/                    # Mã nguồn Backend API, AI Agent & Dữ liệu
│   ├── README.md               # Hướng dẫn chi tiết thiết lập & vận hành Backend
│   ├── main.py                 # FastAPI Application, CORS, static file mount & REST endpoints
│   ├── hybrid_search.py        # Động cơ tìm kiếm lai Dual-Engine (Graph-CoT + Vector + SQL)
│   ├── llm_agent.py            # Tích hợp Ollama LLM, chuỗi tư duy CoT & bóc tách thuộc tính
│   ├── embeddings.py           # Module sinh vector 768-d qua Ollama nomic-embed-text
│   ├── vector_service.py       # Tích hợp Qdrant Client, cấu hình collection & tìm kiếm ngữ nghĩa
│   ├── index_vectors.py        # Script vector hóa toàn bộ sản phẩm từ MySQL đẩy vào Qdrant
│   ├── import_all_hm_data.py   # Script đồng bộ 2 chiều (ảnh thực tế <-> metadata <-> CSDL)
│   ├── db_models.py            # SQLAlchemy ORM Models (Product & ProductVariant)
│   ├── database.py             # Cấu hình engine kết nối CSDL MySQL (SessionLocal)
│   ├── requirements.txt        # Danh sách các thư viện Python
│   └── data/                   # Thư mục chứa dữ liệu thô CSDL H&M (không commit lên Git)
│       ├── README.md           # Hướng dẫn lấy dữ liệu metadata & ảnh sản phẩm
│       ├── articles.csv        # File metadata chi tiết sản phẩm H&M (~36 MB)
│       └── images/             # Kho ảnh sản phẩm thực tế theo thư mục tiền tố (010, 011...)
│
└── frontend/                   # Mã nguồn Frontend Client (Vue 3, Vite, Tailwind CSS v4)
    ├── README.md               # Hướng dẫn chi tiết cài đặt & cấu trúc Frontend
    ├── package.json            # Khai báo npm dependencies & build scripts
    ├── vite.config.js          # Cấu hình Vite & plugin Tailwind CSS v4
    ├── index.html              # Template HTML chính của Single Page Application
    └── src/
        ├── App.vue             # Component gốc quản lý state tập trung & điều phối dữ liệu
        ├── main.js             # Entrypoint khởi tạo Vue application
        ├── style.css           # Cấu hình phong cách giao diện & Tailwind CSS v4
        ├── services/
        │   └── aiService.js    # Service gọi API Backend (getProducts, sendChatMessage, format)
        ├── data/
        │   └── products.js     # Mock metadata và danh sách mô hình AI
        └── components/
            ├── BrandLogo.vue           # Logo thương hiệu H&M AI Catalog
            ├── CartDrawer.vue          # Giỏ hàng trượt bên phải kèm tính tổng tiền
            ├── ChatInterface.vue       # Khung chat AI, hiển thị CoT steps & câu lệnh SQL
            ├── ProductCard.vue         # Card sản phẩm kèm color swatches đổi ảnh tức thì
            ├── ProductDetailModal.vue  # Modal chi tiết sản phẩm & bảng thông số CSDL thực tế
            ├── ProductGrid.vue         # Lưới sản phẩm, Drawer lọc danh mục & thanh phân trang
            └── ToastNotification.vue   # Thông báo toast phản hồi tương tác người dùng
```

---

## 📡 5. Danh sách API Endpoints chính

| Phương thức | Đường dẫn | Chức năng | Dữ liệu trả về tiêu biểu |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Kiểm tra trạng thái hệ thống & kết nối CSDL | `{"status": "success", "message": "FastAPI đang chạy..."}` |
| `GET` | `/api/models` | Trả về danh sách mô hình AI hỗ trợ | Thông tin mô hình Graph-CoT Reasoning Search |
| `GET` | `/api/products` | Lấy danh sách sản phẩm ban đầu kèm đầy đủ biến thể, màu sắc, giá và ảnh | Mảng JSON các sản phẩm kèm `color_details`, `color_images` |
| `POST` | `/api/chat` | Chat tìm kiếm thông minh kết hợp Graph-CoT, Vector Search và SQL | Câu trả lời AI, chuỗi CoT, câu truy vấn SQL & danh sách SP |
| `GET` | `/images/{sub}/{file}` | Mount trực tiếp thư mục ảnh tĩnh cục bộ | File nhị phân ảnh sản phẩm thực tế (JPG/PNG) |

---

## 📦 6. Lưu ý về dữ liệu (Data Source & Dataset)

Các file dữ liệu lớn của H&M không được lưu trữ trên Git để tối ưu dung lượng repository:
- `backend/data/articles.csv` (~36 MB metadata sản phẩm).
- `backend/data/images/` (~105,064 file ảnh sản phẩm phân bố trong các thư mục con từ `010/` đến `095/`).

👉 **Cách chuẩn bị dữ liệu:**
1. Liên hệ **Huy** để nhận các file dữ liệu này và đặt vào đúng vị trí thư mục `backend/data/`.
2. Chạy lệnh `python import_all_hm_data.py` để hệ thống tự động đối chiếu và nạp vào MySQL.
3. Chạy lệnh `python index_vectors.py` để sinh vector embedding 768 chiều nạp vào Qdrant.
4. Xem hướng dẫn chi tiết tại [backend/data/README.md](backend/data/README.md).

---

## 🛠️ 7. Công nghệ sử dụng (Tech Stack)

| Lớp hệ thống | Công nghệ sử dụng | Vai trò & Điểm nổi bật |
| :--- | :--- | :--- |
| **Frontend** | Vue 3, Vite, Tailwind CSS v4, Lucide Icons | Reactive UI, Hot Module Replacement, Micro-animations, Mobile-friendly |
| **Backend API** | FastAPI, Uvicorn, Pydantic, Python 3.10+ | Bất đồng bộ hiệu năng cao, tự động sinh tài liệu Swagger/OpenAPI |
| **Relational Database** | MySQL 8.0, SQLAlchemy ORM, PyMySQL | Lưu trữ dữ liệu quan hệ có cấu trúc Master-Variant, quản lý tồn kho |
| **Vector Database** | Qdrant Vector DB (Docker) | Indexing vector đặc trưng, tìm kiếm tương đồng Cosine kết hợp lọc payload |
| **AI LLM Inference** | Ollama (`qwen2.5:3b`) | Suy luận chuỗi tư duy CoT cục bộ, bóc tách thực thể ngôn ngữ tự nhiên |
| **Embeddings** | Ollama (`nomic-embed-text`) | Sinh vector ngữ nghĩa 768 chiều phục vụ tìm kiếm tương đồng |
| **Containerization** | Docker, Docker Compose | Đóng gói môi trường MySQL 8.0 và Qdrant dễ dàng triển khai |
