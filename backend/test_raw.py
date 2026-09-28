import sys
import json
import requests
import database
import db_models
from llm_agent import OLLAMA_URL, OLLAMA_MODEL, COMMON_RULES, cot_unified_search_intent

sys.stdout.reconfigure(encoding='utf-8')
db = database.SessionLocal()
cats = [r[0] for r in db.query(db_models.Product.product_type).filter(db_models.Product.product_type.isnot(None)).distinct().all() if r[0]]
db.close()

user_query = "tìm găng tay màu trắng"
cat_list_str = ", ".join([f'"{c}"' for c in cats])

prompt = f"""Bạn là trợ lý AI chuyên gia phân loại tìm kiếm thời trang H&M theo phương pháp Chain-of-Thought (Graph-CoT).
Khách hàng đang tìm kiếm: "{user_query}"

Danh sách DUY NHẤT các danh mục sản phẩm hiện có trong kho H&M (product_type):
[{cat_list_str}]

{COMMON_RULES}

Nhiệm vụ thực hiện từng bước suy luận Chain-of-Thought (BẮT BUỘC diễn giải toàn bộ bằng TIẾNG VIỆT):
- Thought 1: Phân tích ý định khách hàng, dịch sang thuật ngữ tiếng Anh thời trang quốc tế.
- Thought 2: Đối chiếu với danh sách kho hàng H&M để chọn danh mục chính xác nhất và 1-2 danh mục liên quan.
- Thought 3: Trích xuất các thuộc tính: màu sắc (dịch sang tiếng Anh H&M: Black, White, Grey, Blue, Dark Blue, Light Blue, Beige, Pink, Dark Red...), kích cỡ (S, M, L, XL...), đối tượng ("Mens", "Ladies", "Kids"), mức giá tối đa dạng số.
- Thought 4: Đưa ra kết luận chiến lược lọc CSDL H&M.

Định dạng JSON BẮT BUỘC trả về (Toàn bộ giá trị thought_process và suy_luan PHẢI viết bằng TIẾNG VIỆT):
{{
  "thought_process": [
    "Thought 1: <Phân tích ý định bằng tiếng Việt>",
    "Thought 2: <Ánh xạ danh mục H&M bằng tiếng Việt>",
    "Thought 3: <Trích xuất thuộc tính bằng tiếng Việt>",
    "Thought 4: <Chiến lược lọc CSDL bằng tiếng Việt>"
  ],
  "suy_luan": "<1 câu tóm tắt logic CoT ngắn gọn bằng tiếng Việt>",
  "category": "<Tên danh mục CHÍNH chọn CHÍNH XÁC từ danh sách trên, hoặc null>",
  "related_categories": ["<Tên danh mục liên quan 1>", "<Tên danh mục liên quan 2>"],
  "gender": "<'Mens' | 'Ladies' | 'Kids' hoặc null>",
  "color": "<Tên màu tiếng Anh hoặc null>",
  "size": "<Size S, M, L, XL, 38, 39... hoặc null>",
  "max_price": <giá tối đa dạng số float hoặc null>
}}"""

r = requests.post(OLLAMA_URL, json={'model': OLLAMA_MODEL, 'prompt': prompt, 'format': 'json', 'stream': False, 'temperature': 0.0}, timeout=30)
print("RAW RESPONSE:")
print(r.json().get('response'))
