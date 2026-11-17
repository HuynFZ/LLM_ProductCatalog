import os
import sys
import time
import gzip
import pandas as pd
import numpy as np
import re
import requests
from tqdm.auto import tqdm

# Cấu hình UTF-8 cho Windows console
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Đường dẫn thư mục dữ liệu
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ==============================================================================
# 1. HÀM TẢI DỮ LIỆU AMAZON BEAUTY (STREAMING VỚI REQUESTS & TQDM)
# ==============================================================================
def download_file_with_progress(url: str, filepath: str, desc: str, max_retries: int = 20):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    temp_path = filepath + ".tmp"
    
    for attempt in range(max_retries):
        try:
            downloaded_bytes = 0
            if os.path.exists(temp_path):
                downloaded_bytes = os.path.getsize(temp_path)
            
            req_headers = {**headers}
            if downloaded_bytes > 0:
                req_headers["Range"] = f"bytes={downloaded_bytes}-"
            
            response = requests.get(url, headers=req_headers, stream=True, timeout=30)
            
            # 206 Partial Content (tải tiếp) hoặc 200 OK (tải mới)
            if response.status_code not in [200, 206]:
                print(f"⚠️ Thử lại ({attempt+1}/{max_retries}) mã lỗi HTTP {response.status_code}")
                time.sleep(2)
                continue
                
            content_len = int(response.headers.get("content-length", 0))
            total_size = content_len + downloaded_bytes if response.status_code == 206 else content_len
            
            if total_size <= downloaded_bytes and downloaded_bytes > 0:
                # Đã tải đủ
                break
                
            mode = "ab" if downloaded_bytes > 0 and response.status_code == 206 else "wb"
            if mode == "wb":
                downloaded_bytes = 0
                
            print(f"📥 Đang tải {desc} (đã có {downloaded_bytes / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB)...")
            with open(temp_path, mode) as f, tqdm(
                total=total_size, initial=downloaded_bytes, unit="B", unit_scale=True, desc=desc
            ) as bar:
                for chunk in response.iter_content(chunk_size=512 * 1024):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
                        
            # Kiểm tra nếu đã tải trọn vẹn
            if os.path.exists(temp_path) and os.path.getsize(temp_path) >= total_size:
                if os.path.exists(filepath):
                    os.remove(filepath)
                os.rename(temp_path, filepath)
                print(f"✅ Hoàn thành tải 100%: {desc}")
                return
        except Exception as e:
            print(f"🔄 Kết nối bị gián đoạn ({e}). Tự động tiếp tục tải từ byte {downloaded_bytes}...")
            time.sleep(2)
            
    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 90 * 1024 * 1024:
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(temp_path, filepath)
        print(f"✅ Đã có đủ dữ liệu: {desc}")

def download_amazon_data():
    base_url = "http://snap.stanford.edu/data/amazon/productGraph/categoryFiles/"
    files = {
        "reviews": "reviews_Beauty_5.json.gz",
        "meta": "meta_Beauty.json.gz"
    }
    
    paths = {}
    for key, filename in files.items():
        filepath = os.path.join(DATA_DIR, filename)
        paths[key] = filepath
        # Kiểm tra file đã có đủ dung lượng hợp lệ chưa
        file_valid = False
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            # reviews ~44MB, meta ~99MB
            if key == "reviews" and size > 40 * 1024 * 1024:
                file_valid = True
            elif key == "meta" and size > 90 * 1024 * 1024:
                file_valid = True
                
        if not file_valid:
            download_file_with_progress(base_url + filename, filepath, filename)
        else:
            print(f"📁 Đã có sẵn file hợp lệ: {filename} ({os.path.getsize(filepath) / (1024*1024):.1f} MB)")
            
    return paths['reviews'], paths['meta']

def parse_amazon_json(path):
    """
    Đọc file .json.gz của Amazon.
    Dùng eval() do định dạng raw dictionary Python của bộ dữ liệu SNAP 2014.
    """
    with gzip.open(path, 'rb') as g:
        for line in g:
            try:
                yield eval(line)
            except Exception:
                continue

# ==============================================================================
# 2. ĐỌC VÀ XÂY DỰNG DATAFRAME & KNOWLEDGE BASE
# ==============================================================================
def load_and_build_kb(limit_reviews: int = None):
    print("=" * 60)
    print("🚀 Bắt đầu tải và nạp dữ liệu Amazon Beauty...")
    rev_path, met_path = download_amazon_data()

    print("\n📦 Đang xử lý reviews_Beauty_5.json.gz...")
    reviews_data = []
    count = 0
    for d in parse_amazon_json(rev_path):
        reviews_data.append({
            'user_id': d.get('reviewerID'),
            'item_id': d.get('asin'),
            'rating': float(d.get('overall', 0.0)),
            'timestamp': int(d.get('unixReviewTime', 0)),
            'review_text': str(d.get('reviewText', '')) # Dùng review text có thật để sinh C_neg
        })
        count += 1
        if limit_reviews and count >= limit_reviews:
            break
            
    amazon_ratings = pd.DataFrame(reviews_data)
    print(f"   -> Đã nạp {len(amazon_ratings)} lượt reviews.")

    print("\n📚 Đang xử lý meta_Beauty.json.gz...")
    meta_data = {}
    for d in parse_amazon_json(met_path):
        asin = d.get('asin')
        if not asin:
            continue
        brand = d.get('brand', 'unknown')
        brand_clean = brand.strip() if brand else "unknown"
        
        title = d.get('title', 'unknown')
        title_clean = title.strip() if title else "unknown"
        
        cats = d.get('categories', [['unknown']])
        first_cat = cats[0] if cats and len(cats) > 0 else ['unknown']
        
        price = d.get('price')
        image_url = d.get('imUrl', '')
        desc = d.get('description', '')
        if isinstance(desc, list):
            desc = " ".join(desc)

        meta_data[asin] = {
            'title': title_clean,
            'brand': brand_clean if brand_clean else "unknown",
            'categories': " | ".join(first_cat) if first_cat else "unknown",
            'price': float(price) if price is not None else None,
            'image_url': image_url,
            'description': str(desc).strip()
        }

    amazon_items = pd.DataFrame.from_dict(meta_data, orient='index').reset_index()
    amazon_items.rename(columns={'index': 'item_id'}, inplace=True)
    print(f"   -> Đã nạp metadata cho {len(amazon_items)} sản phẩm.")

    print("\n🔗 Đang kết hợp (Merge) Ratings và Metadata...")
    amazon_full_df = amazon_ratings.merge(amazon_items, on='item_id', how='inner')
    amazon_full_df = amazon_full_df.dropna(subset=['user_id', 'item_id', 'rating'])

    # Tạo Knowledge Base thực tế dạng Dict tra cứu O(1)
    amazon_real_kb = amazon_items.set_index('item_id').to_dict(orient='index')

    print("=" * 60)
    print(f"✅ DỮ LIỆU HOÀN TẤT:")
    print(f"   • Số Users duy nhất: {amazon_full_df['user_id'].nunique():,}")
    print(f"   • Số Items duy nhất: {amazon_full_df['item_id'].nunique():,}")
    print(f"   • Tổng số Ratings:   {len(amazon_full_df):,}")
    print(f"   • Kích thước KB:      {len(amazon_real_kb):,} sản phẩm.")
    print("=" * 60)

    return amazon_full_df, amazon_real_kb, amazon_items, amazon_ratings

if __name__ == "__main__":
    df, kb, items, ratings = load_and_build_kb()

