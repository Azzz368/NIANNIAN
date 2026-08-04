# start_backend.ps1 - start the FastAPI service
# Windows PowerShell usage:
#   .\start_backend.ps1
#   .\start_backend.ps1 -PublicTunnel  # TokenStar local image animation

param(
    [switch]$PublicTunnel
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $root

# Load project .env when present. Python also loads .env.local itself.
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#=\s][^=]*)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    Write-Host "[OK] Loaded .env" -ForegroundColor Green
}

Write-Host "[INFO] Starting NianNian FastAPI backend..." -ForegroundColor Cyan
Write-Host "       Frontend: http://localhost:8000/static/index.html" -ForegroundColor Cyan
Write-Host "       API docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "       Health:   http://localhost:8000/api/health" -ForegroundColor Cyan
Write-Host ""

Set-Location "$root\backend"
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$tunnelProcess = $null
$tunnelOut = $null
$tunnelErr = $null
try {
    if ($PublicTunnel) {
        $cloudflared = Get-Command "cloudflared" -ErrorAction SilentlyContinue
        if (-not $cloudflared) {
            throw "cloudflared was not found. Install it or start without -PublicTunnel."
        }
        $tunnelOut = [IO.Path]::GetTempFileName()
        $tunnelErr = [IO.Path]::GetTempFileName()
        $startTunnel = @{
            FilePath = $cloudflared.Source
            ArgumentList = @("tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate")
            RedirectStandardOutput = $tunnelOut
            RedirectStandardError = $tunnelErr
            WindowStyle = "Hidden"
            PassThru = $true
        }
        $tunnelProcess = Start-Process @startTunnel

        $deadline = (Get-Date).AddSeconds(45)
        $publicUrl = ""
        while ((Get-Date) -lt $deadline -and -not $publicUrl) {
            Start-Sleep -Milliseconds 500
            $combined = ""
            if (Test-Path -LiteralPath $tunnelOut) {
                $combined += Get-Content -Raw -LiteralPath $tunnelOut -ErrorAction SilentlyContinue
            }
            if (Test-Path -LiteralPath $tunnelErr) {
                $combined += Get-Content -Raw -LiteralPath $tunnelErr -ErrorAction SilentlyContinue
            }
            if ($combined -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
                $publicUrl = $matches[0]
            }
            if ($tunnelProcess.HasExited) {
                throw "cloudflared exited before a public URL was available. Check the network."
            }
        }
        if (-not $publicUrl) {
            throw "cloudflared did not provide a public URL within 45 seconds."
        }
        $env:PUBLIC_BASE_URL = $publicUrl
        Write-Host "[OK] TokenStar public frame URL: $publicUrl" -ForegroundColor Green
        Write-Host "     This temporary URL is valid only for the current process." -ForegroundColor DarkGray
    }

    & $python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
}
finally {
    if ($tunnelProcess -and -not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    }
    foreach ($tempLog in @($tunnelOut, $tunnelErr)) {
        if ($tempLog -and (Test-Path -LiteralPath $tempLog)) {
            Remove-Item -LiteralPath $tempLog -Force -ErrorAction SilentlyContinue
        }
    }
}
