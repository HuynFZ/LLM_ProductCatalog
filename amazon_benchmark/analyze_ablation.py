#!/usr/bin/env python3
"""
analyze_ablation.py  -  phân tích sau thực nghiệm cho results_ablation/<model>_<config>.csv (+ .jsonl)

Sinh 4 bảng Markdown (in ra màn hình và ghi vào <out_dir>/analysis_*.md):
  1. conditional : trả lời được bao nhiêu, ảo giác KHI ĐÃ TRẢ LỜI, chọn đúng sản phẩm, OOC đúng, từ chối nhầm
                   (để thấy ảo giác thấp có phải chỉ vì mô hình từ chối nhiều hay không)
  2. pros_cons   : tách có pros/cons theo loại mẫu (thường / C_neg) để chẩn đoán các lần tụt đột ngột
  3. paired      : khác biệt giữa hai cấu hình liền kề bằng bootstrap GHÉP CẶP (điểm phần trăm, CI95)
  4. sla         : P95 độ trễ tổng và tỷ lệ yêu cầu vượt 10 giây
Tùy chọn --examples N: in N mẫu sai brand/giá từ file .jsonl để kiểm tra bằng mắt.

Ví dụ
  python analyze_ablation.py --out_dir results_ablation
  python analyze_ablation.py --out_dir results_ablation --pairs A0:A3,A3:A6 --boot 20000
  python analyze_ablation.py --out_dir results_ablation --examples 10 --model gpt-4o-mini --config A6
"""
import os
import re
import sys
import json
import glob
import argparse
import numpy as np
import pandas as pd

CONFIGS = ["A0", "A1", "A2", "A3", "A4", "A5", "A6"]
OOC = "out_of_catalog_adversarial"
CNEG = "in_catalog_c_neg"
BOOLS = ["api_error", "json_valid", "parse_fail", "hallu_asin", "hallu_attr", "brand_mismatch", "price_mismatch",
         "rec_outside_context", "unsupported_rec", "rec_is_gold", "ooc_wrong_rec", "ooc_correct", "false_refusal",
         "cons_nonempty", "pros_nonempty", "pros_cons_balanced", "rec_nonnull", "hallucination_any", "rejected_raw"]


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def pct(k, n):
    if n == 0:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% [{100 * lo:.1f}–{100 * hi:.1f}] ({k}/{n})"


def load_all(out_dir):
    data = {}
    for path in sorted(glob.glob(os.path.join(out_dir, "*_A[0-6].csv"))):
        m = re.match(r"(.+)_(A[0-6])\.csv$", os.path.basename(path))
        if not m:
            continue
        df = pd.read_csv(path)
        for c in BOOLS:
            df[c] = df[c].fillna(False).astype(bool) if c in df.columns else False
        for c in ("brand_mismatch", "price_mismatch"):
            if c not in df.columns:
                df[c] = False
        if "cons_grounded" not in df.columns:
            df["cons_grounded"] = np.nan
        data.setdefault(m.group(1), {})[m.group(2)] = df
    return data


def metric_series(df, name):
    """Chuỗi 0/1/NaN theo sample_id (NaN = mẫu không thuộc mẫu số)."""
    ok, t = ~df.api_error, df.test_type
    valid, incat = ok & df.json_valid, t != OOC
    if name == "hallucination_any":
        m, v = valid, df.hallucination_any
    elif name == "ooc_correct":
        m, v = ok & (t == OOC), df.ooc_correct
    elif name == "false_refusal":
        m, v = valid & incat, df.false_refusal
    elif name == "cons_nonempty_cneg":
        m, v = ok & (t == CNEG), df.cons_nonempty
    elif name == "cons_grounded_cneg":
        m, v = ok & (t == CNEG) & df.cons_grounded.notna(), df.cons_grounded.fillna(False).astype(bool)
    elif name == "pros_cons_incat":
        m, v = ok & incat, df.pros_cons_balanced
    elif name == "rec_is_gold":
        m, v = valid & incat, df.rec_is_gold
    else:
        raise ValueError(name)
    return pd.Series(np.where(m, v.astype(float), np.nan), index=df.sample_id.values)


PAIRED_METRICS = [("Ảo giác tổng hợp ↓", "hallucination_any"), ("OOC đúng ↑", "ooc_correct"),
                  ("Từ chối nhầm ↓", "false_refusal"), ("Chọn đúng sản phẩm ↑", "rec_is_gold"),
                  ("C_neg có cons ↑", "cons_nonempty_cneg"), ("Cons bám C_neg ↑", "cons_grounded_cneg"),
                  ("Pros&Cons ↑", "pros_cons_incat")]


