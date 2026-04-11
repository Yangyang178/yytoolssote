@echo off
chcp 65001 >nul
title 网站服务器 - 启动工具

echo ================================================
echo   🚀 网站服务器启动工具
echo ================================================
echo.

cd /d "%~dp0"

python start_server.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ 启动失败！请检查错误信息。
    pause
)

pause
