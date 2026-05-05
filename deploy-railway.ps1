# ============================================================
#  Inteliaudit — Deploy a Railway (ejecutar en PowerShell)
#  Requiere: railway login completado previamente
# ============================================================

$ErrorActionPreference = "Stop"
$projectDir = "C:\Users\Gustavo\OneDrive\Dev\Inteliaudit"
Set-Location $projectDir

Write-Host "`n[1/5] Creando proyecto en Railway..." -ForegroundColor Cyan
railway init --name "Inteliaudit"

Write-Host "`n[2/5] Conectando repo GitHub..." -ForegroundColor Cyan
railway link

Write-Host "`n[3/5] Agregando base de datos PostgreSQL..." -ForegroundColor Cyan
railway add --plugin postgresql

Write-Host "`n[4/5] Configurando variables de entorno..." -ForegroundColor Cyan

# Generá una SECRET_KEY segura
$secretKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

railway variables --set "SECRET_KEY=$secretKey"
railway variables --set "DEBUG=false"
railway variables --set "STORAGE_PATH=/app/storage"

Write-Host "`n   SECRET_KEY generada: $secretKey" -ForegroundColor Yellow
Write-Host "   (guardala en un lugar seguro)" -ForegroundColor Yellow

Write-Host "`n   Si tenés ANTHROPIC_API_KEY, pegala ahora (Enter para saltear):" -ForegroundColor Yellow
$anthropicKey = Read-Host "   ANTHROPIC_API_KEY"
if ($anthropicKey -ne "") {
    railway variables --set "ANTHROPIC_API_KEY=$anthropicKey"
}

Write-Host "`n[5/5] Deployando..." -ForegroundColor Cyan
railway up --detach

Write-Host "`n✅ Deploy iniciado!" -ForegroundColor Green
Write-Host "   Seguí el progreso en: https://railway.app/dashboard" -ForegroundColor Cyan

# Mostrar la URL del servicio
Write-Host "`n   URL de tu app:" -ForegroundColor Cyan
railway status
