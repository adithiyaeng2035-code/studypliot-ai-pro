$ErrorActionPreference = "Stop"

$env:LLM_BASE_URL = "https://api.openai.com/v1"
$env:LLM_MODEL = "gpt-4o-mini"
$secureApiKey = Read-Host "Enter your OpenAI API key" -AsSecureString
$env:LLM_API_KEY = (New-Object System.Net.NetworkCredential("", $secureApiKey)).Password
$secureApiKey.Dispose()

try {
    Set-Location $PSScriptRoot
    python -m app.main
}
finally {
    Remove-Item Env:LLM_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:LLM_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:LLM_MODEL -ErrorAction SilentlyContinue
}
