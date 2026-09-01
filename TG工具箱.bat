@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
rem launcher: pass current dir to script (script auto-detects mode)
set PY=C:\Python314\python.exe
if not exist "%PY%" (
  echo [!] C:\Python314\python.exe not found
  pause
  exit /b 1
)
set SCRIPT=%~dp0工具箱\tg_tool.py
if not exist "%SCRIPT%" set SCRIPT=%~dp0..\工具箱\tg_tool.py
if not exist "%SCRIPT%" (
  echo [!] tg_tool.py not found: look in toolbox folder next to or above this bat
  pause
  exit /b 1
)
"%PY%" -X utf8 "%SCRIPT%"
pause