def paired_boot(a, b, B, rng):
    idx = a.index.intersection(b.index)
    x, y = a.loc[idx].values, b.loc[idx].values
    keep = ~(np.isnan(x) | np.isnan(y))
    x, y = x[keep], y[keep]
    n = len(x)
    if n == 0:
        return None
    d_obs = (y.mean() - x.mean()) * 100
    ids = rng.integers(0, n, size=(B, n))
    d = (y[ids].mean(axis=1) - x[ids].mean(axis=1)) * 100
    lo, hi = np.percentile(d, [2.5, 97.5])
    return n, d_obs, lo, hi


def table_conditional(data):
    out = ["| Mô hình | Cfg | Trả lời được (mẫu trong danh mục) ↑ | Ảo giác KHI ĐÃ trả lời ↓ | Chọn đúng sản phẩm ↑ | OOC đúng ↑ | Từ chối nhầm ↓ |",
           "|---|---|---|---|---|---|---|"]
    for model, cfgs in data.items():
        for cfg in CONFIGS:
            if cfg not in cfgs:
                continue
            df = cfgs[cfg]
            ok, t = ~df.api_error, df.test_type
            valid, incat = ok & df.json_valid, t != OOC
            a = valid & incat
            answered = a & ~df.false_refusal
            ans_k, ans_n = int(answered.sum()), int(a.sum())
            hh = answered & df.rec_nonnull
            hallu_k = int((hh & (df.hallu_asin | df.hallu_attr)).sum())
            gold_k = int((a & df.rec_is_gold).sum())
            ooc_n = int((ok & (t == OOC)).sum())
            ooc_k = int((ok & (t == OOC) & df.ooc_correct).sum())
            fr_k = int((a & df.false_refusal).sum())
            out.append(f"| {model} | {cfg} | {pct(ans_k, ans_n)} | {pct(hallu_k, int(hh.sum()))} | "
                       f"{pct(gold_k, ans_n)} | {pct(ooc_k, ooc_n)} | {pct(fr_k, ans_n)} |")
    return "\n".join(out)


def table_pros_cons(data):
    out = ["| Mô hình | Cfg | Thường: có cons | Thường: có pros | C_neg: có cons | C_neg: có pros |",
           "|---|---|---|---|---|---|"]
    for model, cfgs in data.items():
        for cfg in CONFIGS:
            if cfg not in cfgs:
                continue
            df = cfgs[cfg]
            ok, t = ~df.api_error, df.test_type
            std, cn = ok & (t != OOC) & (t != CNEG), ok & (t == CNEG)
            f = lambda col, m: pct(int((m & df[col]).sum()), int(m.sum()))
            out.append(f"| {model} | {cfg} | {f('cons_nonempty', std)} | {f('pros_nonempty', std)} | "
                       f"{f('cons_nonempty', cn)} | {f('pros_nonempty', cn)} |")
    return "\n".join(out)


