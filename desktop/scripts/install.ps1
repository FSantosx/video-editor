# Instala tudo que o Video Editor precisa no Windows. Pode rodar de novo para atualizar/consertar.
#   - Python 3.12 (via winget, se não houver)
#   - ambiente virtual com o backend + bibliotecas CUDA (cuBLAS/cuDNN) para a GPU NVIDIA
#   - ffmpeg com NVENC e libass (legendas)
#   - modelo do Whisper + autoteste (GPU, NVENC, legendas)
param(
    [switch]$SkipModel,     # não baixa o modelo nem roda o autoteste (usado no CI)
    [switch]$NoShortcut
)

. "$PSScriptRoot\common.ps1"

Write-Host "Video Editor - instalação" -ForegroundColor Magenta
Write-Host "Pasta: $DesktopDir"

# ---------------------------------------------------------------- Python
Write-Step "Python"
function Find-Python {
    foreach ($ver in @("3.12", "3.11", "3.13")) {
        try {
            $exe = & py "-$ver" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
        } catch { }
        $guess = Join-Path $env:LOCALAPPDATA ("Programs\Python\Python" + $ver.Replace(".", "") + "\python.exe")
        if (Test-Path $guess) { return $guess }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "    Instalando Python 3.12 com o winget..."
        winget install --id Python.Python.3.12 -e --scope user --silent `
            --accept-package-agreements --accept-source-agreements | Out-Host
        $python = Find-Python
    }
}
if (-not $python) {
    Write-Fail "Python 3.12 não encontrado. Instale em https://www.python.org/downloads/ (marque 'Add to PATH') e rode o Instalar.bat de novo."
    exit 1
}
Write-Ok $python

# ---------------------------------------------------------------- GPU
Write-Step "Placa de vídeo"
$gpu = Test-NvidiaGpu
if ($gpu) { Write-Ok "NVIDIA: $gpu" } else { Write-Warn "Nenhuma placa NVIDIA encontrada (ou driver ausente): vai usar a CPU." }

# ---------------------------------------------------------------- venv + pacotes
Write-Step "Ambiente Python e dependências (pode levar alguns minutos)"
if (-not (Test-Path $VenvPython)) {
    & $python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Fail "Falha ao criar o ambiente virtual"; exit 1 }
}
& $VenvPython -m pip install --upgrade pip --quiet --disable-pip-version-check
& $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt") --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Write-Fail "Falha ao instalar as dependências do backend"; exit 1 }
Write-Ok "backend"
if ($gpu) {
    # DLLs do CUDA 12 / cuDNN 9 usadas pelo CTranslate2 (faster-whisper) - não precisa instalar o CUDA Toolkit
    & $VenvPython -m pip install "nvidia-cublas-cu12" "nvidia-cudnn-cu12>=9,<10" --quiet --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { Write-Warn "Falha ao instalar cuBLAS/cuDNN: a transcrição vai rodar na CPU" }
    else { Write-Ok "bibliotecas CUDA (cuBLAS, cuDNN)" }
}

# ---------------------------------------------------------------- ffmpeg
Write-Step "ffmpeg (com NVENC e legendas)"
$ffmpegExe = Join-Path $FfmpegBin "ffmpeg.exe"
if (-not (Test-Path $ffmpegExe)) {
    New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null
    $zip = Join-Path $ToolsDir "ffmpeg.zip"
    $sources = @(
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    )
    $ok = $false
    foreach ($url in $sources) {
        try {
            Write-Host "    Baixando $url"
            Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -ErrorAction Stop
            $tmp = Join-Path $ToolsDir "ffmpeg-tmp"
            if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
            Expand-Archive -Path $zip -DestinationPath $tmp -Force -ErrorAction Stop
            $bin = Get-ChildItem -Path $tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1
            if (-not $bin) { throw "ffmpeg.exe não encontrado no zip" }
            $target = Join-Path $ToolsDir "ffmpeg"
            if (Test-Path $target) { Remove-Item -Recurse -Force $target }
            New-Item -ItemType Directory -Force -Path $target | Out-Null
            Move-Item -Path $bin.Directory.FullName -Destination $FfmpegBin -ErrorAction Stop
            Remove-Item -Recurse -Force $tmp
            $ok = $true
            break
        } catch {
            Write-Warn "Falhou: $($_.Exception.Message)"
        } finally {
            if (Test-Path $zip) { Remove-Item -Force $zip }
        }
    }
    if (-not $ok) { Write-Fail "Não consegui baixar o ffmpeg. Verifique a internet e rode de novo."; exit 1 }
}
$filters = & $ffmpegExe -hide_banner -filters 2>$null | Out-String
if ($filters -notmatch "\ssubtitles\s") { Write-Fail "Este ffmpeg não tem libass (legendas)."; exit 1 }
$encoders = & $ffmpegExe -hide_banner -encoders 2>$null | Out-String
if ($encoders -match "h264_nvenc") { Write-Ok "ffmpeg com NVENC e legendas" } else { Write-Warn "ffmpeg sem NVENC: render na CPU" }

# ---------------------------------------------------------------- config
Write-Step "Configuração"
if (-not (Test-Path $ConfigFile)) {
    Copy-Item $ConfigExample $ConfigFile
    if (-not $gpu) {
        Set-ConfigValue "WHISPER_MODEL" "small"   # na CPU o large é lento demais
        Set-ConfigValue "WORKERS" "1"
    }
    Write-Ok "criado $ConfigFile"
} else {
    Write-Ok "mantido $ConfigFile"
}

# ---------------------------------------------------------------- modelo + autoteste
if (-not $SkipModel) {
    $cfg = Set-AppEnvironment
    Write-Step "Modelo do Whisper ($($cfg['WHISPER_MODEL'])) e autoteste"
    Write-Host "    Na primeira vez baixa o modelo (cerca de 1,6 GB para o large-v3-turbo)."
    & $VenvPython (Join-Path $PSScriptRoot "selftest.py")
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Ok "autoteste passou"
    } elseif ($code -eq 2) {
        Write-Fail "Autoteste falhou (veja acima). Corrija e rode o Instalar.bat de novo."
        exit 1
    } else {
        # Processo abortou (ex.: DLL do cuDNN incompatível) ao usar a GPU: segue na CPU
        Write-Warn "A transcrição na GPU falhou (código $code). Configurando WHISPER_DEVICE=cpu."
        Set-ConfigValue "WHISPER_DEVICE" "cpu"
        Set-ConfigValue "WHISPER_MODEL" "small"
        $env:WHISPER_DEVICE = "cpu"; $env:WHISPER_MODEL = "small"
        & $VenvPython (Join-Path $PSScriptRoot "selftest.py")
        if ($LASTEXITCODE -ne 0) { Write-Fail "Autoteste na CPU também falhou."; exit 1 }
        Write-Ok "autoteste passou na CPU"
    }
}

# ---------------------------------------------------------------- atalho
if (-not $NoShortcut) {
    try {
        $shell = New-Object -ComObject WScript.Shell
        $lnk = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Video Editor.lnk"))
        $lnk.TargetPath = Join-Path $DesktopDir "Iniciar.bat"
        $lnk.WorkingDirectory = $DesktopDir
        $lnk.Description = "Video Editor - cortes automáticos"
        $lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,18"
        $lnk.Save()
        Write-Ok "atalho 'Video Editor' criado na Área de Trabalho"
    } catch {
        Write-Warn "não consegui criar o atalho: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "Instalação concluída! Para usar, abra o Iniciar.bat (ou o atalho na Área de Trabalho)." -ForegroundColor Green
