$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
$virtualEnvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $virtualEnvPython)) {
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonLauncher) {
        & $pythonLauncher.Source -3 -m venv (Join-Path $PSScriptRoot ".venv")
    } else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "Python 3 is required. Install Python 3 and select 'Add Python to PATH', then run this script again."
        }
        & $pythonCommand.Source -m venv (Join-Path $PSScriptRoot ".venv")
    }
    if ($LASTEXITCODE -ne 0) { throw "Could not create the StudyPilot virtual environment." }
}

& $virtualEnvPython -c "import fastapi, uvicorn, mcp, psycopg2, pwdlib, multipart, pypdf, openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing StudyPilot requirements. This may take a few minutes on the first run."
    & $virtualEnvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Check your internet connection and try again." }
}

$previousAuthEnabled = [Environment]::GetEnvironmentVariable("AUTH_ENABLED", "Process")
$env:AUTH_ENABLED = "true"
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()
$env:PORT = "$port"

$secureApiKey = $null
try {
    $env:LLM_BASE_URL = "https://api.openai.com/v1"
    $env:LLM_MODEL = "gpt-4o-mini"
    $secureApiKey = Read-Host "Enter your OpenAI API key" -AsSecureString
    if ($secureApiKey.Length -eq 0) { throw "An OpenAI API key is required to enable AI features." }
    $env:LLM_API_KEY = (New-Object System.Net.NetworkCredential("", $secureApiKey)).Password

    $url = "http://127.0.0.1:$port/doubts.html"
    Start-Job -ScriptBlock { param($browserUrl) Start-Sleep -Seconds 3; Start-Process $browserUrl } -ArgumentList $url | Out-Null
    Write-Host "StudyPilot with OpenAI is starting at $url"
    & $virtualEnvPython -m app.main
} finally {
    if ($secureApiKey) { $secureApiKey.Dispose() }
    Remove-Item Env:LLM_API_KEY,Env:LLM_BASE_URL,Env:LLM_MODEL,Env:PORT -ErrorAction SilentlyContinue
    if ($null -eq $previousAuthEnabled) {
        Remove-Item Env:AUTH_ENABLED -ErrorAction SilentlyContinue
    } else {
        $env:AUTH_ENABLED = $previousAuthEnabled
    }
}
