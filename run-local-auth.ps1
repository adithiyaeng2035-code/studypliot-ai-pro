$ErrorActionPreference = "Stop"

$env:AUTH_ENABLED = "true"
$env:AUTH_ALLOW_REGISTRATION = "true"
$env:AUTH_COOKIE_SECURE = "false"
Set-Location $PSScriptRoot

Write-Host "StudyPilot account setup is enabled with the local SQLite database."
Write-Host "Open http://127.0.0.1:8000/login.html to register or sign in."

try {
    python -m app.main
}
finally {
    Remove-Item Env:AUTH_ALLOW_REGISTRATION -ErrorAction SilentlyContinue
    Remove-Item Env:AUTH_COOKIE_SECURE -ErrorAction SilentlyContinue
    Remove-Item Env:AUTH_ENABLED -ErrorAction SilentlyContinue
}
