import os
import requests
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from qdrant_client import QdrantClient

# --- CẤU HÌNH KẾT NỐI ---
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:rootpassword@localhost:3306/ecommerce_db")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
AI_API_URL = os.getenv("AI_API_URL", "http://localhost:8001/api/v1/embed-query")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
qdrant = QdrantClient(QDRANT_URL)

app = FastAPI(title="E-commerce LLM System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ChatRequest(BaseModel):
    query: str
    model: str = "que2search-vector"
    limit: int = 200
    is_ai_chat: bool = False

@app.get("/")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "success", "message": "FastAPI đang chạy. Đã kết nối MySQL thành công!"}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi kết nối CSDL: {str(e)}"}

@app.get("/api/models")
def get_available_models():
    """Trả về danh sách mô hình AI đã kết nối với hệ thống API (chỉ Que2Search + Qdrant)"""
    return [
        {
            "id": "que2search-vector",
            "name": "Que2Search + Qdrant",
            "provider": "Local Embedding & Vector DB",
            "badge": "Vector Search ⚡",
            "description": "Nhúng vector ngữ nghĩa 256 chiều và tìm kiếm khoảng cách Cosine trên Qdrant",
            "status": "connected",
            "type": "vector"
        }
    ]

@app.get("/api/products")
def get_all_products(db: Session = Depends(get_db)):
    try:
        sql = text("""
            SELECT 
                parent_asin AS id, 
                title AS name, 
                price AS original_price, 
                discount_percent,
                average_rating AS rating,
                rating_number AS reviews_count,
                main_category AS category,
                image_url
            FROM products 
            LIMIT 200
        """)
        result = db.execute(sql).mappings().all()
        return [dict(row) for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
def process_chat(request: ChatRequest, db: Session = Depends(get_db)):
    user_text = request.query
    
    # 1. Tùy chỉnh giới hạn dựa trên nguồn gửi
    final_limit = 5 if request.is_ai_chat else request.limit
    
    # --- XỬ LÝ: MÔ HÌNH VECTOR SEARCH (Que2Search + Qdrant) ---
    try:
        # Gọi mô hình Que2Search để nhúng vector từ khóa (256 chiều)
        ai_response = requests.post(AI_API_URL, json={"text": user_text}, timeout=10)
        if ai_response.status_code != 200:
            raise Exception("Không thể giao tiếp với Que2Search Embedding API (port 8001)")
        
        query_vector = ai_response.json()["vector"]

        # Tìm kiếm khoảng cách Vector trên Qdrant có áp dụng điểm chuẩn
        search_result = qdrant.query_points(    
            collection_name="products",
            query=query_vector,
            limit=final_limit,
            score_threshold=0.35
        ).points

        matched_products = []
        matched_ids = []
        
        # Rút trích dữ liệu (Payload) đã lưu trên Qdrant
        for hit in search_result:
            matched_ids.append(hit.payload.get("parent_asin"))
            matched_products.append({
                "id": hit.payload.get("parent_asin"),
                "name": hit.payload.get("title"),
                "original_price": hit.payload.get("price"),
                "image_url": hit.payload.get("image_url"),
                "match_score": round(hit.score, 4)
            })

        if not matched_products:
            ai_msg = f"Tôi không tìm thấy sản phẩm nào phù hợp với yêu cầu *'{user_text}'* trong cơ sở dữ liệu."
        else:
            top_name = matched_products[0].get('name', 'Sản phẩm')
            top_score = matched_products[0].get('match_score', 0)
            ai_msg = f"Đã tìm thấy **{len(matched_products)} sản phẩm** thông qua **Que2Search Vector Search**!\n\n🌟 Sản phẩm khớp ngữ nghĩa cao nhất: **{top_name}** (Độ tương đồng: **{int(top_score*100)}%**)."

        return {
            "user_query": user_text,
            "model_used": "que2search-vector",
            "search_method": "Semantic Vector Search (Que2Search + Qdrant)",
            "ai_response": ai_msg,
            "matched_product_ids": matched_ids,
            "products_data": matched_products
        }
        
    except Exception as e:
        # Fallback tìm kiếm từ khóa SQL nếu service AI embedding tạm thời chưa kết nối
        try:
            clean_query = user_text.replace("'", "''").strip()
            sql_fallback = f"SELECT parent_asin AS id, title AS name, price AS original_price, discount_percent, average_rating AS rating, rating_number AS reviews_count, main_category AS category, image_url FROM products WHERE title LIKE '%{clean_query}%' LIMIT {final_limit};"
            result = db.execute(text(sql_fallback)).mappings().all()
            
            fb_products = []
            fb_ids = []
            for row in result:
                d = dict(row)
                fb_ids.append(d["id"])
                fb_products.append({
                    "id": d["id"],
                    "name": d["name"],
                    "original_price": float(d["original_price"] or 0),
                    "discount_percent": int(d["discount_percent"] or 0),
                    "image_url": d["image_url"],
                    "category": d["category"],
                    "rating": float(d["rating"] or 4.8),
                    "reviews_count": int(d["reviews_count"] or 0),
                    "match_score": 0.85
                })
            
            if fb_products:
                return {
                    "user_query": user_text,
                    "model_used": "que2search-vector",
                    "search_method": "Database Fallback Search",
                    "ai_response": f"*(Que2Search API offline - chuyển sang tìm kiếm trực tiếp CSDL)*: Tìm thấy **{len(fb_products)} sản phẩm** cho từ khóa **{user_text}**.",
                    "matched_product_ids": fb_ids,
                    "products_data": fb_products
                }
            else:
                 return {
                    "user_query": user_text,
                    "model_used": "que2search-vector",
                    "search_method": "Database Fallback Search",
                    "ai_response": "Không tìm thấy sản phẩm nào.",
                    "matched_product_ids": [],
                    "products_data": []
                }
        except Exception as fallback_e:
            return {
                "user_query": user_text,
                "model_used": "que2search-vector",
                "search_method": "Error",
                "ai_response": f"Không thể kết nối đến Que2Search API (lỗi: {str(e)}). Lỗi fallback: {str(fallback_e)}",
                "matched_product_ids": [],
                "products_data": []
            }