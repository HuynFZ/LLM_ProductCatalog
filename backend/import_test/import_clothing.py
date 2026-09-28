import os
import json
import gzip
import random
import re
import urllib.request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "mysql+pymysql://root:rootpassword@localhost:3307/ecommerce_db"
)

def import_clothing_from_ucsd():
    print("=" * 60)
    print("🚀 Bắt đầu đọc luồng dữ liệu JSONL.GZ trực tiếp từ UCSD...")
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Xóa bảng cũ và tạo bảng mới có thêm cột 'description'
    try:
        session.execute(text("DROP TABLE IF EXISTS products"))
        create_table_sql = text("""
            CREATE TABLE products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                parent_asin VARCHAR(50) UNIQUE,
                title TEXT,
                description TEXT,
                price FLOAT,
                average_rating FLOAT,
                rating_number INT,
                main_category VARCHAR(100),
                image_url TEXT,
                discount_percent INT
            )
        """)
        session.execute(create_table_sql)
        session.commit()
    except Exception as e:
        print(f"❌ Lỗi khi khởi tạo lại bảng MySQL: {e}")
        return

    # 2. Cập nhật câu lệnh INSERT để nhận thêm biến :description
    insert_sql = text("""
        REPLACE INTO products 
        (parent_asin, title, description, price, average_rating, rating_number, main_category, image_url, discount_percent)
        VALUES 
        (:parent_asin, :title, :description, :price, :average_rating, :rating_number, :main_category, :image_url, :discount_percent)
    """)

    url = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_Clothing_Shoes_and_Jewelry.jsonl.gz"
    total_imported = 0

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with gzip.GzipFile(fileobj=response) as gz:
                print("⏳ Đang giải nén và nạp 1000 sản phẩm Thời trang (có kèm mô tả chi tiết)...")
                
                for line in gz:
                    if total_imported >= 1000:
                        break
                        
                    try:
                        item = json.loads(line)
                        
                        # --- LOGIC XỬ LÝ ẢNH ---
                        images = item.get("images")
                        image_url = "https://via.placeholder.com/300?text=No+Image"
                        if isinstance(images, list) and len(images) > 0:
                            first_img = images[0]
                            if isinstance(first_img, dict):
                                image_url = first_img.get("hi_res") or first_img.get("large") or first_img.get("thumb") or image_url
                            elif isinstance(first_img, str):
                                image_url = first_img
                                
                        # --- LOGIC BÓC TÁCH MÔ TẢ & ĐẶC ĐIỂM (NEW) ---
                        desc_data = item.get("description", [])
                        feat_data = item.get("features", [])
                        
                        if isinstance(desc_data, str): desc_data = [desc_data]
                        if isinstance(feat_data, str): feat_data = [feat_data]
                        
                        # Gộp cả mô tả và các tính năng nổi bật lại thành 1 đoạn văn
                        combined_desc = " ".join(desc_data + feat_data).strip()
                        final_desc = combined_desc if combined_desc else "Không có thông tin mô tả chi tiết."
                        
                        # --- LOGIC XỬ LÝ GIÁ ---
                        raw_price = item.get("price")
                        try:
                            if raw_price and str(raw_price).lower() != "none":
                                clean_price = re.sub(r'[^\d.]', '', str(raw_price))
                                price_val = float(clean_price) if clean_price else random.uniform(10.0, 100.0)
                            else:
                                price_val = random.uniform(10.0, 100.0)
                        except:
                            price_val = random.uniform(10.0, 100.0)

                        title = item.get("title")
                        
                        # 3. Thêm trường description vào cục dữ liệu để đẩy lên DB
                        product_data = {
                            "parent_asin": item.get("parent_asin") or f"B0{random.randint(10000000,99999999)}",
                            "title": title if title and str(title).lower() != "none" else "Sản phẩm không tên",
                            "description": final_desc,
                            "price": price_val,
                            "average_rating": float(item.get("average_rating") or 4.5),
                            "rating_number": int(item.get("rating_number") or 0),
                            "main_category": "Clothing Shoes and Jewelry",
                            "image_url": image_url,
                            "discount_percent": random.choice([0, 10, 15, 20, 30])
                        }
                        
                        session.execute(insert_sql, product_data)
                        total_imported += 1
                        
                    except Exception as e:
                        print(f"\n❌ Lỗi văng tại bản ghi thứ {total_imported + 1}: {e}")
                        break 

        session.commit()
        print(f"✅ Đã nạp thành công {total_imported} sản phẩm thời trang vào MySQL!")
        print("=" * 60)
    except Exception as e:
        session.rollback()
        print(f"❌ Lỗi khi đọc file jsonl.gz: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    import_clothing_from_ucsd()