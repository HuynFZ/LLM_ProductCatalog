import os
import sys
import time
import random
import pandas as pd
from sqlalchemy import text
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, PointIdsList

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Import kết nối CSDL MySQL
from database import engine

# Cấu hình Qdrant & Thư mục dữ liệu
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "hm_products"
IMAGE_DIR = "data/images" if os.path.exists("data/images") else "images"
ARTICLES_CSV = "data/articles.csv" if os.path.exists("data/articles.csv") else "articles.csv"
BASE_IMAGE_URL = "http://localhost:8080/images/"

def import_remaining_data():
    start_time = time.time()
    print("=" * 65)
    print("🔄 ĐỒNG BỘ 2 CHIỀU: CẬP NHẬT THEO THƯ MỤC ẢNH THỰC TẾ (THÊM MỚI & XÓA CŨ)")
    print("=" * 65)

    # =========================================================================
    # 1. QUÉT TOÀN BỘ ẢNH THỰC TẾ HIỆN CÓ TRÊN ĐĨA CỨNG
    # =========================================================================
    print("📂 [1/4] Đang quét danh sách các file ảnh thực tế trong thư mục images...")
    existing_images = {}
    for sub in os.listdir(IMAGE_DIR):
        sub_path = os.path.join(IMAGE_DIR, sub)
        if os.path.isdir(sub_path):
            for fname in os.listdir(sub_path):
                if fname.lower().endswith(('.jpg', '.png', '.jpeg')):
                    art_id = os.path.splitext(fname)[0]
                    existing_images[art_id] = f"{sub}/{fname}"

    disk_image_set = set(existing_images.keys())
    print(f"  -> Tổng số file ảnh thực tế hiện có trên đĩa cứng: {len(disk_image_set)} ảnh.")

    # =========================================================================
    # 2. DỌN DẸP DỮ LIỆU ĐÃ BỊ XÓA KHỎI THƯ MỤC ẢNH
    # =========================================================================
    print("\n🧹 [2/4] Kiểm tra và tự động dọn dẹp các ảnh đã bị xóa khỏi thư mục...")
    
    # 2.1. Dọn dẹp trong MySQL
    with engine.begin() as conn:
        db_articles = set(r[0] for r in conn.execute(text("SELECT DISTINCT article_id FROM product_variants")).all())
        deleted_articles_mysql = db_articles - disk_image_set

        if deleted_articles_mysql:
            print(f"  -> Phát hiện {len(deleted_articles_mysql)} mã ảnh đã bị xóa khỏi đĩa cứng trong MySQL.")
            # Xóa các biến thể tương ứng theo từng batch để tránh quá tải câu lệnh SQL
            del_list = list(deleted_articles_mysql)
            chunk_size = 1000
            total_deleted_vars = 0
            for i in range(0, len(del_list), chunk_size):
                chunk = tuple(del_list[i:i + chunk_size])
                res = conn.execute(text("DELETE FROM product_variants WHERE article_id IN :arts"), {"arts": chunk})
                total_deleted_vars += res.rowcount

            # Xóa các Master Products không còn biến thể nào
            res_prod = conn.execute(text("""
                DELETE FROM products 
                WHERE id NOT IN (SELECT DISTINCT product_id FROM product_variants)
            """))
            print(f"  🗑️ Đã xóa {total_deleted_vars} biến thể và {res_prod.rowcount} sản phẩm mồ côi khỏi MySQL.")
        else:
            print("  ✅ Dữ liệu MySQL hoàn toàn khớp với đĩa cứng, không có ảnh thừa.")

    # 2.2. Dọn dẹp trong Qdrant
    try:
        qdrant = QdrantClient(url=QDRANT_URL)
        if qdrant.collection_exists(QDRANT_COLLECTION):
            # Lấy tất cả Point ID trong Qdrant
            qdrant_ids = set()
            offset = None
            while True:
                records, next_offset = qdrant.scroll(
                    collection_name=QDRANT_COLLECTION,
                    limit=1000,
                    offset=offset,
                    with_payload=False,
                    with_vectors=False
                )
                if not records:
                    break
                for r in records:
                    qdrant_ids.add(r.id)
                offset = next_offset
                if offset is None:
                    break

            # Điểm cần xóa: những point mà mã article_id không còn file ảnh
            qdrant_delete_points = [pid for pid in qdrant_ids if str(pid).zfill(10) not in disk_image_set]
            if qdrant_delete_points:
                print(f"  -> Phát hiện {len(qdrant_delete_points)} vector points trong Qdrant đã bị xóa file ảnh.")
                del_chunk = 1000
                for i in range(0, len(qdrant_delete_points), del_chunk):
                    chunk_pids = qdrant_delete_points[i:i + del_chunk]
                    qdrant.delete(
                        collection_name=QDRANT_COLLECTION,
                        points_selector=PointIdsList(points=chunk_pids)
                    )
                print(f"  🗑️ Đã xóa {len(qdrant_delete_points)} points khỏi Qdrant collection '{QDRANT_COLLECTION}'.")
            else:
                print("  ✅ Collection Qdrant hoàn toàn khớp với đĩa cứng, không có vector thừa.")
    except Exception as e:
        print(f"  ⚠️ Lưu ý kiểm tra Qdrant: {e}")

    # =========================================================================
    # 3. ĐỌC METADATA TỪ ARTICLES.CSV (CHỈ LẤY CÁC ẢNH ĐANG TỒN TẠI)
    # =========================================================================
    print(f"\n📄 [3/4] Đang đối chiếu metadata từ {ARTICLES_CSV}...")
    if not os.path.exists(ARTICLES_CSV):
        print(f"❌ Lỗi: Không tìm thấy {ARTICLES_CSV}!")
        return

    df = pd.read_csv(ARTICLES_CSV, dtype=str).fillna("")
    df['clean_article_id'] = df['article_id'].str.zfill(10)
    
    # Chỉ giữ các dòng mà file ảnh thực sự tồn tại trên đĩa cứng
    df_valid = df[df['clean_article_id'].isin(disk_image_set)].copy()
    print(f"  -> Tìm thấy {len(df_valid)} dòng metadata tương ứng với các ảnh đang có.")

    # =========================================================================
    # 4. NẠP BỔ SUNG NẾU CÓ ẢNH MỚI (MYSQL & QDRANT)
    # =========================================================================
    print("\n🚀 [4/4] Kiểm tra và nạp bổ sung sản phẩm mới...")
    with engine.begin() as conn:
        existing_pids = set(r[0] for r in conn.execute(text("SELECT id FROM products")).all())
        existing_vids = set(r[0] for r in conn.execute(text("SELECT variant_id FROM product_variants")).all())

    # Lọc Master Products và Variants mới
    grouped = df_valid.groupby("product_code")
    new_products_batch = []
    new_variants_batch = []

    for product_code, group_rows in grouped:
        p_code_str = str(product_code)
        first_row = group_rows.iloc[0]
        prod_name = str(first_row['prod_name'])[:250]
        product_type = str(first_row['product_type_name'])[:95]
        product_group = str(first_row.get('product_group_name', ''))[:95]
        gender_group = str(first_row.get('index_group_name', ''))[:45]
        department = str(first_row.get('department_name', ''))[:95]
        pattern = str(first_row.get('graphical_appearance_name', 'Solid'))[:45]
        detail_desc = str(first_row.get('detail_desc', ''))[:990]

        if p_code_str not in existing_pids:
            new_products_batch.append({
                "id": p_code_str,
                "name": prod_name,
                "product_type": product_type,
                "product_group": product_group,
                "gender_group": gender_group,
                "department": department,
                "pattern": pattern,
                "detail_desc": detail_desc
            })

        # Phân loại size
        pg_lower = product_group.lower()
        if 'shoes' in pg_lower:
            sizes = ['38', '39', '40', '41', '42']
        elif any(k in pg_lower for k in ['accessories', 'bags', 'items', 'socks', 'tights']):
            sizes = ['One Size']
        else:
            sizes = ['S', 'M', 'L', 'XL']

        unique_articles = group_rows.drop_duplicates(subset=['clean_article_id'])
        for _, art_row in unique_articles.iterrows():
            art_id = str(art_row['clean_article_id'])
            color = str(art_row.get('colour_group_name', 'Standard'))[:45]
            base_price = round(random.uniform(19.99, 119.99), 2)

            for sz in sizes:
                v_id = f"{art_id}-{sz}".replace(" ", "")
                if v_id not in existing_vids:
                    stock = random.randint(5, 50) if random.random() > 0.15 else 0
                    new_variants_batch.append({
                        "variant_id": v_id,
                        "product_id": p_code_str,
                        "article_id": art_id,
                        "color": color,
                        "size": sz,
                        "price": base_price,
                        "stock_quantity": stock
                    })

    # Nạp vào MySQL nếu có sản phẩm mới
    if new_products_batch or new_variants_batch:
        with engine.begin() as conn:
            chunk_size = 5000
            for i in range(0, len(new_products_batch), chunk_size):
                chunk = new_products_batch[i:i + chunk_size]
                conn.execute(text("""
                    INSERT IGNORE INTO products 
                    (id, name, product_type, product_group, gender_group, department, pattern, detail_desc)
                    VALUES (:id, :name, :product_type, :product_group, :gender_group, :department, :pattern, :detail_desc)
                """), chunk)

            for i in range(0, len(new_variants_batch), chunk_size):
                chunk = new_variants_batch[i:i + chunk_size]
                conn.execute(text("""
                    INSERT IGNORE INTO product_variants 
                    (variant_id, product_id, article_id, color, size, price, stock_quantity)
                    VALUES (:variant_id, :product_id, :article_id, :color, :size, :price, :stock_quantity)
                """), chunk)
        print(f"  ✅ Đã nạp thêm {len(new_products_batch)} sản phẩm và {len(new_variants_batch)} biến thể mới vào MySQL.")
    else:
        print("  ℹ️ MySQL đã đầy đủ, không có sản phẩm mới cần nạp thêm.")

    # Nạp vào Qdrant nếu có point mới
    try:
        qdrant = QdrantClient(url=QDRANT_URL)
        if not qdrant.collection_exists(QDRANT_COLLECTION):
            qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=128, distance=Distance.COSINE)
            )

        # Lấy lại danh sách ID đang có trong Qdrant
        current_qdrant_ids = set()
        offset = None
        while True:
            records, next_offset = qdrant.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=1000,
                offset=offset,
                with_payload=False,
                with_vectors=False
            )
            if not records:
                break
            for r in records:
                current_qdrant_ids.add(r.id)
            offset = next_offset
            if offset is None:
                break

        points_to_upsert = []
        zero_vector = [0.0] * 128
        unique_articles_all = df_valid.drop_duplicates(subset=['clean_article_id'])
        for _, row in unique_articles_all.iterrows():
            art_id = str(row['clean_article_id'])
            try:
                point_id = int(art_id)
            except ValueError:
                continue

            if point_id in current_qdrant_ids:
                continue  # Đã có

            rel_img = existing_images.get(art_id, f"{art_id[:3]}/{art_id}.jpg")
            img_url = f"{BASE_IMAGE_URL}{rel_img}"

            payload = {
                "article_id": art_id,
                "product_id": str(row['product_code']),
                "name": str(row['prod_name']),
                "product_type": str(row['product_type_name']),
                "product_group": str(row.get('product_group_name', '')),
                "gender_group": str(row.get('index_group_name', '')),
                "department": str(row.get('department_name', '')),
                "color": str(row.get('colour_group_name', '')),
                "image_url": img_url
            }

            points_to_upsert.append(PointStruct(
                id=point_id,
                vector=zero_vector,
                payload=payload
            ))

        if points_to_upsert:
            batch_size = 500
            for i in range(0, len(points_to_upsert), batch_size):
                batch = points_to_upsert[i:i + batch_size]
                qdrant.upsert(collection_name=QDRANT_COLLECTION, points=batch)
            print(f"  ✅ Đã nạp thêm {len(points_to_upsert)} points mới vào Qdrant.")
        else:
            print("  ℹ️ Qdrant đã đầy đủ, không có points mới cần nạp thêm.")

    except Exception as e:
        print(f"  ⚠️ Lưu ý Qdrant: {e}")

    # Báo cáo tổng kết số lượng hiện tại
    with engine.begin() as conn:
        final_prods = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()
        final_vars = conn.execute(text("SELECT COUNT(*) FROM product_variants")).scalar()

    try:
        final_qdrant = qdrant.get_collection(QDRANT_COLLECTION).points_count
    except Exception:
        final_qdrant = "N/A"

    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 65)
    print(f"🎉 ĐỒNG BỘ HOÀN TẤT TRONG {elapsed} GIÂY!")
    print(f"📊 TỔNG KẾT TRẠNG THÁI HIỆN TẠI:")
    print(f"  • File ảnh thực tế trên đĩa: {len(disk_image_set)} ảnh")
    print(f"  • MySQL Master Products:    {final_prods} sản phẩm")
    print(f"  • MySQL Product Variants:   {final_vars} biến thể")
    print(f"  • Qdrant Vector Points:     {final_qdrant} points")
    print("=" * 65)

if __name__ == "__main__":
    import_remaining_data()
