# Sobe a PoC SEM Docker (Windows / PowerShell), usando a fila por arquivo.
# Uso:  .\run_local.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -q -r requirements.txt

$env:TRANSPORT = "file"
$env:EVENT_QUEUE_DIR = "$PWD\event_queue"

Write-Host "Subindo cashflow-service (8001) e consolidation-service (8002)..."
$cf = Start-Process -FilePath $py -ArgumentList "-m","cashflow_service" `
    -Environment @{PORT="8001"} -PassThru -WindowStyle Hidden
$env:PORT = "8002"
$cons = Start-Process -FilePath $py -ArgumentList "-m","consolidation_service" `
    -Environment @{PORT="8002"} -PassThru -WindowStyle Hidden

Start-Sleep 3
Write-Host "Pronto."
Write-Host "  cashflow:      http://localhost:8001/docs"
Write-Host "  consolidation: http://localhost:8002/docs"
Write-Host ""
Write-Host "Exemplo:"
Write-Host '  $b = @{merchant_id="M1"; type="CREDIT"; amount=100; entry_date="2026-10-20"} | ConvertTo-Json'
Write-Host '  Invoke-RestMethod -Uri localhost:8001/entries -Method Post -Body $b -ContentType application/json'
Write-Host '  Invoke-RestMethod "localhost:8002/balance?merchant_id=M1&date=2026-10-20"'
Write-Host ""
Write-Host "Ctrl+C para encerrar."
try { Wait-Process -Id $cf.Id, $cons.Id } finally {
    Stop-Process -Id $cf.Id, $cons.Id -Force -ErrorAction SilentlyContinue
}
