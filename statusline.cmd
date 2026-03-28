@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    py -3 "%SCRIPT_DIR%statusline.py"
    exit /b 0
  )
)

where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    python "%SCRIPT_DIR%statusline.py"
    exit /b 0
  )
)

where python3 >nul 2>nul
if not errorlevel 1 (
  python3 -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    python3 "%SCRIPT_DIR%statusline.py"
    exit /b 0
  )
)

echo Claude
exit /b 0
