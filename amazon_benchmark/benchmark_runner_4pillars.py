import os
import sys
import time
import json
import re
import argparse
import requests
import pandas as pd
import numpy as np
from tqdm.auto import tqdm
from dotenv import load_dotenv

# Cấu hình UTF-8
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Đường dẫn thư mục
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(CURRENT_DIR, "data")

# Nạp file .env từ backend hoặc root
load_dotenv(os.path.join(ROOT_DIR, "backend", ".env"))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
if "localhost" in OLLAMA_URL:
    OLLAMA_URL = OLLAMA_URL.replace("localhost", "127.0.0.1")

# Khởi tạo Gemini client an toàn
GEMINI_CLIENT = None
if GEMINI_API_KEY:
    try:
        os.environ.pop("GOOGLE_API_KEY", None)
        from google import genai
        GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Warning: Không thể khởi tạo genai.Client: {e}")

# ==============================================================================
# 1. UNIFIED LLM GATEWAY (ĐIỀU PHỐI GỌI MODEL ĐA NỀN TẢNG)
# ==============================================================================
def query_model(model_name: str, system_prompt: str, user_prompt: str, timeout: int = 60) -> tuple:
    """
    Gửi prompt tới mô hình tương ứng (Gemini, OpenAI, hoặc Ollama Local).
    Trả về: (response_text: str, latency_ms: float, error_code: str)
    """
    m_lower = model_name.lower().strip()
    t_start = time.perf_counter()

    try:
        # A. GOOGLE GEMINI API
        if m_lower.startswith("gemini"):
            global GEMINI_CLIENT
            if not GEMINI_CLIENT:
                if not GEMINI_API_KEY:
                    return "", 0.0, "Missing_Gemini_Key"
                os.environ.pop("GOOGLE_API_KEY", None)
                from google import genai
                GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
            
            from google.genai import types
            target_model = model_name
            if target_model in ["gemini-1.5-flash-lite", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-flash-lite", "gemini-flash-lite-latest"]:
                target_model = "gemini-3.5-flash-lite"
            elif target_model in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-3.5-flash"]:
                target_model = "gemini-3.5-flash"
                
            config = types.GenerateContentConfig(
                temperature=0.1,
                system_instruction=system_prompt,
                response_mime_type="application/json"
            )
            max_retries = 3
            for attempt in range(max_retries + 1):
                try:
                    # Giữ nhịp gọi API an toàn cho tài khoản Gemini Pay-as-you-go (Tier 1)
                    time.sleep(0.3)
                    res = GEMINI_CLIENT.models.generate_content(
                        model=target_model,
                        contents=user_prompt,
                        config=config
                    )
                    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
                    return res.text, latency_ms, "OK"
                except Exception as e_inner:
                    err_str = str(e_inner)
                    if ("503" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < max_retries:
                        sleep_s = 5.0 if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) else 2.0
                        time.sleep(sleep_s)
                        continue
                    raise e_inner

        # B. OPENAI GPT API
        elif m_lower.startswith("gpt-"):
            if not OPENAI_API_KEY:
                return "", 0.0, "Missing_OpenAI_Key"
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=timeout)
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            if res.status_code == 200:
                text_out = res.json()["choices"][0]["message"]["content"]
                return text_out, latency_ms, "OK"
            return "", latency_ms, f"HTTP_{res.status_code}"

        # C. LOCAL OLLAMA (Qwen, Gemma, Llama, Phi...)
        else:
            chat_url = "http://127.0.0.1:11434/api/chat"
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_predict": 750
                }
            }
            res = requests.post(chat_url, json=payload, timeout=timeout)
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            if res.status_code == 200:
                text_out = res.json().get("message", {}).get("content", "{}")
                return text_out, latency_ms, "OK"
            return "", latency_ms, f"Ollama_HTTP_{res.status_code}"

    except Exception as e:
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        return "", latency_ms, f"Exception_{str(e)[:50]}"


