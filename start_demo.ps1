# start_demo.ps1 — Start the Django demo server + a fresh Cloudflare quick tunnel.
# Run:  powershell -ExecutionPolicy Bypass -File start_demo.ps1
# The demo URL is printed at the end (also saved in logs\tunnel.err.log).
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# stop any previous server / tunnel
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like '*manage.py runserver*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Remove-Item "$root\logs\tunnel.err.log", "$root\logs\tunnel.log" -ErrorAction SilentlyContinue

# fresh Django server (background)
Start-Process -FilePath "$root\venv\Scripts\python.exe" `
  -ArgumentList 'manage.py','runserver','127.0.0.1:8000','--noreload' `
  -WorkingDirectory $root `
  -RedirectStandardOutput "$root\logs\runserver.log" `
  -RedirectStandardError "$root\logs\runserver.err.log" `
  -WindowStyle Hidden

# fresh Cloudflare quick tunnel (background)
Start-Process -FilePath 'C:\Program Files (x86)\cloudflared\cloudflared.exe' `
  -ArgumentList 'tunnel','--url','http://127.0.0.1:8000','--no-autoupdate' `
  -WorkingDirectory $root `
  -RedirectStandardOutput "$root\logs\tunnel.log" `
  -RedirectStandardError "$root\logs\tunnel.err.log" `
  -WindowStyle Hidden

# wait for the tunnel URL
$url = $null
foreach ($i in 1..45) {
  if (Test-Path "$root\logs\tunnel.err.log") {
    $raw = (Get-Content "$root\logs\tunnel.err.log" -Raw) -replace "`e\[[0-9;]*m", ''
    $m = [regex]::Match($raw, 'https://[a-z0-9-]+\.trycloudflare\.com')
    if ($m.Success) { $url = $m.Value; break }
  }
  Start-Sleep -Seconds 1
}
if ($url) { Write-Host "Demo URL: $url" -ForegroundColor Green }
else { Write-Host "URL not found yet - check logs\tunnel.err.log" -ForegroundColor Yellow }
Write-Host "Demo login: clientdemo / CandleDemo@2026"
