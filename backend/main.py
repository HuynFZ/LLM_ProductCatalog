import os
import sys
import re
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text

# Import từ các module trong hệ thống của bạn
from database import SessionLocal
from db_models import Product
from hybrid_search import execute_hybrid_search

# Tự động nhận diện thư mục images (ưu tiên data/images nếu đã gộp)
IMAGE_DIR = "data/images" if os.path.exists("data/images") else "images"
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR, exist_ok=True)

app = FastAPI(title="H&M Hybrid Search API (Auto-CoT)")

# Mở cổng cho frontend (Vue.js) truy cập thư mục ảnh cục bộ
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

# Cấu hình CORS cho phép Frontend kết nối
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# CÁC SCHEMAS DỮ LIỆU
# ==========================================
# Cho phép nhận thêm các trường từ Vue.js (như model_id) mà không báo lỗi 422
class ChatRequest(BaseModel):
    query: str
    model_id: str = None  

# ==========================================
# CÁC ENDPOINTS (API ROUTES)
# ==========================================

@app.get("/")
def health_check():
    """Kiểm tra trạng thái hệ thống và kết nối MySQL"""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "success", "message": "FastAPI đang chạy. Hệ thống H&M đã sẵn sàng!"}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi CSDL: {str(e)}"}
    finally:
        db.close()


@app.get("/api/models")
def get_available_models():
    """Trả về danh sách các mô hình AI đang được sử dụng"""
    return [
        {
            "id": "auto-cot",
            "name": "Graph-CoT Reasoning Search",
            "provider": "Graph-CoT (Qwen 2.5) & MySQL",
            "badge": "Graph-CoT 🌟",
            "description": "Suy luận đa tầng Chain-of-Thought trên đồ thị danh mục H&M kết hợp Hybrid SQL",
            "status": "connected",
            "type": "llm"
        }
    ]


@app.get("/api/products")
def get_all_products():
    """Lấy danh sách sản phẩm mặc định kèm đầy đủ các trường dữ liệu CSDL"""
    db = SessionLocal()
    try:
        # Dùng ORM để lấy dữ liệu H&M kèm quan hệ variants
        products = db.query(Product).limit(1000).all()
        
        products_data = []
        for prod in products:
            variants = prod.variants or []
            first_variant = variants[0] if variants else None
            price = round(first_variant.price, 2) if (first_variant and first_variant.price) else 29.99
            color = first_variant.color if first_variant else "Tiêu chuẩn"
            size = first_variant.size if first_variant else "M"
            stock = first_variant.stock_quantity if (first_variant and first_variant.stock_quantity is not None) else 25
            variant_id = first_variant.variant_id if first_variant else f"{prod.id}-{color}-{size}"
            
            # Lấy article_id của biến thể đầu tiên để load ảnh
            article_id = str(first_variant.article_id if (first_variant and getattr(first_variant, 'article_id', None)) else prod.id).zfill(10)
            sub_folder = article_id[:3]
            
            available_colors = list(dict.fromkeys(v.color for v in variants if v.color))
            available_sizes = list(dict.fromkeys(v.size for v in variants if v.size))
            
            color_images = {}
            color_details = {}
            for v in variants:
                c = v.color or "Tiêu chuẩn"
                art = str(getattr(v, 'article_id', None) or prod.id).zfill(10)
                img = f"http://localhost:8080/images/{art[:3]}/{art}.jpg"
                color_images[c] = img
                
                if c not in color_details:
                    color_details[c] = {
                        "color": c,
                        "article_id": art,
                        "image_url": img,
                        "price": round(v.price, 2) if v.price else price,
                        "stock_quantity": 0,
                        "sizes": [],
                        "size_stocks": {}
                    }
                if v.size:
                    if v.size not in color_details[c]["sizes"]:
                        color_details[c]["sizes"].append(v.size)
                    s_qty = int(v.stock_quantity) if v.stock_quantity is not None else 0
                    color_details[c]["size_stocks"][v.size] = s_qty
                    color_details[c]["stock_quantity"] += s_qty
            
            products_data.append({
                "id": str(prod.id),
                "name": prod.name,
                "product_type": prod.product_type or "N/A",
                "product_group": getattr(prod, "product_group", "") or "Thời trang H&M",
                "department": prod.department or "H&M Collection",
                "gender_group": getattr(prod, "gender_group", "") or "H&M Collection",
                "pattern": getattr(prod, "pattern", "") or "Solid",
                "detail_desc": prod.detail_desc or "Sản phẩm thời trang H&M chính hãng với thiết kế tinh tế.",
                "color": color,
                "size": size,
                "stock_quantity": stock,
                "variant_id": variant_id,
                "article_id": article_id,
                "available_colors": available_colors if available_colors else [color],
                "available_sizes": available_sizes if available_sizes else [size],
                "color_images": color_images,
                "color_details": color_details,
                "original_price": price,
                "discount_percent": 0,
                "rating": 4.8, 
                "reviews_count": 120,
                "category": prod.product_type or "N/A",
                "image_url": f"http://localhost:8080/images/{sub_folder}/{article_id}.jpg"
            })
        return products_data
    except Exception as e:
        print(f"LỖI NGHIÊM TRỌNG KHI LẤY SẢN PHẨM: {e}")
        return []
    finally:
        db.close()


