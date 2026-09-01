@echo off
chcp 65001 >nul
title TG小号工具箱GUI
set PY=C:\Python314\python.exe
set TOOLBOX=%~dp0工具箱

if not exist "%TOOLBOX%\tg_ui.py" (
    for %%I in ("%~dp0..") do set PARENT=%%~fI
    if exist "!PARENT!\工具箱\tg_ui.py" set TOOLBOX=!PARENT!\工具箱
)
if not exist "%TOOLBOX%\tg_ui.py" (
    echo [!] tg_ui.py not found in toolbox folder
    pause
    exit /b 1
)

"%PY%" -X utf8 "%TOOLBOX%\tg_ui.py"
if errorlevel 1 pause
