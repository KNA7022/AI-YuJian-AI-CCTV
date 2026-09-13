param([string]$BindAddress = "127.0.0.1", [int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$runtimePython = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
if (!(Test-Path -LiteralPath $runtimePython)) { throw "请先按 docs/live-deployment.md 创建 .venv 并安装依赖。" }
if (!(Test-Path -LiteralPath "web/frontend/dist/index.html")) { throw "请先在 web/frontend 运行 npm install 和 npm run build。" }
$env:YUJIAN_HOST = $BindAddress
$env:YUJIAN_PORT = "$Port"
& $runtimePython -m web.api.run
