"""
benchmark_runner_4pillars_v2.py — Shared utilities, metrics, KB loading and LLM helpers
Phục vụ runner ablation v3 và benchmark 4 trụ cột.
"""
import os
import sys
import re
import json
import math
import pickle
import pandas as pd
from tqdm.auto import tqdm
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(CURRENT_DIR, "data")

# Nạp file .env từ root hoặc demo/backend
load_dotenv(os.path.join(ROOT_DIR, ".env"))
load_dotenv(os.path.join(ROOT_DIR, "demo", "backend", ".env"))
load_dotenv(os.path.join(ROOT_DIR, "backend", ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
if "localhost" in OLLAMA_CHAT_URL:
    OLLAMA_CHAT_URL = OLLAMA_CHAT_URL.replace("localhost", "127.0.0.1")

OOC = "out_of_catalog_adversarial"
CNEG = "in_catalog_c_neg"
STANDARD = "in_catalog_standard"

VERIFIER_SYSTEM = (
    "Bạn là Chuyên viên Kiểm định Độc lập (Independent Reliability Verifier). "
    "Nhiệm vụ của bạn là rà soát và tự sửa lỗi (Self-Correction) phản hồi của chatbot "
    "để đảm bảo tính trung thực, không bịa đặt sản phẩm và tuân thủ chặt chẽ ràng buộc người dùng. "
    "Chỉ trả về DUY NHẤT một khối JSON hợp lệ."
)


def is_null(v) -> bool:
    if v is None:
        return True
    s = str(v).strip().lower()
    return s in ["null", "none", "", "nan"]


def as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ["true", "1", "yes"]
    return bool(v)


def nonempty_list(v) -> bool:
    return bool(v and isinstance(v, list) and len(v) > 0)


def extract_json(text: str):
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        candidate = match.group(1).strip()
    else:
        m_brace = re.search(r"(\{[\s\S]*\})", text)
        candidate = m_brace.group(1).strip() if m_brace else text
    try:
        return json.loads(candidate)
    except Exception:
        pass
    # Sửa lỗi trailing comma phổ biến
    candidate_clean = re.sub(r",\s*([\]}])", r"\1", candidate)
    try:
        return json.loads(candidate_clean)
    except Exception:
        return None


def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + (z ** 2) / n
    center = (p + (z ** 2) / (2 * n)) / denom
    diff = (z * math.sqrt((p * (1 - p) / n) + (z ** 2) / (4 * (n ** 2)))) / denom
    lower = max(0.0, center - diff)
    upper = min(1.0, center + diff)
    return (round(lower * 100, 1), round(upper * 100, 1))


def _rate(series, mask=None) -> dict:
    sub = series[mask] if mask is not None else series
    n = int(len(sub))
    if n == 0:
        return {"pct": 0.0, "k": 0, "n": 0, "ci95": [0.0, 0.0]}
    k = int(sub.sum())
    pct = round(k / n * 100, 1)
    ci = wilson(k, n)
    return {"pct": pct, "k": k, "n": n, "ci95": list(ci)}


def resolve_gemini_id(model_name: str, api_id: str = None) -> str:
    if api_id:
        return api_id
    m = model_name.lower().strip()
    if m in ["gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-1.5-flash-lite", "gemini-flash-lite"]:
        return "gemini-3.5-flash-lite"
    if m in ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash"]:
        return "gemini-3.5-flash"
    return model_name


def load_real_kb() -> dict:
    kb_cache_file = os.path.join(DATA_DIR, "real_kb_cache.pkl")
    if os.path.exists(kb_cache_file):
        print("⚡ Đang nạp nhanh Knowledge Base từ Cache (real_kb_cache.pkl)...")
        with open(kb_cache_file, "rb") as f:
            real_kb = pickle.load(f)
        print(f"✅ Đã nạp tức thì {len(real_kb):,} sản phẩm từ Real KB Cache.")
        return real_kb

    kb_file = os.path.join(DATA_DIR, "meta_Beauty.json.gz")
    if not os.path.exists(kb_file):
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu KB: {kb_file}")

    from load_amazon_data import parse_amazon_json
    print("📚 Đang nạp và lập chỉ mục Knowledge Base Amazon Beauty...")
    real_kb = {}
    for d in parse_amazon_json(kb_file):
        asin = d.get('asin')
        if asin:
            desc = d.get('description', '')
            if isinstance(desc, list):
                desc = " ".join(desc)
            cats = d.get('categories', [['unknown']])[0]
            real_kb[asin] = {
                "title": str(d.get('title', 'unknown')).strip(),
                "brand": str(d.get('brand', 'unknown')).strip(),
                "price": float(d.get('price')) if d.get('price') is not None else None,
                "categories": " | ".join(cats) if cats else "unknown",
                "description": str(desc).strip()
            }
    with open(kb_cache_file, "wb") as f:
        pickle.dump(real_kb, f)
    print(f"✅ Đã nạp và lưu cache {len(real_kb):,} sản phẩm trong Real KB.")
    return real_kb


def detect_correction_need(parsed: dict, sample: dict):
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
