"""
benchmark_runner_ablation_v3.py  -  runner ablation theo ablation_spec v1.1

Đặt CẠNH benchmark_runner_4pillars_v2.py trong amazon_benchmark/ (file này import các hàm dùng chung từ v2).

THIẾT KẾ (đã chốt trong spec v1.1)
  * MỘT schema JSON thống nhất cho MỌI cấu hình (schema là "thước đo", không phải biến thí nghiệm).
    Ngữ nghĩa (khi nào từ chối, phải nêu nhược điểm...) chỉ đến từ các thành phần prompt.
  * Các cấu hình CỘNG DỒN:
      A0 naive (KHÔNG có system prompt) | A1 +profile | A2 +rag | A3 +cneg | A4 +cot
      A5 +selfcheck (checklist tự kiểm tra trong prompt) | A6 +verifier (lượt gọi sửa lỗi thứ hai) = khung đầy đủ
  * Ngữ cảnh: sản phẩm ĐÚNG + (k-1) sản phẩm gây nhiễu (--k 5). Mẫu OOC nhận k sản phẩm nhiễu thay vì
    thông báo "0 kết quả" (tránh rò rỉ đáp án).  --k 1 --ooc_context zero  = hành vi cũ (oracle).
    LƯU Ý: đây vẫn là ngữ cảnh "oracle + nhiễu ngẫu nhiên", CHƯA phải truy xuất thật (BM25/embedding).
  * C_neg: mặc định chỉ review trong mẫu test (--neg_r 1). --neg_r 10 nạp tối đa 10 review 1-2 sao/sản phẩm
    từ data/reviews_Beauty_5.json.gz (tải bởi load_amazon_data.py).
  * Log theo spec: <model>_<config>.jsonl (prompt đầy đủ, context, token_usage, timestamp, status), kèm .csv và .summary.json.

VÍ DỤ
  python benchmark_runner_ablation_v3.py --model gpt-4o-mini --config A0 --limit 10
  for c in A0 A1 A2 A3 A4 A5 A6; do python benchmark_runner_ablation_v3.py --model qwen2.5:3b --config $c --judge_model gpt-4o-mini; done
  python benchmark_runner_ablation_v3.py --table --models gpt-4o-mini qwen2.5:3b
"""
import os
import sys
import re
import json
import math
import time
import hashlib
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

DEFAULT_OUT_DIR = os.path.join(HERE, "results_ablation")
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
# 1. GATEWAY  ->  dict(text, latency_ms, status, model_id, usage)
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
            res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers,
                                json=payload, timeout=timeout)
            if res.status_code == 200:
                body = res.json()
                u = body.get("usage", {}) or {}
                return done(text=body["choices"][0]["message"]["content"] or "",
                            model_id=body.get("model", out["model_id"]),
                            usage={"prompt_tokens": u.get("prompt_tokens"),
                                   "completion_tokens": u.get("completion_tokens"),
                                   "total_tokens": u.get("total_tokens")})
            return done(status=f"HTTP_{res.status_code}")

        else:  # Ollama
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
# 2. PROMPT: các khối ghép theo thành phần
# ==============================================================================
PROFILE_BLOCK = """Bạn là "BeautyAdvisor" — Chuyên viên Tư vấn Mua sắm Mỹ phẩm Khách quan của sàn thương mại điện tử Amazon Beauty.

PHẠM VI HOẠT ĐỘNG:
- Bạn CHỈ tư vấn sản phẩm Làm đẹp & Mỹ phẩm (chăm sóc da, trang điểm, chăm sóc tóc, nước hoa, chăm sóc cá nhân, dụng cụ làm đẹp).
- Nếu khách hỏi về mặt hàng ngoài phạm vi trên (ví dụ: điện tử, thời trang, đồ gia dụng) hoặc về sản phẩm không tồn tại, hãy lịch sự từ chối, đặt "is_out_of_catalog_rejected": true và "recommended_item_id": null.

RÀNG BUỘC BẮT BUỘC:
1. TUYỆT ĐỐI không bịa đặt tên sản phẩm, mã ASIN, thương hiệu, thành phần hoặc giá tiền không có trong thông tin được cung cấp.
2. Nếu không đủ thông tin để tư vấn chắc chắn, hãy nói thẳng là chưa đủ thông tin thay vì đoán.
3. Luôn cân bằng: khi tư vấn một sản phẩm, nêu cả ưu điểm lẫn nhược điểm/lưu ý.
4. Trả lời khách bằng ngôn ngữ của họ (mặc định tiếng Việt)."""

