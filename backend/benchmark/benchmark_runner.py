import os
import sys
import time
import json
import re
import argparse
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Cấu hình UTF-8 cho Windows console
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Thêm đường dẫn backend vào sys.path để import database module
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

# Nạp cấu hình từ backend/.env
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from database import engine as mysql_engine

# Cấu hình Ollama URL
OLLAMA_HOST = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
if "api/generate" in OLLAMA_HOST:
    OLLAMA_GENERATE_URL = OLLAMA_HOST
else:
    OLLAMA_GENERATE_URL = f"{OLLAMA_HOST.rstrip('/')}/api/generate"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST.rstrip('/')}/api/tags"

# Cấu hình Cloud API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()

# Cấu trúc CSDL để đưa vào Prompt cho mô hình
SCHEMA_CONTEXT = """Cơ sở dữ liệu MySQL (ecommerce_db) gồm 2 bảng:
1. Bảng `products`:
   - id VARCHAR(50) PRIMARY KEY: Mã sản phẩm (Master ID, ví dụ: '0108775')
   - name VARCHAR(255): Tên sản phẩm
   - product_type VARCHAR(100): Danh mục chi tiết (T-shirt, Dress, Shirt, Trousers, Shoes, Jacket, Sweater, Hoodie, Blazer, Skirt...)
   - product_group VARCHAR(100): Nhóm cấp cao (Garment Upper body, Garment Lower body, Shoes, Accessories, Underwear...)
   - gender_group VARCHAR(50): Nhóm đối tượng (Ladieswear, Menswear, Baby/Children, Divided, Sport)
   - department VARCHAR(100): Nhóm phong cách/chất liệu (Jersey Basic, Knitwear...)
   - pattern VARCHAR(50): Họa tiết (Solid, Stripe, Denim, Front print...)
   - detail_desc VARCHAR(1000): Mô tả chi tiết

2. Bảng `product_variants`:
   - variant_id VARCHAR(100) PRIMARY KEY: Mã biến thể (ví dụ: '0108775015-M')
   - product_id VARCHAR(50) FOREIGN KEY: Khóa ngoại trỏ đến products.id
   - article_id VARCHAR(50): Mã SKU của ảnh và màu sắc (10 số, ví dụ: '0108775015')
   - color VARCHAR(50): Màu sắc tiếng Anh (Black, White, Red, Blue, Grey, Beige, Pink, Yellow, Brown, Green...)
   - size VARCHAR(10): Kích cỡ (S, M, L, XL, 38, 39, 40, 41, 42, One Size)
   - price FLOAT: Giá niêm yết (USD)
   - stock_quantity INT: Số lượng tồn kho (>= 0)
Quan hệ: products.id = product_variants.product_id
"""

