param([switch]$Folder)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Test-CompatiblePython {
    param([string]$Executable, [string[]]$LauncherArguments = @())
    # Keep native Python errors separate from PowerShell's error handling.
    & $Executable @LauncherArguments -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) and sys.platform == 'win32' else 1)" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

$BuildPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $BuildPython) {
    if (-not (Test-CompatiblePython -Executable $BuildPython)) {
        throw "Le .venv existant requiert Python Windows 3.11, 3.12 ou 3.13. Verifiez avec .\.venv\Scripts\python.exe --version. Il a ete conserve sans modification."
    }
} else {
    $BootstrapPython = $null
    $BootstrapArguments = @()
    $PythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($PythonCommand -and (Test-CompatiblePython -Executable $PythonCommand.Source)) {
        $BootstrapPython = $PythonCommand.Source
    } else {
        $Launcher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($Launcher) {
            foreach ($Version in @("-3.12", "-3.13", "-3.11")) {
                if (Test-CompatiblePython -Executable $Launcher.Source -LauncherArguments @($Version)) {
                    $BootstrapPython = $Launcher.Source
                    $BootstrapArguments = @($Version)
                    break
                }
            }
        }
    }
    if (-not $BootstrapPython) {
        throw "Aucun Python Windows compatible trouve. Installez Python 3.12 (ou 3.11/3.13), puis relancez. Utilisez python --version ou py -0p pour verifier."
    }
    if (Test-Path (Join-Path $PSScriptRoot ".venv")) {
        throw "Le dossier .venv existe mais ne contient pas Scripts\python.exe. Il a ete conserve. Renommez-le avant de creer un nouvel environnement Windows."
    }
    & $BootstrapPython @BootstrapArguments -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Creation du .venv echouee" }
}

Write-Host "Python utilise : $BuildPython"
& $BuildPython --version
& $BuildPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Installation echouee" }
& $BuildPython -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependances incompatibles" }
$BundleMode = if ($Folder) { "--onedir" } else { "--onefile" }
# Each build gets a fresh working directory outside the synced checkout.
$BuildScratch = Join-Path ([System.IO.Path]::GetTempPath()) ("CompagnonBuild-" + [guid]::NewGuid().ToString("N"))
$WorkPath = Join-Path $BuildScratch "work"
$SpecPath = Join-Path $BuildScratch "spec"
$PreviousPyInstallerCache = $env:PYINSTALLER_CONFIG_DIR
$BuildSucceeded = $false
New-Item -ItemType Directory -Path $WorkPath, $SpecPath -Force | Out-Null
try {
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $BuildScratch "cache"
    Write-Host "Fichiers temporaires de compilation : $BuildScratch"
    & $BuildPython -m PyInstaller --noconfirm $BundleMode --workpath $WorkPath --specpath $SpecPath --distpath (Join-Path $PSScriptRoot "dist") --windowed --name Compagnon --icon (Join-Path $PSScriptRoot "assets\compagnon.ico") --collect-data faster_whisper --collect-binaries ctranslate2 --collect-data soundcard --collect-all pywinauto --collect-all comtypes --hidden-import pystray._win32 (Join-Path $PSScriptRoot "main.py")
    if ($LASTEXITCODE -ne 0) { throw "Compilation echouee. Diagnostic conserve dans $BuildScratch" }
    $BuildSucceeded = $true
} finally {
    if ($null -eq $PreviousPyInstallerCache) {
        Remove-Item Env:\PYINSTALLER_CONFIG_DIR -ErrorAction SilentlyContinue
    } else {
        $env:PYINSTALLER_CONFIG_DIR = $PreviousPyInstallerCache
    }
    if ($BuildSucceeded) {
        try {
            Remove-Item -LiteralPath $BuildScratch -Recurse -Force
        } catch {
            Write-Warning "Compilation terminee, mais nettoyage temporaire impossible : $BuildScratch"
        }
    }
}
if ($Folder) {
    Write-Host "Application : dist\Compagnon\Compagnon.exe (distribuer le dossier entier)."
} else {
    $Output = Get-Item .\dist\Compagnon.exe
    Write-Host ("Executable unique : {0} ({1:N1} Mo). Les modeles Whisper seront telecharges au premier usage." -f $Output.FullName, ($Output.Length / 1MB))
}