RAG_BLOCK = """DỮ LIỆU DANH MỤC (GROUNDING):
- CHỈ được gợi ý và nhắc tới sản phẩm có trong phần [DANH MỤC SẢN PHẨM]. Mã ASIN, thương hiệu và giá phải khớp 100% với danh mục.
- Nếu không có sản phẩm nào trong danh mục phù hợp với yêu cầu, hãy đặt "recommended_item_id": null và giải thích, không bịa sản phẩm."""

CNEG_BLOCK = """CÂN BẰNG ĐA CHIỀU (ĐÁNH GIÁ TIÊU CỰC):
- Với mỗi sản phẩm được gợi ý, BẮT BUỘC nêu ít nhất 1 nhược điểm/cảnh báo thực tế dựa trên [ĐÁNH GIÁ TIÊU CỰC TỪ NGƯỜI DÙNG].
- Nhược điểm phải là thông tin có thật từ đánh giá, không được tự sáng tác. Nếu không có đánh giá tiêu cực nào, hãy nói rõ là chưa ghi nhận phản hồi tiêu cực."""

COT_BLOCK = """QUY TRÌNH SUY LUẬN BẮT BUỘC (4 BƯỚC) — điền lần lượt vào các trường thought_1 ... thought_4 của JSON:
1. Phân tích ngữ cảnh & nhu cầu (loại da, mối quan tâm, ngân sách; yêu cầu có thuộc phạm vi không).
2. Đối soát danh mục: chỉ chọn sản phẩm thực sự phù hợp, chỉ từ [DANH MỤC SẢN PHẨM].
3. Cân bằng ưu/nhược điểm dựa trên đánh giá tiêu cực.
4. Quyết định: gợi ý hay từ chối, kèm lý do ngắn gọn."""

SELFCHECK_BLOCK = """TỰ KIỂM TRA TRƯỚC KHI TRẢ LỜI (bắt buộc):
[ ] Mã ASIN gợi ý (nếu có) có nằm trong [DANH MỤC SẢN PHẨM] không? Thương hiệu và giá có khớp danh mục không?
[ ] Nếu yêu cầu ngoài phạm vi: đã đặt is_out_of_catalog_rejected=true và recommended_item_id=null chưa?
[ ] Nếu có gợi ý: mảng "cons" có ít nhất 1 nhược điểm bám theo đánh giá tiêu cực chưa?
Nếu có điều kiện nào chưa đạt, hãy sửa lại rồi mới xuất JSON."""

BLOCKS = [("profile", PROFILE_BLOCK), ("rag", RAG_BLOCK), ("cneg", CNEG_BLOCK),
          ("cot", COT_BLOCK), ("selfcheck", SELFCHECK_BLOCK)]

COT_LINES = [
    '"thought_1_context": "phân tích nhu cầu và phạm vi yêu cầu"',
    '"thought_2_catalog_check": "đối soát với danh mục sản phẩm"',
    '"thought_3_pros_cons": "cân bằng ưu và nhược điểm"',
    '"thought_4_decision": "quyết định gợi ý hay từ chối, kèm lý do"',
]
SCHEMA_LINES = [
    '"response_to_user": "câu trả lời gửi khách hàng"',
    '"recommended_item_id": "mã ASIN của sản phẩm gợi ý, hoặc null nếu không gợi ý sản phẩm nào"',
    '"brand": "thương hiệu của sản phẩm được gợi ý, hoặc null"',
    '"price_usd": số (USD) của sản phẩm được gợi ý, hoặc null',
    '"is_out_of_catalog_rejected": true nếu bạn từ chối vì yêu cầu ngoài phạm vi của sàn, ngược lại false',
    '"pros": ["ưu điểm 1", "ưu điểm 2"]',
    '"cons": ["nhược điểm/cảnh báo 1"]',
]
ZERO_MSG = "[Hệ thống: tìm kiếm trong danh mục không trả về sản phẩm nào.]"


def schema_text(cot: bool) -> str:
    lines = (COT_LINES if cot else []) + SCHEMA_LINES
    return "{\n" + ",\n".join("  " + ln for ln in lines) + "\n}"


