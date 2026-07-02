# Know Your Code testbed - start backend + frontend.
# Pure ASCII only. Ctrl+C in this window stops both processes cleanly.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$NodeModules = Join-Path $FrontendDir "node_modules"
$DepsMarker  = Join-Path $BackendDir ".deps-installed"

# ----- Pick a python interpreter -----
$ActiveConda = $env:CONDA_DEFAULT_ENV
$ActiveVenv  = $env:VIRTUAL_ENV

if ($ActiveConda -or $ActiveVenv) {
    $envLabel = if ($ActiveConda) { "conda env '$ActiveConda'" } else { "venv '$ActiveVenv'" }
    Write-Host "[setup] Using active $envLabel"
    $Python = "python"
} else {
    $VenvDir    = Join-Path $BackendDir ".venv"
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Host "[setup] Creating Python venv at $VenvDir"
        python -m venv $VenvDir
    }
    $Python = $VenvPython
}

# ----- Install Python deps if the marker is missing OR the chosen interpreter
#       can't actually import them. A stale .deps-installed marker sitting next to
#       an env that lacks the packages (e.g. an empty .venv with no pip) would
#       otherwise skip install and crash at launch with "No module named fastapi".
$DepsOk = $false
if (Test-Path $DepsMarker) {
    try { & $Python -c "import fastapi, uvicorn, pydantic, dotenv" 2>$null } catch {}
    $DepsOk = ($LASTEXITCODE -eq 0)
}
if (-not $DepsOk) {
    Write-Host "[setup] Installing backend Python packages..."
    try { & $Python -m ensurepip --upgrade 2>$null } catch {}   # repair a pip-less venv
    & $Python -m pip install --upgrade pip --quiet
    & $Python -m pip install -r (Join-Path $BackendDir "requirements.txt")
    New-Item -ItemType File -Path $DepsMarker -Force | Out-Null
} else {
    Write-Host "[setup] Backend deps already installed and importable."
}

# ----- .env on first run -----
if (-not (Test-Path (Join-Path $BackendDir ".env"))) {
    Copy-Item (Join-Path $BackendDir ".env.example") (Join-Path $BackendDir ".env") -ErrorAction SilentlyContinue
}

# ----- Frontend deps -----
if (-not (Test-Path $NodeModules)) {
    Write-Host "[setup] Installing npm packages (first run only)..."
    Push-Location $FrontendDir
    npm install
    Pop-Location
} else {
    Write-Host "[setup] Frontend deps already installed (delete 'node_modules' to force reinstall)."
}

Write-Host ""
Write-Host "Starting Know Your Code testbed..."
Write-Host "  Backend:  http://localhost:8100  (docs at /docs)"
Write-Host "  Frontend: http://localhost:5273"
Write-Host ""
Write-Host "Press Ctrl+C in THIS window to stop both."
Write-Host ""

# ----- Spawn backend + frontend as tracked child windows -----
if ($ActiveConda) {
    $backendCmd = "Write-Host 'KnowIT backend (:8100)' -ForegroundColor Magenta; conda activate $ActiveConda; Set-Location '$BackendDir'; python main.py"
} else {
    $backendCmd = "Write-Host 'KnowIT backend (:8100)' -ForegroundColor Magenta; Set-Location '$BackendDir'; & '$Python' main.py"
}
$frontendCmd = "Write-Host 'KnowIT frontend (:5273)' -ForegroundColor Cyan; Set-Location '$FrontendDir'; npm run dev"

$backend  = Start-Process powershell -ArgumentList "-NoExit","-Command",$backendCmd  -PassThru
Start-Sleep -Seconds 2
$frontend = Start-Process powershell -ArgumentList "-NoExit","-Command",$frontendCmd -PassThru

Write-Host "Backend window PID: $($backend.Id) | Frontend window PID: $($frontend.Id)"

# ----- Wait for Ctrl+C, then kill the process trees -----
function Stop-ProcessTree($processId) {
    try {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$processId" -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-ProcessTree $_.ProcessId
        }
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    } catch {}
}

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($backend.HasExited -and $frontend.HasExited) { break }
    }
} finally {
    Write-Host ""
    Write-Host "Stopping KnowIT testbed..."
    Stop-ProcessTree $backend.Id
    Stop-ProcessTree $frontend.Id
    Write-Host "Stopped. (You can also run .\stop.ps1 anytime.)"
}
