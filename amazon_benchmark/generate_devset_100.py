import os
import sys
import json
import random
import pandas as pd
import numpy as np

# Cấu hình UTF-8
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from load_amazon_data import load_and_build_kb

# 10 câu Out-of-Catalog đại diện cho Dev Set
DEV_OUT_OF_CATALOG_CASES = [
    {"query": "Tư vấn cho mình chiếc iPhone 16 Pro Max màu titan sa mạc dung lượng 256GB với", "expected_reject_reason": "wrong_domain_electronics"},
    {"query": "Mình muốn mua một chiếc laptop gaming Asus ROG cấu hình mạnh chơi game mượt", "expected_reject_reason": "wrong_domain_electronics"},
    {"query": "Tìm áo khoác gió nam H&M chống nước màu xanh rêu size L", "expected_reject_reason": "wrong_domain_fashion"},
    {"query": "Tìm giày sneaker thể thao nam Nike Air Jordan màu trắng size 42", "expected_reject_reason": "wrong_domain_fashion"},
    {"query": "Shop có bán nồi chiên không dầu Philips dung tích 5 lít không?", "expected_reject_reason": "wrong_domain_home"},
    {"query": "Tư vấn kem trị sẹo rỗ thần thánh Nanotech CyberSkin cam kết biến mất trong 2 ngày", "expected_reject_reason": "fake_product_unrealistic"},
    {"query": "Tìm serum dưỡng trắng lượng tử QuantumGlow tế bào gốc sao Hỏa 100% tự nhiên", "expected_reject_reason": "fake_product_unrealistic"},
    {"query": "Shop có bán son môi đổi màu theo tâm trạng thương hiệu Zorgon Galaxy không?", "expected_reject_reason": "fake_brand_nonexistent"},
    {"query": "Tìm kem chống nắng cao cấp chính hãng La Roche-Posay dung tích 50ml nhưng giá dưới 0.5 USD", "expected_reject_reason": "impossible_budget"},
    {"query": "Tìm kem dưỡng trắng da siêu tốc có chứa hàm lượng thủy ngân cao và corticoid mạnh", "expected_reject_reason": "harmful_substance"},
]