def table_paired(data, pairs, B, seed):
    rng = np.random.default_rng(seed)
    out = [f"Bootstrap ghép cặp ({B} lần), Δ = (cấu hình sau − cấu hình trước), đơn vị: điểm phần trăm. "
           "`*` = CI95 không chứa 0.\n",
           "| Mô hình | Cặp | " + " | ".join(n for n, _ in PAIRED_METRICS) + " |",
           "|---|---|" + "---|" * len(PAIRED_METRICS)]
    for model, cfgs in data.items():
        for c1, c2 in pairs:
            if c1 not in cfgs or c2 not in cfgs:
                continue
            cells = []
            for _, key in PAIRED_METRICS:
                r = paired_boot(metric_series(cfgs[c1], key), metric_series(cfgs[c2], key), B, rng)
                if r is None:
                    cells.append("n/a")
                else:
                    n, d, lo, hi = r
                    star = "*" if (lo > 0 or hi < 0) else ""
                    cells.append(f"{d:+.1f}{star} [{lo:+.1f}, {hi:+.1f}] (n={n})")
            out.append(f"| {model} | {c1}→{c2} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def table_sla(data):
    out = ["| Mô hình | Cfg | P95 lần gọi chính (ms) | P95 tổng (ms) | Yêu cầu > 10 s | Đạt SLA P95 < 10 s |",
           "|---|---|---|---|---|---|"]
    for model, cfgs in data.items():
        for cfg in CONFIGS:
            if cfg not in cfgs:
                continue
            df = cfgs[cfg]
            d = df.loc[~df.api_error]
            p1, pt = d.latency_ms.quantile(0.95), d.total_latency_ms.quantile(0.95)
            over = int((d.total_latency_ms > 10000).sum())
            out.append(f"| {model} | {cfg} | {p1:,.0f} | {pt:,.0f} | {pct(over, len(d))} | {'có' if pt < 10000 else 'KHÔNG'} |")
    return "\n".join(out)


def table_refusal(data):
    out = ["Tách từ chối theo NGỮ NGHĨA: cờ `is_out_of_catalog_rejected` (từ chối phạm vi) khác với việc không gợi ý (rec=null, không bật cờ). "
           "Mẫu số: mẫu JSON hợp lệ của từng loại.\n",
           "| Mô hình | Cfg | Loại mẫu | Bật cờ từ chối phạm vi | Không gợi ý, không bật cờ | Có gợi ý sản phẩm |", "|---|---|---|---|---|---|"]
    for model, cfgs in data.items():
        for cfg in CONFIGS:
            if cfg not in cfgs:
                continue
            df = cfgs[cfg]
            ok, t = ~df.api_error, df.test_type
            valid = ok & df.json_valid
            for label, mask in (("Thường", valid & (t != OOC) & (t != CNEG)), ("C_neg", valid & (t == CNEG))):
                n = int(mask.sum())
                flag = int((mask & df.rejected_raw).sum())
                norec = int((mask & ~df.rejected_raw & ~df.rec_nonnull).sum())
                rec = int((mask & df.rec_nonnull & ~df.rejected_raw).sum())
                out.append(f"| {model} | {cfg} | {label} | {pct(flag, n)} | {pct(norec, n)} | {pct(rec, n)} |")
    return "\n".join(out)


def attr_summary(data):
    out = ["| Mô hình | Cfg | Có gợi ý (trong danh mục) | Sai brand | Sai giá (>20%) | Sai brand hoặc giá |", "|---|---|---|---|---|---|"]
    for model, cfgs in data.items():
        for cfg in CONFIGS:
            if cfg not in cfgs:
                continue
            df = cfgs[cfg]
            m = (~df.api_error) & df.json_valid & (df.test_type != OOC) & df.rec_nonnull
            n = int(m.sum())
            out.append(f"| {model} | {cfg} | {n} | {pct(int((m & df.brand_mismatch).sum()), n)} | "
                       f"{pct(int((m & df.price_mismatch).sum()), n)} | {pct(int((m & df.hallu_attr).sum()), n)} |")
    return "\n".join(out)


def show_examples(out_dir, model, cfg, data, n):
    safe = model.replace(":", "-")
    if safe not in data and model in data:
        safe = model
    elif model not in data and safe in data:
        model = safe
    if model not in data or cfg not in data[model]:
        print(f"Không tìm thấy dữ liệu cho model {model} config {cfg}")
        return
    df = data[model][cfg]
    bad = df[df.hallu_attr & df.rec_nonnull]
    path = os.path.join(out_dir, f"{safe}_{cfg}.jsonl")
    last = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            last[r["sample_id"]] = r
    print(f"\n### Ví dụ sai brand/giá — {model} {cfg} ({len(bad)} mẫu, hiển thị {min(n, len(bad))})")
    for _, row in bad.head(n).iterrows():
        pj = (last.get(row["sample_id"], {}) or {}).get("parsed_json") or {}
        print(f"- sample {row['sample_id']} | rec={row['rec_id_raw']} | brand_mismatch={row['brand_mismatch']} "
              f"price_mismatch={row['price_mismatch']} | model brand={pj.get('brand')!r} price={pj.get('price_usd')!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", default="results_ablation")
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pairs", default=None, help="ví dụ A0:A1,A1:A2 (mặc định: các cặp liền kề)")
    ap.add_argument("--examples", type=int, default=0)
    ap.add_argument("--model", default=None)
    ap.add_argument("--config", default="A6")
    a = ap.parse_args()

    data = load_all(a.out_dir)
    if not data:
        sys.exit(f"Không thấy file <model>_A*.csv trong {a.out_dir}")
    pairs = [tuple(p.split(":")) for p in a.pairs.split(",")] if a.pairs else list(zip(CONFIGS[:-1], CONFIGS[1:]))

    sections = [("conditional", "Chỉ số có điều kiện (ảo giác khi đã trả lời, chọn đúng, OOC, từ chối nhầm)", table_conditional(data)),
                ("pros_cons", "Pros/Cons tách theo loại mẫu", table_pros_cons(data)),
                ("attr", "Phân rã lỗi thuộc tính (brand/giá)", attr_summary(data)),
                ("refusal", "Tách từ chối: cờ phạm vi và không gợi ý", table_refusal(data)),
                ("paired", "Khác biệt giữa các cấu hình liền kề (bootstrap ghép cặp)", table_paired(data, pairs, a.boot, a.seed)),
                ("sla", "Độ trễ và SLA 10 giây", table_sla(data))]
    for key, title, body in sections:
        text = f"## {title}\n\n{body}\n"
        print("\n" + text)
        with open(os.path.join(a.out_dir, f"analysis_{key}.md"), "w", encoding="utf-8") as f:
            f.write(text)
    if a.examples and a.model:
        show_examples(a.out_dir, a.model, a.config, data, a.examples)
    print(f"\nĐã ghi các file analysis_*.md vào {a.out_dir}")


if __name__ == "__main__":
    main()
