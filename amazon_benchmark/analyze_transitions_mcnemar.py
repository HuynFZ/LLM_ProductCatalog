"""
analyze_transitions_mcnemar.py
Bảng chuyển trạng thái (State Transition Table) và Kiểm định McNemar chính xác (Exact McNemar Test)
cho từng bước chuyển đổi:
- Bước 1: Thô (Raw) -> Sau sửa luật (Rule Repair)
- Bước 2: Sau sửa luật -> Sau Verifier (Cascaded Observable)
- Bước 3: Thô (Raw) -> Sau Verifier (Pure Verifier Observable)
"""

import json
import os
import sys
import argparse
import pandas as pd
import numpy as np
from scipy.stats import binomtest


def is_sample_correct(row):
    """
    Tiêu chuẩn mẫu ĐẠT TOÀN DIỆN:
    - Nếu OOC: ooc_correct == True
    - Nếu C_neg: false_refusal == False, rec_is_gold == True, cneg_cons_real == True, hallucination_any == False
    - Nếu Standard: false_refusal == False, rec_is_gold == True, hallucination_any == False
    """
    t = row["test_type"]
    if t == "out_of_catalog_adversarial":
        return bool(row.get("ooc_correct", False))
    elif t == "in_catalog_c_neg":
        return bool(not row.get("false_refusal", True) and row.get("rec_is_gold", False)
                    and row.get("cneg_cons_real", False) and not row.get("hallucination_any", True))
    else:
        return bool(not row.get("false_refusal", True) and row.get("rec_is_gold", False)
                    and not row.get("hallucination_any", True))