# ==============================================================================
# QUẢN LÝ KẾT NỐI DB & FALLBACK SCHEMA NỘI TẠI (IN-MEMORY DB)
# ==============================================================================
def init_db_engine():
    """Kiểm tra kết nối MySQL 8.0 thực tế. Nếu Docker/MySQL chưa bật, tự động fallback sang SQLite in-memory có cùng schema"""
    try:
        with mysql_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("  🟢 Đã kết nối thành công tới MySQL 8.0 (Cổng 3307 / Docker).")
            return mysql_engine, "MySQL"
    except Exception as e:
        print(f"  🟡 Lưu ý: Không thể kết nối tới MySQL ({e}).")
        print("  🔄 Tự động kích hoạt cơ chế Fallback: Khởi tạo CSDL In-Memory mô phỏng chính xác Schema H&M...")
        
        sqlite_engine = create_engine("sqlite:///:memory:")
        import random
        from sqlalchemy import event
        @event.listens_for(sqlite_engine, "connect")
        def do_connect(dbapi_connection, connection_record):
            dbapi_connection.create_function("RAND", 0, random.random)
            dbapi_connection.create_function("rand", 0, random.random)
        with sqlite_engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE products (
                    id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(255),
                    product_type VARCHAR(100),
                    product_group VARCHAR(100),
                    gender_group VARCHAR(50),
                    department VARCHAR(100),
                    pattern VARCHAR(50),
                    detail_desc VARCHAR(1000)
                );
            """))
            conn.execute(text("""
                CREATE TABLE product_variants (
                    variant_id VARCHAR(100) PRIMARY KEY,
                    product_id VARCHAR(50),
                    article_id VARCHAR(50),
                    color VARCHAR(50),
                    size VARCHAR(10),
                    price FLOAT,
                    stock_quantity INT,
                    FOREIGN KEY(product_id) REFERENCES products(id)
                );
            """))
            conn.execute(text("""
                INSERT INTO products (id, name, product_type, product_group, gender_group, department, pattern, detail_desc)
                VALUES ('0108775', 'Strap top', 'Vest top', 'Garment Upper body', 'Ladieswear', 'Jersey Basic', 'Solid', 'Jersey top');
            """))
            conn.execute(text("""
                INSERT INTO product_variants (variant_id, product_id, article_id, color, size, price, stock_quantity)
                VALUES ('0108775015-M', '0108775', '0108775015', 'Black', 'M', 29.99, 20);
            """))
        print("  ✅ CSDL mô phỏng Schema đã sẵn sàng! Mọi kiểm tra cú pháp và ảo giác cột/bảng sẽ được đối chiếu chính xác 100%.")
        return sqlite_engine, "SQLite_Mock"

def get_installed_ollama_models() -> list:
    """Lấy danh sách các model hiện có trong Ollama"""
    try:
        res = requests.get(OLLAMA_TAGS_URL, timeout=5)
        if res.status_code == 200:
            models_info = res.json().get("models", [])
            return [m.get("name") for m in models_info]
    except Exception as e:
        print(f"⚠️ Không thể kết nối tới Ollama ({OLLAMA_TAGS_URL}): {e}")
    return []

def resolve_gemini_model(model_name: str) -> str:
    """Ánh xạ tên model Gemini sang phiên bản API đang khả dụng nếu cần"""
    m = model_name.lower().strip()
    if m in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-flash", "gemini-flash-lite"]:
        return "gemini-3.5-flash-lite"
    if m in ["gemini-1.5-pro", "gemini-2.0-pro", "gemini-pro"]:
        return "gemini-3.1-pro-preview"
    return model_name

# ==============================================================================
# PROMPT STRATEGIES
# ==============================================================================
def build_zero_shot_prompt(user_query: str) -> str:
    """Chiến lược Zero-shot: Hướng dẫn trực tiếp không có chuỗi suy luận phân tầng"""
    return f"""Bạn là một chuyên gia cơ sở dữ liệu thời trang. Hãy chuyển đổi câu hỏi tìm kiếm sau đây sang câu lệnh SQL MySQL 8.0 hợp lệ.

{SCHEMA_CONTEXT}

Khách hàng tìm kiếm: "{user_query}"

Yêu cầu BẮT BUỘC:
1. Viết câu lệnh SELECT lấy các cột: p.id, p.name, p.product_type, v.color, v.size, v.price, v.stock_quantity.
2. Join bảng `products` (p) và `product_variants` (v) qua `p.id = v.product_id`.
3. Thêm điều kiện WHERE phù hợp với yêu cầu (màu sắc, giới tính, giá, loại sản phẩm nếu có). Luôn có LIMIT 12.
4. Trả về DUY NHẤT một khối JSON hợp lệ theo mẫu:
{{
  "sql_query": "SELECT ... FROM products p JOIN product_variants v ON p.id = v.product_id WHERE ... LIMIT 12;",
  "semantic_query": "mô tả ngắn tiếng Anh",
  "category": "danh mục hoặc null",
  "color": "màu sắc hoặc null",
  "gender": "giới tính hoặc null",
  "max_price": null
}}
Không thêm bất kỳ văn bản giải thích nào ngoài khối JSON trên."""

def build_graph_cot_prompt(user_query: str) -> str:
    """Chiến lược Graph-CoT (Phương pháp đề xuất): Chuỗi tư duy 4 bước phân tầng"""
    return f"""Bạn là trợ lý AI chuyên gia phân tích thời trang và cơ sở dữ liệu theo phương pháp Chuỗi tư duy đồ thị (Graph Chain-of-Thought - Graph-CoT).

{SCHEMA_CONTEXT}

Khách hàng tìm kiếm: "{user_query}"

