"""
benchmark_runner_ablation_v4.py  -  Ablation Runner v4 (Prompt v1.2 + Rule-Based Parser Repair)

KẾ THỪA VÀ NÂNG CẤP TỪ v3:
1. Prompt v1.2:
   - Làm rõ định nghĩa cờ `is_out_of_catalog_rejected`: CHỈ bật true khi yêu cầu NGOÀI ngành mỹ phẩm/bịa đặt.
   - Nới lỏng "hội chứng siêu cảnh giác": Khi danh mục có sản phẩm mỹ phẩm phù hợp, tự tin gợi ý kèm phân tích khách quan.
   - Đổi tên `thought_3_pros_cons` -> `thought_3_balance` và nhấn mạnh `pros` / `cons` là 2 mảng bắt buộc ở ngoài JSON.
   - Hướng dẫn trường hợp không có review tiêu cực: ghi rõ trong cons `["Chưa ghi nhận phản hồi tiêu cực trên hệ thống"]`.
   - Giải mã HTML entity (`html.unescape`) trong toàn bộ chuỗi danh mục trước khi nạp vào prompt.
2. Rule-Based Parser Repair (SLA Optimization):
   - Sửa lỗi schema/thiếu key bằng phân tích luật (0ms latency), trích xuất pros/cons từ thought nếu model quên key ngoài.
   - Bỏ qua lượt gọi LLM thứ hai (Verifier) nếu luật đã sửa xong, đưa độ trễ Edge model về < 10s.
3. Hỗ trợ tập Dev Set 100 mẫu độc lập (`--testset_file`) trước khi đóng băng chạy tập Test 500 mẫu.
"""
import os
import sys
import re
import json
import math
import time
import hashlib
import html
import inspect
import argparse
import random
import pickle
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import benchmark_runner_4pillars_v2 as v2                                   # noqa: E402
from benchmark_runner_4pillars_v2 import (is_null, as_bool, nonempty_list,   # noqa: E402
                                          extract_json, _rate, wilson, OOC, CNEG, tqdm,
                                          load_real_kb, resolve_gemini_id, DATA_DIR)

DEFAULT_OUT_DIR = os.path.join(HERE, "results_ablation_v4")
TZ = timezone(timedelta(hours=7))

ALL_COMPONENTS = ["profile", "rag", "cneg", "cot", "selfcheck", "verifier"]
PRESETS = {
    "A0": [],
    "A1": ["profile"],
    "A2": ["profile", "rag"],
    "A3": ["profile", "rag", "cneg"],
    "A4": ["profile", "rag", "cneg", "cot"],
    "A5": ["profile", "rag", "cneg", "cot", "selfcheck"],
    "A6": ["profile", "rag", "cneg", "cot", "selfcheck", "verifier"],
}

# ==============================================================================
# 1. GATEWAY -> dict(text, latency_ms, status, model_id, usage)
# ==============================================================================
_GEMINI = None


def query_model(model_name: str, system_prompt, user_prompt: str, cfg: dict, timeout: int = 60) -> dict:
    global _GEMINI
    m = model_name.lower().strip()
    api_id = cfg.get("api_model_id")
    out = {"text": "", "latency_ms": 0.0, "status": "OK", "model_id": api_id or model_name,
           "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}}
    t0 = time.perf_counter()

    def done(**kw):
        out.update(kw)
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return out

    try:
        if m.startswith("gemini"):
            if not v2.GEMINI_API_KEY:
                return done(status="Missing_Gemini_Key")
            if _GEMINI is None:
                os.environ.pop("GOOGLE_API_KEY", None)
                from google import genai
                _GEMINI = genai.Client(api_key=v2.GEMINI_API_KEY)
            from google.genai import types
            target = resolve_gemini_id(model_name, api_id)
            kw = dict(temperature=cfg["temperature"], response_mime_type="application/json",
                      max_output_tokens=cfg["max_tokens"], seed=cfg["seed"])
            if system_prompt:
                kw["system_instruction"] = system_prompt
            config = types.GenerateContentConfig(**kw)
            for attempt in range(4):
                try:
                    time.sleep(0.3)
                    res = _GEMINI.models.generate_content(model=target, contents=user_prompt, config=config)
                    um = getattr(res, "usage_metadata", None)
                    usage = {"prompt_tokens": getattr(um, "prompt_token_count", None),
                             "completion_tokens": getattr(um, "candidates_token_count", None),
                             "total_tokens": getattr(um, "total_token_count", None)}
                    return done(text=res.text or "", model_id=getattr(res, "model_version", None) or target,
                                usage=usage)
                except Exception as e_in:
                    err = str(e_in)
                    if ("503" in err or "429" in err or "RESOURCE_EXHAUSTED" in err) and attempt < 3:
                        time.sleep(5.0 if ("429" in err or "RESOURCE_EXHAUSTED" in err) else 2.0)
                        continue
                    raise

        elif m.startswith("gpt-"):
            if not v2.OPENAI_API_KEY:
                return done(status="Missing_OpenAI_Key")
            msgs = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + \
                   [{"role": "user", "content": user_prompt}]
            payload = {"model": api_id or model_name, "messages": msgs,
                       "response_format": {"type": "json_object"}, "temperature": cfg["temperature"],
                       "max_tokens": cfg["max_tokens"], "seed": cfg["seed"]}
            headers = {"Authorization": f"Bearer {v2.OPENAI_API_KEY}", "Content-Type": "application/json"}
            for attempt in range(4):
                res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=timeout)
                if res.status_code == 200:
                    d = res.json()
                    u = d.get("usage") or {}
                    usage = {"prompt_tokens": u.get("prompt_tokens"),
                             "completion_tokens": u.get("completion_tokens"),
                             "total_tokens": u.get("total_tokens")}
                    return done(text=d["choices"][0]["message"]["content"],
                                model_id=d.get("model") or api_id or model_name, usage=usage)
                if res.status_code in (429, 500, 502, 503) and attempt < 3:
                    time.sleep(4.0)
                    continue
                return done(status=f"HTTP_{res.status_code}_{res.text[:80]}")

        else:
            # Ollama
            msgs = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + \
                   [{"role": "user", "content": user_prompt}]
            payload = {"model": api_id or model_name, "messages": msgs, "stream": False, "format": "json",
                       "options": {"temperature": cfg["temperature"], "num_predict": cfg["max_tokens"],
                                   "seed": cfg["seed"]}}
            res = requests.post(v2.OLLAMA_CHAT_URL, json=payload, timeout=timeout)
            if res.status_code == 200:
                body = res.json()
                pt, ct = body.get("prompt_eval_count"), body.get("eval_count")
                return done(text=body.get("message", {}).get("content", "") or "",
                            model_id=body.get("model", out["model_id"]),
                            usage={"prompt_tokens": pt, "completion_tokens": ct,
                                   "total_tokens": (pt + ct) if (pt is not None and ct is not None) else None})
            return done(status=f"Ollama_HTTP_{res.status_code}")

    except Exception as e:
        return done(status=f"Exception_{type(e).__name__}_{str(e)[:40]}")


# ==============================================================================
# 2. PROMPT DEFINITIONS: v1.1 vs v1.2
# ==============================================================================
PROFILE_BLOCK_V11 = """Bạn là "BeautyAdvisor" — Chuyên viên Tư vấn Mua sắm Mỹ phẩm Khách quan của sàn thương mại điện tử Amazon Beauty.

PHẠM VI HOẠT ĐỘNG:
- Bạn CHỈ tư vấn sản phẩm Làm đẹp & Mỹ phẩm (chăm sóc da, trang điểm, chăm sóc tóc, nước hoa, chăm sóc cá nhân, dụng cụ làm đẹp).
- Nếu khách hỏi về mặt hàng ngoài phạm vi trên (ví dụ: điện tử, thời trang, đồ gia dụng) hoặc về sản phẩm không tồn tại, hãy lịch sự từ chối, đặt "is_out_of_catalog_rejected": true và "recommended_item_id": null.

RÀNG BUỘC BẮT BUỘC:
1. TUYỆT ĐỐI không bịa đặt tên sản phẩm, mã ASIN, thương hiệu, thành phần hoặc giá tiền không có trong thông tin được cung cấp.
2. Nếu không đủ thông tin để tư vấn chắc chắn, hãy nói thẳng là chưa đủ thông tin thay vì đoán.
3. Luôn cân bằng: khi tư vấn một sản phẩm, nêu cả ưu điểm lẫn nhược điểm/lưu ý.
4. Trả lời khách bằng ngôn ngữ của họ (mặc định tiếng Việt)."""

RAG_BLOCK_V11 = """DỮ LIỆU DANH MỤC (GROUNDING):
- CHỈ được gợi ý và nhắc tới sản phẩm có trong phần [DANH MỤC SẢN PHẨM]. Mã ASIN, thương hiệu và giá phải khớp 100% với danh mục.
- Nếu không có sản phẩm nào trong danh mục phù hợp với yêu cầu, hãy đặt "recommended_item_id": null và giải thích, không bịa sản phẩm."""

CNEG_BLOCK_V11 = """CÂN BẰNG ĐA CHIỀU (ĐÁNH GIÁ TIÊU CỰC):
- Với mỗi sản phẩm được gợi ý, BẮT BUỘC nêu ít nhất 1 nhược điểm/cảnh báo thực tế dựa trên [ĐÁNH GIÁ TIÊU CỰC TỪ NGƯỜI DÙNG].
- Nhược điểm phải là thông tin có thật từ đánh giá, không được tự sáng tác. Nếu không có đánh giá tiêu cực nào, hãy nói rõ là chưa ghi nhận phản hồi tiêu cực."""