# ==============================================================================
# 2. XÂY DỰNG PROMPT 4 TRỤ CỘT TOÀN DIỆN (LIU ET AL. & WANG ET AL.)
# ==============================================================================
def build_4pillars_prompts(sample: dict, real_kb: dict) -> tuple:
    """
    Tạo bộ Prompt tích hợp chặt chẽ 4 Trụ Cột:
    - Trụ cột 1: Profile & Instruction (Role, Domain, Intent, Demand Constraints)
    - Trụ cột 2: Knowledge (Advanced RAG context, C_neg từ review 1-2 sao, User History)
    - Trụ cột 3: Reasoning & Planning (4-step Structured CoT: Context -> Attributes -> Pros/Cons -> Decision)
    - Trụ cột 4: Reliability (Template JSON nghiêm ngặt để chuẩn bị cho bước Verifier)
    """
    test_type = sample.get("test_type", "in_catalog_standard")
    user_query = sample.get("user_query", "")
    target_info = sample.get("ground_truth_target")
    neg_info = sample.get("negative_constraints", {})
    user_prof = sample.get("user_profile", {})

    # TRỤ CỘT 1: Profile & Instruction
    system_prompt = """Bạn là "Chuyên viên Tư vấn Thương mại Điện tử Độc lập & Khách quan" (Objective E-commerce Shopping Advisor) cho sàn thương mại điện tử chuyên ngành Làm đẹp & Mỹ phẩm (Amazon Beauty).

QUY TẮC RÀNG BUỘC NGHIÊM NGẶT (DEMAND CONSTRAINTS):
1. Phạm vi (Domain): Chỉ tư vấn các sản phẩm thuộc danh mục Làm đẹp & Mỹ phẩm có thật trong Cơ sở tri thức (Knowledge Base) của sàn.
2. Chống Ảo giác (Zero-Hallucination): Tuyệt đối KHÔNG tự ý bịa đặt tên sản phẩm, thương hiệu, thành phần, giá tiền hoặc công dụng không có trong dữ liệu được cung cấp.
3. Xử lý Yêu cầu Ngoại lai (Out-of-Catalog / Non-existent): Nếu khách hàng hỏi về các mặt hàng không thuộc ngành mỹ phẩm (như đồ điện tử, thời trang, gia dụng) hoặc hỏi về sản phẩm/thương hiệu không tồn tại trong kho, bạn BẮT BUỘC phải từ chối lịch sự, giải thích rõ sàn không kinh doanh mặt hàng này.
4. Tính Khách quan Đa chiều (Pros & Cons): Khi tư vấn sản phẩm, BẮT BUỘC phải nêu cả ưu điểm phù hợp VÀ nhược điểm/cảnh báo rủi ro (dựa trên phản hồi tiêu cực C_neg của người dùng trước) thay vì chỉ tâng bốc một chiều."""

    # TRỤ CỘT 2: Knowledge Layer (RAG Context Injection)
    kb_context_str = ""
    if test_type != "out_of_catalog_adversarial" and target_info:
        item_id = target_info.get("item_id")
        kb_item = real_kb.get(item_id, target_info)
        kb_context_str += f"""--- THÔNG TIN SẢN PHẨM TRONG KHO (KNOWLEDGE BASE) ---
• Mã SKU (ASIN): {item_id}
• Tên sản phẩm: {kb_item.get('title')}
• Thương hiệu (Brand): {kb_item.get('brand')}
• Danh mục (Category): {kb_item.get('categories')}
• Giá niêm yết: {f"${kb_item.get('price'):.2f}" if kb_item.get('price') else "Chưa cập nhật"}
• Mô tả chi tiết: {kb_item.get('description', '')[:300]}
"""
        # Bổ sung C_neg từ review 1-2 sao thật
        if neg_info.get("has_negative_constraint") and neg_info.get("c_neg_text"):
            kb_context_str += f"""• Phản hồi tiêu cực thực tế từ khách hàng cũ (C_neg): "{neg_info.get('c_neg_text')}"\n"""
        
        # Lịch sử sở thích của user (C_sim)
        if user_prof and user_prof.get("top_positive_history"):
            kb_context_str += "--- LỊCH SỬ MUA SẮM VÀ SỞ THÍCH CỦA KHÁCH HÀNG ---\n"
            for h in user_prof.get("top_positive_history", []):
                kb_context_str += f"- Từng thích: {h.get('title')} (Đánh giá: {h.get('rating')} sao)\n"
    else:
        kb_context_str = """--- THÔNG TIN SẢN PHẨM TRONG KHO (KNOWLEDGE BASE) ---
[Thông báo hệ thống: Tìm kiếm CSDL sàn trả về 0 kết quả phù hợp. Không tìm thấy sản phẩm hoặc mặt hàng này trong danh mục Mỹ phẩm của sàn.]
"""

    # TRỤ CỘT 3 & 4: Reasoning (Structured CoT) & Format Specification
    user_prompt = f"""{kb_context_str}
Khách hàng hỏi: "{user_query}"

Hãy thực hiện suy luận từng bước theo 4 bước tư duy logic (Structured CoT) và trả về DUY NHẤT một khối JSON hợp lệ theo đúng cấu trúc sau:
{{
  "thought_1_user_context": "Phân tích nhu cầu, phong cách, giới tính/loại da của khách và xác định xem yêu cầu này có hợp lệ trong sàn mỹ phẩm hay là câu hỏi ngoài ngành/hết hàng.",
  "thought_2_attribute_evaluation": "Đối chiếu thuộc tính sản phẩm với CSDL sàn. Xác định rõ sản phẩm có tồn tại và giá cả/thông số có chính xác hay không.",
  "thought_3_pros_and_cons": "Phân tích đa chiều: Nêu rõ Ưu điểm (Pros) và Nhược điểm/Cảnh báo (Cons) dựa trên phản hồi tiêu cực C_neg. Nếu là sản phẩm không có thật/ngoài kho thì ghi rõ không có dữ liệu.",
  "thought_4_decision": "Lập luận quyết định: Nên gợi ý sản phẩm này hay từ chối một cách lịch sự, giải thích logic ngắn gọn.",
  "response_to_user": "Lời thoại trực tiếp trả lời khách hàng (viết bằng tiếng Việt tự nhiên, thân thiện, khách quan, có phân tích ưu nhược điểm hoặc từ chối lịch sự nếu không có hàng).",
  "recommended_item_id": "Mã ASIN của sản phẩm gợi ý nếu có trong kho, hoặc null nếu từ chối",
  "is_out_of_catalog_rejected": true nếu đây là yêu cầu ngoài ngành/không có trong kho và bạn đã từ chối lịch sự, ngược lại false,
  "pros": ["ưu điểm 1", "ưu điểm 2"],
  "cons": ["nhược điểm 1 hoặc cảnh báo rủi ro dựa trên C_neg"]
}}"""

    return system_prompt, user_prompt


