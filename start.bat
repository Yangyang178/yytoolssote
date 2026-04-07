@echo off
chcp 65001 >nul 2>&1
title yytoolssite-aipro 网站服务器
color 0A

echo ========================================
echo   yytoolssite-aipro 网站服务器
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查虚拟环境...
if not exist "venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先创建虚拟环境
    pause
    exit /b 1
)

echo [2/3] 启动网站服务...
echo.
echo 访问地址: http://localhost:9876
echo 按 Ctrl+C 停止服务
echo.
echo ----------------------------------------

"%~dp0venv\Scripts\python.exe" app.py

pause
