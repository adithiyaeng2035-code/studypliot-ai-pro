$ErrorActionPreference = "Stop"

$env:LLM_BASE_URL = "https://api.openai.com/v1"
$env:LLM_MODEL = "gpt-4o-mini"
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()
$env:PORT = "$port"
$secureApiKey = Read-Host "Enter your OpenAI API key" -AsSecureString
$env:LLM_API_KEY = (New-Object System.Net.NetworkCredential("", $secureApiKey)).Password
$secureApiKey.Dispose()

try {
    Set-Location $PSScriptRoot
    $virtualEnvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (Test-Path $virtualEnvPython) {
        $python = $virtualEnvPython
    } else {
        $python = (Get-Command python).Source
    }
    $url = "http://127.0.0.1:$port/doubts.html"
    Start-Job -ScriptBlock { param($browserUrl) Start-Sleep -Seconds 3; Start-Process $browserUrl } -ArgumentList $url | Out-Null
    Write-Host "StudyPilot with OpenAI is starting at $url"
    & $python -m app.main
}
finally {
    Remove-Item Env:LLM_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:LLM_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:LLM_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:PORT -ErrorAction SilentlyContinue
}
