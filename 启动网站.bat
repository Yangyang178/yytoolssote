@echo off
chcp 65001 >nul 2>&1
title 网站服务器 - 一键启动
color 0A

echo.
echo ╔══════════════════════════════════════╗
echo ║   yytoolssite-aipro 启动工具 v3.0   ║
echo ╚══════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM 检查虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境！
    pause
    exit /b 1
)

REM 创建必要目录
if not exist "data" mkdir data >nul 2>&1
if not exist "uploads" mkdir uploads >nul 2>&1

echo [✓] 环境准备完成
echo.
echo [✓] 正在启动网站服务...
echo.
echo ┌────────────────────────────────────┐
echo │  访问地址: http://localhost:9876   │
echo │  按 Ctrl+C 可停止服务              │
echo └────────────────────────────────────┘
echo.

REM 使用 start 命令在新窗口中启动，避免阻塞
start "Flask Server" /MIN cmd /c "cd /d "%~dp0" && "%~dp0venv\Scripts\python.exe" app.py && pause"

echo [✓] 服务已在后台启动！
echo.
echo 提示：如果浏览器无法访问，请等待 5-10 秒后刷新页面
echo.
pause
