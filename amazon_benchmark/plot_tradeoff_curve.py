"""
plot_tradeoff_curve.py
Vẽ đường cong đánh đổi (Trade-off Curve / Pareto Frontier) giữa:
- Trục X: False Refusal Rate (%) (Lỗi Loại I: Từ chối nhầm mẫu hợp lệ trong danh mục)
- Trục Y: OOC Leakage Rate (%) (Lỗi Loại II: Bỏ lọt mẫu ngoài danh mục = 100 - OOC Correct)
Kèm khoảng tin cậy Wilson 95% trên cả hai trục.
"""

import matplotlib.pyplot as plt
import numpy as np

# Cài đặt font và style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, ax = plt.subplots(figsize=(10, 7), dpi=300)

# Dữ liệu từ thực nghiệm Dev 130 (Qwen2.5:3B)
# Điểm: (Tên, X_mean, [X_low, X_high], Y_mean, [Y_low, Y_high], màu, marker, offset_text)
data = [
    ("v1.1 Thô (Raw)\n[Siêu cảnh giác]", 57.8, [47.5, 67.5], 0.0, [0.0, 8.8], "#d9534f", "s", (-15, 12)),
    ("v1.1 + Sửa luật\n(Rule Repair)", 7.8, [3.8, 15.2], 0.0, [0.0, 8.8], "#f0ad4e", "^", (12, 10)),
    ("v1.2 Thô (Raw)", 10.1, [5.4, 18.1], 15.0, [7.1, 29.1], "#5bc0de", "o", (10, 10)),
    ("v1.2 + Sửa luật\n(Rule Repair)", 1.1, [0.2, 6.1], 7.5, [2.6, 19.9], "#0275d8", "D", (12, -8)),
    ("v1.2 + Verifier Thực tế\n(Observable)", 10.1, [5.4, 18.1], 7.5, [2.6, 19.9], "#6f42c1", "v", (-20, -22)),
    ("v1.2 + Verifier Lý thuyết\n(Oracle)", 10.1, [5.4, 18.1], 0.0, [0.0, 8.8], "#6c757d", "x", (12, -18)),
    ("v1.2 + Phối hợp Thực tế\n(Cascaded Obs) [*]", 3.4, [1.2, 9.4], 7.5, [2.6, 19.9], "#5cb85c", "*", (15, 8)),
    ("v1.2 + Phối hợp Lý thuyết\n(Cascaded Oracle)", 1.1, [0.2, 6.1], 0.0, [0.0, 8.8], "#292b2c", "P", (-25, 12)),
]

for label, x, x_ci, y, y_ci, color, marker, offset in data:
    xerr = [[x - x_ci[0]], [x_ci[1] - x]]
    yerr = [[y - y_ci[0]], [y_ci[1] - y]]
    
    # Vẽ điểm và thanh sai số Wilson 95%
    ax.errorbar(x, y, xerr=xerr, yerr=yerr, fmt=marker, color=color, ecolor=color,
                elinewidth=1.5, capsize=4, capthick=1.5, markersize=10, alpha=0.9, zorder=4)
    
    # Chú thích nhãn
    ax.annotate(label, (x, y), textcoords="offset points", xytext=offset,
                fontsize=9, fontweight='bold' if '[*]' in label else 'normal',
                color=color, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, alpha=0.7, lw=0.8),
                zorder=5)

# Vẽ vùng Pareto lý tưởng (Góc dưới bên trái: cả hai lỗi đều bằng 0%)
ax.axvspan(-2, 5, ymin=0, ymax=0.3, color='#e8f5e9', alpha=0.4, label="Vùng tối ưu Pareto mong đợi", zorder=1)

# Vẽ đường cong đánh đổi thực tế (Pareto Frontier) nối các điểm trội thực tế
# Điểm thực tế: v1.2+Rule (1.1, 7.5) -> v1.1+Rule (7.8, 0.0)
pareto_x = [1.1, 7.8]
pareto_y = [7.5, 0.0]
ax.plot(pareto_x, pareto_y, '--', color='#2e7d32', lw=2, alpha=0.8, label="Đường biên Pareto thực tế (Không Oracle)", zorder=2)

ax.set_xlabel("Tỷ lệ Từ chối nhầm - Type I Error (%)\n[Yêu cầu hợp lệ trong danh mục bị từ chối/bỏ trống]", fontsize=11, fontweight='bold')
ax.set_ylabel("Tỷ lệ Bỏ lọt OOC - Type II Error (%)\n[Yêu cầu ngoài phạm vi không bị chặn = 100 - OOC Correct]", fontsize=11, fontweight='bold')
ax.set_title("Đường cong Đánh đổi (Trade-off Curve) giữa Từ chối nhầm và Bỏ lọt OOC\n(Qwen2.5:3B trên tập Dev 130, Thanh sai số Wilson CI95)", fontsize=13, fontweight='bold', pad=15)

ax.set_xlim(-2, 70)
ax.set_ylim(-2, 35)

ax.legend(loc="upper right", frameon=True, fontsize=10)
plt.tight_layout()

out_png = "amazon_benchmark/tradeoff_curve_qwen.png"
plt.savefig(out_png, dpi=300)
print(f"✅ Đã lưu đồ thị đường cong đánh đổi tại: {out_png}")
