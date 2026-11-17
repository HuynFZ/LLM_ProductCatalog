import os
import sys
import glob
import pandas as pd
import numpy as np

# Cấu hình UTF-8 cho Windows Terminal
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def aggregate_benchmark_results():
    pattern = os.path.join(CURRENT_DIR, "results_4pillars_*.csv")
    csv_files = glob.glob(pattern)

    if not csv_files:
        print("❌ Chưa có file kết quả benchmark nào (results_4pillars_*.csv).")
        return None

    rows = []
    for f in csv_files:
        df = pd.read_csv(f)
        if df.empty:
            continue
        model_name = df['model_name'].iloc[0]
        n_total = len(df)
        avg_lat = df['latency_ms'].mean()
        p95_lat = df['latency_ms'].quantile(0.95)
        json_rate = (df['json_valid'].sum() / n_total) * 100
        hallu_rate = (df['hallucination'].sum() / n_total) * 100
        
        # Out-of-Catalog (OOC) Rejection Acc
        df_ooc = df[df['test_type'] == "out_of_catalog_adversarial"]
        ooc_acc = (df_ooc['ooc_rejected_correctly'].sum() / len(df_ooc) * 100) if not df_ooc.empty else 0.0

        # C_neg Violated
        df_cneg = df[df['test_type'] == "in_catalog_c_neg"]
        cneg_vio = (df_cneg['c_neg_violated'].sum() / len(df_cneg) * 100) if not df_cneg.empty else 0.0

        # Pros & Cons Dialectic Balance
        balance_rate = (df['pros_cons_balanced'].sum() / n_total) * 100

        rows.append({
            "Mô hình": model_name,
            "N": n_total,
            "Độ trễ TB (ms)": round(avg_lat, 1),
            "P95 (ms)": round(p95_lat, 1),
            "JSON Hợp lệ (%)": round(json_rate, 1),
            "Tỷ lệ Ảo giác (%)": round(hallu_rate, 1),
            "Chặn Ngoại lai OOC (%)": round(ooc_acc, 1),
            "Vi phạm C_neg (%)": round(cneg_vio, 1),
            "Cân bằng Pros/Cons (%)": round(balance_rate, 1)
        })

    summary_df = pd.DataFrame(rows).sort_values(by="Độ trễ TB (ms)")
    
    print("\n" + "=" * 90)
    print("📊 BẢNG TỔNG HỢP SO SÁNH BENCHMARK 4 TRỤ CỘT CHO CÁC MÔ HÌNH")
    print("=" * 90)
    print(summary_df.to_string(index=False))
    print("=" * 90)

    # Xuất Markdown Table thuần túy (không phụ thuộc tabulate)
    headers = list(summary_df.columns)
    md_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join([":---:" if i > 0 else ":---" for i in range(len(headers))]) + " |"
    ]
    for _, r in summary_df.iterrows():
        md_lines.append("| " + " | ".join(str(r[c]) for c in headers) + " |")
    md_table = "\n".join(md_lines)

    md_file = os.path.join(CURRENT_DIR, "BENCHMARK_SUMMARY.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("# Bảng So Sánh Đánh Giá Các Mô Hình (4-Pillar Conversational E-Commerce Framework)\n\n")
        f.write(md_table)
        f.write("\n\n*Ghi chú: Tỷ lệ Ảo giác và Vi phạm C_neg càng thấp càng tốt; Chặn OOC và Cân bằng Pros/Cons càng cao càng tốt.*\n")
    print(f"✅ Đã lưu tóm tắt Markdown tại: {md_file}")

    # Xuất LaTeX Table cho bài báo / luận văn
    tex_file = os.path.join(CURRENT_DIR, "paper_table_4pillars.tex")
    tex_content = summary_df.to_latex(index=False, float_format="%.1f", caption="Comprehensive 4-Pillar Benchmark across Candidate LLMs", label="tab:4pillars_benchmark")
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(tex_content)
    print(f"✅ Đã xuất mã bảng LaTeX tại: {tex_file}")

    return summary_df

if __name__ == "__main__":
    aggregate_benchmark_results()

