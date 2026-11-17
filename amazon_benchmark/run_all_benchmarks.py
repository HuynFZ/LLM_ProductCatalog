import os
import sys
import argparse
import subprocess

# Cấu hình UTF-8 cho Windows Terminal
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_RUNNER = os.path.join(CURRENT_DIR, "benchmark_runner_4pillars.py")
VISUALIZER = os.path.join(CURRENT_DIR, "visualize_results.py")

DEFAULT_MODELS = [
    "gpt-4o-mini",
    "qwen2.5:3b",
    "gemma2:2b",
    "llama3.2:3b"
]

def main():
    parser = argparse.ArgumentParser(description="Chạy Benchmark 4 Trụ Cột Hàng Loạt cho Các Mô Hình")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="Danh sách mô hình cần benchmark")
    parser.add_argument("--limit", type=int, default=50, help="Số lượng mẫu chạy cho mỗi model (vd: 50, 100, 500)")
    args = parser.parse_args()

    print("=" * 80)
    print("🚀 BẮT ĐẦU CHẠY BENCHMARK HÀNG LOẠT (4-PILLAR CONVERSATIONAL E-COMMERCE)")
    print(f"📋 Danh sách mô hình: {', '.join(args.models)}")
    print(f"🎯 Số lượng mẫu mỗi mô hình: {args.limit}")
    print("=" * 80)

    for m in args.models:
        print(f"\n▶️ ĐANG THỰC HIỆN BENCHMARK CHO: [{m}]...")
        cmd = [sys.executable, BENCHMARK_RUNNER, "--model", m, "--limit", str(args.limit)]
        subprocess.run(cmd, check=False)

    print("\n" + "=" * 80)
    print("📊 TỔNG HỢP VÀ XUẤT BẢNG SO SÁNH...")
    print("=" * 80)
    subprocess.run([sys.executable, VISUALIZER], check=False)

if __name__ == "__main__":
    main()