def _fmt_product(i: int, asin: str, p: dict) -> str:
    price = p.get("price")
    price_s = f"${price:.2f}" if isinstance(price, (int, float)) and price else "Chưa cập nhật"
    return (f"Sản phẩm {i}:\n- ASIN: {asin}\n- Tên: {p.get('title')}\n- Thương hiệu: {p.get('brand')}\n"
            f"- Danh mục: {p.get('categories')}\n- Giá: {price_s}\n"
            f"- Mô tả: {str(p.get('description', ''))[:300]}")


def build_context(sample: dict, kb: dict, k: int, neg_r: int, neg_index: dict,
                  decoy_keys: list, ooc_context: str, seed: int) -> dict:
    t, sid = sample.get("test_type"), sample.get("sample_id")
    gold = sample.get("ground_truth_target") or None
    gold_id = gold.get("item_id") if gold else None
    neg = sample.get("negative_constraints") or {}
    c_neg_text = neg.get("c_neg_text") if neg.get("has_negative_constraint") else None

    items, n_dec = [], 0
    if t != OOC and gold_id:
        items.append(gold_id)
        n_dec = max(0, k - 1)
    elif t == OOC and ooc_context == "decoy":
        n_dec = k
    rng = random.Random(f"{seed}-{sid}")
    tries = 0
    while n_dec > 0 and decoy_keys and tries < 100 * max(1, n_dec):
        tries += 1
        a = decoy_keys[rng.randrange(len(decoy_keys))]
        if a != gold_id and a not in items:
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
            neg_chunks.append(f"[{a} — {info.get('title', '')}]\n" +
                              "\n".join(f'Review {j + 1}: "{r}"' for j, r in enumerate(revs)))
            neg_n += len(revs)
    neg_text = "\n\n".join(neg_chunks) if neg_chunks else "(Không có đánh giá tiêu cực nào cho các sản phẩm trên.)"
    return {"asins": items, "catalog_text": catalog_text, "neg_text": neg_text,
            "neg_n": neg_n, "gold_id": gold_id}


def build_prompts(sample: dict, comps: list, ctx: dict) -> tuple:
    use = set(comps)
    blocks = [txt for name, txt in BLOCKS if name in use]
    system_prompt = "\n\n".join(blocks) if blocks else None      # A0: KHÔNG có system prompt

    parts = []
    if "rag" in use:
        parts.append(f"[DANH MỤC SẢN PHẨM]\n{ctx['catalog_text']}\n[/DANH MỤC SẢN PHẨM]")
    if "cneg" in use:
        parts.append(f"[ĐÁNH GIÁ TIÊU CỰC TỪ NGƯỜI DÙNG (1-2 sao)]\n{ctx['neg_text']}\n"
                     f"[/ĐÁNH GIÁ TIÊU CỰC TỪ NGƯỜI DÙNG]")
    parts.append(f'Khách hàng hỏi: "{sample.get("user_query", "")}"')
    parts.append("Chỉ trả về MỘT khối JSON hợp lệ theo cấu trúc sau, không thêm văn bản nào ngoài JSON:\n"
                 + schema_text("cot" in use))
    return system_prompt, "\n\n".join(parts)


def _prompt_version() -> str:
    try:
        src = inspect.getsource(build_prompts) + inspect.getsource(build_context)
    except Exception:
        src = "unknown"
    blob = "".join(t for _, t in BLOCKS) + "".join(COT_LINES) + "".join(SCHEMA_LINES) + src
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:8]


PROMPT_VERSION = _prompt_version()

# ==============================================================================
# 3. CHẤM ĐIỂM
# ==============================================================================
def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _to_float(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"\d+(?:\.\d+)?", str(v).replace(",", ""))
    return float(m.group(0)) if m else None


def brand_match(pred, cat) -> bool:
    p, c = _norm(pred), _norm(cat)
    if not p or not c or c in ("unknown", "nan", "none"):
        return True                       # không kiểm tra được -> không tính là sai
    return p == c or p in c or c in p     # khớp mềm (chuẩn hóa + chứa nhau)


