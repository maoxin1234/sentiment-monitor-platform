# 快速启动脚本（Windows PowerShell）
# 模拟模式，无需 Kafka/Redis/Ollama
Set-Location "$PSScriptRoot\backend"

# 检查虚拟环境
if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境..." -ForegroundColor Cyan
    python -m venv .venv
}

# 激活并安装依赖
& ".venv\Scripts\Activate.ps1"
pip install -q -r requirements.txt

# 环境变量（模拟模式）
$env:USE_MOCK   = "true"
$env:MOCK_RATE  = "5"
$env:LLM_ROUTING = "local_first"

# 如有云端 API Key 填入此处（留空则仅用规则分析）
# $env:CLOUD_API_KEY  = "sk-..."
# $env:CLOUD_LLM_URL  = "https://api.deepseek.com/v1"
# $env:CLOUD_MODEL    = "deepseek-chat"

Write-Host ""
Write-Host "══════════════════════════════════════" -ForegroundColor Blue
Write-Host "  舆情监控平台启动中..." -ForegroundColor Cyan
Write-Host "  访问地址: http://localhost:8001" -ForegroundColor Green
Write-Host "  API 文档: http://localhost:8001/docs" -ForegroundColor Yellow
Write-Host "══════════════════════════════════════" -ForegroundColor Blue
Write-Host ""

python main.py
