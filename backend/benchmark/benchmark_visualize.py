import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

# Cấu hình UTF-8 cho Windows console
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Thiết lập phong cách hiển thị biểu đồ học thuật chuẩn quốc tế
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 14

def to_markdown_table(df_table: pd.DataFrame) -> str:
    """Tự sinh bảng Markdown chuẩn mà không cần thư viện tabulate bên ngoài"""
    headers = list(df_table.columns)
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df_table.iterrows():
        row_vals = [str(val) for val in row.values]
        lines.append("| " + " | ".join(row_vals) + " |")
    return "\n".join(lines)

def plot_benchmark_figures(
    results_csv: str = "benchmark_results.csv",
    output_dir: str = None
):
    csv_path = os.path.join(CURRENT_DIR, results_csv)
    if not os.path.exists(csv_path):
        print(f"❌ Không tìm thấy file dữ liệu: {csv_path}")
        return

    out_dir = output_dir or CURRENT_DIR
    os.makedirs(out_dir, exist_ok=True)

    df = pd.read_csv(csv_path)
    print(f"📈 Đang đọc {len(df)} dòng dữ liệu từ {results_csv} để tạo biểu đồ...")

    # Bảng tổng hợp hiệu năng
    summary = df.groupby(["Model", "Prompt_Type"]).agg(
        Total_Queries=("Query_ID", "count"),
        SQL_Success_Rate=("SQL_Success", lambda x: round(x.mean() * 100, 2)),
        JSON_Valid_Rate=("JSON_Valid", lambda x: round(x.mean() * 100, 2)),
        Avg_Latency_ms=("Latency_ms", lambda x: round(x.mean(), 2)),
        P95_Latency_ms=("Latency_ms", lambda x: round(x.quantile(0.95), 2)),
        Hallucination_Rate=("Error_Code", lambda x: round((x.str.contains("Hallucination", na=False)).mean() * 100, 2))
    ).reset_index()

    print("\n--- BẢNG THỐNG KÊ TỔNG HỢP HIỆU NĂNG ---")
    print(summary.to_string(index=False))

    # ==========================================================================
    # HÌNH 1: SCATTER PLOT (LOG-SCALE) - ĐÁNH ĐỔI ĐỘ TRỄ VS TỶ LỆ THÀNH CÔNG
    # ==========================================================================
    # Cải tiến: Dùng thang đo Logarit trục X để tách biệt các model 1-4s không bị đè lên nhau
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=300)
    
    colors = {
        "Zero-shot": "#E76F51",       # Đỏ cam (baseline)
        "Graph-CoT": "#2A9D8F"        # Xanh ngọc (đề xuất)
    }
    markers = {
        "Zero-shot": "o",
        "Graph-CoT": "^"
    }

    # Vẽ các điểm phân tán
    for p_type in ["Zero-shot", "Graph-CoT"]:
        sub_df = summary[summary["Prompt_Type"] == p_type]
        ax.scatter(
            sub_df["Avg_Latency_ms"],
            sub_df["SQL_Success_Rate"],
            label=f"{p_type} Prompting",
            color=colors[p_type],
            marker=markers[p_type],
            s=170,
            alpha=0.9,
            edgecolors="black",
            linewidth=1.2,
            zorder=4
        )

    # Đặt trục X theo thang Logarit để phân tán đều từ 1.000ms đến 100.000ms
    ax.set_xscale("log")
    ax.set_xlim(800, 150000)
    ax.set_ylim(-5, 108)

    # Tùy chỉnh nhãn trục X thành giây dễ đọc
    tick_values = [1000, 2000, 5000, 10000, 20000, 50000, 100000]
    tick_labels = ["1s", "2s", "5s", "10s", "20s", "50s", "100s"]
    ax.set_xticks(tick_values)
    ax.get_xaxis().set_major_formatter(ticker.FixedFormatter(tick_labels))

    # Đặt nhãn chú thích thông minh không bị đè nhau
    custom_offsets = {
        ("gemini-1.5-flash", "Zero-shot"): (-25, 12),
        ("gemini-1.5-flash", "Graph-CoT"): (15, 12),
        ("gpt-4o-mini", "Zero-shot"): (-15, -18),
        ("gpt-4o-mini", "Graph-CoT"): (25, -16),
        ("qwen2.5:3b", "Zero-shot"): (30, -5),
        ("qwen2.5:3b", "Graph-CoT"): (30, 8),
        ("gemma2:2b", "Zero-shot"): (35, 0),
        ("gemma2:2b", "Graph-CoT"): (35, 0),
        ("qwen2.5-coder:7b", "Zero-shot"): (40, 5),
        ("qwen2.5-coder:7b", "Graph-CoT"): (40, -15),
        ("llama3.1:8b", "Zero-shot"): (-45, 12),
        ("llama3.1:8b", "Graph-CoT"): (40, 10),
        ("mistral:7b", "Zero-shot"): (-35, -18),
        ("mistral:7b", "Graph-CoT"): (35, 5),
        ("deepseek-r1:7b", "Zero-shot"): (-45, 12),
        ("deepseek-r1:7b", "Graph-CoT"): (40, -10),
    }

    for _, row in summary.iterrows():
        key = (row["Model"], row["Prompt_Type"])
        dx, dy = custom_offsets.get(key, (20, 10))
        label_text = f"{row['Model']}"
        ax.annotate(
            label_text,
            (row["Avg_Latency_ms"], row["SQL_Success_Rate"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=8.5,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#999999", alpha=0.85),
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0", color="#666666", lw=0.7),
            zorder=5
        )

    # Vùng phân chia học thuật
    ax.axvspan(800, 6000, color="#E8F5E9", alpha=0.4, label="Interactive Zone (<6s)")
    ax.text(2200, 5, "⚡ Interactive Real-time Zone (<6s)", fontsize=9, color="#2E7D32", style="italic", ha="center")

    ax.set_title("Trade-off Between Inference Latency (Log Scale) and SQL Execution Success Rate", pad=15)
    ax.set_xlabel("Average Latency (Log Scale, Thấp hơn là tốt hơn) [ms/s]")
    ax.set_ylabel("SQL Execution Success Rate (%) [Cao hơn là tốt hơn]")
    ax.grid(True, which="both", linestyle="--", alpha=0.5, zorder=0)
    ax.legend(loc="lower left", frameon=True, shadow=True)
    
    fig1_path = os.path.join(out_dir, "figure1_latency_vs_sql_success.png")
    plt.tight_layout()
    plt.savefig(fig1_path)
    plt.close()
    print(f"  ✅ Đã lưu Biểu đồ 1 (Log-scale cải tiến): {fig1_path}")

    # ==========================================================================
    # HÌNH 2: HORIZONTAL GROUPED BAR CHART - SO SÁNH TRỰC DIỆN RÕ RÀNG
    # ==========================================================================
    # Sắp xếp mô hình theo điểm trung bình từ cao đến thấp
    model_order = summary.groupby("Model")["SQL_Success_Rate"].mean().sort_values(ascending=True).index.tolist()
    
    fig, ax = plt.subplots(figsize=(10, 7), dpi=300)
    y = np.arange(len(model_order))
    height = 0.38

    zs_vals = []
    cot_vals = []
    for m in model_order:
        zv = summary[(summary["Model"] == m) & (summary["Prompt_Type"] == "Zero-shot")]["SQL_Success_Rate"]
        cv = summary[(summary["Model"] == m) & (summary["Prompt_Type"] == "Graph-CoT")]["SQL_Success_Rate"]
        zs_vals.append(zv.values[0] if len(zv) > 0 else 0)
        cot_vals.append(cv.values[0] if len(cv) > 0 else 0)

    rects1 = ax.barh(y - height/2, zs_vals, height, label="Zero-shot (Baseline)", color="#E76F51", edgecolor="black", linewidth=0.8)
    rects2 = ax.barh(y + height/2, cot_vals, height, label="Graph-CoT (Proposed)", color="#2A9D8F", edgecolor="black", linewidth=0.8)

    ax.set_title("SQL Execution Accuracy: Zero-shot vs. Graph-CoT across 8 LLM Architectures", pad=15)
    ax.set_xlabel("Execution Success Rate (%)")
    ax.set_yticks(y)
    ax.set_yticklabels(model_order, fontweight="bold")
    ax.set_xlim(0, 115)
    ax.grid(axis="x", linestyle="--", alpha=0.6)
    ax.legend(loc="lower right", frameon=True)

    # Thêm số liệu rõ ràng bên cạnh từng thanh bar
    for rect in rects1:
        w = rect.get_width()
        ax.annotate(f"{w:.1f}%", xy=(w, rect.get_y() + rect.get_height()/2),
                    xytext=(4, 0), textcoords="offset points", ha="left", va="center", fontsize=8.5, fontweight="bold", color="#A83220")

    for rect in rects2:
        w = rect.get_width()
        ax.annotate(f"{w:.1f}%", xy=(w, rect.get_y() + rect.get_height()/2),
                    xytext=(4, 0), textcoords="offset points", ha="left", va="center", fontsize=8.5, fontweight="bold", color="#1D6C60")

    fig2_path = os.path.join(out_dir, "figure2_prompt_comparison_bar.png")
    plt.tight_layout()
    plt.savefig(fig2_path)
    plt.close()
    print(f"  ✅ Đã lưu Biểu đồ 2 (Nằm ngang không bị đè nhãn): {fig2_path}")

    # ==========================================================================
    # HÌNH 3: PHÂN TÍCH TỶ LỆ LỖI VÀ ẢO GIÁC (CLEAN HORIZONTAL STACKED BAR)
    # ==========================================================================
    failed_rows = df[df["SQL_Success"] == 0].copy()
    if not failed_rows.empty:
        # Gom nhóm lỗi thành các hạng mục lớn dễ hiểu
        def categorize_error(code):
            c = str(code)
            if "Column Hallucination" in c: return "Column Hallucination"
            if "Schema Hallucination" in c: return "Schema Hallucination"
            if "JSON" in c or "Decode" in c: return "JSON Formatting Failure"
            if "MissingSQLKey" in c: return "Missing SQL Field"
            if "HTTP" in c or "500" in c: return "HTTP / Token Limit Abortion"
            if "Syntax" in c: return "SQL Syntax Error"
            if "Empty" in c: return "Empty Model Response"
            return "Other Execution Error"

        failed_rows["Error_Category"] = failed_rows["Error_Code"].apply(categorize_error)
        failed_rows["Model_Prompt"] = failed_rows["Model"] + " (" + failed_rows["Prompt_Type"] + ")"

        # Lấy bảng tần suất lỗi
        err_matrix = failed_rows.groupby(["Model_Prompt", "Error_Category"]).size().unstack(fill_value=0)
        # Sắp xếp theo tổng số lỗi giảm dần
        err_matrix["Total"] = err_matrix.sum(axis=1)
        err_matrix = err_matrix.sort_values(by="Total", ascending=True).drop(columns=["Total"])

        fig, ax = plt.subplots(figsize=(11, 6.5), dpi=300)
        # Bảng màu phân biệt rõ ràng
        palette = ["#D62828", "#F77F00", "#FCBF49", "#003049", "#6A4C93", "#4A7C59", "#8D99AE"]
        err_matrix.plot(kind="barh", stacked=True, ax=ax, color=palette[:len(err_matrix.columns)], edgecolor="black", linewidth=0.6)

        ax.set_title("Taxonomy of Query Generation Failures & Hallucinations by Model and Prompt", pad=15)
        ax.set_xlabel("Number of Failure Cases (Out of 100 queries)")
        ax.set_ylabel("(Model, Prompt Strategy)")
        ax.grid(axis="x", linestyle="--", alpha=0.6)
        plt.legend(title="Failure Category", bbox_to_anchor=(1.02, 1), loc="upper left", frameon=True)

        fig3_path = os.path.join(out_dir, "figure3_hallucination_breakdown.png")
        plt.tight_layout()
        plt.savefig(fig3_path)
        plt.close()
        print(f"  ✅ Đã lưu Biểu đồ 3 (Phân loại lỗi sạch sẽ): {fig3_path}")

    # ==========================================================================
    # HÌNH 4 (MỚI): HEATMAP ĐỘ CHÍNH XÁC THEO 6 LOẠI CÂU HỎI TRUY VẤN
    # ==========================================================================
    # Cực kỳ giá trị cho bài báo: Thể hiện mô hình nào mạnh ở câu hỏi trực tiếp hay câu ngữ cảnh
    pivot_acc = df.pivot_table(
        index=["Model", "Prompt_Type"],
        columns="Query_Type",
        values="SQL_Success",
        aggfunc="mean"
    ) * 100

    # Đổi tên cột cho ngắn gọn
    type_rename = {
        "Direct_Category": "Direct Cat",
        "Contextual_Lifestyle": "Contextual",
        "Multi_Attribute_Budget": "Multi-Attr",
        "OutOfStock_ColorShift": "Out-of-Stock",
        "Kids_Specialized": "Kids Spec",
        "Accessories_Edge": "Accessories"
    }
    pivot_acc = pivot_acc.rename(columns=type_rename)

    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    sns.heatmap(
        pivot_acc,
        annot=True,
        fmt=".1f",
        cmap="YlGnBu",
        cbar_kws={'label': 'SQL Success Rate (%)'},
        linewidths=0.5,
        linecolor="white",
        ax=ax,
        vmin=0,
        vmax=100
    )
    ax.set_title("SQL Execution Accuracy (%) across 6 Query Complexity Categories", pad=15)
    ax.set_xlabel("Query Complexity & Intent Category", labelpad=10)
    ax.set_ylabel("(Model, Prompting Strategy)", labelpad=10)

    fig4_path = os.path.join(out_dir, "figure4_query_complexity_heatmap.png")
    plt.tight_layout()
    plt.savefig(fig4_path)
    plt.close()
    print(f"  ✅ Đã lưu Biểu đồ 4 (Heatmap phân tầng câu hỏi): {fig4_path}")

    # ==========================================================================
    # HÌNH 5 (MỚI): BOXPLOT PHÂN BỐ ĐỘ TRỄ (LATENCY VARIANCE & STABILITY)
    # ==========================================================================
    # Chứng minh tính ổn định của Cloud API vs độ trễ biến thiên lớn của Local 7B
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)
    
    # Sắp xếp theo thứ tự độ trễ trung vị tăng dần
    median_order = df.groupby("Model")["Latency_ms"].median().sort_values().index.tolist()
    
    sns.boxplot(
        data=df,
        x="Model",
        y="Latency_ms",
        hue="Prompt_Type",
        order=median_order,
        palette={"Zero-shot": "#E76F51", "Graph-CoT": "#2A9D8F"},
        ax=ax,
        showmeans=True,
        meanprops={"marker": "o", "markerfacecolor": "white", "markeredgecolor": "black", "markersize": "5"}
    )
    ax.set_yscale("log")
    ax.set_yticks([1000, 2000, 5000, 10000, 20000, 50000, 100000, 150000])
    ax.get_yaxis().set_major_formatter(ticker.FixedFormatter(["1s", "2s", "5s", "10s", "20s", "50s", "100s", "150s"]))
    
    ax.set_title("Inference Latency Distribution & Outliers (Log Scale)", pad=15)
    ax.set_xlabel("Evaluated LLM Architectures (Ordered by Speed)")
    ax.set_ylabel("Inference Latency (ms / s)")
    plt.xticks(rotation=20, ha="right", fontweight="bold")
    ax.grid(True, which="both", axis="y", linestyle="--", alpha=0.5)
    ax.legend(title="Prompting Strategy", loc="upper left")

    fig5_path = os.path.join(out_dir, "figure5_latency_distribution_boxplot.png")
    plt.tight_layout()
    plt.savefig(fig5_path)
    plt.close()
    print(f"  ✅ Đã lưu Biểu đồ 5 (Boxplot độ trễ & độ ổn định): {fig5_path}")

    # ==========================================================================
    # XUẤT BẢNG LATEX & MARKDOWN
    # ==========================================================================
    tex_path = os.path.join(out_dir, "paper_summary_table.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        latex_str = summary.to_latex(
            index=False,
            caption="Comprehensive Performance Evaluation of 8 LLM Architectures under Zero-shot and Graph-CoT Prompting.",
            label="tab:llm_benchmark_all"
        )
        f.write(latex_str)
    print(f"  📝 Đã xuất bảng LaTeX: {tex_path}")

    md_path = os.path.join(out_dir, "paper_summary_table.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 📊 BẢNG TỔNG HỢP KẾT QUẢ THỰC NGHIỆM CHO BÀI BÁO KHOA HỌC (8 MÔ HÌNH)\n\n")
        f.write(to_markdown_table(summary))
        f.write("\n")
    print(f"  📝 Đã xuất bảng Markdown: {md_path}")

    print("\n🎉 HOÀN TẤT VẼ LẠI VÀ XUẤT TOÀN BỘ 5 BIỂU ĐỒ HỌC THUẬT ĐẲNG CẤP!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trực quan hóa kết quả benchmark phục vụ bài báo khoa học")
    parser.add_argument("--csv", type=str, default="benchmark_results.csv", help="File CSV kết quả")
    parser.add_argument("--outdir", type=str, default=None, help="Thư mục lưu biểu đồ")
    args = parser.parse_args()

    plot_benchmark_figures(results_csv=args.csv, output_dir=args.outdir)
