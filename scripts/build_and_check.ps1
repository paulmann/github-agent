#Requires -Version 7.0
<#
.SYNOPSIS
    Build github-agent and verify the artefact end to end.

.DESCRIPTION
    Mirrors scripts/build_and_check.sh: builds the sdist and the wheel, runs twine check,
    asserts the artefact version matches PACK_VERSION in tools/ghalib/util.py, proves the
    wheel layout (ghagent.py and ghalib/ flat in site-packages, no tools package), proves
    there is no runtime dependency except the optional png extra, installs the wheel in a
    clean virtual environment, and runs the installed CLI against this checkout.

    Everything happens under the temporary directory; the repository tree is not modified.

.PARAMETER Python
    Python 3.11+ interpreter used to create the virtual environments. Default: python.

.EXAMPLE
    pwsh -NoProfile -File scripts/build_and_check.ps1
#>
[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Work = Join-Path ([System.IO.Path]::GetTempPath()) ("ghagent-check-" + [guid]::NewGuid().ToString("N"))
$BuildVenv = Join-Path $Work "build-venv"
$TestVenv = Join-Path $Work "test-venv"
$Dist = Join-Path $Work "dist"

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "== $Text =="
}

function Assert-ExitCode {
    param([string]$Label)
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

try {
    New-Item -ItemType Directory -Force -Path $Dist | Out-Null

    Write-Step "build environment"
    & $Python -m venv $BuildVenv
    Assert-ExitCode "creating the build virtual environment"
    $BuildPy = Join-Path $BuildVenv "Scripts\python.exe"
    & $BuildPy -m pip install --quiet --disable-pip-version-check --upgrade pip build twine
    Assert-ExitCode "installing build and twine"

    Write-Step "build sdist and wheel"
    & $BuildPy -m build --outdir $Dist $Root
    Assert-ExitCode "python -m build"

    Write-Step "twine check"
    $Artifacts = Get-ChildItem -Path $Dist -File
    & $BuildPy -m twine check @($Artifacts.FullName)
    Assert-ExitCode "twine check"

    Write-Step "version from the single source"
    $UtilText = Get-Content -Raw (Join-Path $Root "tools/ghalib/util.py")
    $VersionMatch = [regex]::Match($UtilText, '(?m)^PACK_VERSION = "([^"]+)"')
    if (-not $VersionMatch.Success) {
        throw "PACK_VERSION is missing from tools/ghalib/util.py"
    }
    $Version = $VersionMatch.Groups[1].Value
    Write-Host "PACK_VERSION: $Version"

    $Wheel = Join-Path $Dist "github_agent_cli-$Version-py3-none-any.whl"
    $Sdist = Join-Path $Dist "github_agent_cli-$Version.tar.gz"
    if (-not (Test-Path $Wheel)) { throw "wheel is missing: $Wheel" }
    if (-not (Test-Path $Sdist)) { throw "sdist is missing: $Sdist" }

    Write-Step "wheel layout"
    $WheelList = & $BuildPy -m zipfile -l $Wheel
    Assert-ExitCode "listing the wheel"
    $WheelList | ForEach-Object { Write-Host $_ }
    if (-not ($WheelList -match '^ghagent\.py\s')) { throw "ghagent.py is not top-level in the wheel" }
    if (-not ($WheelList -match '^ghalib/')) { throw "ghalib/ is not top-level in the wheel" }
    if ($WheelList -match '^tools/') { throw "the wheel installs a top-level tools package" }

    Write-Step "no third-party runtime dependency"
    $MetadataCheck = @'
import email
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as archive:
    name = next(item for item in archive.namelist() if item.endswith(".dist-info/METADATA"))
    metadata = email.message_from_bytes(archive.read(name))
requires = metadata.get_all("Requires-Dist") or []
print("Requires-Dist:", requires or "none")
unexpected = [item for item in requires if "extra ==" not in item]
if unexpected:
    raise SystemExit(f"runtime dependencies found: {unexpected}")
'@
    $MetadataCheck | & $BuildPy - $Wheel
    Assert-ExitCode "checking Requires-Dist"

    Write-Step "clean installation"
    & $Python -m venv $TestVenv
    Assert-ExitCode "creating the test virtual environment"
    $TestPy = Join-Path $TestVenv "Scripts\python.exe"
    $Ghagent = Join-Path $TestVenv "Scripts\ghagent.exe"
    & $TestPy -m pip install --quiet --disable-pip-version-check $Wheel
    Assert-ExitCode "installing the wheel"
    $Actual = ((& $Ghagent --version) -join " ").Trim()
    Assert-ExitCode "ghagent --version"
    Write-Host "ghagent --version: $Actual"
    if ($Actual -ne "github-agent $Version") {
        throw "expected 'github-agent $Version', got '$Actual'"
    }
    & $TestPy -m pip list
    Assert-ExitCode "pip list"

    Write-Step "smoke test on the repository checkout"
    Push-Location $Root
    try {
        & $Ghagent doc --root .
        Assert-ExitCode "ghagent doc --root ."
        & $Ghagent audit . --min-score 80
        Assert-ExitCode "ghagent audit . --min-score 80"
    }
    finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "PASS: github-agent $Version built, checked and installed with no runtime dependency"
}
finally {
    if (Test-Path $Work) {
        Remove-Item -Recurse -Force $Work -ErrorAction SilentlyContinue
    }
}
