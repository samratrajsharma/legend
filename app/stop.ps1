# Kill anything listening on the KnowIT testbed ports - including the PARENT that
# spawned it.
#
# uvicorn's --reload runs a reloader parent plus a worker child. The port belongs to
# the child, so killing only the child lets the parent instantly respawn it: the port
# never frees, and a -Fresh wipe then races a backend that is still very much alive
# (and busy recreating the folders you just deleted).
$ErrorActionPreference = "SilentlyContinue"

function Stop-Tree($procId) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Tree $_.ProcessId }
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

function Stop-Port($port) {
    $conns = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    if ($conns.Count -eq 0) { Write-Host "Port $port : nothing to stop."; return }
    foreach ($c in $conns) {
        $procId = $c.OwningProcess
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
        if ($proc -and $proc.ParentProcessId) {
            $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)" -ErrorAction SilentlyContinue
            # if our listener's parent is also python, that is the uvicorn reloader
            if ($parent -and $parent.Name -match '^(python|pythonw|python3|py)\.exe$') {
                Write-Host "Port $port : killing uvicorn reloader PID $($parent.ProcessId) (+ worker $procId)."
                Stop-Tree $parent.ProcessId
                continue
            }
        }
        Write-Host "Port $port : killing PID $procId."
        Stop-Tree $procId
    }
}

Stop-Port 8100   # backend
Stop-Port 5273   # frontend

Start-Sleep -Milliseconds 600
foreach ($p in 8100, 5273) {
    if (@(Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue).Count -gt 0) {
        Write-Host "Port $p : STILL IN USE - something is holding it." -ForegroundColor Red
    } else {
        Write-Host "Port $p : free."
    }
}
Write-Host "Stopped Know Your Code testbed."
