"""
plot_tradeoff_curve.py
Vẽ đường cong đánh đổi (Trade-off Curve / Pareto Frontier) giữa:
- Trục X: False Refusal Rate (%) (Lỗi Loại I: Từ chối nhầm mẫu hợp lệ trong danh mục)
- Trục Y: OOC Leakage Rate (%) (Lỗi Loại II: Bỏ lọt mẫu ngoài danh mục = 100 - OOC Correct)
Bao gồm:
1. Các cấu hình LLM (Prompt v1.1 vs v1.2, Sửa luật, Verifier, Phối hợp Cascaded)
2. Đường cơ sở đối chứng phi LLM (Non-LLM Baseline: BM25 Top-1 Score Thresholding trên 259k SKU)
"""

import matplotlib.pyplot as plt
import numpy as np

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, ax = plt.subplots(figsize=(11, 7.5), dpi=300)

# 1. Dữ liệu các cấu hình LLM Qwen2.5:3B
# Điểm: (Tên, X_mean, [X_low, X_high], Y_mean, [Y_low, Y_high], màu, marker, offset_text)
llm_data = [
    ("v1.1 Thô (Raw)\n[Siêu cảnh giác cực đoan]", 57.8, [47.5, 67.5], 0.0, [0.0, 8.8], "#d9534f", "s", (-20, 14)),
    ("v1.1 + Sửa luật\n(Rule Repair)", 7.8, [3.8, 15.2], 0.0, [0.0, 8.8], "#f0ad4e", "^", (10, 12)),
    ("v1.2 Thô (Raw)", 10.1, [5.4, 18.1], 15.0, [7.1, 29.1], "#5bc0de", "o", (10, 10)),
    ("v1.2 + Sửa luật (Rule L1-L5)", 1.1, [0.2, 6.1], 7.5, [2.6, 19.9], "#0275d8", "D", (12, -8)),
    ("v1.2 + Verifier Thực tế (Obs)", 10.1, [5.4, 18.1], 7.5, [2.6, 19.9], "#6f42c1", "v", (-20, -22)),
    ("v1.2 + Phối hợp Thực tế\n(Cascaded Obs) [*]", 1.1, [0.2, 6.1], 7.5, [2.6, 19.9], "#2e7d32", "*", (12, 12)),
]

for label, x, x_ci, y, y_ci, color, marker, offset in llm_data:
    xerr = [[x - x_ci[0]], [x_ci[1] - x]]
    yerr = [[y - y_ci[0]], [y_ci[1] - y]]
    
    ax.errorbar(x, y, xerr=xerr, yerr=yerr, fmt=marker, color=color, ecolor=color,
                elinewidth=1.5, capsize=4, capthick=1.5, markersize=10, alpha=0.9, zorder=5)
    
    ax.annotate(label, (x, y), textcoords="offset points", xytext=offset,
                fontsize=9, fontweight='bold' if '[*]' in label else 'normal',
                color=color, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, alpha=0.8, lw=0.8),
                zorder=6)

# 2. Đường cơ sở phi LLM: BM25 Thresholding trên 259k SKU
# (FPR: False Refusal %, FNR: OOC Leakage % = 100 - TPR %)
bm25_points = [
    (0.0, 27.5, "BM25 (tau=22.88)\n[FR=0%, Leak=27.5%]"),
    (3.75, 20.0, "BM25 (Youden tau=29.33)\n[FR=3.8%, Leak=20%]"),
    (15.0, 12.5, "BM25 (tau=37.0)"),
    (31.25, 7.5, "BM25 (tau=43.45)\n[FR=31.2%, Leak=7.5%]"),
    (55.0, 2.5, "BM25 (tau=52.0)"),
]
bm25_x = [p[0] for p in bm25_points]
bm25_y = [p[1] for p in bm25_points]

ax.plot(bm25_x, bm25_y, 'o--', color='#888888', lw=2, markersize=7, alpha=0.85,
        label="Đường cơ sở phi LLM: Ngưỡng điểm BM25 Top-1 (AUROC = 93.9%)", zorder=3)

# Chú thích 2 điểm mốc BM25
ax.annotate(bm25_points[0][2], (bm25_points[0][0], bm25_points[0][1]), textcoords="offset points", xytext=(10, -5),
            fontsize=8, color="#555555", style='italic')
ax.annotate(bm25_points[3][2], (bm25_points[3][0], bm25_points[3][1]), textcoords="offset points", xytext=(10, 8),
            fontsize=8, color="#c9302c", fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.2", fc="#fff5f5", ec="#d9534f", alpha=0.8, lw=0.8))

# Vẽ vùng Pareto mong đợi
ax.axvspan(-2, 5, ymin=0, ymax=0.3, color='#e8f5e9', alpha=0.45, label="Vùng tối ưu Pareto mục tiêu (Type I & II < 10%)", zorder=1)

# Vẽ đường nối Pareto giữa v1.2+Cascaded và v1.1+Rule
ax.plot([1.1, 7.8], [7.5, 0.0], '-', color='#2e7d32', lw=2.5, alpha=0.9,
        label="Đường biên Pareto LLM thực tế (Cascaded Obs -> Rule v1.1)", zorder=4)

ax.set_xlabel("Tỷ lệ Từ chối nhầm - Type I Error (%)\n[Yêu cầu hợp lệ trong danh mục bị từ chối/bỏ trống]", fontsize=11, fontweight='bold')
ax.set_ylabel("Tỷ lệ Bỏ lọt OOC - Type II Error (%)\n[Yêu cầu ngoài phạm vi không bị chặn = 100 - OOC Correct]", fontsize=11, fontweight='bold')
ax.set_title("Đường cong Đánh đổi (Trade-off Curve) giữa Từ chối nhầm và Bỏ lọt OOC\nSo sánh Mô hình Đề xuất (LLM Cascaded) vs Baseline Phi LLM (BM25 Thresholding trên 259k SKU)",
             fontsize=12, fontweight='bold', pad=15)

ax.set_xlim(-2, 65)
ax.set_ylim(-2, 35)

ax.legend(loc="upper right", frameon=True, fontsize=9.5)
plt.tight_layout()

out_png = "amazon_benchmark/tradeoff_curve_qwen.png"
plt.savefig(out_png, dpi=300)
print(f"✅ Đã lưu đồ thị đường cong đánh đổi nâng cấp tại: {out_png}")