# ==============================================================================
# 3. TRỤ CỘT 4: VÒNG LẶP XÁC MINH & TỰ SỬA LỖI (STEP-AWARE SELF-CORRECTION)
# ==============================================================================
def apply_self_correction(parsed_json: dict, sample: dict, real_kb: dict, model_name: str) -> tuple:
    """
    Trụ cột 4 (Reliability): Tự kiểm tra câu trả lời trước khi xuất ra:
    - Nếu câu ngoài kho nhưng mô hình bị ảo giác (gợi ý bừa) -> Tự hiệu chỉnh.
    - Nếu có C_neg nhưng mô hình chỉ khen một chiều (bỏ quên nhược điểm) -> Nhắc mô hình bổ sung Cons.
    Trả về: (final_json: dict, triggered: bool, success: bool)
    """
    test_type = sample.get("test_type")
    neg_info = sample.get("negative_constraints", {})
    
    triggered = False
    success = False

    # 1. Phát hiện ảo giác ở các ca Out-of-Catalog (Bẫy ngoài ngành)
    if test_type == "out_of_catalog_adversarial":
        rec_id = parsed_json.get("recommended_item_id")
        is_rejected = parsed_json.get("is_out_of_catalog_rejected", False)
        
        # Nếu model tự bịa ra 1 item_id hoặc không nhận diện là hàng ngoài kho
        if (rec_id is not None and rec_id != "null") or not is_rejected:
            triggered = True
            # Tạo prompt phản hồi sửa lỗi (Critic feedback loop)
            critique_prompt = f"""CẢNH BÁO TỰ KIỂM TRA (SELF-CORRECTION):
Câu hỏi của khách hàng: "{sample.get('user_query')}" là một yêu cầu NGOÀI NGÀNH HÀNG hoặc SẢN PHẨM KHÔNG CÓ TRONG KHO.
Theo quy tắc của Trụ cột 1 & Trụ cột 4, bạn tuyệt đối KHÔNG ĐƯỢC PHÉP gợi ý sản phẩm bịa đặt.
Hãy sửa lại câu trả lời: Đặt "recommended_item_id": null, "is_out_of_catalog_rejected": true, và viết lại "response_to_user" từ chối một cách lịch sự, trung thực."""
            
            raw_fix, _, status = query_model(model_name, "Bạn là hệ thống tự sửa lỗi độ tin cậy AI (Self-Correction Verifier). Trả về JSON sửa đổi.", critique_prompt, timeout=40)
            if status == "OK":
                try:
                    m = re.search(r'\{.*\}', raw_fix, re.DOTALL)
                    if m:
                        fixed_json = json.loads(m.group(0))
                        if fixed_json.get("is_out_of_catalog_rejected") is True:
                            success = True
                            return fixed_json, triggered, success
                except Exception:
                    pass

    # 2. Phát hiện thiên lệch: Bỏ sót nhược điểm C_neg ở các ca có phản hồi xấu
    elif test_type == "in_catalog_c_neg" and neg_info.get("has_negative_constraint"):
        cons_list = parsed_json.get("cons", [])
        if not cons_list or len(cons_list) == 0:
            triggered = True
            critique_prompt = f"""CẢNH BÁO TỰ KIỂM TRA (SELF-CORRECTION):
Khách hàng đã hỏi về các lo ngại và sản phẩm này có phản hồi tiêu cực thực tế (C_neg): "{neg_info.get('c_neg_text')}".
Bạn hiện chưa nêu rõ các nhược điểm (Cons) trong câu trả lời. Hãy cập nhật lại mảng "cons" và bổ sung lời cảnh báo khách quan vào "response_to_user"."""
            
            raw_fix, _, status = query_model(model_name, "Bạn là hệ thống tự sửa lỗi độ tin cậy AI (Self-Correction Verifier). Trả về JSON sửa đổi.", critique_prompt, timeout=40)
            if status == "OK":
                try:
                    m = re.search(r'\{.*\}', raw_fix, re.DOTALL)
                    if m:
                        fixed_json = json.loads(m.group(0))
                        if fixed_json.get("cons") and len(fixed_json.get("cons")) > 0:
                            success = True
                            return fixed_json, triggered, success
                except Exception:
                    pass

    return parsed_json, triggered, success


