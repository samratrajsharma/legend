# Kill anything listening on the KnowIT testbed ports.
$ErrorActionPreference = "SilentlyContinue"

function Stop-Port($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "Port $port : nothing to stop." ; return }
    foreach ($c in $conns) {
        try {
            Stop-Process -Id $c.OwningProcess -Force
            Write-Host "Port $port : killed PID $($c.OwningProcess)."
        } catch {
            Write-Host "Port $port : could not kill PID $($c.OwningProcess)."
        }
    }
}

Stop-Port 8100   # backend
Stop-Port 5273   # frontend
Write-Host "Stopped Know Your Code testbed."
