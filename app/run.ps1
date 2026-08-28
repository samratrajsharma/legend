# Legend testbed - start backend + frontend.
# Pure ASCII only. Ctrl+C in this window stops both processes cleanly.
#
#   .\run.ps1               start normally
#   .\run.ps1 -Fresh        wipe ALL indexed repos, caches and tracking history, then start
#   .\run.ps1 -Fresh -Yes   same, no confirmation prompt
#   .\run.ps1 -Reload       backend hot-reload (LEGEND_RELOAD=1) - see main.py for why it is off by default
#   .\run.ps1 -Website      marketing site ONLY (:5300) - no backend, no engine, no cache
#
# -Fresh does NOT touch .env (API keys), node_modules, or the python env.

param(
    [switch]$Fresh,
    [switch]$Yes,
    [switch]$Reload,
    [switch]$Website
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$NodeModules = Join-Path $FrontendDir "node_modules"
$DepsMarker  = Join-Path $BackendDir ".deps-installed"
$SiteDir     = Join-Path (Split-Path -Parent $Root) "legend-frontend"

# ----- -Website : the public landing page, on its own -----
# Deliberately standalone: no python, no uvicorn, no engine, no data dir, no proxy.
# It is a static marketing page, so it must be runnable (and buildable) by someone
# who has never installed the backend at all.
if ($Website) {
    if (-not (Test-Path -LiteralPath $SiteDir)) {
        Write-Host "Marketing site not found at $SiteDir" -ForegroundColor Red
        exit 1
    }
    if (-not (Test-Path (Join-Path $SiteDir "node_modules"))) {
        Write-Host "[site] Installing npm packages (first run only)..."
        Push-Location $SiteDir
        npm install
        Pop-Location
    }
    Write-Host ""
    Write-Host "Legend - marketing site" -ForegroundColor Green
    Write-Host "  http://localhost:5300"
    Write-Host "  Standalone: no backend, no engine, no cache."
    Write-Host "  Ctrl+C to stop."
    Write-Host ""
    Push-Location $SiteDir
    try { npm run dev } finally { Pop-Location }
    exit 0
}

# ----- The data dir the backend actually uses (app.py: LEGEND_DATA_DIR, default ./.cache)
function Get-DataDir {
    if ($env:LEGEND_DATA_DIR) { $v = $env:LEGEND_DATA_DIR }
    else {
        $v = $null
        $envFile = Join-Path $BackendDir ".env"
        if (Test-Path $envFile) {
            $m = Select-String -Path $envFile -Pattern '^\s*LEGEND_DATA_DIR\s*=\s*(.+)$' | Select-Object -First 1
            if ($m) { $v = $m.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'") }
        }
    }
    if (-not $v) { $v = Join-Path $BackendDir ".cache" }
    elseif (-not [System.IO.Path]::IsPathRooted($v)) { $v = Join-Path $BackendDir $v }
    return [System.IO.Path]::GetFullPath($v)
}

# Kill a process and everything under it. uvicorn's reloader is a parent + a worker
# child; killing only the child makes the parent respawn it instantly.
function Stop-Tree($procId) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Tree $_.ProcessId }
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

function Stop-Servers {
    foreach ($port in 8100, 5273) {
        foreach ($c in @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) {
            $procId = $c.OwningProcess
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
            if ($proc -and $proc.ParentProcessId) {
                $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)" -ErrorAction SilentlyContinue
                if ($parent -and $parent.Name -match '^(python|pythonw|python3|py)\.exe$') {
                    Stop-Tree $parent.ProcessId    # the uvicorn reloader
                    continue
                }
            }
            Stop-Tree $procId
        }
    }
}

function Test-PortsFree {
    foreach ($port in 8100, 5273) {
        if (@(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).Count -gt 0) {
            return $false
        }
    }
    return $true
}

# Empty a tree the fast way. Do NOT walk it from PowerShell: a git cache holds tens of
# thousands of loose objects and touching each one from PS takes minutes - it looks
# like a hang. robocopy /MIR from an empty folder is native, handles >260-char paths,
# and does not choke on the read-only files in .git/objects.
function Clear-Tree($path) {
    if (-not (Test-Path -LiteralPath $path)) { return $true }
    $empty = Join-Path $env:TEMP ("kyc_empty_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $empty -Force | Out-Null
    try {
        cmd /c "robocopy `"$empty`" `"$path`" /MIR /NFL /NDL /NJH /NJS /NP /R:1 /W:1 >nul 2>&1"
    } finally {
        Remove-Item -LiteralPath $empty -Force -Recurse -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $path)) { return $true }
    return (@(Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue).Count -eq 0)
}

