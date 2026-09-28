import os
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "mysql+pymysql://root:rootpassword@localhost:3307/ecommerce_db"
)

def import_tiki_data():
    print("=" * 60)
    print("🚀 Bắt đầu lấy dữ liệu sản phẩm Việt Nam từ Tiki API...")
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Danh sách các từ khóa muốn cào dữ liệu trên Tiki
    search_queries = [
        {"q": "điện thoại", "category": "Điện Thoại & Phụ Kiện"},
        {"q": "laptop", "category": "Laptop & Thiết Bị IT"},
        {"q": "đồ gia dụng", "category": "Điện Gia Dụng"},
        {"q": "mỹ phẩm", "category": "Làm Đẹp - Sức Khỏe"}
    ]

    # Giả lập trình duyệt Chrome để không bị Tiki chặn
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        insert_sql = text("""
            INSERT IGNORE INTO products 
            (parent_asin, title, price, average_rating, rating_number, main_category, image_url, discount_percent)
            VALUES 
            (:parent_asin, :title, :price, :average_rating, :rating_number, :main_category, :image_url, :discount_percent)
        """)

        total_imported = 0

        for item in search_queries:
            keyword = item["q"]
            cat_name = item["category"]
            print(f"⏳ Đang tải từ khóa: {keyword}...")
            
            cat_imported = 0
            for page in range(1, 6): # 5 trang x 50 = 250 sản phẩm / danh mục
                if cat_imported >= 250:
                    break
                url = f"https://tiki.vn/api/v2/products?limit=50&page={page}&q={keyword}"
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json().get("data", [])
                    if not data:
                        break
                    
                    for product in data:
                        if cat_imported >= 250:
                            break
                        product_data = {
                            # Đổi tiền tố thành TIKI_ để không trùng với hàng Amazon
                            "parent_asin": f"TIKI_{product.get('id')}",
                            "title": product.get("name", "Sản phẩm không tên"),
                            "price": float(product.get("price", 0)),
                            "average_rating": float(product.get("rating_average", 0)),
                            "rating_number": int(product.get("review_count", 0)),
                            "main_category": cat_name,
                            "image_url": product.get("thumbnail_url", "https://via.placeholder.com/150"),
                            "discount_percent": int(product.get("discount_rate", 0))
                        }
                        session.execute(insert_sql, product_data)
                        cat_imported += 1
                        total_imported += 1
                else:
                    print(f"⚠️ Bị từ chối khi tải '{keyword}' trang {page} (Mã lỗi: {response.status_code})")
                    break

        session.commit()
        print(f"✅ Đã nạp thành công {total_imported} sản phẩm thật từ Tiki vào MySQL!")
        print("=" * 60)
        
    except Exception as e:
        session.rollback()
        print(f"❌ Lỗi khi nạp dữ liệu: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    import_tiki_data()