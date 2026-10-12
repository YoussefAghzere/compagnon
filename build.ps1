$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 requis" }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Installation échouée" }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name Compagnon --collect-all faster_whisper --collect-all ctranslate2 --collect-all soundcard main.py
if ($LASTEXITCODE -ne 0) { throw "Compilation échouée" }
Write-Host "Application portable : dist\Compagnon\Compagnon.exe (distribuer le dossier entier)."