COT_BLOCK_V11 = """QUY TRÌNH SUY LUẬN BẮT BUỘC (4 BƯỚC) — điền lần lượt vào các trường thought_1 ... thought_4 của JSON:
1. Phân tích ngữ cảnh & nhu cầu (loại da, mối quan tâm, ngân sách; yêu cầu có thuộc phạm vi không).
2. Đối soát danh mục: chỉ chọn sản phẩm thực sự phù hợp, chỉ từ [DANH MỤC SẢN PHẨM].
3. Cân bằng ưu/nhược điểm dựa trên đánh giá tiêu cực.
4. Quyết định: gợi ý hay từ chối, kèm lý do ngắn gọn."""

SELFCHECK_BLOCK_V11 = """TỰ KIỂM TRA TRƯỚC KHI TRẢ LỜI (bắt buộc):
[ ] Mã ASIN gợi ý (nếu có) có nằm trong [DANH MỤC SẢN PHẨM] không? Thương hiệu và giá có khớp danh mục không?
[ ] Nếu yêu cầu ngoài phạm vi: đã đặt is_out_of_catalog_rejected=true và recommended_item_id=null chưa?
[ ] Nếu có gợi ý: mảng "cons" có ít nhất 1 nhược điểm bám theo đánh giá tiêu cực chưa?
Nếu có điều kiện nào chưa đạt, hãy sửa lại rồi mới xuất JSON."""

BLOCKS_V11 = [
    ("profile", PROFILE_BLOCK_V11),
    ("rag", RAG_BLOCK_V11),
    ("cneg", CNEG_BLOCK_V11),
    ("cot", COT_BLOCK_V11),
    ("selfcheck", SELFCHECK_BLOCK_V11),
]

COT_LINES_V11 = [
    '"thought_1_context": "phân tích nhu cầu và phạm vi yêu cầu"',
    '"thought_2_catalog_check": "đối soát với danh mục sản phẩm"',
    '"thought_3_pros_cons": "cân bằng ưu và nhược điểm"',
    '"thought_4_decision": "quyết định gợi ý hay từ chối, kèm lý do"',
]

SCHEMA_LINES_V11 = [
    '"response_to_user": "câu trả lời gửi khách hàng"',
    '"recommended_item_id": "mã ASIN của sản phẩm gợi ý, hoặc null nếu không gợi ý sản phẩm nào"',
    '"brand": "thương hiệu của sản phẩm được gợi ý, hoặc null"',
    '"price_usd": số (USD) của sản phẩm được gợi ý, hoặc null',
    '"is_out_of_catalog_rejected": true nếu bạn từ chối vì yêu cầu ngoài phạm vi của sàn, ngược lại false',
    '"pros": ["ưu điểm 1", "ưu điểm 2"]',
    '"cons": ["nhược điểm/cảnh báo 1"]',
]

PROFILE_BLOCK_V12 = """Bạn là "BeautyAdvisor" — Chuyên viên Tư vấn Mua sắm Mỹ phẩm Khách quan của sàn thương mại điện tử Amazon Beauty.

PHẠM VI HOẠT ĐỘNG:
- Bạn CHỈ tư vấn sản phẩm Làm đẹp & Mỹ phẩm (chăm sóc da, trang điểm, chăm sóc tóc, dầu gội, sữa tắm, nước hoa, chăm sóc cá nhân, dụng cụ làm đẹp).
- ĐỊNH NGHĨA CỜ TỪ CHỐI (is_out_of_catalog_rejected): CHỈ đặt "is_out_of_catalog_rejected": true khi yêu cầu của khách hàng hoàn toàn NẰM NGOÀI ngành hàng Làm đẹp (ví dụ: điện tử, điện thoại, máy tính, thời trang, đồ gia dụng, xe cộ...) hoặc đòi hỏi sản phẩm bịa đặt/chất cấm.
- NẾU sản phẩm thuộc ngành Làm đẹp & Mỹ phẩm và đã có trong [DANH MỤC SẢN PHẨM], kể cả khi sản phẩm có nhược điểm hoặc khách có làn da nhạy cảm, TUYỆT ĐỐI KHÔNG bật cờ từ chối này (phải đặt "is_out_of_catalog_rejected": false); hãy tự tin gợi ý sản phẩm đó và cảnh báo nhược điểm rõ ràng, khách quan trong "cons".

RÀNG BUỘC BẮT BUỘC:
1. TUYỆT ĐỐI không bịa đặt tên sản phẩm, mã ASIN, thương hiệu, thành phần hoặc giá tiền không có trong thông tin được cung cấp.
2. Khi trong [DANH MỤC SẢN PHẨM] đã có sản phẩm mỹ phẩm phù hợp với câu hỏi của khách, bạn VẪN PHẢI điền mã ASIN của sản phẩm đó vào "recommended_item_id" để khách tham khảo, đồng thời phân tích ưu điểm và cảnh báo nhược điểm khách quan trong "cons". KHÔNG ĐẶT recommended_item_id: null khi danh mục đã có sản phẩm phù hợp.
3. Luôn cân bằng: khi tư vấn một sản phẩm, nêu cả ưu điểm lẫn nhược điểm/lưu ý.
4. Trả lời khách bằng ngôn ngữ của họ (mặc định tiếng Việt)."""

RAG_BLOCK_V12 = """DỮ LIỆU DANH MỤC (GROUNDING):
- CHỈ được gợi ý và nhắc tới sản phẩm có trong phần [DANH MỤC SẢN PHẨM]. Mã ASIN, thương hiệu và giá phải khớp 100% với danh mục.
- Nếu không có sản phẩm nào trong danh mục phù hợp với yêu cầu làm đẹp, hãy đặt "recommended_item_id": null và giải thích trong response_to_user, không bịa sản phẩm (nhưng vẫn giữ "is_out_of_catalog_rejected": false vì câu hỏi vẫn thuộc ngành mỹ phẩm)."""

CNEG_BLOCK_V12 = """CÂN BẰNG ĐA CHIỀU (ĐÁNH GIÁ TIÊU CỰC):
- Với mỗi sản phẩm được gợi ý, BẮT BUỘC nêu ít nhất 1 nhược điểm/cảnh báo thực tế dựa trên [ĐÁNH GIÁ TIÊU CỰC TỪ NGƯỜI DÙNG] đưa vào mảng "cons".
- Nhược điểm phải là thông tin có thật từ đánh giá, không được tự sáng tác. Nếu phần đánh giá ghi nhận không có phản hồi tiêu cực nào, hãy ghi trong mảng cons: ["Chưa ghi nhận phản hồi tiêu cực từ người dùng trên hệ thống"]."""

COT_BLOCK_V12 = """QUY TRÌNH SUY LUẬN BẮT BUỘC (4 BƯỚC) — điền lần lượt vào các trường thought_1 ... thought_4 của JSON:
1. thought_1_context: Phân tích nhu cầu và phạm vi (câu hỏi có thuộc ngành mỹ phẩm không).
2. thought_2_catalog_check: Đối soát danh mục, chọn sản phẩm mỹ phẩm phù hợp nhất trong [DANH MỤC SẢN PHẨM].
3. thought_3_balance: Cân bằng ưu và nhược điểm dựa trên đánh giá thực tế (chỉ là bước suy nghĩ nháp).
4. thought_4_decision: Quyết định gợi ý sản phẩm nào, kèm tóm tắt lý do.

LƯU Ý ĐẶC BIỆT QUAN TRỌNG:
thought_1 .. thought_4 chỉ là các bước suy nghĩ nháp. Bạn BẮT BUỘC phải xuất đầy đủ 2 mảng riêng biệt "pros" và "cons" ở các khóa ngoài của JSON (không được lược bỏ)."""

SELFCHECK_BLOCK_V12 = """TỰ KIỂM TRA TRƯỚC KHI TRẢ LỜI (bắt buộc):
[ ] Mã ASIN gợi ý (nếu có) có nằm trong [DANH MỤC SẢN PHẨM] không? Thương hiệu và giá có khớp danh mục không?
[ ] Nếu yêu cầu NẰM NGOÀI ngành mỹ phẩm: đã đặt is_out_of_catalog_rejected=true và recommended_item_id=null chưa?
[ ] Nếu yêu cầu THUỘC ngành mỹ phẩm: is_out_of_catalog_rejected phải là false!
[ ] Cả 2 khóa ngoài "pros" và "cons" đã có đầy đủ mảng danh sách chưa?
Nếu có điều kiện nào chưa đạt, hãy sửa lại rồi mới xuất JSON."""

BLOCKS_V12 = [
    ("profile", PROFILE_BLOCK_V12),
    ("rag", RAG_BLOCK_V12),
    ("cneg", CNEG_BLOCK_V12),
    ("cot", COT_BLOCK_V12),
    ("selfcheck", SELFCHECK_BLOCK_V12),
]

COT_LINES_V12 = [
    '"thought_1_context": "phân tích nhu cầu và phạm vi yêu cầu (ngành mỹ phẩm hay ngoài ngành)"',
    '"thought_2_catalog_check": "đối soát với danh mục sản phẩm, chọn ASIN phù hợp nhất"',
    '"thought_3_balance": "cân nhắc ưu điểm và nhược điểm thực tế"',
    '"thought_4_decision": "quyết định gợi ý hay từ chối, kèm lý do"',
]
SCHEMA_LINES_V12 = [
    '"response_to_user": "câu trả lời gửi khách hàng"',
    '"recommended_item_id": "mã ASIN của sản phẩm gợi ý, hoặc null nếu không gợi ý sản phẩm nào"',
    '"brand": "thương hiệu của sản phẩm được gợi ý, hoặc null"',
    '"price_usd": số (USD) của sản phẩm được gợi ý, hoặc null',
    '"is_out_of_catalog_rejected": true nếu yêu cầu NẰM NGOÀI ngành mỹ phẩm/bịa đặt, ngược lại false',
    '"pros": ["ưu điểm 1", "ưu điểm 2"] (bắt buộc, không để trống nếu có gợi ý)',
    '"cons": ["nhược điểm 1"] (bắt buộc; nếu không có đánh giá xấu thì ghi ["Chưa ghi nhận phản hồi tiêu cực trên hệ thống"])',
]
ZERO_MSG = "[Hệ thống: tìm kiếm trong danh mục không trả về sản phẩm nào.]"


