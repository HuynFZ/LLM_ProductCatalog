import os
import requests
import json
import re

# Hỗ trợ cả chạy cục bộ và chạy bên trong Docker container
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

# Toàn bộ 62 danh mục sản phẩm chính xác có trong CSDL H&M
ALL_HM_CATEGORIES = [
    'Alice band', 'Bag', 'Ballerinas', 'Belt', 'Bikini top', 'Blazer', 'Blouse', 'Bodysuit', 
    'Boots', 'Bra', 'Bracelet', 'Cap/peaked', 'Cardigan', 'Coat', 'Costumes', 'Dress', 
    'Earring', 'Felt hat', 'Gloves', 'Hair clip', 'Hair string', 'Hair/alice band', 
    'Hat/beanie', 'Hat/brim', 'Hoodie', 'Jacket', 'Jumpsuit/Playsuit', 'Kids Underwear top', 
    'Leggings/Tights', 'Necklace', 'Night gown', 'Other accessories', 'Other shoe', 
    'Outdoor overall', 'Polo shirt', 'Pyjama bottom', 'Pyjama jumpsuit/playsuit', 
    'Pyjama set', 'Robe', 'Sandals', 'Scarf', 'Shirt', 'Shorts', 'Skirt', 'Sleep Bag', 
    'Slippers', 'Sneakers', 'Socks', 'Straw hat', 'Sunglasses', 'Sweater', 'Swimsuit', 
    'Swimwear bottom', 'T-shirt', 'Tailored Waistcoat', 'Tie', 'Top', 'Trousers', 
    'Umbrella', 'Underwear Tights', 'Underwear bottom', 'Vest top'
]

# Bộ từ điển ánh xạ từ khóa tiếng Việt / tiếng Anh -> Danh mục chuẩn H&M
CATEGORY_SYNONYMS = {
    # Phụ kiện & Găng tay & Mũ
    "găng tay": "Gloves", "bao tay": "Gloves", "glove": "Gloves", "gloves": "Gloves",
    "mũ len": "Hat/beanie", "nón len": "Hat/beanie", "beanie": "Hat/beanie",
    "mũ lưỡi trai": "Cap/peaked", "nón kết": "Cap/peaked", "cap": "Cap/peaked",
    "mũ cói": "Straw hat", "nón cói": "Straw hat",
    "mũ": "Hat/beanie", "nón": "Hat/beanie",
    "khăn": "Scarf", "khăn choàng": "Scarf", "khăn quàng": "Scarf", "scarf": "Scarf",
    "thắt lưng": "Belt", "dây nịt": "Belt", "belt": "Belt",
    "túi": "Bag", "túi xách": "Bag", "balo": "Bag", "ví": "Bag", "bag": "Bag",
    "kính": "Sunglasses", "kính râm": "Sunglasses", "kính mát": "Sunglasses", "sunglasses": "Sunglasses",
    "ô": "Umbrella", "dù": "Umbrella", "umbrella": "Umbrella",
    "cà vạt": "Tie", "tie": "Tie",
    "tất": "Socks", "vớ": "Socks", "socks": "Socks", "sock": "Socks",
    "vòng cổ": "Necklace", "dây chuyền": "Necklace",
    "khuyên tai": "Earring", "bông tai": "Earring",
    "vòng tay": "Bracelet", "lắc tay": "Bracelet",
    "kẹp tóc": "Hair clip", "dây buộc tóc": "Hair string", "băng đô": "Alice band",

    # Áo
    "áo thun": "T-shirt", "áo phông": "T-shirt", "t-shirt": "T-shirt", "tshirt": "T-shirt", "tee": "T-shirt",
    "áo sơ mi": "Shirt", "sơ mi": "Shirt", "shirt": "Shirt",
    "áo polo": "Polo shirt", "polo": "Polo shirt",
    "áo khoác": "Jacket", "jacket": "Jacket",
    "áo khoác len": "Cardigan", "cardigan": "Cardigan",
    "áo blazer": "Blazer", "blazer": "Blazer", "áo vest": "Blazer",
    "áo măng tô": "Coat", "áo khoác dạ": "Coat", "coat": "Coat",
    "áo len": "Sweater", "áo dệt kim": "Sweater", "sweater": "Sweater", "knitwear": "Sweater",
    "áo hoodie": "Hoodie", "hoodie": "Hoodie", "áo nỉ": "Hoodie",
    "áo 2 dây": "Vest top", "áo hai dây": "Vest top", "áo sát nách": "Vest top", "áo ba lỗ": "Vest top", "vest top": "Vest top", "tank top": "Vest top",
    "áo blouse": "Blouse", "blouse": "Blouse", "áo kiểu": "Blouse",
    "áo gile": "Tailored Waistcoat", "gile": "Tailored Waistcoat",
    "áo": "Top", "top": "Top",

    # Quần & Váy
    "váy": "Dress", "đầm": "Dress", "dress": "Dress",
    "chân váy": "Skirt", "skirt": "Skirt",
    "quần dài": "Trousers", "quần jeans": "Trousers", "quần jean": "Trousers", "quần tây": "Trousers", "quần suông": "Trousers", "quần kaki": "Trousers", "trousers": "Trousers", "pants": "Trousers", "jeans": "Trousers",
    "quần đùi": "Shorts", "quần soóc": "Shorts", "quần short": "Shorts", "shorts": "Shorts", "short": "Shorts",
    "quần tất": "Underwear Tights", "quần bó": "Leggings/Tights", "quần legging": "Leggings/Tights", "leggings": "Leggings/Tights",
    "quần": "Trousers",

    # Đồ lót & Đồ bơi
    "áo lót": "Bra", "áo ngực": "Bra", "bra": "Bra",
    "quần lót": "Underwear bottom", "quần sịp": "Underwear bottom", "quần chip": "Underwear bottom", "sịp": "Underwear bottom",
    "bikini": "Bikini top", "đồ bơi": "Swimsuit", "áo tắm": "Swimsuit", "quần bơi": "Swimwear bottom",

    # Giày dép
    "giày sneaker": "Sneakers", "giày thể thao": "Sneakers", "sneaker": "Sneakers", "sneakers": "Sneakers",
    "giày bốt": "Boots", "bốt": "Boots", "boots": "Boots", "boot": "Boots",
    "giày cao gót": "Other shoe", "giày búp bê": "Ballerinas",
    "xăng đan": "Sandals", "sandal": "Sandals", "sandals": "Sandals", "dép quai hậu": "Sandals",
    "dép": "Slippers", "dép lê": "Slippers", "slippers": "Slippers",
    "giày": "Sneakers",

    # Trẻ em & Đồ ngủ
    "bodysuit": "Bodysuit", "đồ liền thân": "Bodysuit", "romper": "Bodysuit",
    "bộ đồ ngủ": "Pyjama set", "đồ ngủ": "Pyjama set", "pyjama": "Pyjama set", "pajamas": "Pyjama set",
    "váy ngủ": "Night gown", "áo choàng ngủ": "Robe", "áo choàng": "Robe"
}