def evaluate(parsed: dict, sample: dict, kb: dict, ctx_asins: list) -> dict:
    t = sample.get("test_type")
    gold_id = (sample.get("ground_truth_target") or {}).get("item_id")
    rec = parsed.get("recommended_item_id")
    null_rec = is_null(rec)
    rec_s = None if null_rec else str(rec).strip()
    rejected = as_bool(parsed.get("is_out_of_catalog_rejected", False))
    pros_ne, cons_ne = nonempty_list(parsed.get("pros")), nonempty_list(parsed.get("cons"))
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
    return {
        "rec_id_raw": rec_s, "rejected_raw": rejected,
        "pros_nonempty": pros_ne, "cons_nonempty": cons_ne, "pros_cons_balanced": pros_ne and cons_ne,
        "hallu_asin": hallu_asin, "hallu_attr": brand_bad or price_bad,
        "brand_mismatch": brand_bad, "price_mismatch": price_bad,
        "rec_outside_context": outside_ctx,
        "unsupported_rec": hallu_asin or outside_ctx,
        "rec_is_gold": t != OOC and rec_s is not None and rec_s == gold_id,
        "ooc_wrong_rec": t == OOC and not null_rec,
        "ooc_correct": t == OOC and rejected and null_rec,
        "false_refusal": t != OOC and (rejected or null_rec),
        "cons_missing": t == CNEG and not cons_ne,
        "rec_nonnull": not null_rec,
    }


MERGE_KEYS = ["recommended_item_id", "brand", "price_usd", "is_out_of_catalog_rejected",
              "response_to_user", "pros", "cons"]


def run_verifier(parsed: dict, reason: str, sample: dict, model_name: str, cfg: dict, timeout: int):
    if reason == "ooc_not_rejected":
        critique = f"""CẢNH BÁO TỰ KIỂM TRA (SELF-CORRECTION):
Câu hỏi của khách hàng: "{sample.get('user_query')}" là yêu cầu NGOÀI PHẠM VI hoặc SẢN PHẨM KHÔNG CÓ TRONG KHO.
Bạn tuyệt đối KHÔNG ĐƯỢC gợi ý sản phẩm bịa đặt.
Hãy sửa lại: "recommended_item_id": null, "is_out_of_catalog_rejected": true, và viết lại "response_to_user" từ chối lịch sự, trung thực. Trả về JSON."""
    else:
        neg = sample.get("negative_constraints", {}) or {}
        critique = f"""CẢNH BÁO TỰ KIỂM TRA (SELF-CORRECTION):
Sản phẩm này có phản hồi tiêu cực thực tế (C_neg): "{neg.get('c_neg_text')}".
Câu trả lời hiện chưa nêu nhược điểm (cons). Hãy cập nhật mảng "cons" bám theo phản hồi trên và bổ sung cảnh báo khách quan vào "response_to_user". Trả về JSON."""
    r = query_model(model_name, v2.VERIFIER_SYSTEM, critique, cfg, timeout=40)
    fixed = extract_json(r["text"]) if r["status"] == "OK" else None
    if fixed:
        merged = dict(parsed)
        for k in MERGE_KEYS:
            if k in fixed:
                merged[k] = fixed[k]
        ok = (as_bool(merged.get("is_out_of_catalog_rejected")) and is_null(merged.get("recommended_item_id"))) \
            if reason == "ooc_not_rejected" else nonempty_list(merged.get("cons"))
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
    return as_bool(obj["covers"])


# ==============================================================================
# 4. TỔNG HỢP
# ==============================================================================
BOOL_COLS = ["json_valid", "api_error", "parse_fail", "hallu_asin", "hallu_attr", "rec_outside_context",
             "unsupported_rec", "rec_is_gold", "ooc_wrong_rec", "ooc_correct", "false_refusal", "cons_nonempty",
             "cons_nonempty_pre", "pros_cons_balanced", "cons_missing", "needs_correction",
             "verifier_triggered", "verifier_success", "hallucination_any", "rec_nonnull"]


