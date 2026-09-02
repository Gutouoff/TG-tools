@echo off
chcp 65001 >nul
title 部署 TG工具箱GUI
echo ============================================
echo   TG工具箱GUI 部署脚本
echo   把 dist\TG工具箱GUI 复制到 D:\Desktop\TG小号\
echo ============================================
echo.

set SRC=%~dp0dist\TG工具箱GUI
set DST=D:\Desktop\TG小号\TG工具箱GUI

if not exist "%SRC%\TG工具箱GUI.exe" (
    echo [!] 没找到 %SRC%\TG工具箱GUI.exe
    echo     请先用 PyInstaller 打包: python -m PyInstaller TG工具箱GUI.spec --noconfirm
    pause
    exit /b 1
)

echo [1/4] 关闭正在运行的工具箱...
taskkill /F /IM TG工具箱GUI.exe >nul 2>&1
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
echo 部署完成! 桌面快捷方式指向的位置已更新。
echo 双击桌面「TG工具箱GUI」即可使用。
pause