def schema_text(cot: bool, prompt_version: str = "v1.2") -> str:
    cot_lines = COT_LINES_V12 if prompt_version == "v1.2" else COT_LINES_V11
    schema_lines = SCHEMA_LINES_V12 if prompt_version == "v1.2" else SCHEMA_LINES_V11
    lines = (cot_lines if cot else []) + schema_lines
    return "{\n" + ",\n".join("  " + ln for ln in lines) + "\n}"


def _fmt_product(i: int, asin: str, p: dict) -> str:
    price = p.get("price")
    price_s = f"${price:.2f}" if isinstance(price, (int, float)) and price else "Chưa cập nhật"
    title = html.unescape(str(p.get("title", "")))
    brand = html.unescape(str(p.get("brand", "")))
    cat = html.unescape(str(p.get("categories", "")))
    desc = html.unescape(str(p.get("description", "")))[:300]
    return (f"Sản phẩm {i}:\n- ASIN: {asin}\n- Tên: {title}\n- Thương hiệu: {brand}\n"
            f"- Danh mục: {cat}\n- Giá: {price_s}\n- Mô tả: {desc}")


def build_context(sample: dict, kb: dict, k: int, neg_r: int, neg_index: dict,
                  decoy_keys: list, ooc_context: str, seed: int, negative_rag: bool = False) -> dict:
    t, sid = sample.get("test_type"), sample.get("sample_id")
    gold = sample.get("ground_truth_target") or None
    gold_id = gold.get("item_id") if gold else None
    neg = sample.get("negative_constraints") or {}
    c_neg_text = neg.get("c_neg_text") if neg.get("has_negative_constraint") else None

    items, n_dec = [], 0
    if negative_rag:
        # Negative RAG / Retrieval Failure: Rút sản phẩm đúng ra khỏi context!
        n_dec = k
    elif t != OOC and gold_id:
        items.append(gold_id)
        n_dec = max(0, k - 1)
    elif t == OOC and ooc_context == "decoy":
        n_dec = k
    rng = random.Random(f"{seed}-{sid}")
    tries = 0
    while n_dec > 0 and decoy_keys and tries < 100 * max(1, n_dec):
        tries += 1
        a = decoy_keys[rng.randrange(len(decoy_keys))]
        if (negative_rag or a != gold_id) and a not in items:
            if negative_rag and a == gold_id:
                continue
            items.append(a)
            n_dec -= 1
    rng.shuffle(items)

    catalog_text = "\n\n".join(_fmt_product(i + 1, a, kb.get(a, gold if a == gold_id else {}))
                               for i, a in enumerate(items)) if items else ZERO_MSG

    neg_chunks, neg_n = [], 0
    for a in items:
        revs = []
        if a == gold_id and c_neg_text:
            revs.append(c_neg_text)
        if neg_index:
            revs += [x for x in neg_index.get(a, []) if x != c_neg_text]
        revs = revs[:neg_r]
        if revs:
            info = kb.get(a, {})
            title_clean = html.unescape(str(info.get('title', '')))
            neg_chunks.append(f"[{a} — {title_clean}]\n" +
                              "\n".join(f'Review {j + 1}: "{r}"' for j, r in enumerate(revs)))
            neg_n += len(revs)
    neg_text = "\n\n".join(neg_chunks) if neg_chunks else "(Không có đánh giá tiêu cực nào cho các sản phẩm trên.)"
    return {"asins": items, "catalog_text": catalog_text, "neg_text": neg_text,
            "neg_n": neg_n, "gold_id": gold_id}


def build_prompts(sample: dict, comps: list, ctx: dict, prompt_version: str = "v1.2") -> tuple:
    use = set(comps)
    blocks_def = BLOCKS_V12 if prompt_version == "v1.2" else BLOCKS_V11
    blocks = [txt for name, txt in blocks_def if name in use]
    system_prompt = "\n\n".join(blocks) if blocks else None

    parts = []
    if "rag" in use:
        parts.append(f"[DANH MỤC SẢN PHẨM]\n{ctx['catalog_text']}\n[/DANH MỤC SẢN PHẨM]")
    if "cneg" in use:
        parts.append(f"[ĐÁNH GIÁ TIÊU CỰC TỪ NGƯỜI DÙNG (1-2 sao)]\n{ctx['neg_text']}\n"
                     f"[/ĐÁNH GIÁ TIÊU CỰC TỪ NGƯỜI DÙNG]")
    parts.append(f'Khách hàng hỏi: "{sample.get("user_query", "")}"')
    parts.append("Chỉ trả về MỘT khối JSON hợp lệ theo cấu trúc sau, không thêm văn bản nào ngoài JSON:\n"
                 + schema_text("cot" in use, prompt_version=prompt_version))
    return system_prompt, "\n\n".join(parts)


def is_placeholder_cons(cons_list) -> bool:
    """
    Kiểm tra xem mảng cons có phải là câu ghi nhận mặc định (placeholder) hay không.
    Ví dụ: 'Chưa ghi nhận phản hồi tiêu cực trên hệ thống', 'Không có đánh giá xấu', v.v.
    """
    if not cons_list or not isinstance(cons_list, list):
        return False
    placeholder_patterns = [
        r"chưa\s*(có|ghi\s*nhận)",
        r"không\s*(có|tìm\s*thấy|ghi\s*nhận)\s*(đánh\s*giá|phản\s*hồi|review|khiếu\s*nại|nhược\s*điểm)",
        r"chưa\s*thấy\s*phản\s*hồi",
        r"no\s*negative\s*review",
        r"không\s*có\s*nhược\s*điểm\s*nào",
        r"chưa\s*ghi\s*nhận\s*phản\s*hồi\s*tiêu\s*cực",
        r"không\s*có\s*thông\s*tin\s*tiêu\s*cực",
    ]
    valid_items = [str(x).strip() for x in cons_list if str(x).strip()]
    if not valid_items:
        return False
    for item in valid_items:
        text = item.lower()
        if not any(re.search(pat, text) for pat in placeholder_patterns):
            return False
    return True


# ==============================================================================
# 3. EVALUATION & MATCHER
# ==============================================================================
def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", html.unescape(str(s)).lower()) if s is not None else ""


def _to_float(v):
    if v is None:
        return None
    try:
        return float(re.sub(r"[^\d.]", "", str(v)))
    except (TypeError, ValueError):
        return None


def brand_match(pred, cat) -> bool:
    if is_null(pred) or is_null(cat):
        return True
    p, c = _norm(pred), _norm(cat)
    if not p or not c or c == "unknown":
        return True
    return p == c or p in c or c in p


