import os
import sys
import requests
import time

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Cấu hình Ollama Embeddings
_raw_ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
# Lấy base URL từ OLLAMA_URL
_base_url = _raw_ollama_url.split("/api/")[0] if "/api/" in _raw_ollama_url else "http://localhost:11434"
if "localhost" in _base_url:
    _base_url = _base_url.replace("localhost", "127.0.0.1")

EMBED_URL = f"{_base_url}/api/embeddings"
EMBED_BATCH_URL = f"{_base_url}/api/embed"
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_DIMENSION = 768

def get_text_embedding(text: str, max_retries: int = 3) -> list:
    """
    Sinh vector đặc trưng (768 chiều) từ đoạn văn bản sử dụng nomic-embed-text qua Ollama.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return [0.0] * EMBED_DIMENSION

    if len(clean_text) > 1000:
        clean_text = clean_text[:1000]

    for attempt in range(max_retries):
        try:
            # Ưu tiên /api/embed
            resp = requests.post(EMBED_BATCH_URL, json={"model": EMBED_MODEL, "input": clean_text}, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                embs = data.get("embeddings", [])
                if embs and len(embs) > 0:
                    return embs[0]
            
            # Fallback sang /api/embeddings
            resp = requests.post(EMBED_URL, json={"model": EMBED_MODEL, "prompt": clean_text}, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                emb = data.get("embedding", [])
                if emb:
                    return emb
            time.sleep(0.5)
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"⚠️ Lỗi sinh embedding cho '{clean_text[:40]}...': {e}")
            time.sleep(0.5)

    return [0.0] * EMBED_DIMENSION

def get_batch_embeddings(texts: list, batch_size: int = 20) -> list:
    """
    Sinh vector hàng loạt cho danh sách text sử dụng API batch /api/embed.
    """
    results = []
    clean_texts = [str(t or "")[:1000] for t in texts]

    for i in range(0, len(clean_texts), batch_size):
        chunk = clean_texts[i:i + batch_size]
        try:
            resp = requests.post(EMBED_BATCH_URL, json={"model": EMBED_MODEL, "input": chunk}, timeout=60)
            if resp.status_code == 200:
                embs = resp.json().get("embeddings", [])
                if len(embs) == len(chunk):
                    results.extend(embs)
                    continue
        except Exception:
            pass

        # Fallback từng câu nếu batch gặp lỗi
        for t in chunk:
            results.append(get_text_embedding(t))

    return results

if __name__ == "__main__":
    test_str = "Black casual streetwear jumpsuit for women, comfortable summer wear"
    print(f"Testing embedding with '{test_str}'...")
    vec = get_text_embedding(test_str)
    print(f"Vector length: {len(vec)} | First 5 values: {vec[:5]}")
