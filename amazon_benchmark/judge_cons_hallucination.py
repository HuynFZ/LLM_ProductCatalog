"""
judge_cons_hallucination.py
Phân loại các trường hợp "bịa cons" trên mẫu Standard:
Tách "cảnh báo chung" (general_caution: giá cao, lưu ý da nhạy cảm, khác biệt màu sắc màn hình)
khỏi "khẳng định cụ thể không có căn cứ" (unsupported_specific: bịa đặt có người dùng chê, bịa thành phần gây hại).
"""

import json
import re
import sys
sys.path.append('amazon_benchmark')
from benchmark_runner_ablation_v4 import nonempty_list, is_placeholder_cons


def classify_cons(cons_list):
    """
    Phân loại nhược điểm trên mẫu Standard không có review tiêu cực:
    - placeholder_variant: Các biến thể của placeholder (ví dụ: 'không được đánh giá tiêu cực')
    - general_caution: Cảnh báo chung / cảm tính thông thường (giá cao, cần thời gian, chú ý da nhạy cảm)
    - unsupported_specific: Khẳng định cụ thể bịa đặt (khẳng định có review xấu thực tế, bịa thành phần)
    """
    if not nonempty_list(cons_list):
        return "empty"
    if is_placeholder_cons(cons_list):
        return "standard_placeholder"

    full_text = " ".join(str(c) for c in cons_list).lower()

    # Biến thể placeholder
    if any(p in full_text for p in ["không được đánh giá tiêu cực", "không có phản hồi xấu", "chưa có đánh giá tiêu cực"]):
        return "placeholder_variant"

    # Khẳng định cụ thể bịa đặt (khẳng định có người dùng phàn nàn / review tiêu cực trong khi RAG không có)
    specific_patterns = [
        r"khách hàng đã (?:đánh giá|phản hồi|chê|báo cáo)",
        r"người dùng đã (?:phản hồi|đánh giá|phàn nàn)",
        r"theo (?:đánh giá|review|nhận xét)",
        r"có chứa (?:chất|cồn|paraben|sls|hóa chất)",
    ]
    if any(re.search(p, full_text) for p in specific_patterns):
        return "unsupported_specific"

    # Mặc định còn lại là cảnh báo chung / cảm tính (giá, loại da, thời gian...)
    return "general_caution"


def run_classification(f_raw="amazon_benchmark/results_disentangle/qwen2.5-3b_A5_v12_raw.jsonl",
                       f_testset="amazon_benchmark/data/dev_test_130.json"):
    with open(f_testset, encoding="utf-8") as f:
        samples = json.load(f)
    std_samples = {d["sample_id"]: d for d in samples if d["test_type"] == "in_catalog_standard"}

    records = []
    with open(f_raw, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            sid = d["sample_id"]
            if sid in std_samples:
                pj = d.get("parsed_json") or {}
                cons = pj.get("cons")
                cat = classify_cons(cons)
                records.append({
                    "sample_id": sid,
                    "cons": cons,
                    "category": cat
                })

    df = pd.DataFrame(records)
    total_std = len(df)
    counts = df["category"].value_counts().to_dict()

    print("=" * 80)
    print("PHÂN LOẠI CHI TIẾT TRƯỜNG CONS TRÊN MẪU STANDARD (N = 69 mẫu hợp lệ)")
    print("=" * 80)
    
    cats = [
        ("standard_placeholder", "Placeholder chuẩn (Chưa ghi nhận phản hồi tiêu cực...)"),
        ("placeholder_variant", "Biến thể của placeholder (không có đánh giá tiêu cực...)"),
        ("general_caution", "Cảnh báo chung / cảm tính (giá cả, da nhạy cảm, màu sắc...)"),
        ("unsupported_specific", "Khẳng định cụ thể không có căn cứ (bịa có người dùng chê...)"),
        ("empty", "Bỏ trống (mảng rỗng hoặc null)"),
    ]

    for c_id, c_label in cats:
        k = counts.get(c_id, 0)
        pct = k / total_std * 100
        print(f"- {c_label:<60}: {k:2d}/{total_std} ({pct:5.1f}%)")

    print("\nChi tiết các mẫu 'Khẳng định cụ thể không có căn cứ' (unsupported_specific):")
    for r in records:
        if r["category"] == "unsupported_specific":
            print(f"  [Sample {r['sample_id']}]: {r['cons']}")

    print("\nChi tiết các mẫu 'Cảnh báo chung / cảm tính' (general_caution):")
    for r in records:
        if r["category"] == "general_caution":
            print(f"  [Sample {r['sample_id']}]: {r['cons']}")


if __name__ == "__main__":
    import argparse
    import pandas as pd
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw_jsonl", default="amazon_benchmark/results_disentangle/qwen2.5-3b_A5_v12_raw.jsonl")
    parser.add_argument("--testset", default="amazon_benchmark/data/dev_test_130.json")
    args = parser.parse_args()
    run_classification(f_raw=args.raw_jsonl, f_testset=args.testset)
