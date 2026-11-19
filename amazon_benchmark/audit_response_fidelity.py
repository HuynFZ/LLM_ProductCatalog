"""
audit_response_fidelity.py - Kiểm tra độ trung thực của response_to_user (Free-Text Hallucination Audit)
Đánh giá xem văn bản tự do gửi cho người dùng có bịa đặt thành phần, công dụng hay thông số không có trong catalog không.
"""
import os
import sys
import json
import re
import pandas as pd
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import benchmark_runner_4pillars_v2 as v2
from benchmark_runner_ablation_v4 import query_model, extract_json

JUDGE_FIDELITY_SYSTEM = """Bạn là Chuyên viên Kiểm định Thực tế (Fact-Checking Auditor) trong thương mại điện tử.
Nhiệm vụ của bạn là so sánh văn bản trả lời của Trợ lý tư vấn (response_to_user) với Dữ liệu danh mục thực tế được cung cấp.

TIÊU CHÍ ĐÁNH GIÁ (Thang điểm 0 - 2):
- Điểm 2 (Hoàn toàn trung thực - Fully Grounded): Tất cả các tuyên bố về sản phẩm (tên, hãng, giá, thành phần, công dụng, chất liệu, tính năng) đều có căn cứ trong Dữ liệu danh mục hoặc là lời chào hỏi xã giao thông thường.
- Điểm 1 (Ngoại suy nhẹ vô hại - Minor Extrapolation): Có một vài nhận định chung chung về mỹ phẩm (ví dụ: "giúp bạn rạng rỡ", "thích hợp dùng hàng ngày") không có trong mô tả nhưng không bịa đặt thành phần hay tính năng cụ thể.
- Điểm 0 (Ảo giác / Bịa đặt - Hallucinated Fact): Bịa đặt thành phần hóa học cụ thể (như "chứa vitamin C, hyaluronic acid"), thông số kỹ thuật (như "chống nước 50m", "SPF 50+"), hoặc công dụng cụ thể không hề có trong dữ liệu được cung cấp.

Chỉ trả về DUY NHẤT một khối JSON:
{
  "score": 0, 1 hoặc 2,
  "hallucinated_claims": ["danh sách các tuyên bố bịa đặt nếu có, hoặc để trống"],
  "explanation": "lý do ngắn gọn trong 1-2 câu"
}"""


def audit_file(jsonl_path: str, judge_model: str = "gemini-2.5-flash-lite", limit: int = 15):
    print(f"\n🔍 Đang thẩm định độ trung thực văn bản tự do từ: {os.path.basename(jsonl_path)}")
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # Lọc các mẫu in-catalog có câu trả lời
    in_cat_records = [r for r in records if r.get("parsed_json") and r.get("test_type") != "out_of_catalog_adversarial"]
    if limit:
        in_cat_records = in_cat_records[:limit]

    cfg = {"temperature": 0.0, "max_tokens": 300, "seed": 42}
    results = []

    for r in in_cat_records:
        sid = r["sample_id"]
        parsed = r["parsed_json"]
        response_text = parsed.get("response_to_user", "")
        usr_prompt = r["prompt"]["user"]
        
        # Trích xuất phần catalog text từ prompt
        m = re.search(r'\[DANH MỤC SẢN PHẨM\](.*?)\[/DANH MỤC SẢN PHẨM\]', usr_prompt, re.DOTALL)
        catalog_text = m.group(1).strip() if m else usr_prompt[:800]

        eval_prompt = f"""[DỮ LIỆU DANH MỤC ĐƯỢC CUNG CẤP]:
{catalog_text}

[CÂU TRẢ LỜI CỦA TRỢ LÝ (RESPONSE_TO_USER)]:
"{response_text}"

Hãy đánh giá xem câu trả lời của Trợ lý có bịa đặt thông tin không có trong danh mục không."""

        res = query_model(judge_model, JUDGE_FIDELITY_SYSTEM, eval_prompt, cfg, timeout=30)
        obj = extract_json(res["text"]) if res["status"] == "OK" else None

        score = obj.get("score") if obj else None
        claims = obj.get("hallucinated_claims") if obj else []
        expl = obj.get("explanation") if obj else res["status"]

        results.append({
            "sample_id": sid,
            "model": r["model"],
            "rec_id": parsed.get("recommended_item_id"),
            "response_to_user": response_text[:120] + "...",
            "fidelity_score": score,
            "hallucinated_claims": claims,
            "explanation": expl
        })
        print(f"  • Sample #{sid}: Score={score}/2 | Bịa đặt={len(claims)} chi tiết | {expl}")

    return pd.DataFrame(results)


