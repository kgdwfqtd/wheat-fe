# Wheat Fe Experiment System - Startup Script
# Encoding: UTF-8
# 新架构：FastAPI 后端 + 静态 HTML 前端（抛弃 Streamlit）

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$LogFile = Join-Path $PSScriptRoot "startup.log"
$ProjectDir = $PSScriptRoot
$BackendPort = 8001

function Write-Log {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    $Line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -Path $LogFile -Value $Line -Encoding UTF8
    Write-Host $Message -ForegroundColor $Color
}

function Clear-Port {
    param([int]$Port)
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        if ($conns) {
            Write-Log "  正在释放端口 $Port ..." "Yellow"
            foreach ($conn in $conns) {
                if ($null -ne $conn.OwningProcess) {
                    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                }
            }
            Start-Sleep -Seconds 1
        }
    }
    catch {
        Write-Log "  端口检查忽略异常: $($_.Exception.Message)" "Yellow"
    }
}

function Wait-Port {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 30
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $conn = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue
            if ($conn.TcpTestSucceeded) {
                return $true
            }
        }
        catch {
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-PythonExe {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return (Get-Command python).Source
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return (Get-Command py).Source
    }
    throw "未找到 Python，可执行文件。请先安装 Python 3.10+。"
}

function Ensure-Dependencies {
    param([string]$PythonExe)
    $code = "import uvicorn, fastapi, pandas, psycopg2, qrcode; print('ok')"
    try {
        $result = & $PythonExe -c $code 2>$null
        if ($LASTEXITCODE -ne 0 -or -not ($result -match 'ok')) {
            throw "missing"
        }
    }
    catch {
        Write-Log "  依赖缺失，开始安装..." "Yellow"
        & $PythonExe -m pip install uvicorn fastapi pandas psycopg2-binary qrcode[pil] pyyaml *> $null
    }
}

try {
    "========================================" | Out-File -FilePath $LogFile -Encoding UTF8
    "Startup: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -FilePath $LogFile -Encoding UTF8 -Append
    "========================================" | Out-File -FilePath $LogFile -Encoding UTF8 -Append

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  Wheat Fe Experiment System (New Architecture)" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""

    Write-Log "[1/4] 检查并释放端口..." "Cyan"
    Clear-Port -Port $BackendPort

    Write-Log "[2/4] 检查 Python 环境..." "Cyan"
    $PythonExe = Get-PythonExe
    $PythonVersion = & $PythonExe --version 2>&1
    Write-Log "  $PythonVersion" "Green"

    Write-Log "[3/4] 检查依赖..." "Cyan"
    Ensure-Dependencies -PythonExe $PythonExe
    Write-Log "  依赖检查完成" "Green"

    Write-Log "[4/4] 启动后端服务 (port $BackendPort)..." "Cyan"
    Push-Location $ProjectDir
    $backendArgs = @('-m', 'uvicorn', 'backend.app:app', '--host', '0.0.0.0', '--port', $BackendPort.ToString())
    $null = Start-Process -FilePath $PythonExe -ArgumentList $backendArgs -WorkingDirectory $ProjectDir -PassThru -WindowStyle Hidden
    Pop-Location

    if (Wait-Port -Port $BackendPort -TimeoutSeconds 20) {
        Write-Log "  后端服务已启动" "Green"
    }
    else {
        Write-Log "  后端服务可能仍在启动中，请稍后检查日志" "Yellow"
    }

    Start-Sleep -Seconds 2
    Start-Process "http://localhost:$BackendPort"

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  System started successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Frontend UI:  http://localhost:$BackendPort" -ForegroundColor White
    Write-Host "  Backend API:  http://localhost:$BackendPort/api/v1/" -ForegroundColor White
    Write-Host "  API Docs:     http://localhost:$BackendPort/docs" -ForegroundColor White
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  这是启动窗口；后台服务将继续运行。" -ForegroundColor Yellow
    Write-Host "  按 Enter 键可关闭此窗口，同时后台服务不受影响。" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Log file: startup.log" -ForegroundColor Gray
    Write-Host ""
    $null = Read-Host
}
catch {
    $err = $_.Exception.Message
    Write-Host ""
    Write-Host "[ERROR] 启动失败: $err" -ForegroundColor Red
    Write-Log "[ERROR] 启动失败: $err" "Red"
    $null = Read-Host
    exit 1
}