def compute_transition(s_before, s_after, name):
    """
    Tính bảng 2x2:
    - a: 1 -> 1 (Giữ nguyên ĐÚNG)
    - b: 1 -> 0 (BỊ HỎNG / HỒI QUY)
    - c: 0 -> 1 (ĐƯỢC CỨU / SỬA ĐÚNG)
    - d: 0 -> 0 (Giữ nguyên SAI)
    """
    a = int(np.sum((s_before == True) & (s_after == True)))
    b = int(np.sum((s_before == True) & (s_after == False)))
    c = int(np.sum((s_before == False) & (s_after == True)))
    d = int(np.sum((s_before == False) & (s_after == False)))
    n_total = a + b + c + d

    # Exact McNemar Test (Binomial test on discordant pairs b and c)
    discordant = b + c
    if discordant == 0:
        p_val = 1.0
    else:
        # 2-sided binomial test
        res = binomtest(c, discordant, p=0.5, alternative='two-sided')
        p_val = res.pvalue

    return {
        "name": name, "n": n_total,
        "kept_correct": a, "regressed": b, "rescued": c, "kept_wrong": d,
        "acc_before": (a + b) / n_total * 100,
        "acc_after": (a + c) / n_total * 100,
        "net_gain": c - b,
        "p_value": p_val
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--res_dir", default="amazon_benchmark/results_disentangle")
    parser.add_argument("--suffix", default="")
    args = parser.parse_args()

    res_dir = args.res_dir
    suf = f"_{args.suffix}" if args.suffix else ""

    f_raw = f"{res_dir}/qwen2.5-3b_A5_v12_raw{suf}.csv"
    f_rep = f"{res_dir}/qwen2.5-3b_A5_v12_repair{suf}.csv"
    f_cas = f"{res_dir}/qwen2.5-3b_A6_v12_cascaded_obs{suf}.csv"
    f_ver = f"{res_dir}/qwen2.5-3b_A6_v12_verifier_obs{suf}.csv"

    if not os.path.exists(f_raw) or not os.path.exists(f_rep):
        print(f"❌ Không tìm thấy file dữ liệu tại {res_dir}")
        return

    df_raw = pd.read_csv(f_raw)
    df_rep = pd.read_csv(f_rep)
    df_cas = pd.read_csv(f_cas) if os.path.exists(f_cas) else None
    df_ver = pd.read_csv(f_ver) if os.path.exists(f_ver) else None

    # Loại bỏ mẫu api error nếu có
    valid_ids = df_raw.loc[df_raw.api_error == False, "sample_id"].values
    df_raw = df_raw[df_raw.sample_id.isin(valid_ids)].sort_values("sample_id").reset_index(drop=True)
    df_rep = df_rep[df_rep.sample_id.isin(valid_ids)].sort_values("sample_id").reset_index(drop=True)
    if df_cas is not None:
        df_cas = df_cas[df_cas.sample_id.isin(valid_ids)].sort_values("sample_id").reset_index(drop=True)
    if df_ver is not None:
        df_ver = df_ver[df_ver.sample_id.isin(valid_ids)].sort_values("sample_id").reset_index(drop=True)

    metrics = [
        ("Đúng toàn diện (Overall Success)", is_sample_correct),
        ("Chặn OOC đúng (OOC Correct)", lambda r: bool(r.get("ooc_correct", False))),
        ("Không từ chối nhầm (In-Catalog 1-FR)", lambda r: bool(not r.get("false_refusal", True))),
        ("Chọn đúng Gold ASIN (Gold Match)", lambda r: bool(r.get("rec_is_gold", False))),
        ("C_neg có nhược điểm thật (Cons Real)", lambda r: bool(r.get("cneg_cons_real", False))),
    ]

    transitions = [
        ("Bước 1: Thô -> Sửa luật (Raw -> Rule Repair)", df_raw, df_rep),
    ]
    if df_cas is not None:
        transitions.append(("Bước 2: Sửa luật -> Verifier (Rule -> Cascaded Obs)", df_rep, df_cas))
    if df_ver is not None:
        transitions.append(("Bước 3: Thô -> Verifier thuần (Raw -> Verifier Obs)", df_raw, df_ver))
    if df_cas is not None:
        transitions.append(("Toàn trình: Thô -> Phối hợp (Raw -> Cascaded Obs)", df_raw, df_cas))

    print("=" * 115)
    print("BẢNG CHUYỂN TRẠNG THÁI (STATE TRANSITION) & KIỂM ĐỊNH MCNEMAR CHÍNH XÁC (EXACT TEST)")
    print("=" * 115)

    for trans_name, df_pre, df_post in transitions:
        print(f"\n📌 {trans_name}")
        headers = ["Chỉ số", "Trước (%)", "Sau (%)", "Được cứu (0->1)", "Bị hỏng (1->0)", "Giữ đúng (1->1)", "Giữ sai (0->0)", "Tăng ròng", "p-value (McNemar)"]
        print(f"| {' | '.join(headers)} |")
        print(f"| {' | '.join(['---'] * len(headers))} |")

        for m_label, m_func in metrics:
            # Filter subset if metric is subset-specific
            if "OOC" in m_label:
                sub_pre = df_pre[df_pre.test_type == "out_of_catalog_adversarial"]
                sub_post = df_post[df_post.test_type == "out_of_catalog_adversarial"]
            elif "In-Catalog" in m_label or "Gold" in m_label:
                sub_pre = df_pre[df_pre.test_type != "out_of_catalog_adversarial"]
                sub_post = df_post[df_post.test_type != "out_of_catalog_adversarial"]
            elif "C_neg" in m_label:
                sub_pre = df_pre[df_pre.test_type == "in_catalog_c_neg"]
                sub_post = df_post[df_post.test_type == "in_catalog_c_neg"]
            else:
                sub_pre = df_pre
                sub_post = df_post

            s_pre = sub_pre.apply(m_func, axis=1)
            s_post = sub_post.apply(m_func, axis=1)

            res = compute_transition(s_pre, s_post, m_label)

            p_str = f"{res['p_value']:.4f}" if res['p_value'] >= 0.0001 else "<0.0001"
            sig = "***" if res['p_value'] < 0.001 else ("**" if res['p_value'] < 0.01 else ("*" if res['p_value'] < 0.05 else "ns"))
            p_display = f"{p_str} ({sig})"

            print(f"| {m_label:<36} | {res['acc_before']:5.1f}% | {res['acc_after']:5.1f}% | "
                  f"{res['rescued']:^14} | {res['regressed']:^13} | {res['kept_correct']:^14} | "
                  f"{res['kept_wrong']:^13} | {res['net_gain']:^+9} | {p_display:<17} |")


if __name__ == "__main__":
    main()
