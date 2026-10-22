$ErrorActionPreference = "Stop"

$ollamaUrl = "http://127.0.0.1:11434"
$modelName = "llama3.2:3b"
$installedModels = Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 5
if (-not ($installedModels.models | Where-Object { $_.name -eq $modelName })) {
    throw "Ollama model '$modelName' is not installed. Install it with: ollama pull $modelName"
}

$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()

$env:LLM_BASE_URL = "$ollamaUrl/v1"
$env:LLM_API_KEY = "ollama-local"
$env:LLM_MODEL = $modelName
$env:PORT = "$port"

Set-Location $PSScriptRoot
$virtualEnvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $virtualEnvPython) {
    $python = $virtualEnvPython
} else {
    $python = (Get-Command python).Source
}

$url = "http://127.0.0.1:$port/doubts.html"
Start-Job -ScriptBlock { param($target) Start-Sleep -Seconds 2; Start-Process $target } -ArgumentList $url | Out-Null
Write-Host "StudyPilot with local Ollama ($modelName) is starting at $url"
try {
    & $python -m app.main
} finally {
    Remove-Item Env:LLM_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:LLM_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:LLM_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:PORT -ErrorAction SilentlyContinue
}
