#!/usr/bin/env python3
"""
rescore_ablation.py  -  chấm lại điểm các lần chạy ablation từ file .jsonl, KHÔNG gọi lại mô hình

Dùng khi sửa định nghĩa/lỗi của hàm chấm điểm (ví dụ brand_match giờ giải mã HTML entity).
Với mỗi <model>_<cfg>.jsonl + .csv:
  * dựng lại JSON cuối cùng (JSON gốc + các trường Verifier đã sửa nếu thành công),
  * chạy lại evaluate() của runner v3 cho các cột chỉ số (hallu_*, ooc_*, cons_*, pros_cons_*, ...),
  * giữ nguyên độ trễ, token, kết quả judge (cons_grounded) và mọi cột không phụ thuộc cách chấm,
  * sao lưu CSV gốc thành <file>.bak.csv (một lần), ghi lại CSV và .summary.json,
  * in so sánh trước/sau cho ảo giác tổng hợp, brand sai, giá sai.

Ví dụ
  python rescore_ablation.py --out_dir results_ablation --dry_run   # chỉ xem thay đổi
  python rescore_ablation.py --out_dir results_ablation             # ghi đè (có backup)
"""
import os
import re
import sys
import json
import glob
import shutil
import argparse
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import benchmark_runner_ablation_v3 as v3  # noqa: E402
from benchmark_runner_4pillars_v2 import extract_json  # noqa: E402


def reconstruct_final(rec: dict) -> dict:
    parsed = rec.get("parsed_json")
    if not isinstance(parsed, dict):
        return None
    ver = rec.get("verifier") or {}
    if ver.get("success") and ver.get("raw"):
        fixed = extract_json(ver["raw"])
        if fixed:
            merged = dict(parsed)
            for k in v3.MERGE_KEYS:
                if k in fixed:
                    merged[k] = fixed[k]
            return merged
    return parsed


def rescore_one(csv_path: str, kb: dict, samples: dict, dry_run: bool):
    base = csv_path[:-4]
    jsonl_path = base + ".jsonl"
    if not os.path.exists(jsonl_path):
        print(f"⚠️  Bỏ qua {os.path.basename(csv_path)}: không có file .jsonl")
        return None
    last = {}
    for line in open(jsonl_path, encoding="utf-8"):
        r = json.loads(line)
        last[r["sample_id"]] = r

    df = pd.read_csv(csv_path)
    before = {"hallucination_any": int(df["hallucination_any"].fillna(False).astype(bool).sum()),
              "brand_mismatch": int(df.get("brand_mismatch", pd.Series(False, index=df.index)).fillna(False).astype(bool).sum()),
              "price_mismatch": int(df.get("price_mismatch", pd.Series(False, index=df.index)).fillna(False).astype(bool).sum())}
    changed = 0
    for i, row in df.iterrows():
        if not bool(row.get("json_valid")):
            continue
        rec = last.get(row["sample_id"])
        sample = samples.get(row["sample_id"])
        final, parsed = (reconstruct_final(rec) if rec else None), (rec.get("parsed_json") if rec else None)
        if rec is None or sample is None or final is None:
            continue
        ctx = (rec.get("context") or {}).get("catalog_asins", [])
        ev = v3.evaluate(final, sample, kb, ctx)
        ev_pre = v3.evaluate(parsed, sample, kb, ctx)
        new_vals = dict(ev)
        new_vals["cons_nonempty_pre"] = ev_pre["cons_nonempty"]
        new_vals["hallucination_any"] = bool(ev["hallu_asin"] or ev["hallu_attr"] or ev["ooc_wrong_rec"])
        for k, v in new_vals.items():
            if k not in df.columns:
                df[k] = None
            if df.at[i, k] != v:
                changed += 1
            df.at[i, k] = v
    after = {"hallucination_any": int(df["hallucination_any"].fillna(False).astype(bool).sum()),
             "brand_mismatch": int(df["brand_mismatch"].fillna(False).astype(bool).sum()),
             "price_mismatch": int(df["price_mismatch"].fillna(False).astype(bool).sum())}

    if not dry_run:
        bak = base + ".bak.csv"
        if not os.path.exists(bak):
            shutil.copyfile(csv_path, bak)
        df.to_csv(csv_path, index=False)
        sj = base + ".summary.json"
        meta = {}
        if os.path.exists(sj):
            old = json.load(open(sj, encoding="utf-8"))
            meta = {k: old[k] for k in ("model", "config", "components", "model_id_used", "temperature", "max_tokens",
                                       "seed", "k", "neg_r", "ooc_context", "prompt_version", "judge_model") if k in old}
        S = v3.summarize(df, meta)
        json.dump(S, open(sj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return before, after, changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", default=os.path.join(HERE, "results_ablation"))
    ap.add_argument("--testset", default=os.path.join(v3.DATA_DIR, "benchmark_test_500.json"))
    ap.add_argument("--dry_run", action="store_true")
    a = ap.parse_args()

    kb = v3.load_real_kb()
    samples = {s["sample_id"]: s for s in json.load(open(a.testset, encoding="utf-8"))}
    print(f"{'Mô hình/cấu hình':<28} {'ảo giác tổng hợp':>20} {'sai brand':>14} {'sai giá':>12}  ô thay đổi")
    for path in sorted(glob.glob(os.path.join(a.out_dir, "*_A[0-6].csv"))):
        if path.endswith(".bak.csv") or path.endswith(".partial.csv"):
            continue
        res = rescore_one(path, kb, samples, a.dry_run)
        if res is None:
            continue
        b, af, ch = res
        name = os.path.basename(path)[:-4]
        print(f"{name:<28} {b['hallucination_any']:>8} → {af['hallucination_any']:<8} "
              f"{b['brand_mismatch']:>5} → {af['brand_mismatch']:<5} {b['price_mismatch']:>4} → {af['price_mismatch']:<4} {ch:>8}")
    print("\n(dry run: chưa ghi gì)" if a.dry_run else "\nĐã ghi CSV + summary (bản gốc: *.bak.csv). Chạy lại analyze_ablation.py để cập nhật bảng.")


if __name__ == "__main__":
    main()
