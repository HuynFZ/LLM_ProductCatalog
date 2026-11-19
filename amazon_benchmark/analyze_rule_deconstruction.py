"""
analyze_rule_deconstruction.py
Phân tích phân rã luật (Rule Deconstruction), so sánh Oracle vs Observable Verifier,
và phân rã trạng thái Cons (Tri-state Cons) trên tập Dev 130.
"""

import json
import glob
import os
import pandas as pd
import numpy as np


def fmt_pct_ci(r):
    if not r or r.get("n", 0) == 0:
        return "n/a"
    return f"{r['pct']:.1f}% [{r['ci95'][0]}, {r['ci95'][1]}]"


def main():
    res_dir = "amazon_benchmark/results_disentangle"
    configs = [
        ("v1.1 Thô (Raw)", "qwen2.5-3b_A5_v11_raw.summary.json", "qwen2.5-3b_A5_v11_raw.csv"),
        ("v1.1 + Sửa luật (Rule)", "qwen2.5-3b_A5_v11_repair.summary.json", "qwen2.5-3b_A5_v11_repair.csv"),
        ("v1.2 Thô (Raw)", "qwen2.5-3b_A5_v12_raw.summary.json", "qwen2.5-3b_A5_v12_raw.csv"),
        ("v1.2 + Sửa luật (Rule)", "qwen2.5-3b_A5_v12_repair.summary.json", "qwen2.5-3b_A5_v12_repair.csv"),
        ("v1.2 + Verifier Thực tế (Obs)", "qwen2.5-3b_A6_v12_verifier_obs.summary.json", "qwen2.5-3b_A6_v12_verifier_obs.csv"),
        ("v1.2 + Verifier Lý thuyết (Oracle)", "qwen2.5-3b_A6_v12_verifier_oracle.summary.json", "qwen2.5-3b_A6_v12_verifier_oracle.csv"),
        ("v1.2 + Phối hợp Thực tế (Cascaded Obs)", "qwen2.5-3b_A6_v12_cascaded_obs.summary.json", "qwen2.5-3b_A6_v12_cascaded_obs.csv"),
        ("v1.2 + Phối hợp Lý thuyết (Cascaded Oracle)", "qwen2.5-3b_A6_v12_cascaded_oracle.summary.json", "qwen2.5-3b_A6_v12_cascaded_oracle.csv"),
    ]

    summaries = {}
    dfs = {}
    for name, s_file, c_file in configs:
        sp = os.path.join(res_dir, s_file)
        cp = os.path.join(res_dir, c_file)
        if os.path.exists(sp):
            with open(sp, encoding="utf-8") as f:
                summaries[name] = json.load(f)
        if os.path.exists(cp):
            dfs[name] = pd.read_csv(cp)

    print("=" * 110)
    print("BẢNG 1: HIỆU NĂNG TỔNG QUAN VÀ ĐÁNH ĐỔI TRÊN TẬP DEV 130 (QWEN2.5:3B)")
    print("=" * 110)
    h1 = ["Cấu hình", "Từ chối nhầm↓", "Chặn OOC↑", "Chọn Gold↑", "C_neg Cons↑", "Pros&Cons↑", "P95 (ms)↓"]
    print(f"| {' | '.join(h1)} |")
    print(f"| {' | '.join(['---'] * len(h1))} |")
    for name, _, _ in configs:
        if name not in summaries:
            continue
        S = summaries[name]
        fr = fmt_pct_ci(S.get("false_refusal_incatalog"))
        ooc = fmt_pct_ci(S.get("ooc_correct"))
        gold = fmt_pct_ci(S.get("rec_is_gold_incatalog"))
        cn_real = fmt_pct_ci(S.get("cneg_cons_real"))
        pc = fmt_pct_ci(S.get("pros_cons_balanced_incatalog"))
        p95 = f"{S['latency_total_ms']['p95']:.0f}"
        print(f"| {name:<35} | {fr:<15} | {ooc:<15} | {gold:<15} | {cn_real:<15} | {pc:<15} | {p95:<8} |")

    print("\n" + "=" * 110)
    print("BẢNG 2: PHÂN RÃ 4 LUẬT CON SỬA LỖI (RULE DECONSTRUCTION)")
    print("=" * 110)
    h2 = ["Cấu hình", "Tổng sửa luật", "L1: Cứu ASIN", "L2: Sửa cờ OOC", "L3: Trích xuất P/C", "L4: Điền Brand/Price"]
    print(f"| {' | '.join(h2)} |")
    print(f"| {' | '.join(['---'] * len(h2))} |")
    for name, _, _ in configs:
        if name not in summaries:
            continue
        S = summaries[name]
        tot = fmt_pct_ci(S.get("rule_repair_rate"))
        l1 = fmt_pct_ci(S.get("rule_recover_asin_rate"))
        l2 = fmt_pct_ci(S.get("rule_ooc_flag_rate"))
        l3 = fmt_pct_ci(S.get("rule_extract_pros_cons_rate"))
        l4 = fmt_pct_ci(S.get("rule_fill_brand_price_rate"))
        print(f"| {name:<35} | {tot:<15} | {l1:<15} | {l2:<15} | {l3:<15} | {l4:<18} |")

    print("\n" + "=" * 110)
    print("BẢNG 3: PHÂN TÍCH CONS 3 TRẠNG THÁI (TRI-STATE CONS DISTRIBUTION & SIDE EFFECTS)")
    print("=" * 110)
    h3 = ["Cấu hình", "C_neg: Thật (Đạt)↑", "C_neg: Placeholder", "C_neg: Rỗng↓", "Std: Placeholder", "Std: Rỗng", "Std: Bịa Cons (Tác dụng phụ)↓"]
    print(f"| {' | '.join(h3)} |")
    print(f"| {' | '.join(['---'] * len(h3))} |")
    for name, _, _ in configs:
        if name not in summaries:
            continue
        S = summaries[name]
        cn_r = fmt_pct_ci(S.get("cneg_cons_real"))
        cn_p = fmt_pct_ci(S.get("cneg_cons_placeholder"))
        cn_e = fmt_pct_ci(S.get("cneg_cons_empty"))
        st_p = fmt_pct_ci(S.get("std_cons_placeholder"))
        st_e = fmt_pct_ci(S.get("std_cons_empty"))
        st_h = fmt_pct_ci(S.get("std_cons_hallu_real"))
        print(f"| {name:<35} | {cn_r:<18} | {cn_p:<18} | {cn_e:<14} | {st_p:<16} | {st_e:<10} | {st_h:<28} |")

    print("\n" + "=" * 110)
    print("BẢNG 4: SO SÁNH VERIFIER THỰC TẾ (OBSERVABLE) VS LÝ THUYẾT (ORACLE)")
    print("=" * 110)
    h4 = ["Cấu hình", "Tỷ lệ Kích hoạt", "Báo động nhầm", "Sửa thành công", "Chặn OOC sau Verifier", "C_neg Cons sau Verifier", "P95 Tổng"]
    print(f"| {' | '.join(h4)} |")
    print(f"| {' | '.join(['---'] * len(h4))} |")
    for name, _, _ in configs:
        if "Verifier" not in name and "Phối hợp" not in name:
            continue
        if name not in summaries:
            continue
        S = summaries[name]
        trig = fmt_pct_ci(S.get("verifier_triggered"))
        fa = fmt_pct_ci(S.get("verifier_false_alarm"))
        succ = fmt_pct_ci(S.get("verifier_success_given_triggered"))
        ooc = fmt_pct_ci(S.get("ooc_correct"))
        cn = fmt_pct_ci(S.get("cneg_cons_real"))
        p95 = f"{S['latency_total_ms']['p95']:.0f} ms"
        print(f"| {name:<35} | {trig:<15} | {fa:<15} | {succ:<15} | {ooc:<22} | {cn:<24} | {p95:<10} |")


if __name__ == "__main__":
    main()
