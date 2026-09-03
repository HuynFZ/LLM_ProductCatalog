import os
import random
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "mysql+pymysql://root:rootpassword@localhost:3306/ecommerce_db"
)

def import_amazon_dataset():
    print("=" * 60)
    print("🚀 Bắt đầu lấy dữ liệu thực tế từ Amazon Dataset (Parquet Direct)...")
    
    try:
        from datasets import load_dataset
    except ImportError:
        print("❌ Lỗi: Chưa cài đặt thư viện 'datasets'.")
        return 0

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Dùng đúng tên thư mục chứa file parquet trên Hugging Face
    categories = [
        "raw_meta_All_Beauty",
        "raw_meta_Electronics",
        "raw_meta_Home_and_Kitchen",
        "raw_meta_Cell_Phones_and_Accessories",
        "raw_meta_Clothing_Shoes_and_Jewelry"
    ]

    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS products (
                parent_asin VARCHAR(50) PRIMARY KEY,
                title TEXT,
                price DECIMAL(10,2) DEFAULT 0.00,
                average_rating FLOAT DEFAULT 0,
                rating_number INT DEFAULT 0,
                main_category VARCHAR(255),
                image_url TEXT,
                discount_percent INT DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """))
        session.execute(text("TRUNCATE TABLE products;"))

        insert_sql = text("""
            INSERT IGNORE INTO products 
            (parent_asin, title, price, average_rating, rating_number, main_category, image_url, discount_percent)
            VALUES 
            (:parent_asin, :title, :price, :average_rating, :rating_number, :main_category, :image_url, :discount_percent)
        """)

        total_imported = 0

        for cat in categories:
            print(f"⏳ Đang tải dữ liệu danh mục: {cat}...")
            try:
                # CÁCH GỌI CHUẨN MỚI: Dùng dictionary mapping {"train": data_files}
                dataset = load_dataset(
                    "parquet", 
                    data_files={"train": f"hf://datasets/McAuley-Lab/Amazon-Reviews-2023/{cat}/*.parquet"}, 
                    split="train", 
                    streaming=True
                )
            except Exception as e:
                print(f"⚠️ Bỏ qua danh mục {cat} do lỗi tải: {e}")
                continue
            
            cat_count = 0
            for item in dataset:
                if cat_count >= 50: # Lấy đúng 50 sản phẩm chất lượng mỗi loại
                    break
                    
                try:
                    images = item.get("images") or {}
                    image_url = "https://via.placeholder.com/150"
                    if isinstance(images, dict):
                        large_imgs = images.get("large") or []
                        hi_res_imgs = images.get("hi_res") or []
                        all_imgs = [img for img in (large_imgs + hi_res_imgs) if img]
                        if all_imgs:
                            image_url = all_imgs[0]
                    elif isinstance(images, list) and images:
                        image_url = str(images[0])
                    
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
                        "main_category": cat.replace("raw_meta_", "").replace("_", " "),
                        "image_url": image_url,
                        "discount_percent": random.choice([0, 10, 15, 20, 30])
                    }
                    
                    session.execute(insert_sql, product_data)
                    cat_count += 1
                    total_imported += 1
                except Exception:
                    continue 

        session.commit()
        print(f"✅ Đã nạp thành công tổng cộng {total_imported} sản phẩm vào MySQL!")
        print("=" * 60)
        return total_imported
    except Exception as e:
        session.rollback()
        print(f"❌ Lỗi khi nạp dữ liệu: {e}")
        return 0
    finally:
        session.close()

if __name__ == "__main__":
    import_amazon_dataset()