"""
analyze_disentangle.py - Phân tích và tách biệt ảnh hưởng (Disentanglement Analysis)
trên tập dữ liệu Dev Set 130 mẫu (70 Standard + 20 C_neg + 40 OOC).

So sánh 4 biến thể thực nghiệm:
(i)   Prompt v1.2, không sửa luật, không Verifier (v12_raw)
(ii)  Prompt v1.2 + Rule Repair, không Verifier (v12_repair)
(iii) Prompt v1.2, không sửa luật + 2nd-turn LLM Verifier (v12_verifier)
(iv)  Prompt v1.1 + Rule Repair, không Verifier (v11_repair)
"""
import os
import sys
import json
import math
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results_disentangle")


def wilson_score_interval(k, n, confidence=0.95):
    if n == 0:
        return 0.0, 0.0
    z = 1.959963984540054  # 95%
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return round(max(0.0, center - margin) * 100, 1), round(min(1.0, center + margin) * 100, 1)


def fmt_stat(k, n):
    if n == 0:
        return "n/a"
    pct = (k / n) * 100
    ci_low, ci_high = wilson_score_interval(k, n)
    return f"{pct:.1f}% ({k}/{n}) [{ci_low}%, {ci_high}%]"


def analyze_results(out_dir=None):
    out_dir = out_dir or RESULTS_DIR
    if not os.path.exists(out_dir):
        print(f"❌ Thư mục {out_dir} chưa tồn tại!")
        return

    json_files = [f for f in os.listdir(out_dir) if f.endswith(".summary.json")]
    if not json_files:
        print(f"⚠️ Chưa có file summary nào trong {out_dir}")
        return

    summaries = {}
    for f in sorted(json_files):
        p = os.path.join(out_dir, f)
        with open(p, encoding="utf-8") as fp:
            summaries[f] = json.load(fp)

    print("=" * 105)
    print("📊 BẢNG TỔNG HỢP DISENTANGLEMENT ANALYSIS (DEV SET 130 MẪU)")
    print("=" * 105)

    rows = []
    for fname, s in summaries.items():
        name = s.get("config", fname.replace(".summary.json", ""))
        model = s.get("model", "")
        pv = s.get("prompt_version", "v1.2")
        rr = s.get("rule_repair", False)
        n_total = s.get("n_total", 0)

        lat_mean = s.get("latency_total_ms", {}).get("mean", 0)
        lat_p95 = s.get("latency_total_ms", {}).get("p95", 0)

        # In-catalog False Refusal
        fr_pre = s.get("false_refusal_pre_incatalog", {})
        fr_post = s.get("false_refusal_incatalog", {})

        # OOC Correct Rejection
        ooc_pre = s.get("ooc_correct_pre", {})
        ooc_post = s.get("ooc_correct", {})

        # Hallucination Any
        hal_pre = s.get("hallucination_any_pre", {})
        hal_post = s.get("hallucination_any_valid", {})

        # C_neg Real Cons
        cn_real = s.get("cneg_real_cons", {})
        cn_place = s.get("cneg_placeholder_cons", {})

        # Standard Placeholder vs Hallucinated Cons
        std_place = s.get("std_cons_placeholder", {})
        std_hallu = s.get("std_cons_hallucinated", {})

        # Rule Repair Rate
        rr_rate = s.get("rule_repair_rate", {})

        rows.append({
            "File": fname,
            "Model": model,
            "Config": name,
            "Prompt": pv,
            "RuleRepair": rr,
            "P95_ms": lat_p95,
            "Mean_ms": lat_mean,
            "RR_Rate": f"{rr_rate.get('pct', 0):.1f}% ({rr_rate.get('k', 0)}/{rr_rate.get('n', 0)})",
            "FR_Pre": f"{fr_pre.get('pct', 0):.1f}% ({fr_pre.get('k', 0)}/{fr_pre.get('n', 0)})",
            "FR_Post": f"{fr_post.get('pct', 0):.1f}% ({fr_post.get('k', 0)}/{fr_post.get('n', 0)}) [{fr_post.get('ci95', [0,0])[0]}%, {fr_post.get('ci95', [0,0])[1]}%]",
            "OOC_Pre": f"{ooc_pre.get('pct', 0):.1f}% ({ooc_pre.get('k', 0)}/{ooc_pre.get('n', 0)})",
            "OOC_Post": f"{ooc_post.get('pct', 0):.1f}% ({ooc_post.get('k', 0)}/{ooc_post.get('n', 0)}) [{ooc_post.get('ci95', [0,0])[0]}%, {ooc_post.get('ci95', [0,0])[1]}%]",
            "C_neg_Real": f"{cn_real.get('pct', 0):.1f}% ({cn_real.get('k', 0)}/{cn_real.get('n', 0)})",
            "Std_Placeholder": f"{std_place.get('pct', 0):.1f}% ({std_place.get('k', 0)}/{std_place.get('n', 0)})",
            "Std_HalluCons": f"{std_hallu.get('pct', 0):.1f}% ({std_hallu.get('k', 0)}/{std_hallu.get('n', 0)})",
            "Hallu_Any": f"{hal_post.get('pct', 0):.1f}% ({hal_post.get('k', 0)}/{hal_post.get('n', 0)})",
        })

    df = pd.DataFrame(rows)
    print(df[["Config", "P95_ms", "RR_Rate", "FR_Post", "OOC_Post", "C_neg_Real", "Std_Placeholder", "Hallu_Any"]].to_string(index=False))
    return df


if __name__ == "__main__":
    analyze_results()
