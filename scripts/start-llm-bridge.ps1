# Advary LLM bridge — run this whenever your laptop is on so the live (Render)
# app can use this machine's Ollama as its brain. When this isn't running, the
# app silently falls back to the deterministic chat, so nothing breaks.
#
# What it does:
#   1) makes sure Ollama is serving and warms qwen3:8b (so the first reply is fast)
#   2) opens a public HTTPS tunnel to your local Ollama and prints the URL
#
# Then set on Render (Dashboard -> your service -> Environment), once:
#   OLLAMA_ENABLED          = true
#   OLLAMA_BASE_URL         = <the https URL this script prints>
#   OLLAMA_MODEL            = qwen3:8b
#   OLLAMA_TIMEOUT_SECONDS  = 45
# and redeploy. (With cloudflared the URL changes each run — see the ngrok note
# at the bottom for a permanent URL.)

$ErrorActionPreference = 'Stop'
$ollama = "C:\Users\ADVARY\AppData\Local\Programs\Ollama\ollama.exe"
$cf = Join-Path $PSScriptRoot "cloudflared.exe"

# 1. Ensure Ollama is up
if (-not (Get-Process -Name "ollama" -ErrorAction SilentlyContinue)) {
    Write-Host "Starting Ollama..."
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

# Warm the model + keep it resident for 2h so chats don't pay the cold-load cost
Write-Host "Warming qwen3:8b (first load can take ~15s)..."
try {
    $body = @{ model="qwen3:8b"; prompt="hi"; stream=$false; keep_alive="2h" } | ConvertTo-Json
    Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $body `
        -ContentType "application/json" -TimeoutSec 120 | Out-Null
    Write-Host "Model warm." -ForegroundColor Green
} catch { Write-Host "Warm-up skipped: $($_.Exception.Message)" -ForegroundColor Yellow }

# 2. Get cloudflared (single binary, no account) and open the tunnel
if (-not (Test-Path $cf)) {
    Write-Host "Downloading cloudflared (one-time)..."
    Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
        -OutFile $cf -UseBasicParsing
}

Write-Host ""
Write-Host "Opening public tunnel to your Ollama. Copy the https://<...>.trycloudflare.com" -ForegroundColor Cyan
Write-Host "URL below into Render's OLLAMA_BASE_URL. Keep this window open. Ctrl+C to stop." -ForegroundColor Cyan
Write-Host ""
& $cf tunnel --url http://localhost:11434

# ── Want a URL that never changes? (so you set Render once, forever) ──────────
# 1) Sign up free at ngrok.com, run:  ngrok config add-authtoken <token>
# 2) Claim your free static domain in the ngrok dashboard.
# 3) Replace the cloudflared line above with:
#       ngrok http 11434 --url=https://<your-domain>.ngrok-free.app
#    and set OLLAMA_BASE_URL on Render to that same domain (set once, done).