# Các nhóm danh mục liên quan gần gũi (Related Taxonomy Links)
RELATED_CATEGORIES_MAP = {
    "T-shirt": ["Top", "Shirt", "Polo shirt"],
    "Shirt": ["T-shirt", "Blouse", "Top"],
    "Top": ["T-shirt", "Vest top", "Blouse"],
    "Vest top": ["Top", "T-shirt"],
    "Sweater": ["Cardigan", "Hoodie", "Top"],
    "Cardigan": ["Sweater", "Jacket"],
    "Hoodie": ["Sweater", "Jacket"],
    "Jacket": ["Coat", "Blazer", "Hoodie"],
    "Blazer": ["Jacket", "Shirt", "Tailored Waistcoat"],
    "Coat": ["Jacket"],
    "Dress": ["Skirt"],
    "Skirt": ["Dress"],
    "Trousers": ["Shorts", "Leggings/Tights"],
    "Shorts": ["Trousers"],
    "Bra": ["Underwear bottom", "Bikini top"],
    "Underwear bottom": ["Bra"],
    "Bikini top": ["Swimsuit", "Swimwear bottom"],
    "Swimsuit": ["Bikini top", "Swimwear bottom"],
    "Swimwear bottom": ["Bikini top", "Swimsuit"],
    "Sneakers": ["Boots", "Sandals", "Other shoe"],
    "Boots": ["Sneakers", "Other shoe"],
    "Gloves": ["Other accessories", "Scarf", "Hat/beanie"],
    "Hat/beanie": ["Cap/peaked", "Scarf", "Other accessories"],
    "Cap/peaked": ["Hat/beanie", "Straw hat"],
    "Bag": ["Belt", "Other accessories"],
    "Socks": ["Underwear Tights", "Leggings/Tights"]
}