def evaluate(parsed: dict, sample: dict, kb: dict, ctx_asins: list, negative_rag: bool = False) -> dict:
    t = sample.get("test_type")
    gold_id = (sample.get("ground_truth_target") or {}).get("item_id")
    rec = parsed.get("recommended_item_id")
    null_rec = is_null(rec)
    rec_s = None if null_rec else str(rec).strip()
    rejected = as_bool(parsed.get("is_out_of_catalog_rejected", False))
    
    pros_raw = parsed.get("pros")
    cons_raw = parsed.get("cons")
    pros_ne, cons_ne = nonempty_list(pros_raw), nonempty_list(cons_raw)
    cons_is_placeholder = is_placeholder_cons(cons_raw)
    has_real_cons = cons_ne and not cons_is_placeholder
    in_kb = rec_s is not None and rec_s in kb

    brand_bad = price_bad = False
    if in_kb:
        info = kb[rec_s]
        if not is_null(parsed.get("brand")) and not brand_match(parsed.get("brand"), info.get("brand")):
            brand_bad = True
        pv, cp = _to_float(parsed.get("price_usd")), info.get("price")
        if pv is not None and cp:
            price_bad = abs(pv - cp) / cp > 0.20

    hallu_asin = rec_s is not None and not in_kb
    outside_ctx = in_kb and rec_s not in ctx_asins

    # Metrics đặc biệt cho Negative RAG (truy xuất hỏng)
    neg_rag_correct = bool(negative_rag and t != OOC and null_rec)
    neg_rag_hallu_gold = bool(negative_rag and t != OOC and rec_s is not None and rec_s == gold_id)
    neg_rag_picked_decoy = bool(negative_rag and t != OOC and rec_s is not None and rec_s in ctx_asins)
    neg_rag_hallu_random = bool(negative_rag and t != OOC and rec_s is not None and rec_s not in ctx_asins and rec_s != gold_id)

    false_refusal = (t != OOC and (rejected or null_rec)) if not negative_rag else False

    # Phân loại Cons chuẩn mực thống kê theo yêu cầu phản biện:
    cons_empty = not nonempty_list(cons_raw)
    cons_placeholder = nonempty_list(cons_raw) and is_placeholder_cons(cons_raw)
    cons_real = nonempty_list(cons_raw) and not is_placeholder_cons(cons_raw)

    # 1. C_neg (có review tiêu cực trong context):
    cneg_cons_real = bool(t == CNEG and cons_real)
    cneg_cons_placeholder = bool(t == CNEG and cons_placeholder)
    cneg_cons_empty = bool(t == CNEG and cons_empty)

    # 2. Standard (in-catalog không có review tiêu cực trong context):
    std_cons_empty = bool(t != OOC and t != CNEG and cons_empty)
    std_cons_placeholder = bool(t != OOC and t != CNEG and cons_placeholder)
    std_cons_hallu_real = bool(t != OOC and t != CNEG and cons_real)

    # Pros&Cons cân bằng:
    if t == CNEG:
        pros_cons_balanced = bool(pros_ne and cons_real)
    elif t != OOC:
        # Trên Standard: Có pros, và cons KHÔNG tự bịa nhược điểm (rỗng hoặc placeholder chuẩn đều hợp lệ)
        pros_cons_balanced = bool(pros_ne and not cons_real)
    else:
        pros_cons_balanced = False

    hallucination_any = bool(hallu_asin or brand_bad or price_bad or (t == OOC and not null_rec) or
                             neg_rag_hallu_gold or neg_rag_hallu_random)

    return {
        "rec_id_raw": rec_s, "rejected_raw": rejected,
        "pros_nonempty": pros_ne, "cons_nonempty": cons_ne,
        "cons_empty": cons_empty, "cons_placeholder": cons_placeholder, "cons_real": cons_real,
        "cneg_cons_real": cneg_cons_real, "cneg_cons_placeholder": cneg_cons_placeholder, "cneg_cons_empty": cneg_cons_empty,
        "std_cons_empty": std_cons_empty, "std_cons_placeholder": std_cons_placeholder, "std_cons_hallu_real": std_cons_hallu_real,
        "pros_cons_balanced": pros_cons_balanced,
        "hallu_asin": hallu_asin, "hallu_attr": brand_bad or price_bad,
        "brand_mismatch": brand_bad, "price_mismatch": price_bad,
        "rec_outside_context": outside_ctx,
        "unsupported_rec": hallu_asin or outside_ctx,
        "rec_is_gold": t != OOC and rec_s is not None and rec_s == gold_id,
        "ooc_wrong_rec": t == OOC and not null_rec,
        "ooc_correct": t == OOC and rejected and null_rec,
        "false_refusal": false_refusal,
        "cons_missing": t == CNEG and cons_empty,
        "rec_nonnull": not null_rec,
        "hallucination_any": hallucination_any,
        "neg_rag_correct": neg_rag_correct,
        "neg_rag_hallu_gold": neg_rag_hallu_gold,
        "neg_rag_picked_decoy": neg_rag_picked_decoy,
        "neg_rag_hallu_random": neg_rag_hallu_random,
    }


# ==============================================================================
# 4. RULE-BASED PARSER REPAIR (SLA < 10s OPTIMIZATION, NO TEST-LABELS / NO ORACLE)
# ==============================================================================
def rule_based_repair(parsed: dict, user_query: str, kb: dict, ctx_asins: list,
                      ctx_neg_n: int = 0, negative_rag: bool = False) -> tuple:
    """
    Sửa lỗi nhanh thuần parser (0ms latency, TUYỆT ĐỐI KHÔNG DÙNG ORACLE / TEST_TYPE / GOLD_ID):
    Phân rã thành 4 luật con độc lập:
    1. rule_recover_asin: Khôi phục ASIN từ context nếu thought/text đã nhắc tới nhưng quên điền key ngoài.
    2. rule_ooc_flag: Sửa cờ OOC khi text từ chối rõ ràng hoặc gỡ cờ OOC khi đã gợi ý ASIN hợp lệ.
    3. rule_extract_pros_cons: Trích xuất pros/cons từ thought nếu mảng ngoài rỗng.
    4. rule_fill_brand_price: Tự điền brand/price từ KB cho ASIN đã chọn hợp lệ.
    """
    if not parsed or not isinstance(parsed, dict):
        return parsed, False, [], {}

    repaired = dict(parsed)
    actions = []
    subrules = {
        "rule_recover_asin": False,
        "rule_ooc_flag": False,
        "rule_extract_pros_cons": False,
        "rule_fill_brand_price": False,
        "rule_cons_clean_standard": False
    }

    rec = repaired.get("recommended_item_id")
    null_rec = is_null(rec)
    rec_s = None if null_rec else str(rec).strip()

    # LUẬT 1: KHÔI PHỤC ASIN TỪ CONTEXT NẾU TEXT/THOUGHT ĐÃ CHỌN SẢN PHẨM (0ms)
    if not negative_rag and null_rec:
        full_text = " ".join(str(v) for v in repaired.values())
        matched_asin = None
        for a in ctx_asins:
            if a in full_text:
                matched_asin = a
                break
        if not matched_asin:
            pred_b = _norm(repaired.get("brand"))
            pred_p = _to_float(repaired.get("price_usd"))
            if pred_b:
                for a in ctx_asins:
                    info = kb.get(a, {})
                    c_b = _norm(info.get("brand"))
                    c_p = info.get("price")
                    if c_b and (pred_b == c_b or pred_b in c_b or c_b in pred_b):
                        if pred_p is not None and c_p and abs(pred_p - c_p) / c_p < 0.10:
                            matched_asin = a
                            break
        if not matched_asin:
            for a in ctx_asins:
                title = str(kb.get(a, {}).get("title", ""))
                clean_title = re.sub(r'[^a-zA-Z0-9 ]', '', title).lower()
                words = [w for w in clean_title.split() if len(w) > 3][:3]
                if words and all(w in full_text.lower() for w in words):
                    matched_asin = a
                    break
        if matched_asin:
            repaired["recommended_item_id"] = matched_asin
            rec_s = matched_asin
            null_rec = False
            subrules["rule_recover_asin"] = True
            actions.append(f"rule_recover_asin_{matched_asin}")

    # LUẬT 2: SỬA CỜ OOC VÀ MÂU THUẪN NỘI BỘ
    # 2a. Nếu đã gợi ý ASIN trong danh mục nhưng lại bật cờ từ chối OOC -> reset cờ về false
    if rec_s and rec_s in ctx_asins and as_bool(repaired.get("is_out_of_catalog_rejected", False)):
        repaired["is_out_of_catalog_rejected"] = False
        subrules["rule_ooc_flag"] = True
        actions.append("rule_ooc_flag_reset_contradiction")

    # 2b. Nếu text phản hồi từ chối rõ ràng nhưng quên bật cờ OOC
    resp_text = str(repaired.get("response_to_user", "")).lower()
    ooc_keywords = ["không thuộc", "ngoài phạm vi", "không có sản phẩm", "không bán", "không tìm thấy", "chỉ tư vấn", "từ chối"]
    if any(w in resp_text for w in ooc_keywords):
        if null_rec or (rec_s and rec_s not in ctx_asins):
            if not as_bool(repaired.get("is_out_of_catalog_rejected", False)):
                repaired["is_out_of_catalog_rejected"] = True
                subrules["rule_ooc_flag"] = True
                actions.append("rule_ooc_flag_set_from_text")
            if not null_rec:
                repaired["recommended_item_id"] = None
                rec_s = None
                null_rec = True
                subrules["rule_ooc_flag"] = True
                actions.append("rule_ooc_flag_cleared_rec")

    # LUẬT 3: TRÍCH XUẤT PROS / CONS TỪ THOUGHT / TEXT
    # 3a. Trích xuất pros nếu thiếu
    if not null_rec and not nonempty_list(repaired.get("pros")):
        extracted_pros = []
        for src in [repaired.get("thought_3_balance"), repaired.get("thought_3_pros_cons"),
                    repaired.get("thought_2_catalog_check"), repaired.get("response_to_user")]:
            if src and isinstance(src, str):
                pos_m = re.findall(r'(?:ưu điểm|điểm mạnh|lợi thế|thành phần tốt|phù hợp)[:\s]+([^.\n;]+)', src, re.I)
                if pos_m:
                    extracted_pros.extend([p.strip() for p in pos_m if len(p.strip()) > 3])
                bullets = re.findall(r'^[+*•-]\s*([^.\n]+)', src, re.M)
                if bullets:
                    extracted_pros.extend([b.strip() for b in bullets[:3]])
        if extracted_pros:
            repaired["pros"] = list(dict.fromkeys(extracted_pros))[:3]
            subrules["rule_extract_pros_cons"] = True
            actions.append("rule_extract_pros_from_thought")
        elif rec_s in kb:
            repaired["pros"] = [f"Sản phẩm phù hợp danh mục {kb[rec_s].get('categories', 'Làm đẹp')}"]
            subrules["rule_extract_pros_cons"] = True
            actions.append("rule_extract_pros_fallback_kb")

    # 3b. Trích xuất cons nếu thiếu
    if not null_rec and not nonempty_list(repaired.get("cons")):
        extracted_cons = []
        for src in [repaired.get("thought_3_balance"), repaired.get("thought_3_pros_cons"),
                    repaired.get("thought_4_decision"), repaired.get("response_to_user")]:
            if src and isinstance(src, str):
                neg_m = re.findall(r'(?:nhược điểm|hạn chế|lưu ý|cảnh báo|không phù hợp)[:\s]+([^.\n;]+)', src, re.I)
                if neg_m:
                    extracted_cons.extend([c.strip() for c in neg_m if len(c.strip()) > 3])
                for sent in re.split(r'[.\n;]', src):
                    if any(w in sent.lower() for w in ["khô da", "dị ứng", "kích ứng", "mùi", "cẩn thận", "nhạy cảm"]):
                        if len(sent.strip()) > 10:
                            extracted_cons.append(sent.strip())
                            break
        if extracted_cons:
            repaired["cons"] = list(dict.fromkeys(extracted_cons))[:2]
            subrules["rule_extract_pros_cons"] = True
            actions.append("rule_extract_cons_from_thought")
        elif ctx_neg_n == 0:
            repaired["cons"] = ["Chưa ghi nhận phản hồi tiêu cực trên hệ thống"]
            subrules["rule_extract_pros_cons"] = True
            actions.append("rule_extract_cons_default_placeholder")

    # LUẬT 4: TỰ ĐIỀN BRAND / PRICE TỪ KB (0ms)
    if rec_s and rec_s in kb:
        info = kb[rec_s]
        if is_null(repaired.get("brand")):
            repaired["brand"] = html.unescape(str(info.get("brand", "")))
            subrules["rule_fill_brand_price"] = True
            actions.append("rule_fill_brand_from_kb")
        if is_null(repaired.get("price_usd")) and info.get("price"):
            repaired["price_usd"] = float(info["price"])
            subrules["rule_fill_brand_price"] = True
            actions.append("rule_fill_price_from_kb")

    # LUẬT 5: CHUẨN HÓA CONS KHI KHÔNG CÓ REVIEW TIÊU CỰC (L5: ctx_neg_n == 0)
    # Khi danh mục RAG không có review xấu (Standard), ép cons về placeholder chuẩn
    # để loại bỏ hoàn toàn các câu cảnh báo tự suy đoán không có cơ sở thực tế.
    if not null_rec and ctx_neg_n == 0:
        placeholder_str = "Chưa ghi nhận phản hồi tiêu cực trên hệ thống"
        cur_cons = repaired.get("cons")
        if not nonempty_list(cur_cons) or not is_placeholder_cons(cur_cons):
            repaired["cons"] = [placeholder_str]
            subrules["rule_cons_clean_standard"] = True
            actions.append("rule_cons_clean_standard_l5")

    return repaired, len(actions) > 0, actions, subrules


