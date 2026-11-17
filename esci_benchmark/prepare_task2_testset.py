"""
Script trích xuất tập dữ liệu kiểm thử chuẩn cho Task 2 (ESCI Multi-class Classification)
từ bộ dữ liệu Amazon ESCI Shopping Queries Dataset (ACM SIGIR 2022).
Tập dữ liệu được trích xuất từ phân vùng 'test' tiếng Anh (locale='us'),
được phân tầng cân đối giữa các nhãn:
- E (Exact): Sản phẩm khớp chính xác nhu cầu.
- I (Irrelevant): Sản phẩm Ảo giác / Không liên quan.
- S (Substitute): Sản phẩm thay thế.
- C (Complement): Phụ kiện / Sản phẩm bổ trợ.
"""

import os
import json
import argparse
import pandas as pd
import pyarrow.dataset as ds

def extract_test_sample(num_samples: int = 100, output_path: str = None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    ex_path = os.path.join(data_dir, "shopping_queries_dataset_examples.parquet")
    prod_path = os.path.join(data_dir, "shopping_queries_dataset_products.parquet")
    
    if output_path is None:
        output_path = os.path.join(data_dir, f"esci_task2_test_{num_samples}.json")
        
    print(f"🔄 Đang đọc file truy vấn: {ex_path}...")
    df_ex = pd.read_parquet(ex_path)
    
    # Lọc phân vùng test tiếng Anh (small_version==1 là tập benchmark chuẩn của cuộc thi KDD Cup)
    us_test = df_ex[(df_ex['split'] == 'test') & (df_ex['product_locale'] == 'us') & (df_ex['small_version'] == 1)]
    print(f"✅ Tìm thấy {len(us_test):,} mẫu trong phân vùng Test (US, small_version).")
    
    # Tỷ lệ phân tầng (Stratified): 35% E, 35% I (Ảo giác), 15% S, 15% C
    n_e = int(num_samples * 0.35)
    n_i = int(num_samples * 0.35)
    n_s = int(num_samples * 0.15)
    n_c = num_samples - n_e - n_i - n_s
    
    print(f"📊 Trích xuất phân tầng: E={n_e}, I(Ảo giác)={n_i}, S={n_s}, C={n_c} (Tổng={num_samples})")
    sample_parts = [
        us_test[us_test['esci_label'] == 'E'].sample(n=n_e, random_state=42),
        us_test[us_test['esci_label'] == 'I'].sample(n=n_i, random_state=42),
        us_test[us_test['esci_label'] == 'S'].sample(n=n_s, random_state=42),
        us_test[us_test['esci_label'] == 'C'].sample(n=n_c, random_state=42)
    ]
    sample_df = pd.concat(sample_parts).sample(frac=1.0, random_state=42).reset_index(drop=True)
    pids = set(sample_df['product_id'].tolist())
    
    print(f"🔍 Đang truy xuất thông tin chi tiết cho {len(pids)} sản phẩm từ {prod_path}...")
    p_dataset = ds.dataset(prod_path, format='parquet')
    scanner = p_dataset.scanner(filter=ds.field('product_id').isin(pids))
    prods_df = scanner.to_table().to_pandas().drop_duplicates(subset=['product_id', 'product_locale'])
    
    merged = pd.merge(sample_df, prods_df, on=['product_id', 'product_locale'], how='left')
    
    # Chuyển đổi thành cấu trúc JSON chuẩn hóa
    records = []
    for idx, row in merged.iterrows():
        records.append({
            "sample_id": idx + 1,
            "example_id": int(row['example_id']),
            "query_id": int(row['query_id']),
            "query": str(row['query']),
            "product_id": str(row['product_id']),
            "product_title": str(row['product_title']) if pd.notnull(row['product_title']) else "No title",
            "product_brand": str(row['product_brand']) if pd.notnull(row['product_brand']) else "Generic",
            "product_color": str(row['product_color']) if pd.notnull(row['product_color']) else "N/A",
            "product_description": str(row['product_description'])[:400] if pd.notnull(row['product_description']) else "",
            "ground_truth_label": str(row['esci_label']),
            "is_hallucination": (str(row['esci_label']) == "I")
        })
        
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        
    print(f"🎉 Đã lưu thành công {len(records)} mẫu kiểm thử Task 2 vào:")
    print(f"   👉 {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=100, help="Số lượng mẫu cần trích xuất")
    args = parser.parse_args()
    extract_test_sample(num_samples=args.samples)

