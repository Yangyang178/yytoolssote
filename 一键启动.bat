@echo off
chcp 65001 >nul 2>&1
title yytoolssite-aipro - 网站服务器
color 0A

echo.
echo ╔══════════════════════════════════════════╗
echo ║     yytoolssite-aipro 网站服务器        ║
echo ║           一键启动脚本 v3.0              ║
echo ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python环境！
    echo 请先安装Python 3.10+并添加到系统PATH
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查 .env 文件
if not exist ".env" (
    echo [提示] 创建默认配置文件...
    copy ".env.example" ".env" >nul 2>&1
)

REM 创建必要目录
if not exist "data" mkdir data
if not exist "uploads" mkdir uploads

echo [✓] 环境检查完成
echo.
echo [✓] 正在启动网站服务...
echo.
echo ┌─────────────────────────────────────┐
echo │  访问地址: http://localhost:9876    │
echo │  按 Ctrl+C 可停止服务               │
echo └─────────────────────────────────────┘
echo.

REM 启动 Flask 应用（使用系统Python）
python app.py

echo.
echo [!] 服务已停止
pause