# ==============================================================================
# 5. VERIFIER & JUDGE (ORACLE vs OBSERVABLE DETECTION)
# ==============================================================================
MERGE_KEYS = ["recommended_item_id", "brand", "price_usd", "is_out_of_catalog_rejected",
              "response_to_user", "pros", "cons"]


def detect_correction_need_oracle(parsed: dict, sample: dict):
    """Cận trên lý thuyết: dùng nhãn kiểm thử test_type (Oracle-guided)"""
    if not parsed or not isinstance(parsed, dict):
        return None
    t = sample.get("test_type")
    rec = parsed.get("recommended_item_id")
    null_rec = is_null(rec)
    rejected = as_bool(parsed.get("is_out_of_catalog_rejected", False))
    if t == OOC:
        if not rejected or not null_rec:
            return "ooc_not_rejected"
    elif t == CNEG:
        neg = sample.get("negative_constraints") or {}
        if neg.get("has_negative_constraint") and not nonempty_list(parsed.get("cons")):
            return "missing_cons"
    return None


def detect_correction_need_observable(parsed: dict, user_query: str, ctx: dict, kb: dict):
    """Tín hiệu quan sát thực tế tại runtime (KHÔNG DÙNG NHÃN KIỂM THỬ)"""
    if not parsed or not isinstance(parsed, dict):
        return None
    rec = parsed.get("recommended_item_id")
    null_rec = is_null(rec)
    rec_s = None if null_rec else str(rec).strip()
    rejected = as_bool(parsed.get("is_out_of_catalog_rejected", False))
    cons = parsed.get("cons")
    cons_ne = nonempty_list(cons)
    is_place = is_placeholder_cons(cons)
    resp_text = str(parsed.get("response_to_user", "")).lower()

    # Tín hiệu 1: Ngữ cảnh RAG có review xấu nhưng cons rỗng hoặc dùng placeholder
    if ctx.get("neg_n", 0) > 0 and (not cons_ne or is_place):
        return "missing_cons"

    # Tín hiệu 2: Văn bản từ chối nhưng cờ boolean OOC chưa bật hoặc vẫn gợi ý ASIN
    ooc_keywords = ["không thuộc", "ngoài phạm vi", "không có sản phẩm", "không bán", "không tìm thấy", "chỉ tư vấn", "từ chối"]
    if any(w in resp_text for w in ooc_keywords):
        if null_rec or (rec_s and rec_s not in ctx.get("asins", [])):
            if not rejected or not null_rec:
                return "ooc_not_rejected"
        else:
            if rejected:
                return "incatalog_contradiction"

    # Tín hiệu 3: Mâu thuẫn gợi ý sản phẩm trong danh mục nhưng lại bật cờ từ chối OOC
    if rec_s and rec_s in ctx.get("asins", []) and rejected:
        return "incatalog_contradiction"

    return None


def run_verifier(parsed: dict, reason: str, user_query: str, ctx_neg_text: str, model_name: str, cfg: dict, timeout: int, ctx_asins: list = None):
    if reason == "ooc_not_rejected":
        critique = f"""CẢNH BÁO TỰ KIỂM TRA (SELF-CORRECTION):
Câu hỏi của khách hàng: "{user_query}" là yêu cầu NGOÀI PHẠM VI hoặc SẢN PHẨM KHÔNG CÓ TRONG KHO.
Bạn tuyệt đối KHÔNG ĐƯỢC gợi ý sản phẩm bịa đặt.
Hãy sửa lại: "recommended_item_id": null, "is_out_of_catalog_rejected": true, và viết lại "response_to_user" từ chối lịch sự, trung thực. Trả về JSON."""
    elif reason == "missing_cons":
        critique = f"""CẢNH BÁO TỰ KIỂM TRA (SELF-CORRECTION):
Sản phẩm này có phản hồi tiêu cực thực tế từ người dùng:
"{ctx_neg_text[:400]}"
Câu trả lời hiện chưa nêu nhược điểm (cons). Hãy cập nhật mảng "cons" bám theo phản hồi trên và bổ sung cảnh báo khách quan vào "response_to_user". Trả về JSON."""
    elif reason == "incatalog_contradiction":
        critique = f"""CẢNH BÁO TỰ KIỂM TRA (SELF-CORRECTION):
Bạn đã gợi ý sản phẩm phù hợp trong danh mục nhưng lại đặt "is_out_of_catalog_rejected": true.
Vì câu hỏi thuộc ngành mỹ phẩm và đã có sản phẩm trong danh mục, hãy sửa lại: "is_out_of_catalog_rejected": false. Trả về JSON."""
    else:
        return parsed, False, 0.0, None

    r = query_model(model_name, v2.VERIFIER_SYSTEM, critique, cfg, timeout=40)
    fixed = extract_json(r["text"]) if r["status"] == "OK" else None
    if fixed:
        merged = dict(parsed)
        # Giới hạn trường được sửa theo đúng loại lỗi (tránh phá hủy trường đã đúng sẵn)
        if reason == "missing_cons":
            allowed_keys = ["cons", "response_to_user"]
        elif reason == "incatalog_contradiction":
            allowed_keys = ["is_out_of_catalog_rejected", "response_to_user"]
        elif reason == "ooc_not_rejected":
            allowed_keys = ["recommended_item_id", "is_out_of_catalog_rejected", "response_to_user"]
        else:
            allowed_keys = MERGE_KEYS

        for k in allowed_keys:
            if k in fixed:
                merged[k] = fixed[k]

        # ĐIỀU KIỆN "KHÔNG GÂY HỒI QUY" (NO-REGRESSION CONSTRAINT):
        # 1. Nếu ban đầu đã có ASIN nằm trong danh mục (in-catalog), Verifier không được phép làm mất ASIN
        #    hoặc bật cờ từ chối (trừ khi chính lý do gọi Verifier là ooc_not_rejected).
        prev_rec = parsed.get("recommended_item_id")
        ctx_asins = ctx_asins or []
        if prev_rec and str(prev_rec).strip() in ctx_asins and reason != "ooc_not_rejected":
            if is_null(merged.get("recommended_item_id")) or as_bool(merged.get("is_out_of_catalog_rejected")):
                # Hồi quy nghiêm trọng -> Bác bỏ kết quả sửa của Verifier
                return parsed, False, r["latency_ms"], r["text"]

        if reason == "ooc_not_rejected":
            ok = as_bool(merged.get("is_out_of_catalog_rejected")) and is_null(merged.get("recommended_item_id"))
        elif reason == "missing_cons":
            ok = nonempty_list(merged.get("cons")) and not is_placeholder_cons(merged.get("cons"))
        elif reason == "incatalog_contradiction":
            ok = not as_bool(merged.get("is_out_of_catalog_rejected"))
        else:
            ok = True
        if ok:
            return merged, True, r["latency_ms"], r["text"]
    return parsed, False, r["latency_ms"], r["text"]


JUDGE_SYSTEM = "Bạn là giám khảo khách quan đánh giá chất lượng tư vấn thương mại điện tử. Chỉ trả về JSON."


def judge_cons_grounded(judge_model: str, c_neg_text: str, final: dict, jcfg: dict):
    prompt = f"""Phản hồi tiêu cực thực tế của khách hàng cũ:
"{c_neg_text}"

Các nhược điểm/cảnh báo mà trợ lý đã nêu:
{json.dumps(final.get('cons'), ensure_ascii=False)}
Lời tư vấn: "{str(final.get('response_to_user', ''))[:400]}"

Câu hỏi: các nhược điểm/cảnh báo trên có phản ánh đúng vấn đề nêu trong phản hồi tiêu cực không (không bịa thêm, không chung chung)?
Trả về DUY NHẤT JSON: {{"covers": true hoặc false}}"""
    r = query_model(judge_model, JUDGE_SYSTEM, prompt, jcfg, timeout=40)
    obj = extract_json(r["text"]) if r["status"] == "OK" else None
    if obj is None or "covers" not in obj:
        return None
    return bool(obj["covers"])


