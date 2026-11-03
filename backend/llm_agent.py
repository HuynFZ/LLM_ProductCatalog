import os
import sys
import requests
import json
import re

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình Ollama LLM
_raw_ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_URL = _raw_ollama_url.replace("localhost", "127.0.0.1") if "localhost" in _raw_ollama_url else _raw_ollama_url
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

# ==============================================================================
# HÀM BÓC TÁCH THUỘC TÍNH CƠ BẢN (FALLBACK)
# ==============================================================================
def rule_based_cot_fallback(user_query: str, *args, **kwargs) -> dict:
    """Bóc tách thuộc tính tự nhiên (Màu sắc, Giới tính, Size, Giá) không cần danh mục cứng"""
    q = user_query.lower()
    
    # 1. Phát hiện đối tượng / giới tính
    gender = None
    if any(w in q for w in ["nam", "men", "boy", "con trai", "đàn ông"]):
        gender = "Mens"
    elif any(w in q for w in ["nữ", "women", "girl", "con gái", "phụ nữ", "bà", "cô", "nàng"]):
        gender = "Ladies"
    elif any(w in q for w in ["bé", "trẻ em", "em bé", "baby", "kid", "sơ sinh", "con nít"]):
        gender = "Kids"

    # 2. Phát hiện màu sắc thông dụng
    color = None
    color_map = {
        "đen": "Black", "black": "Black",
        "trắng": "White", "white": "White",
        "be": "Beige", "kem": "Light Beige", "beige": "Beige",
        "xám": "Grey", "ghi": "Grey", "grey": "Grey", "gray": "Grey",
        "xanh biển": "Blue", "xanh nước biển": "Blue", "xanh da trời": "Light Blue", "xanh ngọc": "Light Turquoise",
        "xanh dương": "Blue", "xanh lam": "Dark Blue", "xanh navy": "Dark Blue", "navy": "Dark Blue", "blue": "Blue",
        "xanh lá": "Green", "green": "Green",
        "đỏ đô": "Dark Red", "đỏ thẫm": "Dark Red", "đỏ đậm": "Dark Red",
        "đỏ tươi": "Red", "đỏ": "Red", "red": "Red",
        "hồng": "Pink", "pink": "Pink",
        "vàng": "Yellow", "yellow": "Yellow",
        "nâu": "Brown", "brown": "Brown",
        "cam": "Light Orange", "orange": "Light Orange"
    }
    for vn_col, en_col in color_map.items():
        if re.search(r'\b' + re.escape(vn_col) + r'\b', q):
            color = en_col
            break

    # 3. Phát hiện size
    size = None
    size_match = re.search(r'\b(size\s*)?(xxl|xl|l|m|s|xs|xxs)\b', q)
    if size_match:
        size = size_match.group(2).upper()
    else:
        num_size = re.search(r'\b(size\s*)?(3[6-9]|4[0-4])\b', q)
        if num_size:
            size = num_size.group(2)

    # 4. Phát hiện giá tối đa
    max_price = None
    price_match = re.search(r'(dưới|tầm|khoảng|giá\s*rẻ\s*hơn|tối\s*đa|nhỏ\s*hơn|<|<=)\s*(\d+(\.\d+)?)', q)
    if price_match:
        try:
            val = float(price_match.group(2))
            if val > 1000:
                val = val / 1000.0
            max_price = val
        except Exception:
            pass

    thought_steps = [
        f"Thought 1: Khách hàng đang tìm kiếm: '{user_query}'{' dành cho ' + gender if gender else ''}.",
        f"Thought 2: Yêu cầu tìm kiếm tự do theo ngữ cảnh/phong cách, kích hoạt truy vấn ngữ nghĩa Vector Search.",
        f"Thought 3: Trích xuất thuộc tính: Màu sắc = '{color or 'Tự do'}', Giới tính = '{gender or 'Tất cả'}', Size = '{size or 'Tự do'}', Giá tối đa = {f'${max_price}' if max_price else 'Không giới hạn'}.",
        f"Thought 4: Lập chiến lược CSDL: Tìm kiếm tương đồng vector trên Qdrant kết hợp lọc thuộc tính màu '{color or 'bất kỳ'}'."
    ]

    return {
        "thought_process": thought_steps,
        "suy_luan": f"Tìm kiếm sản phẩm theo ngữ nghĩa cho yêu cầu '{user_query}', màu {color or 'bất kỳ'}.",
        "semantic_query": user_query,
        "category": None,
        "related_categories": [],
        "gender": gender,
        "color": color,
        "size": size,
        "max_price": max_price
    }