# ==============================================================================
# 4. TRÌNH ĐIỀU PHỐI BENCHMARK CHÍNH (BENCHMARK RUNNER)
# ==============================================================================
def run_benchmark(model_name: str, limit: int = None, output_csv: str = None):
    print("=" * 75)
    print(f"🚀 KHỞI CHẠY BENCHMARK 4 TRỤ CỘT CHO MÔ HÌNH: [{model_name}]")
    print("=" * 75)

    testset_file = os.path.join(DATA_DIR, "benchmark_test_500.json")
    if not os.path.exists(testset_file):
        print(f"❌ Không tìm thấy file {testset_file}. Hãy chạy generate_testset_500.py trước!")
        return

    with open(testset_file, "r", encoding="utf-8") as f:
        test_samples = json.load(f)

    if limit:
        test_samples = test_samples[:limit]
        print(f"⚠️ Chế độ kiểm thử nhanh: Giới hạn {limit} mẫu.")

    # Nạp Knowledge Base để đối chiếu (sử dụng cache pickle tăng tốc 100x)
    kb_cache_file = os.path.join(DATA_DIR, "real_kb_cache.pkl")
    if os.path.exists(kb_cache_file):
        import pickle
        print("⚡ Đang nạp nhanh Knowledge Base từ Cache (real_kb_cache.pkl)...")
        with open(kb_cache_file, "rb") as f:
            real_kb = pickle.load(f)
        print(f"✅ Đã nạp tức thì {len(real_kb):,} sản phẩm từ Real KB Cache.")
    else:
        kb_file = os.path.join(DATA_DIR, "meta_Beauty.json.gz")
        from load_amazon_data import parse_amazon_json
        print("📚 Đang nạp và lập chỉ mục Knowledge Base Amazon Beauty...")
        real_kb = {}
        for d in parse_amazon_json(kb_file):
            asin = d.get('asin')
            if asin:
                desc = d.get('description', '')
                if isinstance(desc, list): desc = " ".join(desc)
                cats = d.get('categories', [['unknown']])[0]
                real_kb[asin] = {
                    "title": str(d.get('title', 'unknown')).strip(),
                    "brand": str(d.get('brand', 'unknown')).strip(),
                    "price": float(d.get('price')) if d.get('price') is not None else None,
                    "categories": " | ".join(cats) if cats else "unknown",
                    "description": str(desc).strip()
                }
        import pickle
        with open(kb_cache_file, "wb") as f:
            pickle.dump(real_kb, f)
        print(f"✅ Đã nạp và lưu cache {len(real_kb):,} sản phẩm trong Real KB.")

    results_record = []
    chk_file = os.path.join(CURRENT_DIR, f"checkpoint_{model_name.replace(':', '_')}.csv")
    final_csv = output_csv or os.path.join(CURRENT_DIR, f"results_4pillars_{model_name.replace(':', '_')}.csv")

    done_sample_ids = set()
    if os.path.exists(chk_file):
        try:
            df_chk = pd.read_csv(chk_file)
            if not df_chk.empty:
                results_record = df_chk.to_dict('records')
                done_sample_ids = set(df_chk['sample_id'].tolist())
                print(f"🔄 Tìm thấy checkpoint dang dở: Đã có {len(done_sample_ids)} mẫu. Tiếp tục chạy từ mẫu {len(done_sample_ids) + 1}/{len(test_samples)}...")
        except Exception as e:
            print(f"Lỗi nạp checkpoint: {e}")

    for idx, sample in enumerate(tqdm(test_samples, desc=f"Benchmark [{model_name}]")):
        s_id = sample.get("sample_id", idx + 1)
        if s_id in done_sample_ids:
            continue
        t_type = sample.get("test_type")
        u_query = sample.get("user_query")

        # 1. Xây dựng prompt qua 4 trụ cột
        sys_p, usr_p = build_4pillars_prompts(sample, real_kb)

        # 2. Gọi mô hình LLM
        raw_resp, latency_ms, status = query_model(model_name, sys_p, usr_p)

        # 3. Phân tích kết quả JSON
        parsed_json = {}
        json_valid = False
        try:
            m = re.search(r'\{.*\}', raw_resp, re.DOTALL)
            if m:
                parsed_json = json.loads(m.group(0))
                json_valid = True
        except Exception:
            json_valid = False

        # 4. Kích hoạt Trụ cột 4: Xác minh và Tự sửa lỗi (Self-Correction)
        sc_triggered = False
        sc_success = False
        if json_valid:
            parsed_json, sc_triggered, sc_success = apply_self_correction(parsed_json, sample, real_kb, model_name)

        # 5. Chấm điểm các độ đo khoa học
        hallucination = False
        c_neg_violated = False
        ooc_rejected_correctly = False
        pros_cons_balanced = False

        if json_valid:
            # A. Kiểm tra độ cân bằng Pros & Cons
            has_pros = bool(parsed_json.get("pros") and len(parsed_json.get("pros")) > 0)
            has_cons = bool(parsed_json.get("cons") and len(parsed_json.get("cons")) > 0)
            pros_cons_balanced = has_pros and has_cons

            # B. Đánh giá ca Out-of-Catalog (Bẫy ảo giác)
            rec_id = parsed_json.get("recommended_item_id")
            is_null_rec = (rec_id is None or str(rec_id).strip().lower() in ["null", "none", "", "nan"])

            if t_type == "out_of_catalog_adversarial":
                is_rej = parsed_json.get("is_out_of_catalog_rejected", False)
                if is_rej and is_null_rec:
                    ooc_rejected_correctly = True
                    hallucination = False
                else:
                    ooc_rejected_correctly = False
                    hallucination = True # Bị ảo giác do gợi ý sản phẩm không có thật cho ca ngoài kho

            # C. Đánh giá ca có Ràng buộc Tiêu cực C_neg
            elif t_type == "in_catalog_c_neg":
                # Nếu không nêu được cons/cảnh báo rủi ro dựa trên C_neg
                if not has_cons:
                    c_neg_violated = True
                # Nếu gợi ý một mã sản phẩm bịa đặt không có trong KB
                if not is_null_rec and str(rec_id).strip() not in real_kb:
                    hallucination = True

            # D. Đánh giá ca Standard
            else:
                # Nếu gợi ý một mã sản phẩm bịa đặt không có trong KB
                if not is_null_rec and str(rec_id).strip() not in real_kb:
                    hallucination = True

        else:
            hallucination = True # Lỗi cú pháp/không trả về kết quả chuẩn

        results_record.append({
            "sample_id": s_id,
            "model_name": model_name,
            "test_type": t_type,
            "latency_ms": latency_ms,
            "json_valid": json_valid,
            "hallucination": hallucination,
            "c_neg_violated": c_neg_violated,
            "ooc_rejected_correctly": ooc_rejected_correctly if t_type == "out_of_catalog_adversarial" else None,
            "pros_cons_balanced": pros_cons_balanced,
            "self_correction_triggered": sc_triggered,
            "self_correction_success": sc_success,
            "status": status,
            "response_snippet": str(parsed_json.get("response_to_user", ""))[:120]
        })

        # Lưu Checkpoint mỗi 10 mẫu để chống mất mát dữ liệu
        if len(results_record) % 10 == 0 or (idx + 1) == len(test_samples):
            pd.DataFrame(results_record).to_csv(chk_file, index=False)

    df_res = pd.DataFrame(results_record)
    df_res.to_csv(final_csv, index=False)
    if os.path.exists(chk_file):
        os.remove(chk_file)

    # ==============================================================================
    # 5. TỔNG HỢP & BÁO CÁO THỐNG KÊ KHOA HỌC
    # ==============================================================================
    n_total = len(df_res)
    avg_lat = df_res['latency_ms'].mean()
    p95_lat = df_res['latency_ms'].quantile(0.95)
    json_rate = (df_res['json_valid'].sum() / n_total) * 100
    hallu_rate = (df_res['hallucination'].sum() / n_total) * 100
    
    # Đo riêng ca OOC
    df_ooc = df_res[df_res['test_type'] == "out_of_catalog_adversarial"]
    ooc_acc = (df_ooc['ooc_rejected_correctly'].sum() / len(df_ooc) * 100) if not df_ooc.empty else 0.0

    # Đo riêng ca C_neg
    df_cneg = df_res[df_res['test_type'] == "in_catalog_c_neg"]
    cneg_violation_rate = (df_cneg['c_neg_violated'].sum() / len(df_cneg) * 100) if not df_cneg.empty else 0.0

    # Đo độ cân bằng Pros/Cons
    balance_rate = (df_res['pros_cons_balanced'].sum() / n_total) * 100

    print("\n" + "=" * 75)
    print(f"🎯 KẾT QUẢ ĐÁNH GIÁ TỔNG HỢP CHO [{model_name}] (N = {n_total}):")
    print(f"   • Độ trễ trung bình (Avg Latency) : {avg_lat:.1f} ms  (P95: {p95_lat:.1f} ms)")
    print(f"   • Tỷ lệ JSON hợp lệ (JSON Valid)  : {json_rate:.1f}%")
    print(f"   • Tỷ lệ Ảo giác (Hallucination)    : {hallu_rate:.1f}% (Càng thấp càng tốt)")
    print(f"   • Bắt bẫy ngoài kho (OOC Rejection): {ooc_acc:.1f}%")
    print(f"   • Vi phạm ràng buộc (C_neg Violated): {cneg_violation_rate:.1f}% (Càng thấp càng tốt)")
    print(f"   • Cân bằng đa chiều (Pros & Cons) : {balance_rate:.1f}%")
    print(f"📁 Bảng dữ liệu chi tiết đã lưu tại: {final_csv}")
    print("=" * 75)

    return {
        "model": model_name,
        "n_samples": n_total,
        "avg_latency_ms": round(avg_lat, 1),
        "p95_latency_ms": round(p95_lat, 1),
        "json_valid_rate": round(json_rate, 1),
        "hallucination_rate": round(hallu_rate, 1),
        "ooc_rejection_acc": round(ooc_acc, 1),
        "c_neg_violation_rate": round(cneg_violation_rate, 1),
        "pros_cons_balance_rate": round(balance_rate, 1)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy Benchmark 4 Trụ Cột cho Chatbot TMĐT")
    parser.add_argument("--model", type=str, default="gemini-1.5-flash", help="Tên model: gemini-1.5-flash, gpt-4o-mini, qwen2.5:3b, gemma2:2b, llama3.2:3b")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số mẫu chạy (vd: 10 mẫu để test nhanh)")
    args = parser.parse_args()

    run_benchmark(model_name=args.model, limit=args.limit)
