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
    "mysql+pymysql://root:rootpassword@localhost:3306/ecommerce_db"
)

def import_clothing_from_ucsd():
    print("=" * 60)
    print("🚀 Bắt đầu đọc luồng dữ liệu JSONL.GZ trực tiếp từ UCSD...")
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Dùng REPLACE INTO để tự động ghi đè dữ liệu lỗi ảnh cũ
    insert_sql = text("""
        REPLACE INTO products 
        (parent_asin, title, price, average_rating, rating_number, main_category, image_url, discount_percent)
        VALUES 
        (:parent_asin, :title, :price, :average_rating, :rating_number, :main_category, :image_url, :discount_percent)
    """)

    url = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_Clothing_Shoes_and_Jewelry.jsonl.gz"
    total_imported = 0

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with gzip.GzipFile(fileobj=response) as gz:
                print("⏳ Đang giải nén và nạp 50 sản phẩm Thời trang...")
                
                for line in gz:
                    if total_imported >= 50:
                        break
                        
                    try:
                        item = json.loads(line)
                        
                        # --- LOGIC XỬ LÝ ẢNH MỚI CHO BỘ JSONL ---
                        images = item.get("images")
                        image_url = "https://via.placeholder.com/300?text=No+Image"
                        
                        if isinstance(images, list) and len(images) > 0:
                            first_img = images[0]
                            if isinstance(first_img, dict):
                                image_url = first_img.get("hi_res") or first_img.get("large") or first_img.get("thumb") or image_url
                            elif isinstance(first_img, str):
                                image_url = first_img
                        # ----------------------------------------
                        
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
                        product_data = {
                            "parent_asin": item.get("parent_asin") or f"B0{random.randint(10000000,99999999)}",
                            "title": title if title and str(title).lower() != "none" else "Sản phẩm không tên",
                            "price": price_val,
                            "average_rating": float(item.get("average_rating") or 4.5),
                            "rating_number": int(item.get("rating_number") or 0),
                            "main_category": "Clothing Shoes and Jewelry",
                            "image_url": image_url,
                            "discount_percent": random.choice([0, 10, 15, 20, 30])
                        }
                        
                        session.execute(insert_sql, product_data)
                        total_imported += 1
                    except Exception:
                        continue 

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