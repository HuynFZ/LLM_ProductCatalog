# 🎨 H&M Product Catalog - Hướng Dẫn Cài Đặt & Phát Triển Frontend

Tài liệu này hướng dẫn chi tiết cách cài đặt, cấu hình và chạy giao diện người dùng **Frontend** (Vue 3, Vite, Tailwind CSS v4, Lucide Icons) trên một máy tính mới.

---

## 📋 1. Yêu cầu hệ thống (Prerequisites)

Trước khi bắt đầu, hãy đảm bảo máy tính đã cài đặt:

| Công cụ | Phiên bản khuyến nghị | Mục đích |
| :--- | :--- | :--- |
| **Node.js** | v18.x hoặc v20.x trở lên | Môi trường runtime JavaScript |
| **npm** | Đi kèm Node.js (v9.x trở lên) | Quản lý gói thư viện frontend |

Kiểm tra phiên bản trong terminal:
```bash
node -v
npm -v
```

---

## 🚀 2. Hướng dẫn cài đặt từng bước cho máy mới

### Bước 2.1: Di chuyển vào thư mục Frontend

Từ thư mục gốc dự án:
```bash
cd frontend
```

### Bước 2.2: Cài đặt các gói thư viện (Dependencies)

Chạy lệnh cài đặt tất cả các dependencies được định nghĩa trong `package.json`:
```bash
npm install
```

> **Gợi ý cho người dùng Windows PowerShell:**
> Nếu gặp thông báo lỗi: `npm.ps1 cannot be loaded because running scripts is disabled on this system`, hãy chạy:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```
> Hoặc sử dụng Command Prompt (`cmd`):
> ```cmd
> cmd /c npm install
> ```

---

### Bước 2.3: Cấu hình biến môi trường (Optional)

Mặc định, Frontend kết nối đến Backend tại `http://localhost:8080`. Nếu Backend của bạn chạy ở một địa chỉ hoặc cổng khác, bạn có thể tạo file `.env` tại thư mục `frontend/`:

```env
# Địa chỉ API Backend FastAPI
VITE_API_URL=http://localhost:8080
```

---

### Bước 2.4: Khởi chạy Development Server

Khởi động máy chủ phát triển Vite với tính năng Hot Module Replacement (HMR):

```bash
npm run dev
```

Sau khi chạy thành công, console sẽ hiển thị:
```
  VITE v8.2.2  ready in 250 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

Truy cập trình duyệt tại: **`http://localhost:5173/`**

---

### Bước 2.5: Đóng gói bản Production (Build)

Khi muốn kiểm tra tính đúng đắn của toàn bộ mã nguồn hoặc triển khai lên production:

```bash
npm run build
```
Thư mục xuất bản thành phẩm sẽ nằm tại `dist/`. Bạn có thể chạy thử bản build với:
```bash
npm run preview
```

---

## ✨ 3. Các tính năng nổi bật trên giao diện

### 🍔 1. Thanh lọc danh mục Hamburger & Quick Pills
- **Nút Hamburger "Danh mục"**: Mở **Slide-over Drawer** từ góc trái màn hình, cho phép tìm kiếm nhanh qua toàn bộ 62 danh mục thời trang H&M.
- **Top 8 Quick Pills**: Tự động hiển thị các danh mục phổ biến nhất (`Trousers`, `Socks`, `T-shirt`, `Dress`, `Sweater`...) kèm số lượng sản phẩm thực tế.
- **Pill đang lọc chủ động**: Hiển thị rõ danh mục đang lọc kèm nút `✕` để bỏ lọc nhanh chóng.

### 🎨 2. Chuyển đổi màu sắc trực tiếp & Đổi ảnh theo thời gian thực
- **Trên từng thẻ sản phẩm ([ProductCard.vue](src/components/ProductCard.vue))**:
  - Hàng chấm màu (swatches) trực quan.
  - Khi click chọn màu, **ảnh sản phẩm lập tức đổi sang góc chụp của màu đó**, đồng thời mã SKU (`#article_id`), giá niêm yết và số lượng tồn kho tự động cập nhật.
- **Trong modal chi tiết ([ProductDetailModal.vue](src/components/ProductDetailModal.vue))**:
  - Đổi màu phóng to ảnh độ phân giải cao.
  - Hiển thị danh sách kích cỡ có sẵn riêng cho màu đó.

### 🗄️ 3. Bảng thông số CSDL thực tế (Database Schema Table)
- Trong cửa sổ chi tiết sản phẩm, toàn bộ thông tin gốc từ CSDL MySQL được trình bày dạng thẻ:
  - Mã SP Master (`id`) & Mã SKU màu (`article_id`).
  - Loại sản phẩm (`product_type`), Nhóm hàng (`product_group`), Phân khúc (`gender_group`).
  - Nhóm phong cách (`department`), Họa tiết (`pattern`), Mô tả chi tiết (`detail_desc`).
  - Tồn kho thời gian thực theo từng phiên bản màu & size.

### 🧠 4. Giao diện Chat AI thông minh (Graph-CoT Assistant)
- Tích hợp khung chat tương tác với trợ lý AI.
- Hiển thị đầy đủ **Chuỗi suy luận Chain-of-Thought (CoT)**:
  - Ý định tìm kiếm (Intent)
  - Ánh xạ đồ thị danh mục (Category Graph Mapping)
  - Trích xuất thuộc tính (Màu sắc, kích cỡ, mức giá, giới tính)
  - Câu truy vấn SQL thực tế sinh bởi hệ thống.

---

## 📁 4. Cấu trúc thư mục Frontend

```
frontend/
├── public/                 # Tài nguyên tĩnh (favicon, logo...)
├── src/
│   ├── assets/             # CSS & Static files
│   ├── components/         # Các Vue components
│   │   ├── BrandLogo.vue           # Logo thương hiệu H&M AI Catalog
│   │   ├── CartDrawer.vue          # Giỏ hàng trượt cạnh phải
│   │   ├── ChatInterface.vue       # Khung chat trợ lý AI Graph-CoT
│   │   ├── ProductCard.vue         # Thẻ sản phẩm với swatch đổi màu
│   │   ├── ProductDetailModal.vue  # Modal chi tiết & bảng thông số CSDL
│   │   ├── ProductGrid.vue         # Lưới sản phẩm & thanh Hamburger danh mục
│   │   └── ToastNotification.vue   # Thông báo toast dạng pop-up
│   ├── services/           # Xử lý gọi API axios (aiService.js)
│   ├── App.vue             # Component gốc quản lý state tập trung
│   ├── main.js             # Entrypoint khởi tạo Vue app
│   └── style.css           # Cấu hình Tailwind CSS v4
├── index.html              # Template HTML chính
├── package.json            # Khai báo dependencies & scripts
├── vite.config.js          # Cấu hình Vite & plugin Tailwind v4
└── README.md
```

---

## ❓ 5. Xử lý sự cố thường gặp (Troubleshooting)

1. **Giao diện báo: `Đang chờ dữ liệu từ API Backend...`:**
   - Đảm bảo Backend FastAPI đang chạy tại `http://localhost:8080`.
   - Kiểm tra API trả về dữ liệu tại [http://localhost:8080/api/products](http://localhost:8080/api/products).
2. **Cổng 5173 bị xung đột:**
   - Vite sẽ tự động chuyển sang cổng tiếp theo (ví dụ: `5174`). Hãy kiểm tra thông báo trên terminal để truy cập đúng cổng.
