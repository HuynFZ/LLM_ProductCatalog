import os
import sys
import time
import argparse
from sqlalchemy import text
from qdrant_client.models import PointStruct
from database import engine, SessionLocal
from db_models import Product, ProductVariant
from embeddings import get_batch_embeddings, EMBED_DIMENSION
from vector_service import (
    get_qdrant_client,
    ensure_vector_collection,
    build_product_semantic_doc,
    COLLECTION_NAME,
    BASE_IMAGE_URL
)

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def index_all_products(limit: int = None, batch_size: int = 25, recreate: bool = False):
    start_time = time.time()
    print("=" * 65)
    print("🚀 BẮT ĐẦU VECTOR HÓA DỮ LIỆU SẢN PHẨM VÀ NẠP VÀO QDRANT")
    print("=" * 65)

    # 1. Đảm bảo collection đúng cấu hình 768 chiều
    ensure_vector_collection(recreate_if_wrong_dim=recreate)
    client = get_qdrant_client()

    # 2. Lấy danh sách ID đã có trong Qdrant để tránh vector hóa lại
    existing_ids = set()
    if not recreate:
        print("🔍 Đang kiểm tra các vector point đã tồn tại trong Qdrant...")
        offset = None
        while True:
            records, next_offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=1000,
                offset=offset,
                with_payload=False,
                with_vectors=False
            )
            if not records:
                break
            for r in records:
                existing_ids.add(r.id)
            offset = next_offset
            if offset is None:
                break
        print(f"  -> Đã có sẵn {len(existing_ids)} points trong Qdrant.")

    # 3. Lấy sản phẩm từ MySQL cùng các biến thể
    db = SessionLocal()
    try:
        from sqlalchemy.orm import joinedload
        query = db.query(Product).options(joinedload(Product.variants))
        if limit:
            query = query.limit(limit)
        products = query.all()
        print(f"📦 Tổng số sản phẩm MySQL cần xử lý: {len(products)} sản phẩm.")

        # 4. Chuẩn bị danh sách items cần tạo vector trong phiên làm việc
        items_to_embed = []
        for prod in products:
            variants = prod.variants or []
            first_variant = variants[0] if variants else None
            
            seen_colors = set()
            for v in (variants if variants else [None]):
                c = v.color if v else "Standard"
                if c in seen_colors:
                    continue
                seen_colors.add(c)
                
                art_id = str(getattr(v, 'article_id', None) or prod.id).zfill(10)
                try:
                    point_id = int(art_id)
                except ValueError:
                    continue

                if point_id in existing_ids:
                    continue

                doc_text = build_product_semantic_doc(prod, v)
                sub_folder = art_id[:3]
                img_url = f"{BASE_IMAGE_URL}{sub_folder}/{art_id}.jpg"
                price = float(v.price) if (v and v.price) else 29.99

                payload = {
                    "article_id": art_id,
                    "product_id": str(prod.id),
                    "name": prod.name,
                    "product_type": prod.product_type or "",
                    "product_group": getattr(prod, "product_group", "") or "",
                    "gender_group": getattr(prod, "gender_group", "") or "",
                    "department": prod.department or "",
                    "color": c,
                    "price": price,
                    "image_url": img_url,
                    "semantic_text": doc_text
                }

                items_to_embed.append({
                    "point_id": point_id,
                    "text": doc_text,
                    "payload": payload
                })
    finally:
        db.close()

    total_items = len(items_to_embed)
    print(f"⚡ Số lượng biến thể cần sinh vector mới: {total_items} items.")
    if total_items == 0:
        print("✅ Toàn bộ sản phẩm đã được vector hóa đầy đủ trong Qdrant!")
        return

    # 5. Sinh vector theo từng batch và upsert vào Qdrant
    total_batches = (total_items + batch_size - 1) // batch_size
    print(f"🔄 Bắt đầu sinh vector theo từng batch ({batch_size} items/batch)...")

    success_count = 0
    for b_idx in range(total_batches):
        batch_start_time = time.time()
        start_i = b_idx * batch_size
        end_i = min(start_i + batch_size, total_items)
        batch_items = items_to_embed[start_i:end_i]

        batch_texts = [it["text"] for it in batch_items]
        batch_vectors = get_batch_embeddings(batch_texts, batch_size=batch_size)

        points = []
        for it, vec in zip(batch_items, batch_vectors):
            # Chỉ nạp nếu vector hợp lệ (không rỗng và đúng 768 chiều)
            if len(vec) == EMBED_DIMENSION and any(v != 0.0 for v in vec[:10]):
                points.append(PointStruct(
                    id=it["point_id"],
                    vector=vec,
                    payload=it["payload"]
                ))

        if points:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            success_count += len(points)

        b_elapsed = round(time.time() - batch_start_time, 2)
        progress = round((end_i / total_items) * 100, 1)
        print(f"  • Batch {b_idx + 1}/{total_batches} ({len(points)} points) hoàn thành trong {b_elapsed}s | Tiến độ: {progress}% ({end_i}/{total_items})")

    elapsed_all = round(time.time() - start_time, 2)
    print("\n" + "=" * 65)
    print(f"🎉 HOÀN THÀNH VECTOR HÓA TRONG {elapsed_all} GIÂY!")
    print(f"📊 Tổng số points mới đã nạp vào Qdrant: {success_count} points.")
    final_info = client.get_collection(COLLECTION_NAME)
    print(f"📊 Tổng số points hiện có trong collection '{COLLECTION_NAME}': {final_info.points_count} points.")
    print("=" * 65)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vectorize product catalog into Qdrant")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số sản phẩm xử lý (None = toàn bộ)")
    parser.add_argument("--batch-size", type=int, default=25, help="Kích thước batch khi gọi embedding")
    parser.add_argument("--recreate", action="store_true", help="Xóa và tạo lại collection Qdrant")
    args = parser.parse_args()

    index_all_products(limit=args.limit, batch_size=args.batch_size, recreate=args.recreate)