COMMON_RULES = """Lưu ý đặc thù của hệ thống phân loại H&M:
- Áo sơ mi phải map vào "Shirt" (tuyệt đối KHÔNG chọn "T-shirt").
- Áo thun, áo phông cộc tay phải map vào "T-shirt".
- Găng tay, bao tay phải map vào "Gloves".
- Áo lót, áo ngực, bra phải map vào "Bra".
- Áo 2 dây, áo sát nách, áo ba lỗ phải map vào "Vest top".
- Quần tất nữ phải map vào "Underwear Tights" hoặc "Leggings/Tights".
- Đồ liền thân của sơ sinh/em bé phải map vào "Bodysuit".
- Áo tắm bơi bikini 2 mảnh map vào "Bikini top", áo tắm 1 mảnh map vào "Swimsuit".
- Quần lót, quần sịp nam/nữ map vào "Underwear bottom".
- Váy liền thân, đầm dài map vào "Dress". Còn chân váy (váy rời) map vào "Skirt".
- Áo len, áo dệt kim chui đầu map vào "Sweater".
- Áo nỉ có mũ map vào "Hoodie".
- Quần dài các loại (jeans, kaki, tây, suông) map vào "Trousers".
- Quần đùi, soóc map vào "Shorts".
- Giày thể thao map vào "Sneakers", giày bốt map vào "Boots"."""

# ==============================================================================
# HÀM BÓC TÁCH RULE-BASED THÔNG MINH CHO H&M
# ==============================================================================
def rule_based_cot_fallback(user_query: str, available_categories: list) -> dict:
    q = user_query.lower()
    
    # 1. Phát hiện đối tượng / giới tính
    gender = None
    if any(w in q for w in ["nam", "men", "boy", "con trai", "đàn ông"]):
        gender = "Mens"
    elif any(w in q for w in ["nữ", "women", "girl", "con gái", "phụ nữ", "bà", "cô", "nàng"]):
        gender = "Ladies"
    elif any(w in q for w in ["bé", "trẻ em", "em bé", "baby", "kid", "sơ sinh", "con nít"]):
        gender = "Kids"

    # 2. Phát hiện danh mục sản phẩm qua bộ từ điển đồng nghĩa (Ưu tiên từ dài trước)
    category = None
    sorted_synonyms = sorted(CATEGORY_SYNONYMS.keys(), key=lambda x: len(x), reverse=True)
    for syn in sorted_synonyms:
        if re.search(r'\b' + re.escape(syn) + r'\b', q):
            category = CATEGORY_SYNONYMS[syn]
            break

    related = RELATED_CATEGORIES_MAP.get(category, []) if category else []

    # 3. Phát hiện màu sắc
    color = None
    color_map = {
        "đen": "Black", "black": "Black",
        "trắng": "White", "white": "White",
        "be": "Beige", "kem": "Light Beige", "beige": "Beige",
        "xám": "Grey", "ghi": "Grey", "grey": "Grey", "gray": "Grey",
        "xanh dương": "Blue", "xanh lam": "Dark Blue", "xanh navy": "Dark Blue", "navy": "Dark Blue", "blue": "Blue",
        "xanh lá": "Green", "green": "Green",
        "đỏ": "Dark Red", "red": "Dark Red",
        "hồng": "Pink", "pink": "Pink",
        "vàng": "Yellow", "yellow": "Yellow",
        "nâu": "Brown", "brown": "Brown",
        "cam": "Light Orange", "orange": "Light Orange"
    }
    for vn_col, en_col in color_map.items():
        if re.search(r'\b' + re.escape(vn_col) + r'\b', q):
            color = en_col
            break

    # 4. Phát hiện size
    size = None
    size_match = re.search(r'\b(size\s*)?(xxl|xl|l|m|s|xs|xxs)\b', q)
    if size_match:
        size = size_match.group(2).upper()
    else:
        num_size = re.search(r'\b(size\s*)?(3[6-9]|4[0-4])\b', q)
        if num_size:
            size = num_size.group(2)

    # 5. Phát hiện giá tối đa
    max_price = None
    price_match = re.search(r'(dưới|tầm|khoảng|giá\s*rẻ\s*hơn|<|<=)\s*(\d+(\.\d+)?)', q)
    if price_match:
        try:
            val = float(price_match.group(2))
            if val > 1000:
                val = val / 1000.0  # Ví dụ 50k -> 50
            max_price = val
        except Exception:
            pass

    thought_steps = [
        f"Thought 1 (Phân tích ý định): Khách hàng tìm kiếm '{user_query}'{' cho ' + gender if gender else ''}.",
        f"Thought 2 (Ánh xạ đồ thị danh mục): Xác định loại sản phẩm là '{category or 'Không xác định'}' (Danh mục liên quan: {related}).",
        f"Thought 3 (Trích xuất thuộc tính): Màu sắc='{color or 'Bất kỳ'}', Size='{size or 'Tự do'}', Giá tối đa={f'${max_price}' if max_price else 'Không giới hạn'}.",
        f"Thought 4 (Chiến lược CSDL): Lập truy vấn SQL trên bảng products và product_variants lọc theo '{category}'."
    ]

    return {
        "thought_process": thought_steps,
        "suy_luan": f"Khách hàng tìm kiếm {category or 'thời trang'}{' cho ' + gender if gender else ''}, màu {color or 'bất kỳ'}.",
        "category": category,
        "related_categories": related,
        "gender": gender,
        "color": color,
        "size": size,
        "max_price": max_price
    }

