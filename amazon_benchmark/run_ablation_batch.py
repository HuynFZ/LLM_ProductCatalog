"""
run_ablation_batch.py — Chạy tự động chuỗi thực nghiệm Ablation (A0 -> A6) trên Windows/Linux.
Tương thích cả PowerShell lẫn Bash.
"""
import os
import sys
import subprocess
import argparse

PYTHON_EXE = sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "benchmark_runner_ablation_v3.py")


def run_batch(model: str, configs: list, judge_model: str = None, limit: int = None,
              timeout: int = 90, retry_errors: bool = False):
    print("=" * 80)
    print(f"BẮT ĐẦU CHUỖI THỰC NGHIỆM ABLATION: {model}")
    print(f"Configs: {configs}")
    print(f"Judge: {judge_model or 'None'}")
    if limit:
        print(f"Limit: {limit} mẫu")
    print("=" * 80)

    for cfg in configs:
        cmd = [PYTHON_EXE, RUNNER, "--model", model, "--config", cfg, "--timeout", str(timeout)]
        if judge_model:
            cmd += ["--judge_model", judge_model]
        if limit:
            cmd += ["--limit", str(limit)]
        if retry_errors:
            cmd += ["--retry_errors"]

        print(f"\n▶ ĐANG CHẠY: {model} | Config {cfg} ...")
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"⚠️ Cảnh báo: Config {cfg} trả về mã lỗi {res.returncode}")

    print("\n" + "=" * 80)
    print(f"HOÀN THÀNH CHUỖI ABLATION CHO MÔ HÌNH: {model}")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy tự động chuỗi ablation A0->A6")
    parser.add_argument("--model", required=True, help="Tên model: gpt-4o-mini, qwen2.5:3b, llama3.2:3b")
    parser.add_argument("--configs", nargs="+", default=["A0", "A1", "A2", "A3", "A4", "A5", "A6"])
    parser.add_argument("--judge_model", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retry_errors", action="store_true")

    args = parser.parse_args()
    run_batch(
        model=args.model,
        configs=args.configs,
        judge_model=args.judge_model,
        limit=args.limit,
        timeout=args.timeout,
        retry_errors=args.retry_errors
    )