def summarize(df: pd.DataFrame, meta: dict) -> dict:
    for c in BOOL_COLS:
        df[c] = df[c].fillna(False).astype(bool) if c in df.columns else False
    ok, t = ~df.api_error, df.test_type
    is_ooc, is_cn, in_cat = t == OOC, t == CNEG, t != OOC
    valid = ok & df.json_valid
    S = dict(meta)
    S["n_total"], S["n_api_error"] = int(len(df)), int(df.api_error.sum())
    S["parse_fail"] = _rate(df.parse_fail, ok)
    S["hallucination_any_valid"] = _rate(df.hallucination_any, valid)
    S["hallu_asin_incatalog"] = _rate(df.hallu_asin, valid & in_cat)
    S["hallu_attr_incatalog"] = _rate(df.hallu_attr, valid & in_cat & df.rec_nonnull)
    S["unsupported_rec_incatalog"] = _rate(df.unsupported_rec, valid & in_cat)
    S["rec_is_gold_incatalog"] = _rate(df.rec_is_gold, valid & in_cat)
    S["ooc_correct"] = _rate(df.ooc_correct, ok & is_ooc)
    S["ooc_wrong_rec"] = _rate(df.ooc_wrong_rec, valid & is_ooc)
    S["false_refusal_incatalog"] = _rate(df.false_refusal, valid & in_cat)
    S["cons_nonempty_cneg_pre"] = _rate(df.cons_nonempty_pre, ok & is_cn)
    S["cons_nonempty_cneg_final"] = _rate(df.cons_nonempty, ok & is_cn)
    S["pros_cons_balanced_incatalog"] = _rate(df.pros_cons_balanced, ok & in_cat)
    judged = ok & is_cn & df.cons_grounded.notna()
    S["cons_grounded_cneg"] = _rate(df.cons_grounded.fillna(False).astype(bool), judged)
    S["verifier_needed"] = _rate(df.needs_correction, valid)
    S["verifier_success_given_triggered"] = _rate(df.verifier_success, ok & df.verifier_triggered)
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
          f'seed={S["seed"]}  prompt_version={S["prompt_version"]}')
    print(f'N={S["n_total"]}  api_error={S["n_api_error"]} (loại khỏi mẫu số)')
    print("-" * 90)
    for label, key in [
        ("Lỗi parse JSON", "parse_fail"),
        ("Ảo giác tổng hợp (ASIN|thuộc tính|OOC gợi ý sai)", "hallucination_any_valid"),
        ("  - ASIN không có trong KB (mẫu trong danh mục)", "hallu_asin_incatalog"),
        ("  - Sai brand/giá so với KB", "hallu_attr_incatalog"),
        ("Gợi ý không có trong ngữ cảnh/KB", "unsupported_rec_incatalog"),
        ("Chọn đúng sản phẩm đích (gold)", "rec_is_gold_incatalog"),
        ("OOC: từ chối đúng", "ooc_correct"),
        ("OOC: gợi ý sai", "ooc_wrong_rec"),
        ("Từ chối nhầm (mẫu trong danh mục)", "false_refusal_incatalog"),
        ("C_neg: có cons TRƯỚC Verifier", "cons_nonempty_cneg_pre"),
        ("C_neg: có cons SAU Verifier", "cons_nonempty_cneg_final"),
        ("C_neg: cons bám C_neg (judge)", "cons_grounded_cneg"),
        ("Pros&Cons (mẫu trong danh mục)", "pros_cons_balanced_incatalog"),
        ("Verifier cần can thiệp", "verifier_needed"),
        ("Verifier sửa thành công", "verifier_success_given_triggered"),
    ]:
        print(f"  {label:<52} {_fmt(S[key])}")
    print(f'  Độ trễ lần gọi chính  mean={S["latency_first_call_ms"]["mean"]}  p95={S["latency_first_call_ms"]["p95"]} ms')
    print(f'  Độ trễ TỔNG           mean={S["latency_total_ms"]["mean"]}  p95={S["latency_total_ms"]["p95"]} ms')
    print("=" * 90)


# ==============================================================================
# 5. CHẠY BENCHMARK
# ==============================================================================
def resolve_components(config, components_arg=None, no_verifier=False):
    comps = [c.strip().lower() for c in components_arg.split(",") if c.strip()] if components_arg is not None \
        else list(PRESETS[config])
    bad = [c for c in comps if c not in ALL_COMPONENTS]
    if bad:
        raise ValueError(f"Thành phần không hợp lệ: {bad}. Hợp lệ: {ALL_COMPONENTS}")
    if no_verifier:
        comps = [c for c in comps if c != "verifier"]
    if "cneg" in comps and "rag" not in comps:
        raise ValueError("'cneg' cần 'rag'.")
    comps = [c for c in ALL_COMPONENTS if c in comps]
    label = next((k for k, v in PRESETS.items() if v == comps), None) or \
        "custom_" + ("+".join(comps) if comps else "none")
    return comps, label


