"""
Runner thực nghiệm Khung 4 Trụ Cột trên bộ dữ liệu Amazon ESCI (Task 2: ESCI Classification)
Đối đầu trực diện với kết quả công bố trong Bảng 4 của bài báo Amazon Science (ACM SIGIR 2022).
Độ đo chính: Micro F1-Score (Amazon Baseline = 0.685).
Có checkpointing tự động mỗi 10 mẫu để chống mất mát dữ liệu.
"""

import os
import json
import time
import re
import argparse
import requests
import pandas as pd
from tqdm import tqdm
from sklearn.metrics import f1_score, accuracy_score, classification_report

# Thiết lập đường dẫn
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# 1. NẠP KHÓA API TỪ .ENV CHO OPENAI NẾU CÓ
def get_openai_client():
    env_path = os.path.join(BASE_DIR, "..", "backend", ".env")
    api_key = None
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    return None

# 2. XÂY DỰNG PROMPT 4 TRỤ CỘT CHO TASK 2 (AMAZON ESCI)
def build_4pillars_esci_prompt(sample: dict) -> tuple:
    query = sample.get("query", "")
    p_title = sample.get("product_title", "")
    p_brand = sample.get("product_brand", "")
    p_color = sample.get("product_color", "")
    p_desc = sample.get("product_description", "")
    
    # TRỤ CỘT 1: Profile & Instruction
    system_prompt = """You are an expert E-Commerce Product Relevance and Hallucination Auditor for Amazon.
Your goal is to evaluate the exact semantic relationship between a customer search query and a candidate product, strictly categorizing it into the ESCI framework:
- E (Exact): The product perfectly matches the customer's query, fulfilling all specified attributes and intent.
- S (Substitute): The product is a viable alternative (same functional utility, but might differ in brand, color, or exact model).
- C (Complement): The product is an accessory, add-on, or complementary item, not the item searched for.
- I (Irrelevant / Hallucination): The product has NO relevant relation or violates key constraints of the query.

STRICT CONSTRAINTS (Reliability Pillar):
1. Distinguish carefully between 'Exact' and 'Irrelevant'. If a product fails to fulfill the primary intent (e.g. searching for a phone and getting a t-shirt), it MUST be classified as 'I'.
2. You must reason step-by-step through a 4-step Structured Chain-of-Thought (CoT) before outputting the final decision."""

    # TRỤ CỘT 2: Knowledge Layer (Product Catalog Data)
    product_context = f"""--- AMAZON PRODUCT SPECIFICATION ---
• Title: {p_title}
• Brand: {p_brand}
• Color: {p_color}
• Description: {p_desc if p_desc else "N/A"}
"""

    # TRỤ CỘT 3 & 4: Structured CoT & Strict JSON Schema
    user_prompt = f"""{product_context}
Customer Search Query: "{query}"

Analyze this query-product pair step-by-step and output ONLY a valid JSON object matching this schema:
{{
  "thought_1_query_intent": "Deconstruct the query: what is the core product category, brand, attributes, and user intent?",
  "thought_2_product_attributes": "Extract the key attributes from the product title, brand, and description.",
  "thought_3_relationship_analysis": "Compare the query constraints vs product features. Is it an Exact match (E), a functional Substitute (S), a Complement accessory (C), or completely Irrelevant/Hallucinated (I)?",
  "predicted_label": "E", "S", "C", or "I",
  "confidence": "High", "Medium", or "Low"
}}"""

    return system_prompt, user_prompt

# 3. GỌI MÔ HÌNH LLM
def query_llm(model_name: str, sys_p: str, usr_p: str, client=None) -> tuple:
    t_start = time.perf_counter()
    raw_text = ""
    
    try:
        # Nhóm OpenAI API
        if "gpt" in model_name:
            if not client:
                client = get_openai_client()
            if not client:
                return "{}", 0, "No_OpenAI_API_Key"
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys_p}, {"role": "user", "content": usr_p}],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=400
            )
            raw_text = resp.choices[0].message.content
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return raw_text, latency_ms, "OK"
            
        # Nhóm Local Ollama (qwen2.5:3b, llama3.2:3b, gemma2:2b)
        else:
            chat_url = "http://127.0.0.1:11434/api/chat"
            payload = {
                "model": model_name,
                "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": usr_p}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.0, "num_predict": 400}
            }
            res = requests.post(chat_url, json=payload, timeout=60)
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            if res.status_code == 200:
                raw_text = res.json().get("message", {}).get("content", "{}")
                return raw_text, latency_ms, "OK"
            return "{}", latency_ms, f"Ollama_HTTP_{res.status_code}"
            
    except Exception as e:
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        return "{}", latency_ms, f"Error_{str(e)[:40]}"