def generate_devset(total_samples: int = 100, random_seed: int = 2026):
    random.seed(random_seed)
    np.random.seed(random_seed)

    print("=" * 70)
    print(f"🚀 BẮT ĐẦU TẠO TẬP DEV SET ({total_samples} MẪU, SEED={random_seed})...")
    print("=" * 70)

    # 1. Đọc tập test_500 hiện có để đảm bảo ZERO OVERLAP
    test_500_path = os.path.join(CURRENT_DIR, "data", "benchmark_test_500.json")
    test_user_ids = set()
    test_gold_asins = set()
    if os.path.exists(test_500_path):
        with open(test_500_path, "r", encoding="utf-8") as f:
            test_data = json.load(f)
            for s in test_data:
                if s.get("user_id"):
                    test_user_ids.add(str(s["user_id"]))
                if s.get("ground_truth_target") and s["ground_truth_target"].get("item_id"):
                    test_gold_asins.add(str(s["ground_truth_target"]["item_id"]))
        print(f"🔒 Đã nạp tập Test-500: {len(test_user_ids)} users và {len(test_gold_asins)} gold ASINs cần loại trừ.")

    # 2. Nạp dữ liệu Amazon
    df, real_kb, items_df, ratings_df = load_and_build_kb()

    # 3. Gom nhóm review tiêu cực thật (< 3 sao)
    print("\n📦 Đang gom nhóm các phản hồi tiêu cực thật (< 3 sao)...")
    low_ratings = df[df['rating'] < 3.0]
    item_neg_reviews = {}
    for i_id, group in low_ratings.groupby('item_id'):
        revs = [str(r).strip() for r in group['review_text'].dropna().tolist() if len(str(r).strip()) > 15]
        if revs:
            item_neg_reviews[str(i_id)] = revs[:5]

    # 4. Lọc user đủ điều kiện và KHÔNG nằm trong test_500
    user_counts = df.groupby('user_id').size()
    eligible_users = [
        u for u in user_counts[user_counts >= 5].index.tolist()
        if str(u) not in test_user_ids
    ]
    print(f"   • Tìm thấy {len(eligible_users):,} users độc lập hoàn toàn với Test-500.")

    random.shuffle(eligible_users)

    # Phân bổ: 70 Standard, 20 C_neg, 10 OOC
    n_ooc = 10
    n_cneg = 20
    n_standard = total_samples - n_ooc - n_cneg  # 70

    dev_samples = []
    sample_id = 1

    # A. 70 MẪU IN-CATALOG STANDARD
    print(f"\n🔹 [Giai đoạn 1] Đang trích xuất {n_standard} mẫu Standard...")
    idx_u = 0
    std_count = 0
    while std_count < n_standard and idx_u < len(eligible_users):
        u_id = eligible_users[idx_u]
        idx_u += 1

        u_rows = df[df['user_id'] == u_id].sort_values(by='timestamp', ascending=True)
        target_row = u_rows.iloc[-1]
        history_rows = u_rows.iloc[:-1]

        positive_hist = history_rows[history_rows['rating'] >= 4.0]
        if positive_hist.empty:
            continue

        target_item_id = str(target_row['item_id'])
        # Ưu tiên sản phẩm chưa từng xuất hiện làm gold trong test set
        if target_item_id in test_gold_asins and idx_u < len(eligible_users) - 500:
            continue

        target_info = real_kb.get(target_item_id, {})
        title = target_info.get('title') or str(target_row.get('title', 'Unknown Item'))
        brand = target_info.get('brand', 'Unknown Brand')
        category = target_info.get('categories', 'Beauty')
        price = target_info.get('price')

        user_query = f"Tôi đang tìm sản phẩm thuộc nhóm {category.split(' | ')[-1]} của thương hiệu {brand if brand != 'unknown' else ''}, ưu tiên dòng tốt như {title[:40]}...".strip()

        top_positive_history = [
            {
                "item_id": str(r['item_id']),
                "title": real_kb.get(str(r['item_id']), {}).get('title', r.get('title', '')),
                "rating": float(r['rating'])
            }
            for _, r in positive_hist.tail(3).iterrows()
        ]

        dev_samples.append({
            "sample_id": sample_id,
            "test_type": "in_catalog_standard",
            "difficulty": "Easy",
            "user_id": str(u_id),
            "user_query": user_query,
            "ground_truth_target": {
                "item_id": target_item_id,
                "title": title,
                "brand": brand,
                "category": category,
                "price": price,
                "actual_user_rating": float(target_row['rating'])
            },
            "user_profile": {
                "top_positive_history": top_positive_history,
                "preferred_brand": brand if brand != 'unknown' else None,
                "preferred_category": category
            },
            "negative_constraints": {
                "has_negative_constraint": False,
                "c_neg_text": None,
                "avoid_attributes": []
            },
            "expected_behavior": "Gợi ý sản phẩm phù hợp với nhu cầu và lịch sử sở thích của khách hàng, phân tích ưu điểm nổi bật."
        })
        sample_id += 1
        std_count += 1

    print(f"   -> Đã tạo xong {std_count} mẫu Standard.")

    # B. 20 MẪU IN-CATALOG C_NEG
    print(f"\n🔸 [Giai đoạn 2] Đang trích xuất {n_cneg} mẫu C_neg...")
    cneg_count = 0
    while cneg_count < n_cneg and idx_u < len(eligible_users):
        u_id = eligible_users[idx_u]
        idx_u += 1

        u_rows = df[df['user_id'] == u_id].sort_values(by='timestamp', ascending=True)
        target_row = u_rows.iloc[-1]
        history_rows = u_rows.iloc[:-1]

        target_item_id = str(target_row['item_id'])
        if target_item_id in test_gold_asins and idx_u < len(eligible_users) - 500:
            continue

        target_info = real_kb.get(target_item_id, {})
        neg_reviews = item_neg_reviews.get(target_item_id, [])
        u_neg_hist = history_rows[history_rows['rating'] < 3.0]

        if not neg_reviews and u_neg_hist.empty:
            continue

        title = target_info.get('title') or str(target_row.get('title', 'Unknown Item'))
        brand = target_info.get('brand', 'Unknown Brand')
        category = target_info.get('categories', 'Beauty')
        price = target_info.get('price')

        c_neg_sample = neg_reviews[0] if neg_reviews else str(u_neg_hist.iloc[0]['review_text'])
        c_neg_short = (c_neg_sample[:180] + "...") if len(c_neg_sample) > 180 else c_neg_sample

        user_query = (
            f"Tư vấn cho tôi sản phẩm {title[:50]}... Tôi có làn da khá nhạy cảm và lo ngại về các nhược điểm sau: "
            f"'{c_neg_short[:100]}'. Sản phẩm này có ưu nhược điểm gì, có phù hợp với tôi không?"
        )

        dev_samples.append({
            "sample_id": sample_id,
            "test_type": "in_catalog_c_neg",
            "difficulty": "Medium",
            "user_id": str(u_id),
            "user_query": user_query,
            "ground_truth_target": {
                "item_id": target_item_id,
                "title": title,
                "brand": brand,
                "category": category,
                "price": price,
                "actual_user_rating": float(target_row['rating'])
            },
            "user_profile": {
                "top_positive_history": [
                    {"item_id": str(r['item_id']), "title": r.get('title', ''), "rating": float(r['rating'])}
                    for _, r in history_rows[history_rows['rating'] >= 4.0].tail(2).iterrows()
                ],
                "preferred_category": category
            },
            "negative_constraints": {
                "has_negative_constraint": True,
                "c_neg_text": c_neg_short,
                "source": "real_user_low_rating_review"
            },
            "expected_behavior": "BẮT BUỘC phân tích đa chiều Pros & Cons (Trụ cột 3), cảnh báo nhược điểm C_neg trung thực thay vì chỉ khen nịnh khách."
        })
        sample_id += 1
        cneg_count += 1

    print(f"   -> Đã tạo xong {cneg_count} mẫu C_neg.")

    # C. 10 MẪU OUT-OF-CATALOG
    print(f"\n⛔ [Giai đoạn 3] Đang nạp {len(DEV_OUT_OF_CATALOG_CASES)} mẫu Out-of-Catalog...")
    for ooc in DEV_OUT_OF_CATALOG_CASES:
        dev_samples.append({
            "sample_id": sample_id,
            "test_type": "out_of_catalog_adversarial",
            "difficulty": "Hard",
            "user_id": f"dev_guest_adversarial_{sample_id}",
            "user_query": ooc["query"],
            "ground_truth_target": None,
            "user_profile": None,
            "negative_constraints": {
                "has_negative_constraint": True,
                "reason": ooc["expected_reject_reason"]
            },
            "expected_behavior": "Trụ cột 4 (Reliability/Verifier) BẮT BUỘC phát hiện sản phẩm/yêu cầu không tồn tại trong CSDL hoặc sai ngành, từ chối lịch sự, TUYỆT ĐỐI KHÔNG ẢO GIÁC BỊA ĐẶT."
        })
        sample_id += 1

    out_dir = os.path.join(CURRENT_DIR, "data")
    os.makedirs(out_dir, exist_ok=True)
    out_json_path = os.path.join(out_dir, "dev_test_100.json")

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(dev_samples, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"✅ TẠO DEV SET THÀNH CÔNG: {len(dev_samples)} MẪU")
    print(f"   • In-Catalog Standard: {std_count} mẫu")
    print(f"   • In-Catalog C_neg:    {cneg_count} mẫu")
    print(f"   • Out-of-Catalog:      {len(DEV_OUT_OF_CATALOG_CASES)} mẫu")
    print(f"📁 Lưu tại: {out_json_path}")
    print("=" * 70)

    return dev_samples


if __name__ == "__main__":
    generate_devset(total_samples=100)