def main():
    out_dir = os.path.join(HERE, "results_dev_slice_20")
    qwen_jsonl = os.path.join(out_dir, "qwen2.5-3b_A6.jsonl")
    gpt_jsonl = os.path.join(out_dir, "gpt-4o-mini_A6.jsonl")

    reports = []
    for path in [qwen_jsonl, gpt_jsonl]:
        if os.path.exists(path):
            df = audit_file(path, judge_model="gemini-2.5-flash-lite", limit=10)
            model_name = df["model"].iloc[0] if len(df) else "Unknown"
            mean_score = df["fidelity_score"].mean()
            zero_hallu_rate = (df["fidelity_score"] == 2).mean() * 100
            minor_rate = (df["fidelity_score"] == 1).mean() * 100
            hallu_rate = (df["fidelity_score"] == 0).mean() * 100

            reports.append({
                "model": model_name,
                "n_samples": len(df),
                "mean_fidelity_score": round(mean_score, 2),
                "fully_grounded_pct": round(zero_hallu_rate, 1),
                "minor_extrapolation_pct": round(minor_rate, 1),
                "factual_hallucination_pct": round(hallu_rate, 1),
                "df": df
            })

    # Xuất báo cáo Markdown
    md_lines = [
        "# BÁO CÁO THẨM ĐỊNH ĐỘ TRUNG THỰC VĂN BẢN TỰ DO (FREE-TEXT FIDELITY AUDIT)",
        "",
        "**Mục tiêu:** Kiểm tra văn bản `response_to_user` xem mô hình có bịa đặt thành phần, công dụng hoặc tính năng kỹ thuật không có trong metadata danh mục hay không.",
        "**Giám khảo:** `gemini-2.5-flash-lite` (LLM-as-a-Judge độc lập, thang điểm 0 - 2).",
        "",
        "## 1. Bảng Tổng hợp Độ trung thực",
        "",
        "| Mô hình | Số mẫu | Điểm trung bình (/2.0) | Hoàn toàn có căn cứ (2đ) | Ngoại suy nhẹ (1đ) | Bịa đặt thành phần (0đ) |",
        "|---|---|---|---|---|---|",
    ]
    for rep in reports:
        md_lines.append(f"| **{rep['model']}** | {rep['n_samples']} | **{rep['mean_fidelity_score']}** / 2.0 | {rep['fully_grounded_pct']}% | {rep['minor_extrapolation_pct']}% | **{rep['factual_hallucination_pct']}%** |")

    md_lines.extend([
        "",
        "## 2. Chi tiết từng mẫu thẩm định",
        ""
    ])
    for rep in reports:
        md_lines.append(f"### Mô hình: {rep['model']}")
        md_lines.append("")
        for _, row in rep["df"].iterrows():
            md_lines.append(f"- **Mẫu #{row['sample_id']} (ASIN: {row['rec_id']})**: Điểm **{row['fidelity_score']}/2**")
            md_lines.append(f"  - *Trích đoạn phản hồi:* \"{row['response_to_user']}\"")
            md_lines.append(f"  - *Nhận xét của Giám khảo:* {row['explanation']}")
            if row['hallucinated_claims']:
                md_lines.append(f"  - *Chi tiết bịa đặt:* {', '.join(row['hallucinated_claims'])}")
            md_lines.append("")

    report_path = os.path.join(out_dir, "audit_freetext_fidelity.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\n✅ Đã xuất báo cáo thẩm định tại: {report_path}")


if __name__ == "__main__":
    main()
