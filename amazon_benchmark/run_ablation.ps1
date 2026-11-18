# run_ablation.ps1 — Script tiện ích chạy thực nghiệm Ablation trên PowerShell

param(
    [string]$Target = "gpt-4o-mini", # gpt-4o-mini, qwen2.5:3b, llama3.2:3b, all, table
    [int]$Limit = 0
)

$PythonExe = "C:\Users\MSI\AppData\Local\Programs\Python\Python311\python.exe"
$Runner = "amazon_benchmark\benchmark_runner_ablation_v3.py"
$Configs = @("A0", "A1", "A2", "A3", "A4", "A5", "A6")

if ($Target -eq "gpt-4o-mini") {
    Write-Host "=== Chạy Ablation A0 -> A6 cho GPT-4o-mini (Judge: gemini-3.5-flash-lite) ===" -ForegroundColor Cyan
    foreach ($c in $Configs) {
        $cmd = "$PythonExe $Runner --model gpt-4o-mini --config $c --judge_model gemini-3.5-flash-lite"
        if ($Limit -gt 0) { $cmd += " --limit $Limit" }
        Write-Host "Executing: $cmd" -ForegroundColor Yellow
        Invoke-Expression $cmd
    }
}
elseif ($Target -eq "qwen2.5:3b") {
    Write-Host "=== Chạy Ablation A0 -> A6 cho Qwen2.5:3b (Judge: gpt-4o-mini) ===" -ForegroundColor Green
    foreach ($c in $Configs) {
        $cmd = "$PythonExe $Runner --model qwen2.5:3b --config $c --judge_model gpt-4o-mini --timeout 90"
        if ($Limit -gt 0) { $cmd += " --limit $Limit" }
        Write-Host "Executing: $cmd" -ForegroundColor Yellow
        Invoke-Expression $cmd
    }
}
elseif ($Target -eq "llama3.2:3b") {
    Write-Host "=== Chạy Ablation A0 -> A6 cho LLaMA-3.2:3b (Judge: gpt-4o-mini) ===" -ForegroundColor Magenta
    foreach ($c in $Configs) {
        $cmd = "$PythonExe $Runner --model llama3.2:3b --config $c --judge_model gpt-4o-mini --timeout 90"
        if ($Limit -gt 0) { $cmd += " --limit $Limit" }
        Write-Host "Executing: $cmd" -ForegroundColor Yellow
        Invoke-Expression $cmd
    }
}
elseif ($Target -eq "table") {
    Write-Host "=== Xuất bảng tổng hợp kết quả Ablation ===" -ForegroundColor Cyan
    Invoke-Expression "$PythonExe $Runner --table --models gpt-4o-mini qwen2.5:3b llama3.2:3b"
}