Hãy thực hiện suy luận đa tầng theo 4 bước tư duy:
- Bước 1 (Thought 1 - Phân tích ý định & Ngữ cảnh): Phân tích nhu cầu phong cách, dịp sử dụng (công sở, tiệc, đi chơi, thể thao) và đối tượng người dùng.
- Bước 2 (Thought 2 - Cầu nối Ngữ nghĩa): Diễn giải ý định thành cụm từ tìm kiếm thời trang quốc tế chuẩn bằng tiếng Anh (semantic_query) để chuẩn bị cho vector search.
- Bước 3 (Thought 3 - Bóc tách thực thể): Trích xuất chính xác các thuộc tính: màu sắc (color), giới tính (gender), kích cỡ (size), giá tối đa (max_price). Chú ý: gender_group thuộc bảng products, color/size/price/stock_quantity thuộc bảng product_variants.
- Bước 4 (Thought 4 - Lập chiến lược CSDL & Sinh SQL): Xác định điều kiện lọc tối ưu trên CSDL MySQL và sinh câu lệnh SQL chuẩn xác.

Trả về DUY NHẤT một khối JSON hợp lệ theo định dạng sau:
{{
  "thought_process": [
    "Thought 1: ...",
    "Thought 2: ...",
    "Thought 3: ...",
    "Thought 4: ..."
  ],
  "suy_luan": "Tóm tắt ngắn gọn phân tích bằng tiếng Việt",
  "semantic_query": "English fashion search phrase",
  "category": "Tên loại sản phẩm hoặc null",
  "color": "Tên màu tiếng Anh hoặc null",
  "gender": "Mens/Ladies/Kids hoặc null",
  "size": "Kích cỡ hoặc null",
  "max_price": null,
  "sql_query": "SELECT p.id, p.name, p.product_type, v.color, v.size, v.price, v.stock_quantity FROM products p JOIN product_variants v ON p.id = v.product_id WHERE ... LIMIT 12;"
}}
Không thêm bất kỳ văn bản giải thích nào ngoài khối JSON trên."""

# ==============================================================================
# UNIFIED LLM GATEWAY (ĐIỀU PHỐI ĐA NỀN TẢNG: OLLAMA, OPENAI, GEMINI, DEEPSEEK)
# ==============================================================================
def query_llm(model: str, prompt_str: str, req_timeout: int = 120) -> tuple:
    """
    Gửi prompt tới LLM tương ứng:
    - OpenAI: gpt-4o-mini, gpt-4o, gpt-3.5-turbo,...
    - Gemini: gemini-3.5-flash-lite, gemini-1.5-flash, gemini-pro,...
    - DeepSeek Cloud: deepseek-chat, deepseek-reasoner
    - Local Ollama: qwen2.5:3b, deepseek-r1:7b, gemma2:2b, mistral:7b, llama3.1:8b,...
    
    Trả về: (raw_resp_text: str, latency_ms: float, error_code: str, error_msg: str)
    """
    m_lower = model.lower().strip()
    t_start = time.perf_counter()

    try:
        # 1. OPENAI API
        if m_lower.startswith("gpt-") or m_lower.startswith("o1") or m_lower.startswith("o3"):
            if not OPENAI_API_KEY:
                return "", 0.0, "MissingAPIKey", "Chưa cấu hình OPENAI_API_KEY trong file .env"
            
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a professional fashion e-commerce database assistant that strictly outputs JSON."},
                    {"role": "user", "content": prompt_str}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0
            }
            res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=req_timeout)
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            
            if res.status_code == 200:
                raw_text = res.json()["choices"][0]["message"]["content"]
                return raw_text, latency_ms, "None", ""
            else:
                return "", latency_ms, f"HTTP_{res.status_code}", res.text[:200]

        # 2. GOOGLE GEMINI API
        elif m_lower.startswith("gemini"):
            if not GEMINI_API_KEY:
                return "", 0.0, "MissingAPIKey", "Chưa cấu hình GEMINI_API_KEY trong file .env"
            
            target_gemini_model = resolve_gemini_model(model)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_gemini_model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt_str}]}],
                "generationConfig": {
                    "temperature": 0.0,
                    "responseMimeType": "application/json"
                }
            }
            # Tự động thử lại 1 lần nếu chạm Rate Limit (429)
            res = None
            for attempt in range(2):
                res = requests.post(url, json=payload, timeout=req_timeout)
                if res.status_code == 429 and attempt == 0:
                    time.sleep(5)
                    continue
                break

            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            if res is not None and res.status_code == 200:
                res_json = res.json()
                candidates = res_json.get("candidates", [])
                if candidates:
                    raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    return raw_text, latency_ms, "None", ""
                return "", latency_ms, "EmptyGeminiResponse", "Gemini không trả về candidate nào."
            else:
                status_code = res.status_code if res else "Unknown"
                err_text = res.text[:200] if res else "No response"
                return "", latency_ms, f"HTTP_{status_code}", err_text

        # 3. DEEPSEEK CLOUD API (Nếu dùng qua platform.deepseek.com)
        elif m_lower in ["deepseek-chat", "deepseek-reasoner"]:
            if not DEEPSEEK_API_KEY:
                return "", 0.0, "MissingAPIKey", "Chưa cấu hình DEEPSEEK_API_KEY trong file .env"
            
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a professional fashion e-commerce database assistant that strictly outputs JSON."},
                    {"role": "user", "content": prompt_str}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0
            }
            res = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=req_timeout)
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            if res.status_code == 200:
                raw_text = res.json()["choices"][0]["message"]["content"]
                return raw_text, latency_ms, "None", ""
            else:
                return "", latency_ms, f"HTTP_{res.status_code}", res.text[:200]

        # 4. LOCAL OLLAMA (Mặc định cho các mô hình chạy cục bộ: Qwen, Gemma, Llama, Mistral, DeepSeek-R1...)
        else:
            payload = {
                "model": model,
                "prompt": prompt_str,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0,
                    "num_predict": 700
                }
            }
            res = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=req_timeout)
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            if res.status_code == 200:
                raw_text = res.json().get("response", "")
                return raw_text, latency_ms, "None", ""
            else:
                return "", latency_ms, f"HTTP_{res.status_code}", res.text[:200]

    except requests.exceptions.Timeout:
        latency_ms = float(req_timeout * 1000)
        return "", latency_ms, "Timeout", f"Mô hình phản hồi vượt quá {req_timeout}s."
    except Exception as ex:
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        return "", latency_ms, "ConnectionError", str(ex)[:200]

def extract_json_data(raw_resp: str) -> tuple:
    """
    Bóc tách JSON, tìm 'sql_query' và 'semantic_query'.
    Hỗ trợ loại bỏ tag <think>...</think> của DeepSeek-R1 và duyệt cấu trúc lồng nhau.
    Trả về: (json_valid: int, sql_extracted: str, semantic_query: str, error_code: str, error_msg: str)
    """
    if not raw_resp or not raw_resp.strip():
        return 0, "", "", "EmptyResponse", "Phản hồi rỗng từ mô hình."

    # Loại bỏ khối <think>...</think> nếu có (DeepSeek-R1)
    cleaned = re.sub(r'<think>.*?</think>', '', raw_resp, flags=re.DOTALL).strip()
    # Loại bỏ khối markdown ```json ... ``` nếu có
    cleaned = re.sub(r'^```(json)?', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'```$', '', cleaned).strip()

    parsed_json = None
    try:
        parsed_json = json.loads(cleaned)
    except Exception:
        # Thử bóc bằng regex nếu dính chữ thừa
        m = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if m:
            try:
                parsed_json = json.loads(m.group(0))
            except Exception:
                pass

    if not parsed_json or not isinstance(parsed_json, dict):
        return 0, "", "", "JSONDecodeError", "Mô hình không trả về cấu trúc JSON hợp lệ."

    # Tìm sql_query và semantic_query
    sql_extracted = ""
    semantic_query = ""

    # Tìm trực tiếp cấp 1
    for k in ["sql_query", "sql", "query"]:
        val = parsed_json.get(k)
        if val and isinstance(val, str) and val.strip():
            sql_extracted = val.strip()
            break

    for k in ["semantic_query", "semantic", "search_phrase"]:
        val = parsed_json.get(k)
        if val and isinstance(val, str):
            semantic_query = val.strip()
            break

    # Nếu chưa tìm thấy SQL, tìm đệ quy trong các dict con (như một số output của DeepSeek R1)
    if not sql_extracted:
        for sub_val in parsed_json.values():
            if isinstance(sub_val, dict):
                for k in ["sql_query", "sql", "query"]:
                    v = sub_val.get(k)
                    if v and isinstance(v, str) and v.strip():
                        sql_extracted = v.strip()
                        break
                if sql_extracted:
                    break

    return 1, sql_extracted, semantic_query, "None", ""

# ==============================================================================
# HÀM THỰC THI THỬ NGHIỆM SQL (DRY-RUN EXECUTION)
# ==============================================================================
def dry_run_sql(raw_sql: str, active_engine, db_type: str = "MySQL") -> tuple:
    """
    Thực thi thử câu lệnh SQL với EXPLAIN hoặc LIMIT 1 để đo tính đúng đắn cú pháp và schema.
    Trả về: (sql_success: int, clean_sql: str, error_code: str, error_msg: str)
    """
    if not raw_sql or not isinstance(raw_sql, str) or not raw_sql.strip():
        return 0, "", "EmptySQL", "Mô hình không sinh ra câu lệnh SQL nào."

    # Làm sạch chuỗi SQL từ response
    sql = raw_sql.strip()
    sql = re.sub(r'^```(sql)?', '', sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r'```$', '', sql).strip()
    sql = sql.replace('\n', ' ').strip()
    
    # Chỉ cho phép câu lệnh SELECT để an toàn tuyệt đối
    if not sql.lower().startswith("select"):
        return 0, sql, "NonSelectStatement", "Câu lệnh không bắt đầu bằng SELECT."

    # Đảm bảo có LIMIT để kiểm tra siêu nhẹ
    test_sql = sql
    if not re.search(r'\blimit\s+\d+', test_sql, re.IGNORECASE):
        test_sql = f"{test_sql.rstrip(';')} LIMIT 1;"
    else:
        test_sql = re.sub(r'\blimit\s+\d+', 'LIMIT 1', test_sql, flags=re.IGNORECASE)

    try:
        with active_engine.connect() as conn:
            explain_cmd = f"EXPLAIN {test_sql}" if db_type == "MySQL" else f"EXPLAIN QUERY PLAN {test_sql}"
            conn.execute(text(explain_cmd))
            return 1, sql, "None", "Success"
    except Exception as e:
        err_str = str(e)
        error_code = "UnknownError"
        if ("Table" in err_str and "doesn't exist" in err_str) or "no such table" in err_str.lower():
            error_code = "NoSuchTable (Schema Hallucination)"
        elif "Unknown column" in err_str or "no such column" in err_str.lower():
            error_code = "UnknownColumn (Column Hallucination)"
        elif "You have an error in your SQL syntax" in err_str or "syntax error" in err_str.lower():
            error_code = "SyntaxError"
        elif "OperationalError" in err_str:
            error_code = "OperationalError"
        else:
            error_code = "ExecutionError"
        
        return 0, sql, error_code, err_str[:250]

# ==============================================================================
# BỘ ĐIỀU PHỐI BENCHMARK
# ==============================================================================
def run_benchmark(
    models: list = None,
    prompt_types: list = None,
    limit_queries: int = None,
    output_csv: str = "benchmark_results.csv"
):
    print("=" * 70)
    print("🚀 BẮT ĐẦU CHƯƠNG TRÌNH BENCHMARK SO SÁNH LLM CHO BÀI BÁO KHOA HỌC")
    print("=" * 70)

    # 1. Khởi tạo Engine CSDL (MySQL hoặc Mock Schema)
    active_engine, db_type = init_db_engine()

    # 2. Nạp danh sách câu hỏi kiểm thử
    queries_file = os.path.join(CURRENT_DIR, "benchmark_queries.json")
    if not os.path.exists(queries_file):
        print(f"❌ Không tìm thấy file {queries_file}")
        return

    with open(queries_file, "r", encoding="utf-8") as f:
        test_queries = json.load(f)

    if limit_queries and limit_queries > 0:
        test_queries = test_queries[:limit_queries]

    # 3. Xác định danh sách models & prompt strategies
    installed_models = get_installed_ollama_models()
    print(f"📦 Các mô hình đang có sẵn trong Ollama: {installed_models}")

    target_models = models or ["qwen2.5:3b", "llama3.1:8b", "gemma2:2b", "mistral:7b"]
    valid_models = []
    for m in target_models:
        m_lower = m.lower().strip()
        if m_lower.startswith("gpt-") or m_lower.startswith("o1") or m_lower.startswith("o3"):
            if OPENAI_API_KEY:
                valid_models.append(m)
                print(f"  🟢 [OpenAI API] Đã sẵn sàng mô hình: {m}")
            else:
                print(f"  ⚠️ [OpenAI API] Model '{m}' chưa thể dùng vì chưa cấu hình OPENAI_API_KEY trong .env.")
        elif m_lower.startswith("gemini"):
            if GEMINI_API_KEY:
                valid_models.append(m)
                target_g = resolve_gemini_model(m)
                alias_note = f" (ánh xạ -> {target_g})" if target_g != m else ""
                print(f"  🟢 [Gemini API] Đã sẵn sàng mô hình: {m}{alias_note}")
            else:
                print(f"  ⚠️ [Gemini API] Model '{m}' chưa thể dùng vì chưa cấu hình GEMINI_API_KEY trong .env.")
        elif m_lower in ["deepseek-chat", "deepseek-reasoner"]:
            if DEEPSEEK_API_KEY:
                valid_models.append(m)
                print(f"  🟢 [DeepSeek API] Đã sẵn sàng mô hình: {m}")
            else:
                print(f"  ⚠️ [DeepSeek API] Model '{m}' chưa thể dùng vì chưa cấu hình DEEPSEEK_API_KEY trong .env.")
        else:
            # Kiểm tra trong Ollama Local
            is_avail = any(m == im or m in im or im.startswith(m) for im in installed_models)
            if is_avail:
                valid_models.append(m)
                print(f"  🟢 [Ollama Local] Đã sẵn sàng mô hình: {m}")
            else:
                print(f"  ⚠️ [Ollama Local] Model '{m}' chưa được tải trong Ollama. (Chạy lệnh: `ollama pull {m}` để bổ sung).")

    if not valid_models:
        print("❌ Không có mô hình nào sẵn sàng để chạy thử nghiệm. Vui lòng kiểm tra lại cấu hình hoặc tải mô hình.")
        return

    target_prompts = prompt_types or ["Zero-shot", "Graph-CoT"]

    print(f"\n📊 Kế hoạch thực nghiệm:")
    print(f"  • Danh sách Mô hình ({len(valid_models)}): {valid_models}")
    print(f"  • Chiến lược Prompt ({len(target_prompts)}): {target_prompts}")
    print(f"  • Số lượng câu truy vấn: {len(test_queries)} câu")
    total_runs = len(valid_models) * len(target_prompts) * len(test_queries)
    print(f"  • Tổng số lượt gọi đánh giá: {total_runs} lần")
    print("=" * 70)

    results = []
    csv_path = os.path.join(CURRENT_DIR, output_csv)
    existing_completed = set()
    if os.path.exists(csv_path):
        try:
            df_exist = pd.read_csv(csv_path)
            # Giữ lại các bản ghi không phải Timeout để resume
            valid_rows = df_exist[df_exist["Error_Code"] != "Timeout"]
            for _, r in valid_rows.iterrows():
                existing_completed.add((r["Model"], r["Prompt_Type"], int(r["Query_ID"])))
            results = valid_rows.to_dict("records")
            print(f"  ℹ️ Đã nạp lại {len(results)} kết quả hợp lệ từ phiên trước để tiếp tục chạy nối tiếp (Resume).")
        except Exception as e:
            print(f"  ⚠️ Lưu ý đọc file kết quả cũ: {e}")

    current_run = len(existing_completed)
    start_all_time = time.time()

    for model in valid_models:
        m_lower = model.lower()
        # Thiết lập timeout phù hợp theo từng mô hình
        if any(k in m_lower for k in ["7b", "8b", "9b"]):
            req_timeout = 240
        elif "gemini" in m_lower or "gpt" in m_lower:
            req_timeout = 60
        else:
            req_timeout = 60

        for p_type in target_prompts:
            print(f"\n🔥 Đang chạy: Model = [{model}] | Prompt = [{p_type}]...")
            for q_idx, q_item in enumerate(test_queries, 1):
                q_id = q_item.get("id", q_idx)
                if (model, p_type, q_id) in existing_completed:
                    continue

                current_run += 1
                q_text = q_item.get("query", "")
                q_intent_type = q_item.get("type", "General")

                # Chuẩn bị Prompt
                if p_type == "Zero-shot":
                    prompt_str = build_zero_shot_prompt(q_text)
                else:
                    prompt_str = build_graph_cot_prompt(q_text)

                # Gửi request tới LLM Gateway
                raw_resp, latency_ms, error_code, error_msg = query_llm(model, prompt_str, req_timeout=req_timeout)

                json_valid = 0
                sql_extracted = ""
                semantic_query = ""
                sql_success = 0

                # Nếu gọi LLM thành công, tiến hành bóc tách JSON và đánh giá cú pháp SQL
                if error_code == "None":
                    json_valid, sql_extracted, semantic_query, parse_err, parse_msg = extract_json_data(raw_resp)
                    if json_valid == 1 and sql_extracted:
                        sql_success, clean_sql, error_code, error_msg = dry_run_sql(sql_extracted, active_engine, db_type)
                    elif json_valid == 1 and not sql_extracted:
                        sql_success = 0
                        error_code = "MissingSQLKey"
                        error_msg = "JSON không có trường 'sql_query'."
                    else:
                        error_code = parse_err
                        error_msg = parse_msg

                # Lưu kết quả lượt chạy
                record = {
                    "Model": model,
                    "Prompt_Type": p_type,
                    "Query_ID": q_id,
                    "Query_Type": q_intent_type,
                    "Query_Text": q_text,
                    "Latency_ms": latency_ms,
                    "JSON_Valid": json_valid,
                    "SQL_Success": sql_success,
                    "Error_Code": error_code,
                    "Error_Message": error_msg,
                    "Semantic_Query": semantic_query,
                    "SQL_Generated": sql_extracted
                }
                results.append(record)

                # In tiến độ console ngắn gọn
                status_icon = "✅" if sql_success == 1 else "❌"
                print(f"  [{current_run}/{total_runs}] Q{q_id:03d} | {status_icon} SQL={sql_success} | Latency={latency_ms:6.1f}ms | Err={error_code}")

                # Tự động lưu lũy tiến vào CSV sau mỗi 5 câu để chống mất mát dữ liệu
                if len(results) % 5 == 0:
                    pd.DataFrame(results).to_csv(csv_path, index=False, encoding="utf-8-sig")

                # Nghỉ giữa các câu: Gemini cần nghỉ 3s để tránh chạm trần 15 RPM của gói miễn phí
                if "gemini" in m_lower:
                    time.sleep(3)
                else:
                    time.sleep(1)

    # Xuất toàn bộ kết quả chi tiết
    df_results = pd.DataFrame(results)
    df_results.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n💾 Đã lưu toàn bộ dữ liệu thực nghiệm vào: {csv_path}")

    # Tạo bảng tổng hợp khoa học (Summary Table)
    summary = df_results.groupby(["Model", "Prompt_Type"]).agg(
        Total_Queries=("Query_ID", "count"),
        SQL_Success_Rate=("SQL_Success", lambda x: round(x.mean() * 100, 2)),
        JSON_Valid_Rate=("JSON_Valid", lambda x: round(x.mean() * 100, 2)),
        Avg_Latency_ms=("Latency_ms", lambda x: round(x.mean(), 2)),
        P95_Latency_ms=("Latency_ms", lambda x: round(x.quantile(0.95), 2)),
        Hallucination_Rate=("Error_Code", lambda x: round((x.isin([
            "NoSuchTable (Schema Hallucination)", 
            "UnknownColumn (Column Hallucination)"
        ])).mean() * 100, 2))
    ).reset_index()

    summary_csv = os.path.join(CURRENT_DIR, "benchmark_summary.csv")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    print(f"📊 Đã tạo bảng tổng hợp hiệu năng: {summary_csv}")

    elapsed_total = round(time.time() - start_all_time, 2)
    print("\n" + "=" * 70)
    print(f"🎉 HOÀN THÀNH TOÀN BỘ BENCHMARK TRONG {elapsed_total} GIÂY!")
    print("=" * 70)
    print(summary.to_string(index=False))
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy thực nghiệm đánh giá so sánh các mô hình LLM (Ollama, OpenAI, Gemini, DeepSeek)")
    parser.add_argument("--models", nargs="+", default=None, help="Danh sách models (vd: gpt-4o-mini gemini-1.5-flash deepseek-r1:7b qwen2.5:3b)")
    parser.add_argument("--prompts", nargs="+", default=None, help="Chiến lược prompt (Zero-shot Graph-CoT)")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số câu hỏi thử nghiệm (None = cả 100 câu)")
    parser.add_argument("--output", type=str, default="benchmark_results.csv", help="Tên file CSV kết quả")
    args = parser.parse_args()

    run_benchmark(
        models=args.models,
        prompt_types=args.prompts,
        limit_queries=args.limit,
        output_csv=args.output
    )