@app.post("/api/chat")
def process_chat(request: ChatRequest):
    """Xử lý câu lệnh tìm kiếm lai kết hợp Graph Chain-of-Thought và SQL"""
    user_text = request.query
    
    try:
        # Thực thi tìm kiếm bằng Graph Chain-of-Thought (Graph-CoT)
        results = execute_hybrid_search(user_text)
        cot_info = getattr(results, 'cot_metadata', {})
        sql_display = cot_info.get('sql_query') or f"SELECT p.id, p.name, p.product_type FROM products p LIMIT {len(results)};"
        thought_steps = cot_info.get('thought_process', [])
        suy_luan = cot_info.get('suy_luan', '')

        # Định dạng chuỗi suy luận Chain-of-Thought (CoT)
        cot_display_lines = []
        if thought_steps:
            for step in thought_steps:
                # Làm nổi bật tên bước (Thought 1, Thought 2, ...)
                step_formatted = re.sub(r'^(Thought\s*\d+\s*(\([^)]+\))?\s*:?)\s*', r'**\1** ', step)
                cot_display_lines.append(f"• {step_formatted}")
        elif suy_luan:
            cot_display_lines.append(f"• **Suy luận CoT:** {suy_luan}")

        cot_header = "🧠 **Chuỗi suy luận Chain-of-Thought (CoT):**\n" + "\n".join(cot_display_lines) if cot_display_lines else ""

        if not results:
            category = cot_info.get('predicted_categories', ['thời trang'])
            color = cot_info.get('color', '')
            size = cot_info.get('size', '')
            ai_msg = (
                f"{cot_header}\n\n"
                f"⚠️ **Kết quả:** Rất tiếc, kho hàng H&M hiện chưa có sản phẩm nào thỏa mãn toàn bộ tiêu chí cho yêu cầu *'{user_text}'*. "
                f"Bạn có thể thử tìm kiếm với màu sắc hoặc danh mục mở rộng hơn nhé!"
            )
            return {
                "user_query": user_text,
                "model_used": "auto-cot",
                "search_method": "Graph-CoT & Hybrid SQL",
                "ai_response": ai_msg,
                "sql_query": sql_display,
                "products_data": []
            }
            
        matched_products = []
        for item in results:
            article_id = str(getattr(item, 'article_id', item.product_id)).zfill(10)
            sub_folder = article_id[:3]
            raw_score = getattr(item, 'match_score', 1.0)
            score_percent = round(raw_score * 100) if raw_score <= 1.0 else round(raw_score)
            reason = getattr(item, 'match_reason', 'Sản phẩm tương đồng')
            
            matched_products.append({
                "id": str(item.product_id),
                "name": item.name,
                "product_type": item.product_type,
                "product_group": getattr(item, "product_group", "") or "Thời trang H&M",
                "department": item.department,
                "gender_group": getattr(item, "gender_group", "") or "H&M Collection",
                "pattern": getattr(item, "pattern", "") or "Solid",
                "detail_desc": item.detail_desc,
                "color": item.color,
                "size": item.size,
                "stock_quantity": item.stock_quantity,
                "variant_id": item.variant_id,
                "article_id": article_id,
                "available_colors": item.available_colors,
                "available_sizes": item.available_sizes,
                "color_images": getattr(item, "color_images", {}),
                "color_details": getattr(item, "color_details", {}),
                "original_price": round(item.price, 2),
                "discount_percent": 0,
                "rating": 5.0,
                "reviews_count": 99,
                "category": item.product_type,
                "match_score": score_percent,
                "match_reason": reason,
                "image_url": f"http://localhost:8080/images/{sub_folder}/{article_id}.jpg"
            })
            
        exact_matches = [p for p in matched_products if p.get('match_score', 0) >= 90]
        related_matches = [p for p in matched_products if p.get('match_score', 0) < 90]
        top_item = matched_products[0]
        
        color_out_of_stock = cot_info.get('color_out_of_stock', False)
        target_color = cot_info.get('color')
        primary_cat = cot_info.get('intent', {}).get('category') or (cot_info.get('predicted_categories', [None])[0])
        
        if color_out_of_stock and target_color and primary_cat:
            all_avail = []
            for p in matched_products:
                all_avail.extend(p.get('available_colors', []))
            avail_unique = list(dict.fromkeys(all_avail))[:4]
            summary_msg = (
                f"🎯 **Kết quả:** Đã tìm thấy **{len(matched_products)}** mẫu **{primary_cat}** trong kho hàng H&M.\n\n"
                f"⚠️ **Thông báo màu sắc:** Màu **{target_color}** hiện tạm hết hàng cho danh mục **{primary_cat}**. "
                f"Hệ thống đã ưu tiên hiển thị các mẫu **{primary_cat}** sẵn có với các màu sắc đa dạng (*{', '.join(avail_unique)}*) bên dưới để bạn tiện tham khảo!"
            )
        else:
            summary_msg = (
                f"🎯 **Kết quả:** Đã tìm thấy **{len(matched_products)}** sản phẩm phù hợp trong CSDL H&M "
                f"({len(exact_matches)} mẫu chuẩn xác tiêu chí & {len(related_matches)} mẫu gợi ý tương đồng)!\n\n"
                f"🌟 Sản phẩm nổi bật nhất: **{top_item['name']}** ({top_item['match_score']}% khớp)."
            )

        full_ai_response = f"{cot_header}\n\n{summary_msg}" if cot_header else summary_msg

        return {
            "user_query": user_text,
            "model_used": "auto-cot",
            "search_method": "Graph-CoT & Hybrid SQL",
            "ai_response": full_ai_response,
            "sql_query": sql_display,
            "products_data": matched_products
        }
        
    except Exception as e:
        print(f"Lỗi API Chat: {e}")
        # Trả về cấu trúc an toàn để giao diện Vue.js không bị sập (Crash)
        return {
            "user_query": user_text,
            "model_used": "auto-cot", # ĐÃ SỬA THÀNH auto-cot
            "search_method": "Error",
            "ai_response": "⚠️ Hệ thống AI đang bận xử lý hoặc gặp sự cố tạm thời. Vui lòng thử lại sau!",
            "sql_query": "ERROR",
            "products_data": []
        }

# ==========================================
# KHỞI CHẠY SERVER
# ==========================================
if __name__ == "__main__":
    import uvicorn
    # Chạy uvicorn trực tiếp từ file main.py ở cổng 8080
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)