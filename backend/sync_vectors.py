from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import requests
import pymysql

qdrant = QdrantClient("http://localhost:6333")
collection_name = "products"

if not qdrant.collection_exists(collection_name):
    qdrant.create_collection(
        collection_name=collection_name, 
        vectors_config=VectorParams(size=256, distance=Distance.COSINE),
    )

db = pymysql.connect(host="localhost", port=3306, user="root", password="rootpassword", database="ecommerce_db")
cursor = db.cursor(pymysql.cursors.DictCursor)

# Quét toàn bộ sản phẩm thay vì LIMIT 100
cursor.execute("SELECT id, parent_asin, title, price, image_url FROM products") 
products = cursor.fetchall()

points = []
print(f"Đang nén {len(products)} sản phẩm thành vector...")

for prod in products:
    response = requests.post(
        "http://localhost:8001/api/v1/embed-query", 
        json={"text": prod['title']}
    )
    
    if response.status_code == 200:
        vector_data = response.json()["vector"]
        points.append(PointStruct(
            id=prod['id'], # Dùng trực tiếp ID nguyên gốc từ MySQL
            vector=vector_data,
            payload={
                "parent_asin": prod['parent_asin'], 
                "title": prod['title'], 
                "price": float(prod['price']),
                "image_url": prod['image_url']
            }
        ))

if points:
    qdrant.upsert(collection_name=collection_name, points=points)
    print("✅ Đồng bộ hoàn tất! Vector đã sẵn sàng trên Qdrant.")