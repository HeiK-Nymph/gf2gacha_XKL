@echo off
setlocal
cd /d "%~dp0"

rem ---------------------------------------------------------------
rem  Launcher for gf2gacha_XKL (run from source)
rem
rem  Why this script exists: it picks a Python interpreter that really
rem  has the dependencies (pywebview / mitmproxy), so you do not get
rem  the confusing "ModuleNotFoundError: No module named 'webview'".
rem     1) D:\Python\python.exe   <- this machine's dev environment
rem     2) python found on PATH
rem
rem  IMPORTANT for future edits:
rem   * keep this file ASCII-only and with CRLF line endings.
rem     Chinese text or LF-only endings make cmd mis-parse the file and
rem     report "xxx is not recognized as an internal or external command".
rem ---------------------------------------------------------------

set "PYEXE="
if exist "D:\Python\python.exe" call :probe "D:\Python\python.exe"
if not defined PYEXE call :probe "python"
if defined PYEXE goto :run

echo [ERROR] No Python with webview + mitmproxy was found.
echo         The "python" on your PATH is probably conda base, which does
echo         not have this project dependencies installed.
echo.
echo         Option 1 - use the dev interpreter directly:
echo                    D:\Python\python.exe -B main.py
echo         Option 2 - install dependencies for the current interpreter:
echo                    pip install -r requirements.txt
echo.
pause
exit /b 1

:run
echo Using interpreter: %PYEXE%
echo Starting app...
"%PYEXE%" -B main.py
echo App exited.
pause
exit /b 0

:probe
%~1 -c "import webview, mitmproxy" >nul 2>&1
if not errorlevel 1 set "PYEXE=%~1"
exit /b