# ==============================================================================
# HÀM CHÍNH: GRAPH CHAIN-OF-THOUGHT (GRAPH-COT) CHO E-COMMERCE H&M
# ==============================================================================
# HÀM CHÍNH: GRAPH CHAIN-OF-THOUGHT (GRAPH-COT) CHO E-COMMERCE H&M
# ==============================================================================
def cot_unified_search_intent(user_query: str, db_categories: list = None, available_categories: list = None) -> dict:
    """
    Chuỗi suy luận Chain-of-Thought (Graph-CoT):
    1. Thought 1 (Ý định): Dịch ngữ nghĩa sang thuật ngữ thời trang quốc tế.
    2. Thought 2 (Đồ thị danh mục H&M): Ánh xạ vào product_type của CSDL H&M và các danh mục liên quan.
    3. Thought 3 (Thuộc tính & Ràng buộc): Bóc tách màu sắc, size, đối tượng (giới tính), mức giá.
    4. Thought 4 (Chiến lược truy vấn): Lập bộ lọc tối ưu cho Hybrid SQL.
    """
    cats = db_categories or available_categories or ALL_HM_CATEGORIES
    fallback = rule_based_cot_fallback(user_query, cats)

    # Lấy các thực thể nền tảng để định hướng LLM tránh ảo giác (Ground Truth Guidance)
    hint_cat = fallback.get("category")
    hint_col = fallback.get("color")
    hint_gen = fallback.get("gender")
    hint_sz = fallback.get("size")
    hint_price = fallback.get("max_price")

    # Gom nhóm danh mục rút gọn để LLM 3B dễ xử lý nhất
    grouped_categories_hint = (
        "Quần áo: T-shirt, Shirt, Dress, Skirt, Trousers, Shorts, Sweater, Hoodie, Jacket, Blazer, Coat, Vest top, Top\n"
        "Đồ lót & Đồ bơi: Bra, Underwear bottom, Bikini top, Swimsuit, Leggings/Tights\n"
        "Giày dép & Phụ kiện: Sneakers, Boots, Sandals, Gloves, Bag, Belt, Scarf, Socks, Hat/beanie, Cap/peaked, Sunglasses"
    )

    detected_hints_str = (
        f"- Danh mục phát hiện: {hint_cat if hint_cat else 'Chưa rõ'}\n"
        f"- Màu sắc phát hiện: {hint_col if hint_col else 'Không có'}\n"
        f"- Giới tính phát hiện: {hint_gen if hint_gen else 'Không giới hạn'}\n"
        f"- Kích cỡ: {hint_sz if hint_sz else 'Không giới hạn'}\n"
        f"- Giá tối đa: {f'${hint_price}' if hint_price else 'Không giới hạn'}"
    )

    prompt = f"""Bạn là trợ lý AI chuyên gia phân loại tìm kiếm thời trang H&M theo phương pháp Chain-of-Thought (Graph-CoT).
Khách hàng đang tìm kiếm: "{user_query}"

Thông tin từ khóa đã phát hiện từ yêu cầu:
{detected_hints_str}

Các nhóm danh mục chính trong kho hàng H&M (product_type):
{grouped_categories_hint}

{COMMON_RULES}

Nhiệm vụ: Phân tích yêu cầu và trả về DUY NHẤT một chuỗi JSON hợp lệ.
Mẫu JSON bắt buộc (toàn bộ diễn giải trong thought_process và suy_luan viết bằng TIẾNG VIỆT):
{{
  "thought_process": [
    "Thought 1: Phân tích ngữ nghĩa yêu cầu khách hàng sang thuật ngữ thời trang quốc tế.",
    "Thought 2: Xác định danh mục H&M chính xác (ví dụ: {hint_cat or 'T-shirt/Shirt/Dress/Gloves/Bra/Sneakers'}).",
    "Thought 3: Trích xuất màu sắc ('{hint_col or 'White/Black...'}'), size, giới tính ('{hint_gen or 'Mens/Ladies/Kids'}'), giá tối đa dạng số.",
    "Thought 4: Lập chiến lược truy vấn CSDL lọc danh mục và thuộc tính."
  ],
  "suy_luan": "1 câu tóm tắt logic ngắn gọn bằng tiếng Việt",
  "category": "{hint_cat or 'Tên danh mục hoặc null'}",
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
            "temperature": 0.0
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=20)
        response.raise_for_status()
        raw_content = response.json().get("response", "{}")
        
        # Parse JSON từ response của Ollama
        data = {}
        try:
            data = json.loads(raw_content)
        except Exception:
            # Tìm khối JSON đầu tiên bằng regex nếu model sinh thêm text
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

        # 1. Trích xuất danh mục
        category = clean_val(data.get("category"))
        
        # Nếu LLM không chọn đúng danh mục chuẩn, quét từ thought_process
        raw_thoughts_text = " ".join([str(t) for t in data.get("thought_process", [])])
        if not category or category not in cats:
            for cat_candidate in cats:
                pattern = r'\b' + re.escape(cat_candidate) + r'\b'
                if re.search(pattern, raw_thoughts_text, re.IGNORECASE):
                    category = cat_candidate
                    break

        # Nếu quy tắc phát hiện danh mục cụ thể (như Gloves, Shirt, T-shirt, Bra), luôn ưu tiên quy tắc để tránh ảo giác
        if fallback.get("category"):
            category = fallback.get("category")
        elif not category:
            category = fallback.get("category")

        # 2. Trích xuất giới tính, màu, size, giá với độ an toàn cao nhất
        gender = clean_val(data.get("gender")) or fallback.get("gender")
        color = clean_val(data.get("color")) or fallback.get("color")
        # Luôn đảm bảo nếu người dùng có nói từ khóa màu rõ ràng thì bắt buộc phải có màu
        if fallback.get("color"):
            color = fallback.get("color")
        if fallback.get("gender"):
            gender = fallback.get("gender")

        size = clean_val(data.get("size")) or fallback.get("size")
        max_price = clean_float(data.get("max_price"))
        if max_price is None:
            max_price = fallback.get("max_price")

        # 3. Lấy danh mục liên quan
        related = RELATED_CATEGORIES_MAP.get(category, []) if category else []

        # 4. Trích xuất chuỗi suy luận
        raw_thoughts = data.get("thought_process", [])
        thought_process = []
        if isinstance(raw_thoughts, list):
            for t in raw_thoughts:
                if isinstance(t, str) and len(t.strip()) > 5:
                    thought_process.append(t.strip())

        # Nếu thought_process bị thiếu hoặc mâu thuẫn (như nói không có màu dù màu tồn tại), dùng chuẩn hóa CoT 4 bước
        has_color_conflict = color and any("không có" in t.lower() and "màu" in t.lower() for t in thought_process)
        if len(thought_process) < 3 or has_color_conflict:
            thought_process = [
                f"Thought 1: Khách hàng đang tìm kiếm '{user_query}'{' dành cho ' + gender if gender else ''}.",
                f"Thought 2: Đối chiếu với danh mục H&M, yêu cầu được ánh xạ chính xác vào danh mục '{category or 'Thời trang'}'.",
                f"Thought 3: Trích xuất thuộc tính: Màu sắc = '{color or 'Tự do'}', Giới tính = '{gender or 'Tất cả'}', Size = '{size or 'Tự do'}', Mức giá = {f'${max_price}' if max_price else 'Không giới hạn'}.",
                f"Thought 4: Lập chiến lược CSDL: Tìm các sản phẩm thuộc danh mục '{category}' và lọc biến thể có màu '{color or 'bất kỳ'}'."
            ]

        suy_luan = clean_val(data.get("suy_luan"))
        if not suy_luan or has_color_conflict:
            suy_luan = f"Tìm kiếm sản phẩm {category or 'thời trang'}{' cho ' + gender if gender else ''}, màu {color or 'bất kỳ'}."

        return {
            "thought_process": thought_process,
            "suy_luan": suy_luan,
            "category": category,
            "related_categories": related,
            "gender": gender,
            "color": color,
            "size": size,
            "max_price": max_price
        }

    except Exception as e:
        print(f"⚠️ Unified CoT Router gặp sự cố ({e}), áp dụng Rule-based CoT fallback...")
        return fallback

# ==============================================================================
# CÁC HÀM CŨ ĐƯỢC GIỮ LẠI (Tương thích ngược)
# ==============================================================================
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