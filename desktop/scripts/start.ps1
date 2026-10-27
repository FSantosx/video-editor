# Inicia o servidor local e abre a interface no navegador. Feche esta janela (ou Ctrl+C) para parar.
. "$PSScriptRoot\common.ps1"

if (-not (Test-Path $VenvPython)) {
    Write-Fail "Ainda não instalado. Rode o Instalar.bat primeiro."
    Read-Host "Enter para sair"
    exit 1
}

$cfg = Set-AppEnvironment
$port = if ($cfg["PORT"]) { $cfg["PORT"] } else { "8765" }
$url = "http://localhost:$port"

# Já está rodando? Só abre o navegador.
try {
    Invoke-WebRequest -Uri "$url/system" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
    Write-Host "O Video Editor já está aberto em $url"
    Start-Process $url
    exit 0
} catch { }

Write-Host "Video Editor" -ForegroundColor Magenta
Write-Host "  Interface:  $url"
Write-Host "  Cortes em:  $env:DATA_DIR"
Write-Host "  Whisper:    $($cfg['WHISPER_MODEL']) ($($cfg['WHISPER_DEVICE']))   Formatos: $($cfg['FORMATS'])"
Write-Host "  Para parar: feche esta janela ou aperte Ctrl+C"
Write-Host ""

if ($cfg["OPEN_BROWSER"] -ne "0") {
    # Abre o navegador quando o servidor responder (processo separado, sem janela)
    $opener = "for (`$i = 0; `$i -lt 120; `$i++) { try { Invoke-WebRequest -Uri '$url/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process '$url'; break } catch { Start-Sleep -Milliseconds 500 } }"
    Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", $opener
}

& $VenvPython -m uvicorn app.main:app --app-dir $BackendDir --host 127.0.0.1 --port $port --workers 1
