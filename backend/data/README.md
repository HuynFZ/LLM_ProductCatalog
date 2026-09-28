# 📦 H&M Dataset Directory (`backend/data/`)

Thư mục này dùng để chứa dữ liệu thô phục vụ hệ thống H&M AI Catalog.

> ⚠️ **LƯU Ý QUAN TRỌNG:**
> Các file dữ liệu lớn (`articles.csv` và thư mục `images/`) **không được đưa lên Git** để tránh làm nặng repository.
> 
> 👉 **Vui lòng liên hệ Huy để nhận toàn bộ file dữ liệu và giải nén/đặt vào đúng cấu trúc sau:**

---

### 📂 Cấu trúc dữ liệu chuẩn cần có trong `backend/data/`:

```
backend/data/
├── articles.csv                   # [Liên hệ Huy] File metadata thông tin sản phẩm H&M (~36 MB)
└── images/                        # [Liên hệ Huy] Thư mục chứa toàn bộ ảnh sản phẩm thực tế
    ├── 010/                       # Các thư mục con theo 3 số đầu của mã SKU
    │   ├── 0108775015.jpg
    │   ├── 0108775044.jpg
    │   └── 0108775051.jpg
    ├── 011/
    ├── 012/
    └── ... (86 thư mục con)
```

---

### 🚀 Sau khi chép xong dữ liệu:
Chạy lệnh đồng bộ vào CSDL MySQL và Qdrant:
```bash
python import_all_hm_data.py
```
Hệ thống sẽ tự động quét các file ảnh trong `backend/data/images/` và đối chiếu metadata trong `backend/data/articles.csv` để nạp vào hệ thống.
