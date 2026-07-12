#Requires -Version 5.1
param(
    [switch]$SkipModel,
    [switch]$PreferReleaseBackup,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$SkillDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $SkillDir

function Resolve-Python {
    param([string]$Preferred)
    if ($Preferred) { return $Preferred }
    try {
        $ver = & py -3 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver) { return $ver.Trim() }
    } catch {}
    try {
        $ver = & python -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver) { return $ver.Trim() }
    } catch {}
    throw "Python not found. Install Python 3.10+ and ensure python/py is on PATH."
}

function Invoke-Python {
    param(
        [string]$PythonExe,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$PyArgs
    )
    & $PythonExe @PyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $PythonExe $($PyArgs -join ' ')"
    }
}

function Install-ModelFromRelease {
    param(
        [string]$SkillRoot,
        [string]$ModelDir
    )
    $zipPath = Join-Path $env:TEMP "bge-small-zh-v1.5.zip"
    $url = "https://github.com/hellowinter2025/zhouli-commentary/releases/latest/download/bge-small-zh-v1.5.zip"
    Write-Host "Downloading Release backup: $url"
    Invoke-WebRequest -Uri $url -OutFile $zipPath
    $modelsRoot = Join-Path $SkillRoot "models"
    New-Item -ItemType Directory -Force -Path $modelsRoot | Out-Null
    Expand-Archive -LiteralPath $zipPath -DestinationPath $modelsRoot -Force
    $configPath = Join-Path $ModelDir "config.json"
    if (-not (Test-Path -LiteralPath $configPath)) {
        $nested = Get-ChildItem -LiteralPath $modelsRoot -Directory | Where-Object {
            Test-Path -LiteralPath (Join-Path $_.FullName "config.json")
        } | Select-Object -First 1
        if ($nested -and $nested.FullName -ne $ModelDir) {
            if (Test-Path -LiteralPath $ModelDir) {
                Remove-Item -LiteralPath $ModelDir -Recurse -Force
            }
            Move-Item -LiteralPath $nested.FullName -Destination $ModelDir
        }
    }
    if (-not (Test-Path -LiteralPath $configPath)) {
        throw "Release backup extract failed: missing $configPath"
    }
}

Write-Host "== zhouli-commentary Windows setup =="
Write-Host "skill_dir=$SkillDir"

$PythonExe = Resolve-Python -Preferred $Python
Write-Host "python=$PythonExe"

Write-Host ""
Write-Host "[1/3] Install Python dependencies..."
Invoke-Python $PythonExe -m pip install -U pip
Invoke-Python $PythonExe -m pip install -r (Join-Path $SkillDir "requirements.txt")

$modelDir = Join-Path $SkillDir "models\bge-small-zh-v1.5"
$configPath = Join-Path $modelDir "config.json"

if (-not $SkipModel) {
    Write-Host ""
    Write-Host "[2/3] Prepare embedding model BAAI/bge-small-zh-v1.5 ..."
    if (Test-Path -LiteralPath $configPath) {
        Write-Host "Local model already exists: $modelDir"
    } elseif ($PreferReleaseBackup) {
        Install-ModelFromRelease -SkillRoot $SkillDir -ModelDir $modelDir
        Write-Host "Model installed to: $modelDir"
    } else {
        Write-Host "Primary path: warm Hugging Face cache (~92 MB first time)..."
        & $PythonExe (Join-Path $SkillDir "scripts\warmup_model.py")
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Hugging Face download failed; trying GitHub Release backup..."
            Install-ModelFromRelease -SkillRoot $SkillDir -ModelDir $modelDir
            Write-Host "Installed model from Release backup: $modelDir"
        } else {
            Write-Host "Hugging Face cache ready"
        }
    }
} else {
    Write-Host ""
    Write-Host "[2/3] Skip model download (-SkipModel)"
}

Write-Host ""
Write-Host "[3/3] Run environment check..."
& $PythonExe (Join-Path $SkillDir "scripts\check_setup.py")
if ($LASTEXITCODE -ne 0) {
    throw "check_setup.py failed"
}

Write-Host ""
Write-Host "Done. Try:"
Write-Host ('  "{0}" scripts\search_classics.py --query demo --top-k 3 --json' -f $PythonExe)