def load_neg_index(r: int) -> dict:
    """asin -> tối đa r review 1-2 sao (cache pickle). Cần data/reviews_Beauty_5.json.gz."""
    cache = os.path.join(DATA_DIR, f"neg_index_r{r}.pkl")
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            return pickle.load(f)
    path = os.path.join(DATA_DIR, "reviews_Beauty_5.json.gz")
    if not os.path.exists(path):
        print(f"⚠️ Không thấy {path}; --neg_r chỉ dùng review có sẵn trong mẫu test.")
        return {}
    from load_amazon_data import parse_amazon_json
    idx = {}
    for d in parse_amazon_json(path):
        if float(d.get("overall", 5)) <= 2.0:
            a, txt = d.get("asin"), str(d.get("reviewText", "")).strip()[:300]
            if a and txt and len(idx.setdefault(a, [])) < r:
                idx[a].append(txt)
    with open(cache, "wb") as f:
        pickle.dump(idx, f)
    print(f"✅ Neg index: {len(idx):,} sản phẩm có review 1-2 sao")
    return idx


def spec_status(api_error, status, parse_fail, raw) -> str:
    if api_error:
        return "timeout" if "imeout" in str(status) else "api_error"
    if not (raw or "").strip():
        return "empty_response"
    return "json_parse_error" if parse_fail else "success"


def run_benchmark(model_name, comps, label, limit=None, k=5, neg_r=1, ooc_context="decoy", seed=42,
                  temperature=0.0, max_tokens=None, api_model_id=None, judge_model=None,
                  retry_errors=False, out_dir=None, kb=None, testset_file=None, timeout=60):
    out_dir = out_dir or DEFAULT_OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    max_tokens = max_tokens or (1500 if "cot" in comps else 1024)
    safe = model_name.replace(":", "-").replace("/", "-")
    base = os.path.join(out_dir, f"{safe}_{label}")
    final_csv, partial_csv, jsonl, summ = base + ".csv", base + ".partial.csv", base + ".jsonl", base + ".summary.json"
    print("=" * 90)
    print(f"🚀 {model_name} | {label} | {comps} | k={k} neg_r={neg_r} ooc={ooc_context} seed={seed} "
          f"temp={temperature} max_tokens={max_tokens}")
    print("=" * 90)

    with open(testset_file or os.path.join(DATA_DIR, "benchmark_test_500.json"), encoding="utf-8") as f:
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
        ctx = build_context(sample, kb, k, neg_r, neg_index, decoy_keys, ooc_context, seed)
        sys_p, usr_p = build_prompts(sample, comps, ctx)
        p_hash = hashlib.sha1(((sys_p or "") + "\n" + usr_p).encode("utf-8")).hexdigest()[:10]

        r = query_model(model_name, sys_p, usr_p, cfg, timeout=timeout)
        model_ids.add(r["model_id"])
        api_error = r["status"] != "OK"
        parsed = None if api_error else extract_json(r["text"])
        json_valid = parsed is not None
        parse_fail = (not api_error) and (not json_valid)

        row = {"sample_id": sid, "model_name": model_name, "config": label, "components": "+".join(comps) or "none",
               "model_id_used": r["model_id"], "temperature": temperature, "max_tokens": max_tokens, "seed": seed,
               "k": k, "neg_r": neg_r, "ooc_context": ooc_context, "prompt_version": PROMPT_VERSION,
               "prompt_hash": p_hash, "test_type": t_type, "status": r["status"], "api_error": api_error,
               "parse_fail": parse_fail, "json_valid": json_valid, "latency_ms": r["latency_ms"],
               "verifier_latency_ms": 0.0, "context_n": len(ctx["asins"]), "neg_review_n": ctx["neg_n"],
               "total_tokens": r["usage"]["total_tokens"]}

        reason, final, v_raw, trig, succ = None, {}, None, False, False
        ev_pre = ev = None
        if json_valid:
            ev_pre = evaluate(parsed, sample, kb, ctx["asins"])
            reason = v2.detect_correction_need(parsed, sample)
            final = parsed
            if reason and "verifier" in comps:
                final, succ, v_lat, v_raw = run_verifier(parsed, reason, sample, model_name, cfg, timeout)
                trig = True
                row["verifier_latency_ms"] = v_lat
            ev = evaluate(final, sample, kb, ctx["asins"])

        row["total_latency_ms"] = round(row["latency_ms"] + row["verifier_latency_ms"], 2)
        row.update({"needs_correction": reason is not None, "correction_reason": reason,
                    "verifier_triggered": trig, "verifier_success": succ,
                    "cons_nonempty_pre": bool(ev_pre["cons_nonempty"]) if ev_pre else False,
                    "cons_grounded": None})
        if ev:
            row.update(ev)
            neg = sample.get("negative_constraints", {}) or {}
            if judge_model and t_type == CNEG and ev["cons_nonempty"] and neg.get("c_neg_text"):
                row["cons_grounded"] = judge_cons_grounded(judge_model, neg["c_neg_text"], final, jcfg)
            row["hallucination_any"] = bool(ev["hallu_asin"] or ev["hallu_attr"] or ev["ooc_wrong_rec"])
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
               "verifier": {"reason": reason, "triggered": trig, "success": succ, "raw": v_raw}}
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
            "ooc_context": ooc_context, "prompt_version": PROMPT_VERSION, "judge_model": judge_model}
    S = summarize(df, meta)
    with open(summ, "w", encoding="utf-8") as f:
        json.dump(S, f, ensure_ascii=False, indent=2)
    print_summary(S)
    print(f"📁 {final_csv}\n📁 {jsonl}\n📁 {summ}")
    return S


