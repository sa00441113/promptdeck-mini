@echo off
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py promptdeck_mini.py
  exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
  python promptdeck_mini.py
  exit /b %errorlevel%
)

set "BUNDLED_PY=C:\stable-diffusion\StabilityMatrix-win-x64\Data\Assets\Python\cpython-3.11.13-windows-x86_64-none\python.exe"
if exist "%BUNDLED_PY%" (
  "%BUNDLED_PY%" promptdeck_mini.py
  exit /b %errorlevel%
)

echo Python was not found. Install Python 3.10 or later, then run this file again.
pause
exit /b 1