# ==============================================================================
# 6. SUMMARIZE & TABLES
# ==============================================================================
BOOL_COLS = [
    "api_error", "parse_fail", "json_valid", "hallu_asin", "hallu_attr",
    "brand_mismatch", "price_mismatch", "rec_outside_context", "unsupported_rec",
    "rec_is_gold", "ooc_wrong_rec", "ooc_correct", "false_refusal", "cons_nonempty",
    "cons_empty", "cons_placeholder", "cons_real", "pros_cons_balanced", "cons_missing",
    "cneg_cons_real", "cneg_cons_placeholder", "cneg_cons_empty",
    "std_cons_empty", "std_cons_placeholder", "std_cons_hallu_real",
    "rule_repaired", "rule_recover_asin", "rule_ooc_flag", "rule_extract_pros_cons", "rule_fill_brand_price", "rule_cons_clean_standard",
    "needs_correction", "verifier_triggered", "verifier_false_alarm", "verifier_success",
    "hallucination_any", "rec_nonnull",
    "neg_rag_correct", "neg_rag_hallu_gold", "neg_rag_picked_decoy", "neg_rag_hallu_random",
    "pre_false_refusal", "pre_ooc_correct", "pre_ooc_wrong_rec", "pre_hallucination_any",
    "pre_pros_cons_balanced", "pre_cons_nonempty",
    "pre_cneg_cons_real", "pre_cneg_cons_placeholder", "pre_cneg_cons_empty",
    "pre_std_cons_empty", "pre_std_cons_placeholder", "pre_std_cons_hallu_real"
]


def summarize(df: pd.DataFrame, meta: dict) -> dict:
    for c in BOOL_COLS:
        df[c] = df[c].fillna(False).astype(bool) if c in df.columns else False
    ok, t = ~df.api_error, df.test_type
    is_ooc, is_cn, in_cat = t == OOC, t == CNEG, t != OOC
    valid = ok & df.json_valid
    S = dict(meta)
    S["n_total"], S["n_api_error"] = int(len(df)), int(df.api_error.sum())
    S["parse_fail"] = _rate(df.parse_fail, ok)
    S["hallucination_any_pre"] = _rate(df.pre_hallucination_any, valid)
    S["hallucination_any_valid"] = _rate(df.hallucination_any, valid)
    S["hallu_asin_incatalog"] = _rate(df.hallu_asin, valid & in_cat)
    S["hallu_attr_incatalog"] = _rate(df.hallu_attr, valid & in_cat & df.rec_nonnull)
    S["unsupported_rec_incatalog"] = _rate(df.unsupported_rec, valid & in_cat)
    S["rec_is_gold_incatalog"] = _rate(df.rec_is_gold, valid & in_cat)
    S["ooc_correct_pre"] = _rate(df.pre_ooc_correct, ok & is_ooc)
    S["ooc_correct"] = _rate(df.ooc_correct, ok & is_ooc)
    S["ooc_wrong_rec"] = _rate(df.ooc_wrong_rec, valid & is_ooc)
    S["false_refusal_pre_incatalog"] = _rate(df.pre_false_refusal, valid & in_cat)
    S["false_refusal_incatalog"] = _rate(df.false_refusal, valid & in_cat)

    # Tri-state cons metrics:
    S["cneg_cons_real_pre"] = _rate(df.pre_cneg_cons_real, valid & is_cn)
    S["cneg_cons_real"] = _rate(df.cneg_cons_real, valid & is_cn)
    S["cneg_cons_placeholder"] = _rate(df.cneg_cons_placeholder, valid & is_cn)
    S["cneg_cons_empty"] = _rate(df.cneg_cons_empty, valid & is_cn)

    S["std_cons_empty"] = _rate(df.std_cons_empty, valid & in_cat & ~is_cn)
    S["std_cons_placeholder"] = _rate(df.std_cons_placeholder, valid & in_cat & ~is_cn)
    S["std_cons_hallu_real_pre"] = _rate(df.pre_std_cons_hallu_real, valid & in_cat & ~is_cn)
    S["std_cons_hallu_real"] = _rate(df.std_cons_hallu_real, valid & in_cat & ~is_cn)

    S["pros_cons_balanced_pre"] = _rate(df.pre_pros_cons_balanced, ok & in_cat)
    S["pros_cons_balanced_incatalog"] = _rate(df.pros_cons_balanced, ok & in_cat)
    judged = ok & is_cn & df.cons_grounded.notna()
    S["cons_grounded_cneg"] = _rate(df.cons_grounded.fillna(False).astype(bool), judged)

    # Rule repair rates (Overall & Sub-rules)
    S["rule_repair_rate"] = _rate(df.rule_repaired, valid)
    S["rule_recover_asin_rate"] = _rate(df.rule_recover_asin, valid)
    S["rule_ooc_flag_rate"] = _rate(df.rule_ooc_flag, valid)
    S["rule_extract_pros_cons_rate"] = _rate(df.rule_extract_pros_cons, valid)
    S["rule_fill_brand_price_rate"] = _rate(df.rule_fill_brand_price, valid)
    S["rule_cons_clean_standard_rate"] = _rate(df.rule_cons_clean_standard, valid)

    # Verifier rates
    S["verifier_needed"] = _rate(df.needs_correction, valid)
    S["verifier_triggered"] = _rate(df.verifier_triggered, ok)
    S["verifier_false_alarm"] = _rate(df.verifier_false_alarm, ok & in_cat & ~is_cn)
    S["verifier_success_given_triggered"] = _rate(df.verifier_success, ok & df.verifier_triggered)

    if meta.get("negative_rag"):
        S["neg_rag_correct_refusal"] = _rate(df.neg_rag_correct, valid & in_cat)
        S["neg_rag_hallu_gold"] = _rate(df.neg_rag_hallu_gold, valid & in_cat)
        S["neg_rag_picked_decoy"] = _rate(df.neg_rag_picked_decoy, valid & in_cat)
        S["neg_rag_hallu_random"] = _rate(df.neg_rag_hallu_random, valid & in_cat)
    lat = df.loc[ok]
    for name, col in (("latency_first_call_ms", "latency_ms"), ("latency_total_ms", "total_latency_ms")):
        S[name] = {"mean": round(float(lat[col].mean()), 1) if len(lat) else None,
                   "p95": round(float(lat[col].quantile(0.95)), 1) if len(lat) else None}
    tok = df.loc[ok, "total_tokens"].dropna()
    S["tokens_total_mean"] = round(float(tok.mean()), 1) if len(tok) else None
    return S


def _fmt(r):
    if not r or r["n"] == 0:
        return "n/a"
    return f'{r["pct"]:5.1f}%  ({r["k"]}/{r["n"]})  CI95 [{r["ci95"][0]}, {r["ci95"][1]}]'


def print_summary(S: dict):
    print("\n" + "=" * 90)
    print(f'{S["model"]} | {S["config"]} | components={S["components"]} | k={S["k"]} neg_r={S["neg_r"]} '
          f'ooc_context={S["ooc_context"]}')
    print(f'model_id_used={S["model_id_used"]}  temp={S["temperature"]}  max_tokens={S["max_tokens"]}  '
          f'seed={S["seed"]}  prompt_version={S["prompt_version"]}  rule_repair={S["rule_repair"]}  '
          f'verifier_mode={S.get("verifier_mode")}')
    print(f'N={S["n_total"]}  api_error={S["n_api_error"]} (loại khỏi mẫu số)')
    print("-" * 90)
    for label, key in [
        ("Lỗi parse JSON", "parse_fail"),
        ("Ảo giác tổng hợp (SAU sửa)", "hallucination_any_valid"),
        ("  - Ảo giác TRƯỚC sửa", "hallucination_any_pre"),
        ("  - ASIN không có trong KB (mẫu trong danh mục)", "hallu_asin_incatalog"),
        ("  - Sai brand/giá so với KB", "hallu_attr_incatalog"),
        ("Gợi ý không có trong ngữ cảnh/KB", "unsupported_rec_incatalog"),
        ("Chọn đúng sản phẩm đích (gold)", "rec_is_gold_incatalog"),
        ("OOC: từ chối đúng (SAU sửa)", "ooc_correct"),
        ("  - OOC từ chối đúng (TRƯỚC sửa)", "ooc_correct_pre"),
        ("OOC: gợi ý sai", "ooc_wrong_rec"),
        ("Từ chối nhầm (SAU sửa, in-catalog)", "false_refusal_incatalog"),
        ("  - Từ chối nhầm (TRƯỚC sửa)", "false_refusal_pre_incatalog"),
        ("C_neg: có nhược điểm THỰC TẾ (cons_real)", "cneg_cons_real"),
        ("  - C_neg cons_real (TRƯỚC sửa)", "cneg_cons_real_pre"),
        ("  - C_neg dùng placeholder", "cneg_cons_placeholder"),
        ("  - C_neg bỏ trống cons (empty)", "cneg_cons_empty"),
        ("C_neg: cons bám C_neg (judge)", "cons_grounded_cneg"),
        ("Standard: dùng placeholder (chuẩn v1.2)", "std_cons_placeholder"),
        ("Standard: bỏ trống cons (empty)", "std_cons_empty"),
        ("Standard: tự bịa nhược điểm (ảo giác cons)", "std_cons_hallu_real"),
        ("  - Standard ảo giác cons (TRƯỚC sửa)", "std_cons_hallu_real_pre"),
        ("Pros&Cons cân bằng (in-catalog)", "pros_cons_balanced_incatalog"),
        ("  - Pros&Cons (TRƯỚC sửa)", "pros_cons_balanced_pre"),
        ("Tỷ lệ mẫu được sửa bởi luật (Rule Repair)", "rule_repair_rate"),
        ("  - Luật 1: Khôi phục ASIN", "rule_recover_asin_rate"),
        ("  - Luật 2: Sửa cờ OOC", "rule_ooc_flag_rate"),
        ("  - Luật 3: Trích xuất pros/cons", "rule_extract_pros_cons_rate"),
        ("  - Luật 4: Điền brand/price từ KB", "rule_fill_brand_price_rate"),
        ("  - Luật 5: Chuẩn hóa cons Standard (L5)", "rule_cons_clean_standard_rate"),
        ("Verifier cần can thiệp", "verifier_needed"),
        ("Verifier kích hoạt (triggered)", "verifier_triggered"),
        ("Verifier báo động nhầm (false alarm)", "verifier_false_alarm"),
        ("Verifier sửa thành công", "verifier_success_given_triggered"),
    ]:
        print(f"  {label:<52} {_fmt(S.get(key))}")
    print(f'  Độ trễ lần gọi chính  mean={S["latency_first_call_ms"]["mean"]}  p95={S["latency_first_call_ms"]["p95"]} ms')
    print(f'  Độ trễ TỔNG           mean={S["latency_total_ms"]["mean"]}  p95={S["latency_total_ms"]["p95"]} ms')
    if S.get("negative_rag"):
        print("  --- KẾT QUẢ NEGATIVE RAG (RETRIEVAL FAILURE) ---")
        print(f"  {'Từ chối đúng khi truy xuất thiếu (không bịa)':<52} {_fmt(S.get('neg_rag_correct_refusal'))}")
        print(f"  {'Ảo giác ASIN gold (không có trong context)':<52} {_fmt(S.get('neg_rag_hallu_gold'))}")
        print(f"  {'Gợi ý nhầm sản phẩm nhiễu (decoy)':<52} {_fmt(S.get('neg_rag_picked_decoy'))}")
        print(f"  {'Ảo giác ASIN ngẫu nhiên':<52} {_fmt(S.get('neg_rag_hallu_random'))}")


