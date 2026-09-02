@echo off
chcp 65001 >nul
title 部署 TG工具箱
echo ============================================
echo   TG工具箱 部署脚本
echo ============================================
echo.
echo 选择要部署的版本:
echo   [1] Web 版   (TG工具箱Web, 推荐, Material 3 界面)
echo   [2] Tkinter 版 (TG工具箱GUI, 旧版)
echo.
set /p CHOICE=请输入 1 或 2 (回车=1): 

if "%CHOICE%"=="" set CHOICE=1
if "%CHOICE%"=="1" set NAME=TG工具箱Web
if "%CHOICE%"=="2" set NAME=TG工具箱GUI
if "%NAME%"=="" (
    echo [!] 无效选择
    pause
    exit /b 1
)

set SRC=%~dp0dist\%NAME%
set DST=D:\Desktop\TG小号\%NAME%

if not exist "%SRC%\%NAME%.exe" (
    echo [!] 没找到 %SRC%\%NAME%.exe
    echo     请先打包: python -m PyInstaller %NAME%.spec --noconfirm
    pause
    exit /b 1
)

echo.
echo [1/4] 关闭正在运行的工具箱...
taskkill /F /IM %NAME%.exe >nul 2>&1
timeout /t 1 /nobreak >nul

echo [2/4] 删除旧版本...
if exist "%DST%" rd /s /q "%DST%"

echo [3/4] 复制新版本...
xcopy /e /i /y "%SRC%" "%DST%" >nul

echo [4/4] 补充头像缓存...
if exist "D:\Desktop\TG小号\工具箱\avatars" (
    if not exist "%DST%\avatars" mkdir "%DST%\avatars"
    copy /y "D:\Desktop\TG小号\工具箱\avatars\*.png" "%DST%\avatars\" >nul
)

echo.
echo 部署完成! 双击 D:\Desktop\TG小号\%NAME%\%NAME%.exe 即可。
pause