# 4. THỰC THI BENCHMARK CÓ CHECKPOINTING
def run_benchmark(model_name: str, limit: int = 500, test_file: str = None):
    if test_file is None:
        file_500 = os.path.join(DATA_DIR, "esci_task2_test_500.json")
        file_100 = os.path.join(DATA_DIR, "esci_task2_test_100.json")
        test_file = file_500 if os.path.exists(file_500) else file_100
        
    if not os.path.exists(test_file):
        print(f"❌ Không tìm thấy file {test_file}! Hãy chạy prepare_task2_testset.py trước.")
        return
        
    with open(test_file, "r", encoding="utf-8") as f:
        samples = json.load(f)[:limit]
        
    print(f"\n==================================================================")
    print(f"🚀 BẮT ĐẦU BENCHMARK 4 TRỤ CỘT TRÊN AMAZON ESCI (TASK 2 - T2)")
    print(f"📌 Mô hình thử nghiệm : {model_name}")
    print(f"📌 Nguồn dữ liệu      : {os.path.basename(test_file)}")
    print(f"📌 Số lượng mẫu       : {len(samples)}")
    print(f"📌 Baseline đối đầu   : Frozen BERT MLP Classifier (Micro F1 = 0.685)")
    print(f"==================================================================\n")
    
    client = get_openai_client() if "gpt" in model_name else None
    
    # Checkpoint setup
    res_clean_name = model_name.replace(":", "_")
    prefix = "ecinstruct" if (test_file and "ecinstruct" in os.path.basename(test_file).lower()) else "esci"
    chk_file = os.path.join(RESULTS_DIR, f"checkpoint_{prefix}_{res_clean_name}.csv")
    final_csv = os.path.join(RESULTS_DIR, f"results_{prefix}_{res_clean_name}.csv")
    
    done_ids = set()
    results = []
    if os.path.exists(chk_file):
        try:
            df_old = pd.read_csv(chk_file)
            done_ids = set(df_old["sample_id"].tolist())
            results = df_old.to_dict(orient="records")
            print(f"🔄 Tìm thấy checkpoint: Đã có {len(done_ids)}/{len(samples)} mẫu. Tiếp tục chạy...")
        except Exception:
            pass
            
    for sample in tqdm(samples, desc=f"Evaluating [{model_name}]"):
        s_id = sample.get("sample_id")
        if s_id in done_ids:
            continue
            
        gt_label = sample.get("ground_truth_label")
        sys_p, usr_p = build_4pillars_esci_prompt(sample)
        
        raw_resp, latency, status = query_llm(model_name, sys_p, usr_p, client)
        
        pred_label = "I" # fallback mặc định nếu lỗi JSON
        parsed = {}
        try:
            m = re.search(r'\{.*\}', raw_resp, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                p_cand = str(parsed.get("predicted_label", "")).strip().upper()
                if p_cand in ["E", "S", "C", "I"]:
                    pred_label = p_cand
                elif "EXACT" in p_cand:
                    pred_label = "E"
                elif "SUBSTITUTE" in p_cand:
                    pred_label = "S"
                elif "COMPLEMENT" in p_cand:
                    pred_label = "C"
                elif "IRRELEVANT" in p_cand:
                    pred_label = "I"
        except Exception:
            pass
            
        results.append({
            "sample_id": s_id,
            "query": sample.get("query"),
            "product_title": sample.get("product_title"),
            "ground_truth": gt_label,
            "prediction": pred_label,
            "is_correct": (gt_label == pred_label),
            "is_hallucination_gt": (gt_label == "I"),
            "is_hallucination_pred": (pred_label == "I"),
            "latency_ms": latency,
            "thought_intent": parsed.get("thought_1_query_intent", ""),
            "thought_analysis": parsed.get("thought_3_relationship_analysis", "")
        })
        
        # Checkpoint mỗi 10 mẫu
        if len(results) % 10 == 0:
            pd.DataFrame(results).to_csv(chk_file, index=False)
            
    # Lưu file kết quả cuối cùng
    df_res = pd.DataFrame(results)
    df_res.to_csv(final_csv, index=False)
    if os.path.exists(chk_file):
        os.remove(chk_file)
        
    # Tính các độ đo khoa học
    y_true = df_res["ground_truth"].tolist()
    y_pred = df_res["prediction"].tolist()
    
    micro_f1 = f1_score(y_true, y_pred, average="micro")
    macro_f1 = f1_score(y_true, y_pred, average="macro")
    acc = accuracy_score(y_true, y_pred)
    
    # Báo cáo chi tiết cho nhãn I (Ảo giác)
    rep = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    f1_irrelevant = rep.get("I", {}).get("f1-score", 0.0)
    prec_irrelevant = rep.get("I", {}).get("precision", 0.0)
    rec_irrelevant = rep.get("I", {}).get("recall", 0.0)
    
    print(f"\n🎯 KẾT QUẢ ĐỐI ĐẦU VỚI BẢNG 4 CỦA AMAZON SCIENCE (N={len(df_res)}):")
    print(f"------------------------------------------------------------------")
    print(f"🔥 Amazon Baseline (Frozen BERT)  : Micro F1 = 0.685 (68.5%)")
    print(f"⭐ Khung 4 Trụ Cột ({model_name}) : Micro F1 = {micro_f1:.4f} ({micro_f1*100:.1f}%)")
    print(f"   - Macro F1                     : {macro_f1:.4f}")
    print(f"   - Độ chính xác Accuracy        : {acc*100:.1f}%")
    print(f"   - F1 nhãn Ảo giác (I)          : {f1_irrelevant:.4f} (Prec: {prec_irrelevant*100:.1f}%, Rec: {rec_irrelevant*100:.1f}%)")
    print(f"   - Độ trễ phản hồi trung bình   : {df_res['latency_ms'].mean():.1f} ms")
    print(f"📁 Kết quả chi tiết đã lưu vào    : {final_csv}")
    print(f"------------------------------------------------------------------\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="Tên model: gpt-4o-mini, qwen2.5:3b, llama3.2:3b, gemma2:2b")
    parser.add_argument("--limit", type=int, default=500, help="Số mẫu cần đánh giá (mặc định: 500)")
    parser.add_argument("--test_file", type=str, default=None, help="Đường dẫn file test json tùy chọn")
    args = parser.parse_args()
    run_benchmark(args.model, args.limit, args.test_file)