def resolve_components(config, components_arg=None, no_verifier=False):
    if components_arg:
        comps = [c.strip() for c in components_arg.split(",") if c.strip()]
        for c in comps:
            if c not in ALL_COMPONENTS:
                raise ValueError(f"Unknown component: {c}. Allowed: {ALL_COMPONENTS}")
        label = "custom_" + "_".join(comps)
    else:
        if config not in PRESETS:
            raise ValueError(f"Unknown preset config: {config}. Allowed: {list(PRESETS)}")
        comps = list(PRESETS[config])
        label = config
    if no_verifier and "verifier" in comps:
        comps.remove("verifier")
        label += "_no_verifier"
    return comps, label


def load_neg_index(r: int) -> dict:
    if r <= 1:
        return {}
    path = os.path.join(DATA_DIR, "reviews_Beauty_5.json.gz")
    if not os.path.exists(path):
        print(f"⚠️ Không thấy {path}, bỏ qua neg_r > 1")
        return {}
    print(f"📦 Đang nạp tối đa {r} review 1-2 sao/sản phẩm từ {path}...")
    import gzip
    idx = {}
    for line in gzip.open(path, "rt", encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if float(d.get("overall", 5.0)) <= 2.0:
            asin = str(d.get("asin", "")).strip()
            txt = str(d.get("reviewText", "")).strip()
            if asin and len(txt) > 20:
                cur = idx.setdefault(asin, [])
                if len(cur) < r:
                    cur.append(txt[:300])
    print(f"   -> Đã lập chỉ mục cho {len(idx):,} sản phẩm có review tiêu cực")
    return idx


def spec_status(api_error, status, parse_fail, raw) -> str:
    if api_error:
        return status
    if not raw or not raw.strip():
        return "empty_response"
    return "json_parse_error" if parse_fail else "success"


# ==============================================================================
# 7. MAIN BENCHMARK LOOP
# ==============================================================================
def run_benchmark(model_name, comps, label, limit=None, k=5, neg_r=1, ooc_context="decoy", seed=42,
                  temperature=0.0, max_tokens=None, api_model_id=None, judge_model=None,
                  retry_errors=False, out_dir=None, kb=None, testset_file=None, timeout=60,
                  use_rule_repair=True, verifier_mode="observable", negative_rag=False,
                  prompt_version="v1.2", label_suffix="", reuse_raw_jsonl=None, overwrite=False):
    out_dir = out_dir or DEFAULT_OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    if label_suffix:
        label = f"{label}_{label_suffix}"
    if negative_rag:
        label += "_negrag"
    max_tokens = max_tokens or (1500 if "cot" in comps else 1024)
    safe = model_name.replace(":", "-").replace("/", "-")
    base = os.path.join(out_dir, f"{safe}_{label}")
    final_csv, partial_csv, jsonl, summ = base + ".csv", base + ".partial.csv", base + ".jsonl", base + ".summary.json"

    cached_raw = {}
    if reuse_raw_jsonl and os.path.exists(reuse_raw_jsonl):
        print(f"📦 Tái sử dụng raw LLM outputs từ: {reuse_raw_jsonl}")
        with open(reuse_raw_jsonl, encoding="utf-8") as f:
            for line in f:
                try:
                    c = json.loads(line)
                    cached_raw[c["sample_id"]] = c
                except Exception:
                    pass
        print(f"   -> Đã nạp {len(cached_raw)} mẫu thô.")

    if overwrite:
        for p in (final_csv, partial_csv, jsonl, summ):
            if os.path.exists(p):
                os.remove(p)

    print("=" * 90)
    print(f"🚀 [Runner v4] {model_name} | {label} | {comps} | k={k} neg_r={neg_r} seed={seed} "
          f"prompt={prompt_version} rule_repair={use_rule_repair} verifier_mode={verifier_mode} "
          f"negative_rag={negative_rag}")
    print(f"📁 Dataset: {testset_file or 'benchmark_test_500.json'}")
    if reuse_raw_jsonl:
        print(f"📦 Raw cache: {reuse_raw_jsonl}")
    print("=" * 90)

    dataset_path = testset_file or os.path.join(DATA_DIR, "benchmark_test_500.json")
    with open(dataset_path, encoding="utf-8") as f:
        samples = json.load(f)
    if limit:
        samples = samples[:limit]
    kb = kb if kb is not None else load_real_kb()
    decoy_keys = sorted(kb.keys())
    neg_index = load_neg_index(neg_r) if neg_r > 1 else {}

    cfg = {"temperature": temperature, "max_tokens": max_tokens, "seed": seed, "api_model_id": api_model_id}
    jcfg = {"temperature": 0.0, "max_tokens": 150, "seed": seed}

    records = []
    for path in (partial_csv, final_csv):
        if os.path.exists(path):
            try:
                records = pd.read_csv(path).to_dict("records")
                print(f"🔄 Nạp {len(records)} dòng từ {os.path.basename(path)}")
                break
            except Exception as e:
                print(f"Lỗi nạp {path}: {e}")
    if retry_errors and records:
        n0 = len(records)
        records = [r for r in records if str(r.get("status")) == "OK"]
        print(f"🔁 --retry_errors: bỏ {n0 - len(records)} dòng lỗi API để chạy lại")
    done_ids = {r["sample_id"] for r in records}
    model_ids = set()

    for idx, sample in enumerate(tqdm(samples, desc=f"[{model_name}|{label}]")):
        sid = sample.get("sample_id", idx + 1)
        if sid in done_ids:
            continue
        t_type = sample.get("test_type")
        user_query = sample.get("user_query", "")
        ctx = build_context(sample, kb, k, neg_r, neg_index, decoy_keys, ooc_context, seed, negative_rag=negative_rag)
        sys_p, usr_p = build_prompts(sample, comps, ctx, prompt_version=prompt_version)

        if sid in cached_raw:
            c = cached_raw[sid]
            r = {
                "status": "OK" if c.get("status") in ["OK", "success"] else c.get("status", "OK"),
                "text": c.get("raw_output", ""),
                "latency_ms": c.get("latency_ms", 0.0),
                "usage": c.get("token_usage", {"total_tokens": 0}),
                "model_id": c.get("model", model_name)
            }
        else:
            r = query_model(model_name, sys_p, usr_p, cfg, timeout=timeout)
        model_ids.add(r["model_id"])
        api_error = r["status"] != "OK"
        parsed = extract_json(r["text"]) if not api_error else None
        parse_fail = bool(not api_error and parsed is None)
        json_valid = bool(not api_error and parsed is not None)

        row = {"sample_id": sid, "model": model_name, "config": label, "test_type": t_type,
               "status": r["status"], "api_error": api_error, "model_id_used": r["model_id"],
               "parse_fail": parse_fail, "json_valid": json_valid, "latency_ms": r["latency_ms"],
               "verifier_latency_ms": 0.0, "context_n": len(ctx["asins"]), "neg_review_n": ctx["neg_n"],
               "total_tokens": r["usage"]["total_tokens"], "rule_repaired": False,
               "rule_repair_actions": ""}

        reason, final, v_raw, trig, succ = None, {}, None, False, False
        ev_pre = ev = None
        rule_subrules = {
            "rule_recover_asin": False,
            "rule_ooc_flag": False,
            "rule_extract_pros_cons": False,
            "rule_fill_brand_price": False,
            "rule_cons_clean_standard": False
        }
        verifier_false_alarm = False

        if json_valid:
            ev_pre = evaluate(parsed, sample, kb, ctx["asins"], negative_rag=negative_rag)
            final = parsed

            # BƯỚC 1: RULE-BASED PARSER REPAIR (0ms)
            if use_rule_repair:
                repaired, was_repaired, actions, subrules = rule_based_repair(
                    parsed, user_query, kb, ctx["asins"],
                    ctx_neg_n=ctx["neg_n"], negative_rag=negative_rag
                )
                if was_repaired:
                    final = repaired
                    row["rule_repaired"] = True
                    row["rule_repair_actions"] = "; ".join(actions)
                    rule_subrules.update(subrules)

            # BƯỚC 2: KIỂM TRA XEM CÒN CẦN VERIFIER LLM HAY KHÔNG
            if verifier_mode == "oracle":
                reason = detect_correction_need_oracle(final, sample)
            else:
                reason = detect_correction_need_observable(final, user_query, ctx, kb)

            if reason and "verifier" in comps and not negative_rag:
                # LLM Verifier lượt 2 chỉ gọi khi luật không xử lý được
                trig = True
                final, succ, v_lat, v_raw = run_verifier(
                    final, reason, user_query, ctx.get("neg_text", ""), model_name, cfg, timeout, ctx_asins=ctx["asins"]
                )
                row["verifier_latency_ms"] = v_lat
                if t_type != OOC and t_type != CNEG and not ev_pre["false_refusal"]:
                    verifier_false_alarm = True

            ev = evaluate(final, sample, kb, ctx["asins"], negative_rag=negative_rag)

            row.update({
                "pre_rec_id": ev_pre["rec_id_raw"],
                "pre_rejected": ev_pre["rejected_raw"],
                "pre_false_refusal": ev_pre["false_refusal"],
                "pre_ooc_correct": ev_pre["ooc_correct"],
                "pre_ooc_wrong_rec": ev_pre["ooc_wrong_rec"],
                "pre_hallucination_any": ev_pre["hallucination_any"],
                "pre_pros_cons_balanced": ev_pre["pros_cons_balanced"],
                "pre_cons_nonempty": ev_pre["cons_nonempty"],
                "pre_cneg_cons_real": ev_pre["cneg_cons_real"],
                "pre_cneg_cons_placeholder": ev_pre["cneg_cons_placeholder"],
                "pre_cneg_cons_empty": ev_pre["cneg_cons_empty"],
                "pre_std_cons_empty": ev_pre["std_cons_empty"],
                "pre_std_cons_placeholder": ev_pre["std_cons_placeholder"],
                "pre_std_cons_hallu_real": ev_pre["std_cons_hallu_real"],
            })

        row.update(rule_subrules)
        row["total_latency_ms"] = round(row["latency_ms"] + row["verifier_latency_ms"], 2)
        row.update({"needs_correction": reason is not None, "correction_reason": reason,
                    "verifier_triggered": trig, "verifier_success": succ,
                    "verifier_false_alarm": verifier_false_alarm,
                    "cons_nonempty_pre": bool(ev_pre["cons_nonempty"]) if ev_pre else False,
                    "cons_grounded": None})
        if ev:
            row.update(ev)
            neg = sample.get("negative_constraints", {}) or {}
            if judge_model and t_type == CNEG and ev["cons_nonempty"] and neg.get("c_neg_text"):
                row["cons_grounded"] = judge_cons_grounded(judge_model, neg["c_neg_text"], final, jcfg)
            row["hallucination_any"] = bool(ev["hallu_asin"] or ev["hallu_attr"] or ev["ooc_wrong_rec"] or
                                            ev.get("neg_rag_hallu_gold") or ev.get("neg_rag_hallu_random"))
        row["response_snippet"] = str(final.get("response_to_user", ""))[:120] if final else ""
        records.append(row)

        rec = {"sample_id": sid, "model": model_name, "config": label,
               "timestamp": datetime.now(tz=TZ).isoformat(),
               "prompt": {"system": sys_p, "user": usr_p},
               "context": {"catalog_asins": ctx["asins"], "gold_asin": ctx["gold_id"],
                           "neg_review_n": ctx["neg_n"]},
               "raw_output": r["text"], "parsed_json": parsed, "latency_ms": r["latency_ms"],
               "token_usage": r["usage"], "status": spec_status(api_error, r["status"], parse_fail, r["text"]),
               "error": r["status"] if api_error else None,
               "rule_repair": {"applied": row["rule_repaired"], "actions": row["rule_repair_actions"], "subrules": rule_subrules},
               "verifier": {"reason": reason, "triggered": trig, "success": succ, "raw": v_raw, "false_alarm": verifier_false_alarm}}
        with open(jsonl, "a", encoding="utf-8") as fj:
            fj.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if len(records) % 10 == 0:
            pd.DataFrame(records).to_csv(partial_csv, index=False)

    df = pd.DataFrame(records)
    df.to_csv(final_csv, index=False)
    if os.path.exists(partial_csv):
        os.remove(partial_csv)
    meta = {"model": model_name, "config": label, "components": comps,
            "model_id_used": sorted(str(m) for m in (model_ids or set(df["model_id_used"].unique()))),
            "temperature": temperature, "max_tokens": max_tokens, "seed": seed, "k": k, "neg_r": neg_r,
            "ooc_context": ooc_context, "prompt_version": prompt_version, "judge_model": judge_model,
            "rule_repair": use_rule_repair, "verifier_mode": verifier_mode,
            "negative_rag": negative_rag, "dataset": os.path.basename(dataset_path)}
    S = summarize(df, meta)
    with open(summ, "w", encoding="utf-8") as f:
        json.dump(S, f, ensure_ascii=False, indent=2)
    print_summary(S)
    return S


def make_table(out_dir: str, models: list) -> str:
    cols = ["hallucination_any_valid", "ooc_correct", "false_refusal_incatalog",
            "cneg_cons_real", "pros_cons_balanced_incatalog", "rec_is_gold_incatalog"]
    headers = ["Config", "Ảo giác↓", "Chặn OOC↑", "Từ chối nhầm↓", "C_neg cons↑", "Pros&Cons↑", "Chọn gold↑", "P95 ms↓"]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for m in models:
        lines.append(f"| **{m}** |" + " |" * (len(headers) - 1))
        safe = m.replace(":", "-").replace("/", "-")
        for cfg in PRESETS:
            p = os.path.join(out_dir, f"{safe}_{cfg}.summary.json")
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as f:
                S = json.load(f)
            cells = []
            for c in cols:
                r = S.get(c)
                cells.append(f'{r["pct"]:.1f}%' if r and r["n"] else "n/a")
            lines.append(f"| {cfg} | " + " | ".join(cells) + f' | {S["latency_total_ms"]["p95"]} |')
    return "\n".join(lines)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Ablation runner v4 (Prompt v1.2 + Rule Repair + Verifier)")
    p.add_argument("--model", default="qwen2.5:3b")
    p.add_argument("--config", default="A6", choices=list(PRESETS))
    p.add_argument("--components", default=None)
    p.add_argument("--no_verifier", action="store_true")
    p.add_argument("--no_rule_repair", action="store_true")
    p.add_argument("--prompt_version", choices=["v1.1", "v1.2"], default="v1.2", help="phiên bản prompt")
    p.add_argument("--verifier_mode", choices=["observable", "oracle"], default="observable",
                   help="chế độ trigger cho Verifier: observable (thực tế triển khai) hoặc oracle (cận trên lý thuyết)")
    p.add_argument("--label_suffix", default="", help="hậu tố ghi chú thêm cho config label")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--neg_r", type=int, default=1)
    p.add_argument("--ooc_context", choices=["decoy", "zero"], default="decoy")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max_tokens", type=int, default=None)
    p.add_argument("--api_model_id", default=None)
    p.add_argument("--judge_model", default=None)
    p.add_argument("--retry_errors", action="store_true")
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--out_dir", default=None)
    p.add_argument("--testset_file", default=None, help="đường dẫn file testset json")
    p.add_argument("--reuse_raw_jsonl", default=None, help="đường dẫn file .jsonl chứa kết quả thô LLM lần gọi 1 để tái sử dụng")
    p.add_argument("--overwrite", action="store_true", help="ghi đè kết quả nếu file đã tồn tại")
    p.add_argument("--negative_rag", action="store_true", help="chạy chế độ Retrieval Failure (không đưa sản phẩm đúng vào context)")
    p.add_argument("--table", action="store_true")
    p.add_argument("--models", nargs="+", default=None)
    return p.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    if a.table:
        print(make_table(a.out_dir or DEFAULT_OUT_DIR, a.models or [a.model]))
        sys.exit(0)
    comps, label = resolve_components(a.config, a.components, a.no_verifier)
    run_benchmark(a.model, comps, label, limit=a.limit, k=a.k, neg_r=a.neg_r, ooc_context=a.ooc_context,
                  seed=a.seed, temperature=a.temperature, max_tokens=a.max_tokens,
                  api_model_id=a.api_model_id, judge_model=a.judge_model, retry_errors=a.retry_errors,
                  out_dir=a.out_dir, testset_file=a.testset_file, timeout=a.timeout,
                  use_rule_repair=not a.no_rule_repair, verifier_mode=a.verifier_mode,
                  negative_rag=a.negative_rag, prompt_version=a.prompt_version,
                  label_suffix=a.label_suffix, reuse_raw_jsonl=a.reuse_raw_jsonl,
                  overwrite=a.overwrite)
