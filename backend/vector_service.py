import os
import sys
import time
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range
)
from sqlalchemy import text
from database import engine, SessionLocal
from db_models import Product, ProductVariant
from embeddings import get_text_embedding, get_batch_embeddings, EMBED_DIMENSION

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
if "localhost" in QDRANT_URL:
    QDRANT_URL = QDRANT_URL.replace("localhost", "127.0.0.1")

COLLECTION_NAME = "hm_products"
BASE_IMAGE_URL = "http://localhost:8080/images/"

def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)

def ensure_vector_collection(recreate_if_wrong_dim: bool = True):
    """Đảm bảo collection hm_products tồn tại với kích thước vector 768 chiều"""
    client = get_qdrant_client()
    try:
        if client.collection_exists(COLLECTION_NAME):
            info = client.get_collection(COLLECTION_NAME)
            current_size = info.config.params.vectors.size
            if current_size != EMBED_DIMENSION:
                print(f"⚠️ Collection hiện tại có kích thước vector {current_size} != {EMBED_DIMENSION}. Cần tạo lại...")
                if recreate_if_wrong_dim:
                    client.delete_collection(COLLECTION_NAME)
                    client.create_collection(
                        collection_name=COLLECTION_NAME,
                        vectors_config=VectorParams(size=EMBED_DIMENSION, distance=Distance.COSINE)
                    )
                    print(f"✅ Đã tạo mới collection '{COLLECTION_NAME}' ({EMBED_DIMENSION} chiều, Cosine Distance).")
        else:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=EMBED_DIMENSION, distance=Distance.COSINE)
            )
            print(f"✅ Đã tạo mới collection '{COLLECTION_NAME}' ({EMBED_DIMENSION} chiều, Cosine Distance).")
    except Exception as e:
        print(f"⚠️ Lỗi cấu hình collection Qdrant: {e}")

def build_product_semantic_doc(prod: Product, variant: ProductVariant = None) -> str:
    """Tạo văn bản ngữ nghĩa phong phú cho sản phẩm để vector hóa"""
    parts = []
    if prod.name:
        parts.append(f"Product: {prod.name}")
    if prod.product_type:
        parts.append(f"Category: {prod.product_type}")
    if getattr(prod, "product_group", ""):
        parts.append(f"Group: {prod.product_group}")
    if getattr(prod, "gender_group", ""):
        parts.append(f"Gender: {prod.gender_group}")
    if variant and variant.color:
        parts.append(f"Color: {variant.color}")
    if getattr(prod, "pattern", "") and prod.pattern != "Solid":
        parts.append(f"Pattern: {prod.pattern}")
    if prod.detail_desc:
        parts.append(f"Details: {prod.detail_desc}")
    
    return ". ".join(parts)

def search_semantic(
    query_text: str,
    color: str = None,
    gender_groups: list = None,
    max_price: float = None,
    limit: int = 15
) -> list:
    """
    Tìm kiếm bằng Vector Embeddings trên Qdrant kết hợp lọc thuộc tính (Filtered Vector Search).
    Trả về danh sách dict: {article_id, product_id, score, payload}
    """
    if not query_text:
        return []

    client = get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        return []

    # 1. Sinh vector cho câu query
    query_vector = get_text_embedding(query_text)

    # 2. Xây dựng bộ lọc Qdrant Payload nếu có
    must_conditions = []
    if color:
        must_conditions.append(
            FieldCondition(key="color", match=MatchValue(value=color))
        )
    if gender_groups and len(gender_groups) > 0:
        # Nếu có giới tính, chấp nhận giới tính đó hoặc unisex / Divided
        gender_should = [
            FieldCondition(key="gender_group", match=MatchValue(value=g))
            for g in gender_groups
        ]
        must_conditions.append(Filter(should=gender_should))
    if max_price is not None and max_price > 0:
        must_conditions.append(
            FieldCondition(key="price", range=Range(lte=max_price))
        )

    query_filter = Filter(must=must_conditions) if must_conditions else None

    # 3. Tìm kiếm trong Qdrant
    try:
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True
        )
        hits = response.points

        # Nếu lọc cứng màu mà không thấy kết quả (hết màu đó), tìm kiếm nới lỏng không lọc màu
        if not hits and color and query_filter:
            fallback_must = [c for c in must_conditions if getattr(c, "key", "") != "color"]
            fallback_filter = Filter(must=fallback_must) if fallback_must else None
            response_fb = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=fallback_filter,
                limit=limit,
                with_payload=True
            )
            hits = response_fb.points

        results = []
        for hit in hits:
            p = hit.payload or {}
            results.append({
                "article_id": str(p.get("article_id", hit.id)).zfill(10),
                "product_id": str(p.get("product_id", "")),
                "score": float(hit.score),
                "payload": p
            })
        return results
    except Exception as e:
        print(f"⚠️ Lỗi truy vấn Qdrant semantic search: {e}")
        return []
