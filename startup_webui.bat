@echo off
title MCP Agent WebUI Launcher
echo ===============================
echo  MCP Agent Web UI - Launch Script
echo ===============================

REM ---- 1. Check if venv exists ----
IF NOT EXIST venv (
    echo [INFO] Python virtual environment "venv" not found.
    echo [INFO] Creating new virtual environment...
    python -m venv venv

    IF ERRORLEVEL 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM ---- 2. Activate virtual environment ----
echo.
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

IF "%VIRTUAL_ENV%"=="" (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [OK] Virtual environment activated: %VIRTUAL_ENV%

REM ---- 3. Check requirements.txt ----
IF NOT EXIST requirements.txt (
    echo.
    echo [ERROR] requirements.txt not found in current folder.
    echo        Please make sure this script is placed in the project root:
    echo        MCP_Agent\
    echo          app\
    echo          agents\
    echo          skills\
    echo          web\
    echo          requirements.txt
    echo          startup_webui.bat
    pause
    exit /b 1
)

REM ---- 4. Install / update dependencies ----
echo.
echo [INFO] Installing / updating required Python packages...
pip install -r requirements.txt

IF ERRORLEVEL 1 (
    echo [ERROR] Failed to install dependencies from requirements.txt
    pause
    exit /b 1
)
echo [OK] All dependencies are ready.

REM ---- 4.5 Install llama-cpp-python (if needed) via Python script ----
echo.
echo [INFO] Checking llama-cpp-python via Python script...
python scripts\install_llama_cpp.py

IF ERRORLEVEL 1 (
    echo [WARN] llama-cpp-python installation script returned non-zero code.
    echo       You can still run the Web UI, but local llama.cpp provider may not work.
)


REM ---- 5. Start Web API + Web UI ----
echo.
echo =======================================
echo  Starting Uvicorn server for Web UI...
echo  Open your browser at: http://127.0.0.1:8000/
echo  (Press Ctrl+C in this window to stop the server)
echo =======================================
echo.

uvicorn web.api.main:app --reload

REM ---- 6. Cleanup / exit ----
echo.
echo [INFO] WebUI server has stopped.
pause
