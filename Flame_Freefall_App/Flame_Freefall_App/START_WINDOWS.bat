@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo Python 3.11 was not found by the Windows launcher. Use Start_Flame_App.ipynb in your existing Python 3.11 Jupyter kernel instead.
    pause
    exit /b 1
  )
)
if not exist ".venv\flame-installed-1.0" (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Package installation failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
  type nul > ".venv\flame-installed-1.0"
)
.venv\Scripts\python.exe launch.py
pause
