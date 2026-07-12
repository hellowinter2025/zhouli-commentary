#Requires -Version 5.1
param(
    [string]$OutputZip = "",
    [string]$SnapshotDir = ""
)

$ErrorActionPreference = "Stop"
$SkillDir = Split-Path -Parent $PSScriptRoot
if (-not $OutputZip) {
    $OutputZip = Join-Path $SkillDir "dist\bge-small-zh-v1.5.zip"
}

$py = Join-Path $SkillDir "scripts\package_model_release.py"
$args = @($py)
if ($OutputZip) { $args += @("--output", $OutputZip) }
if ($SnapshotDir) { $args += @("--snapshot", $SnapshotDir) }

$python = $null
try {
    $python = (& py -3 -c "import sys; print(sys.executable)").Trim()
} catch {}
if (-not $python) {
    $python = (& python -c "import sys; print(sys.executable)").Trim()
}
& $python @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
