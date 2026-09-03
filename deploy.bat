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
echo [1/3] 关闭正在运行的工具箱...
taskkill /F /IM %NAME%.exe >nul 2>&1
timeout /t 1 /nobreak >nul

echo [2/3] 覆盖程序文件(保留 avatars/profiles 等缓存)...
xcopy /e /i /y "%SRC%" "%DST%" >nul

echo [3/3] 确保头像与资料缓存存在(已存在则跳过)...
if not exist "%DST%\avatars" mkdir "%DST%\avatars"
if exist "D:\Desktop\TG小号\工具箱\avatars" (
    copy /y "D:\Desktop\TG小号\工具箱\avatars\*.png" "%DST%\avatars\" >nul
    copy /y "D:\Desktop\TG小号\工具箱\avatars\*.jpg" "%DST%\avatars\" >nul
)
for %%F in (profiles.json whitelist.json nicknames.json) do (
    if not exist "%DST%\%%F" if exist "D:\Desktop\TG小号\工具箱\%%F" copy /y "D:\Desktop\TG小号\工具箱\%%F" "%DST%\%%F" >nul
)

echo.
echo 部署完成! 双击 D:\Desktop\TG小号\%NAME%\%NAME%.exe 即可。
pause
