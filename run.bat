@echo off
rem work-widget launcher for Windows (double-click to run)
rem   run.bat         run the widget (creates venv / installs deps if missing)
rem   run.bat setup   (re)create venv and install deps only
rem   run.bat test    run tests
rem NOTE: keep this file ASCII-only. cmd.exe reads .bat in the OEM codepage,
rem       so non-ASCII text (Korean) breaks batch parsing.
setlocal
cd /d "%~dp0"

set "VENV=%~dp0venv"
set "PY=%VENV%\Scripts\python.exe"
set "PYW=%VENV%\Scripts\pythonw.exe"

set "DO_INSTALL="
if not exist "%PY%" set "DO_INSTALL=1"
if /i "%~1"=="setup" set "DO_INSTALL=1"

if defined DO_INSTALL (
    if not exist "%PY%" (
        echo Creating virtual environment...
        python -m venv "%VENV%"
        if errorlevel 1 (
            echo ERROR: Python 3 not found. Install Python 3 first.
            pause
            exit /b 1
        )
    )
    echo Installing dependencies...
    "%PY%" -m pip install --upgrade pip
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: dependency install failed.
        pause
        exit /b 1
    )
)

if /i "%~1"=="setup" (
    echo Setup complete. Run run.bat to launch.
    exit /b 0
)
if /i "%~1"=="test" (
    "%PY%" -m pytest -q
    exit /b %errorlevel%
)

echo Launching work-widget...
start "" "%PYW%" "%~dp0main.py"
endlocal
