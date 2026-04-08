@echo off
chcp 65001 >nul 2>&1
title yytoolssite-aipro - 网站服务器
color 0A

echo.
echo ╔══════════════════════════════════════════╗
echo ║     yytoolssite-aipro 网站服务器        ║
echo ║           一键启动脚本 v4.0              ║
echo ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python环境！
    echo 请先安装Python 3.10+并添加到系统PATH
    echo 下载地址: https://www.python.org/downloads/
    echo.
    echo 安装时请务必勾选 "Add Python to PATH" 选项
    pause
    exit /b 1
)

echo [✓] Python环境检测通过
python --version

REM 检查虚拟环境是否存在
if not exist "venv\Scripts\python.exe" (
    echo.
    echo [提示] 虚拟环境不存在，正在创建...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败！
        pause
        exit /b 1
    )
    echo [✓] 虚拟环境创建成功
)

REM 检查依赖是否安装
echo.
echo [检查] 正在检查依赖...
venv\Scripts\python.exe -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [提示] 依赖未安装，正在自动安装...
    echo 这可能需要几分钟，请耐心等待...
    echo.
    venv\Scripts\pip.exe install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [警告] 清华源安装失败，尝试默认源...
        venv\Scripts\pip.exe install -r requirements.txt
    )
    echo [✓] 依赖安装完成
) else (
    echo [✓] 依赖已安装
)

REM 检查 .env 文件
if not exist ".env" (
    echo.
    echo [提示] 创建默认配置文件...
    if exist ".env.example" (
        copy ".env.example" ".env" >nul 2>&1
    )
)

REM 创建必要目录
if not exist "data" mkdir data
if not exist "uploads" mkdir uploads

echo.
echo ═══════════════════════════════════════════
echo [✓] 环境准备完成，正在启动网站服务...
echo ═══════════════════════════════════════════
echo.
echo ┌─────────────────────────────────────┐
echo │  访问地址: http://localhost:9876    │
echo │  按 Ctrl+C 可停止服务               │
echo └─────────────────────────────────────┘
echo.

REM 启动 Flask 应用（使用虚拟环境Python）
venv\Scripts\python.exe app.py

echo.
echo [!] 服务已停止
pause
