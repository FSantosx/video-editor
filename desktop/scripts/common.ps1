# Funções compartilhadas pelos scripts do Video Editor (Windows PowerShell 5.1+).

# Continue: com "Stop", qualquer texto em stderr de pip/ffmpeg viraria exceção no PowerShell 5.1;
# os erros são checados explicitamente via $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest fica muito mais rápido
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$DesktopDir = Split-Path -Parent $PSScriptRoot
$RepoDir = Split-Path -Parent $DesktopDir
$BackendDir = Join-Path $RepoDir "backend"
$VenvDir = Join-Path $DesktopDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ToolsDir = Join-Path $DesktopDir "tools"
$FfmpegBin = Join-Path $ToolsDir "ffmpeg\bin"
$ModelsDir = Join-Path $DesktopDir "models"
$ConfigFile = Join-Path $DesktopDir "config.env"
$ConfigExample = Join-Path $DesktopDir "config.example.env"

function Write-Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Ok($text) { Write-Host "    OK  $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "    !!  $text" -ForegroundColor Yellow }
function Write-Fail($text) { Write-Host "    XX  $text" -ForegroundColor Red }

function Read-Config {
    # Lê KEY=VALUE do config.env (com os padrões do config.example.env por baixo)
    $values = [ordered]@{}
    foreach ($file in @($ConfigExample, $ConfigFile)) {
        if (-not (Test-Path $file)) { continue }
        foreach ($line in Get-Content -Encoding UTF8 $file) {
            $t = $line.Trim()
            if ($t -eq "" -or $t.StartsWith("#")) { continue }
            $i = $t.IndexOf("=")
            if ($i -lt 1) { continue }
            $values[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim()
        }
    }
    return $values
}

function Set-ConfigValue($key, $value) {
    # Altera (ou acrescenta) uma chave no config.env preservando o resto
    $lines = @()
    if (Test-Path $ConfigFile) { $lines = @(Get-Content -Encoding UTF8 $ConfigFile) }
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$key\s*=") { $lines[$i] = "$key=$value"; $found = $true }
    }
    if (-not $found) { $lines += "$key=$value" }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllLines($ConfigFile, $lines, $utf8)
}

function Set-AppEnvironment {
    # Variáveis lidas pelo backend (backend/app/config.py)
    $cfg = Read-Config
    foreach ($key in $cfg.Keys) {
        if ($cfg[$key] -ne "") { Set-Item -Path "Env:$key" -Value $cfg[$key] }
    }
    if (-not $cfg["DATA_DIR"]) { $env:DATA_DIR = Join-Path $DesktopDir "data" }
    $env:DESKTOP_MODE = "1"
    $env:WEB_DIR = Join-Path $DesktopDir "web"
    $env:API_KEY = ""                 # só escuta em 127.0.0.1: sem senha
    $env:HF_HOME = $ModelsDir         # modelos do Whisper ficam dentro desta pasta
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    if (Test-Path $FfmpegBin) { $env:PATH = "$FfmpegBin;$env:PATH" }
    return $cfg
}

function Test-NvidiaGpu {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $smi) { return $null }
    try {
        $info = & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>$null
        if ($LASTEXITCODE -eq 0 -and $info) { return ($info | Select-Object -First 1).Trim() }
    } catch { }
    return $null
}