# ----- -Fresh : start from a clean slate -----
if ($Fresh) {
    $DataDir = Get-DataDir
    Write-Host ""
    Write-Host "[fresh] Data directory: $DataDir" -ForegroundColor Yellow

    if (Test-Path -LiteralPath $DataDir) {
        $repoCount = @(Get-ChildItem -LiteralPath (Join-Path $DataDir "repos")   -Directory -ErrorAction SilentlyContinue).Count
        $trkCount  = @(Get-ChildItem -LiteralPath (Join-Path $DataDir "tracked") -Directory -ErrorAction SilentlyContinue).Count
        Write-Host "[fresh] This permanently deletes:" -ForegroundColor Yellow
        Write-Host "          - $repoCount cloned repo(s) + their indexes"
        Write-Host "          - $trkCount tracked folder(s) and ALL timeline history"
        Write-Host "          - vector store, chunk caches, snapshots, worktrees, repos.json"
        Write-Host "[fresh] Keeps: .env (API keys), node_modules, python env." -ForegroundColor DarkGray

        if (-not $Yes) {
            $answer = Read-Host "Type 'yes' to wipe and start fresh"
            if ($answer -ne "yes") { Write-Host "[fresh] Aborted. Nothing deleted."; exit 1 }
        }
    } else {
        Write-Host "[fresh] Already clean." -ForegroundColor Yellow
    }

    Write-Host "[fresh] Stopping backend/frontend (incl. the uvicorn reloader)..."
    Stop-Servers
    Start-Sleep -Seconds 2
    if (-not (Test-PortsFree)) {
        Start-Sleep -Seconds 2
        Stop-Servers
        Start-Sleep -Seconds 1
    }
    if (-not (Test-PortsFree)) {
        Write-Host "[fresh] A server is still running and would recreate the cache." -ForegroundColor Red
        Write-Host "[fresh] Close its window (or run .\stop.ps1), then retry." -ForegroundColor Red
        exit 1
    }
    Write-Host "[fresh] Ports free."

    if (Test-Path -LiteralPath $DataDir) {
        Write-Host "[fresh] Deleting $DataDir ..."
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $ok = Clear-Tree $DataDir
        $sw.Stop()
        if ($ok) {
            Write-Host ("[fresh] Wiped in {0:N1}s." -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
        } else {
            Write-Host "[fresh] Still present after $([math]::Round($sw.Elapsed.TotalSeconds,1))s:" -ForegroundColor Red
            Get-ChildItem -LiteralPath $DataDir -Force -ErrorAction SilentlyContinue |
                ForEach-Object { Write-Host "          $($_.FullName)" -ForegroundColor Red }
            exit 1
        }
    }

    foreach ($extra in @((Join-Path $Root "..\engine\.legend_cache"), (Join-Path $Root "..\.legend_cache"))) {
        if (Test-Path -LiteralPath $extra) {
            Write-Host "[fresh] Also removing $extra"
            Clear-Tree $extra | Out-Null
        }
    }
    Write-Host "[fresh] Clean." -ForegroundColor Green
    Write-Host ""
}

# ----- Refuse to start on top of a server that is already running -----
if (-not (Test-PortsFree)) {
    Write-Host "Port 8100 or 5273 is already in use - a testbed is already running." -ForegroundColor Yellow
    Write-Host "Stopping it first..." -ForegroundColor Yellow
    Stop-Servers
    Start-Sleep -Seconds 2
    if (-not (Test-PortsFree)) {
        Write-Host "Could not free the ports. Run .\stop.ps1 and try again." -ForegroundColor Red
        exit 1
    }
}

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

# ----- Install Python deps if the marker is missing OR the interpreter can't import them
$DepsOk = $false
if (Test-Path $DepsMarker) {
    try { & $Python -c "import fastapi, uvicorn, pydantic, dotenv, docx, reportlab" 2>$null } catch {}
    $DepsOk = ($LASTEXITCODE -eq 0)
}
if (-not $DepsOk) {
    Write-Host "[setup] Installing backend Python packages..."
    try { & $Python -m ensurepip --upgrade 2>$null } catch {}
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
Write-Host "Starting Legend testbed..."
Write-Host "  Backend:  http://localhost:8100  (docs at /docs)"
Write-Host "  Frontend: http://localhost:5273"
if ($Reload) { Write-Host "  Backend hot-reload: ON" -ForegroundColor Yellow }
Write-Host ""
Write-Host "Press Ctrl+C in THIS window to stop both."
Write-Host ""

# ----- Spawn backend + frontend as tracked child windows -----
$reloadPrefix = if ($Reload) { "`$env:LEGEND_RELOAD='1'; " } else { "`$env:LEGEND_RELOAD='0'; " }
if ($ActiveConda) {
    $backendCmd = "Write-Host 'Legend backend (:8100)' -ForegroundColor Magenta; conda activate $ActiveConda; Set-Location '$BackendDir'; $reloadPrefix python main.py"
} else {
    $backendCmd = "Write-Host 'Legend backend (:8100)' -ForegroundColor Magenta; Set-Location '$BackendDir'; $reloadPrefix & '$Python' main.py"
}
$frontendCmd = "Write-Host 'Legend frontend (:5273)' -ForegroundColor Cyan; Set-Location '$FrontendDir'; npm run dev"

$backend  = Start-Process powershell -ArgumentList "-NoExit","-Command",$backendCmd  -PassThru
Start-Sleep -Seconds 2
$frontend = Start-Process powershell -ArgumentList "-NoExit","-Command",$frontendCmd -PassThru

Write-Host "Backend window PID: $($backend.Id) | Frontend window PID: $($frontend.Id)"

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($backend.HasExited -and $frontend.HasExited) { break }
    }
} finally {
    Write-Host ""
    Write-Host "Stopping Legend testbed..."
    Stop-Tree $backend.Id
    Stop-Tree $frontend.Id
    Write-Host "Stopped. (You can also run .\stop.ps1 anytime.)"
}
