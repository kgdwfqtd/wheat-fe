$ErrorActionPreference = "Stop"
$port = 8001
Write-Host "Looking for processes on port $port..."
$conns = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"
if ($conns) {
    foreach ($line in $conns) {
        if ($line -match 'LISTENING\s+(\d+)') {
            $p = $matches[1]
            Write-Host "Found PID: $p (killing)"
            Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 3
}
Write-Host "[auth] 用户表初始化后启动..."
Set-Location "d:\kaifa\wheat-fe"
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8001