# ==============================================================================
# 6. BẢNG ABLATION (Markdown) TỪ CÁC FILE .summary.json
# ==============================================================================
TABLE_COLS = [("Ảo giác ↓", "hallucination_any_valid"), ("OOC đúng ↑", "ooc_correct"),
              ("Từ chối nhầm ↓", "false_refusal_incatalog"), ("C_neg có cons ↑", "cons_nonempty_cneg_final"),
              ("Cons bám C_neg ↑", "cons_grounded_cneg"), ("Pros&Cons ↑", "pros_cons_balanced_incatalog"),
              ("Lỗi parse ↓", "parse_fail")]


def make_table(out_dir: str, models: list) -> str:
    lines = []
    for model in models:
        safe = model.replace(":", "-").replace("/", "-")
        lines += [f"\n### {model}\n",
                  "| Cấu hình | " + " | ".join(c for c, _ in TABLE_COLS) + " | P95 tổng (ms) |",
                  "|---|" + "---|" * (len(TABLE_COLS) + 1)]
        for cfg in PRESETS:
            p = os.path.join(out_dir, f"{safe}_{cfg}.summary.json")
            if not os.path.exists(p):
                continue
            S = json.load(open(p, encoding="utf-8"))
            cells = []
            for _, key in TABLE_COLS:
                r = S.get(key)
                cells.append("n/a" if not r or r["n"] == 0 else f'{r["pct"]}% [{r["ci95"][0]}–{r["ci95"][1]}]')
            lines.append(f"| {cfg} | " + " | ".join(cells) + f' | {S["latency_total_ms"]["p95"]} |')
    return "\n".join(lines)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Ablation runner v3 (A0-A6)")
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--config", default="A6", choices=list(PRESETS))
    p.add_argument("--components", default=None, help="ghi đè config, ví dụ profile,rag,cneg")
    p.add_argument("--no_verifier", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--k", type=int, default=5, help="số sản phẩm trong ngữ cảnh (1 = oracle thuần)")
    p.add_argument("--neg_r", type=int, default=1, help="số review tiêu cực/sản phẩm (1 = chỉ review của mẫu)")
    p.add_argument("--ooc_context", choices=["decoy", "zero"], default="decoy")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max_tokens", type=int, default=None, help="mặc định 1024 (1500 nếu có CoT)")
    p.add_argument("--api_model_id", default=None)
    p.add_argument("--judge_model", default=None)
    p.add_argument("--retry_errors", action="store_true")
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--out_dir", default=None)
    p.add_argument("--table", action="store_true", help="in bảng ablation từ các file summary")
    p.add_argument("--models", nargs="+", default=None, help="dùng với --table")
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
                  out_dir=a.out_dir, timeout=a.timeout)
