@echo off
rem Builds "dist\QR Studio.exe". Run on Windows with Python 3.10+ installed.
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv || goto :error
)
.venv\Scripts\python -m pip install --upgrade pip || goto :error
.venv\Scripts\pip install -r requirements-build.txt || goto :error
.venv\Scripts\python packaging\build.py || goto :error
echo.
echo Done: dist\QR Studio.exe
pause
exit /b 0
:error
echo Build failed.
pause
exit /b 1