# ==============================================================================
# HÀM CHÍNH: GRAPH CHAIN-OF-THOUGHT (GRAPH-COT) VỚI OLLAMA (KHÔNG PHỤ THUỘC DANH MỤC CỨNG)
# ==============================================================================
def cot_unified_search_intent(user_query: str, *args, **kwargs) -> dict:
    """
    Suy luận đa tầng Chain-of-Thought (Graph-CoT):
    - Tự do phân tích phong cách, ngữ cảnh và ý định của người dùng.
    - Viết lại câu tìm kiếm thời trang tối ưu (semantic_query) phục vụ Vector Embedding.
    - Bóc tách các thuộc tính cứng: màu sắc, giới tính, size, giá tối đa.
    - Hoàn toàn KHÔNG ràng buộc vào bất kỳ danh sách danh mục cố định nào.
    """
    fallback = rule_based_cot_fallback(user_query)

    hint_col = fallback.get("color")
    hint_gen = fallback.get("gender")
    hint_sz = fallback.get("size")
    hint_price = fallback.get("max_price")

    detected_hints_str = (
        f"- Màu sắc phát hiện: {hint_col if hint_col else 'Không có'}\n"
        f"- Giới tính phát hiện: {hint_gen if hint_gen else 'Không giới hạn'}\n"
        f"- Kích cỡ: {hint_sz if hint_sz else 'Không giới hạn'}\n"
        f"- Giá tối đa: {f'${hint_price}' if hint_price else 'Không giới hạn'}"
    )

    prompt = f"""Bạn là trợ lý AI chuyên gia phân tích tìm kiếm thời trang theo phương pháp Chain-of-Thought (CoT).
Khách hàng đang tìm kiếm: "{user_query}"

Thông tin thuộc tính đã phát hiện:
{detected_hints_str}

Nhiệm vụ của bạn:
1. Phân tích ý định, phong cách, chất liệu hoặc ngữ cảnh sử dụng của khách hàng.
2. Viết lại một câu mô tả tìm kiếm thời trang quốc tế chuẩn bằng tiếng Anh (semantic_query) để đưa vào mô hình vector embedding (ví dụ: "black casual streetwear jumpsuit for women").
3. Trích xuất màu sắc (color), giới tính (gender), kích cỡ (size), và giá tối đa (max_price).
4. Lập chuỗi tư duy 4 bước (thought_process) và 1 câu tóm tắt (suy_luan) hoàn toàn bằng TIẾNG VIỆT.

Mẫu JSON BẮT BUỘC trả về (DUY NHẤT một khối JSON hợp lệ):
{{
  "thought_process": [
    "Thought 1: Phân tích nhu cầu, phong cách và ngữ cảnh của khách hàng.",
    "Thought 2: Diễn giải ý định thành cụm từ tìm kiếm ngữ nghĩa thời trang tối ưu.",
    "Thought 3: Trích xuất các thuộc tính: màu sắc, giới tính, kích cỡ, mức giá.",
    "Thought 4: Đề xuất chiến lược tìm kiếm vector trên không gian ngữ nghĩa kết hợp lọc thuộc tính."
  ],
  "suy_luan": "1 câu tóm tắt ngắn gọn bằng tiếng Việt",
  "semantic_query": "câu mô tả ngắn tiếng Anh tối ưu để tìm kiếm vector",
  "category": "loại sản phẩm chung nếu có (ví dụ: Jumpsuit, Dress, T-shirt, Shoes...) hoặc null",
  "gender": "{hint_gen or 'Mens/Ladies/Kids hoặc null'}",
  "color": "{hint_col or 'Tên màu tiếng Anh hoặc null'}",
  "size": "{hint_sz or 'Kích cỡ hoặc null'}",
  "max_price": {hint_price if hint_price is not None else 'null'}
}}"""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_predict": 600
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=40)
        response.raise_for_status()
        raw_content = response.json().get("response", "{}")

        # Parse JSON từ response của Ollama
        data = {}
        try:
            data = json.loads(raw_content)
        except Exception:
            m = re.search(r'\{.*\}', raw_content, re.DOTALL)
            if m:
                data = json.loads(m.group(0))

        def clean_val(val):
            if val is None or str(val).strip().lower() in ["null", "none", "", "n/a", "undefined"]:
                return None
            return str(val).strip()

        def clean_float(val):
            v = clean_val(val)
            if v is not None:
                try:
                    num = float(re.sub(r'[^\d.]', '', str(v)))
                    if num > 1000:
                        num = num / 1000.0
                    return num
                except Exception:
                    return None
            return None

        # 1. Trích xuất thuộc tính
        gender = clean_val(data.get("gender")) or fallback.get("gender")
        color = clean_val(data.get("color")) or fallback.get("color")
        if fallback.get("color"):
            color = fallback.get("color")
        if fallback.get("gender"):
            gender = fallback.get("gender")

        size = clean_val(data.get("size")) or fallback.get("size")
        max_price = clean_float(data.get("max_price"))
        if max_price is None:
            max_price = fallback.get("max_price")

        category = clean_val(data.get("category"))
        semantic_query = clean_val(data.get("semantic_query")) or user_query

        # 2. Trích xuất chuỗi suy luận
        raw_thoughts = data.get("thought_process", [])
        thought_process = []
        if isinstance(raw_thoughts, list):
            for t in raw_thoughts:
                if isinstance(t, str) and len(t.strip()) > 5 and not t.strip().lower().startswith("suy_luan"):
                    thought_process.append(t.strip())

        has_color_conflict = color and any("không có" in t.lower() and "màu" in t.lower() for t in thought_process)
        if len(thought_process) < 3 or has_color_conflict:
            cat_desc = f"danh mục '{category}'" if category else "yêu cầu phong cách tự do"
            thought_process = [
                f"Thought 1: Khách hàng đang tìm kiếm: '{user_query}'{' dành cho ' + gender if gender else ''}.",
                f"Thought 2: Chuyển đổi ý định sang truy vấn ngữ nghĩa thời trang: '{semantic_query}'.",
                f"Thought 3: Trích xuất thuộc tính: Màu sắc = '{color or 'Tự do'}', Giới tính = '{gender or 'Tất cả'}', Size = '{size or 'Tự do'}', Mức giá = {f'${max_price}' if max_price else 'Không giới hạn'}.",
                f"Thought 4: Lập chiến lược CSDL: Tìm kiếm tương đồng vector trên Qdrant kết hợp lọc thuộc tính màu '{color or 'bất kỳ'}'."
            ]

        suy_luan = clean_val(data.get("suy_luan"))
        if not suy_luan or has_color_conflict:
            suy_luan = f"Tìm kiếm sản phẩm theo ngữ nghĩa cho '{user_query}', màu {color or 'bất kỳ'}."

        return {
            "thought_process": thought_process,
            "suy_luan": suy_luan,
            "semantic_query": semantic_query,
            "category": category,
            "related_categories": [],
            "gender": gender,
            "color": color,
            "size": size,
            "max_price": max_price
        }

    except Exception as e:
        print(f"⚠️ CoT Router gặp sự cố ({e}), áp dụng Fallback bóc tách tự nhiên...")
        return fallback

# Tương thích ngược
def extract_attributes(user_query: str) -> dict:
    cot_res = cot_unified_search_intent(user_query)
    return {
        "color": cot_res.get("color"),
        "size": cot_res.get("size"),
        "max_price": cot_res.get("max_price"),
        "gender": cot_res.get("gender")
    }

def score_category_relevance(user_query: str, category_name: str) -> int:
    return 1

def score_categories_batch(user_query: str, categories: list) -> dict:
    return {c: 1 for c in categories}