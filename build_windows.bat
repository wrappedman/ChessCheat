@echo off
setlocal
title ChessCheat - Lightweight Python Build

:: ==================================================================
:: ChessCheat lightweight Windows build
::
:: Required: 64-bit Python 3.10+ with Tcl/Tk.
:: The script installs Python if absent, creates a small local venv,
:: installs python-chess and PyInstaller, builds a single-file app, and
:: downloads the Stockfish engine beside the executable.
::
:: No Flutter, Android SDK, Visual Studio, C++ compiler, or Chocolatey
:: is required. Expected build footprint: about 150-250 MB including
:: the app and Stockfish engine; temporary SDK/tool downloads are not kept.
:: ==================================================================

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "PYTHON_CMD="

:: ---- 1. Find Python 3.12, then any Python 3.10+ --------------------
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3.12"
    if not defined PYTHON_CMD (
        py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=py -3"
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

:: ---- 2. Install Python only if needed ------------------------------
if not defined PYTHON_CMD (
    echo [1/5] Installing Python 3.12...
    where winget >nul 2>&1
    if not errorlevel 1 (
        winget install --exact --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    ) else (
        where choco >nul 2>&1
        if errorlevel 1 (
            echo ERROR: Install Python 3.12 from https://www.python.org/downloads/windows/
            echo        Make sure the installer includes Tcl/Tk and the Python launcher.
            pause
            exit /b 1
        )
        choco install python312 -y --no-progress
    )
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if not defined PYTHON_CMD (
        where py >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=py -3.12"
    )
    if not defined PYTHON_CMD (
        echo ERROR: Python was installed but could not be found in this command window.
        echo        Close this window, open a new Command Prompt, then run build_windows.bat again.
        pause
        exit /b 1
    )
)

echo [1/5] Python found: %PYTHON_CMD%
%PYTHON_CMD% -c "import tkinter, sqlite3; print('Tkinter and SQLite are available.')"
if errorlevel 1 (
    echo ERROR: This Python installation does not include Tcl/Tk.
    echo        Reinstall standard 64-bit Python and enable the Tcl/Tk feature.
    pause
    exit /b 1
)
%PYTHON_CMD% -c "import struct; raise SystemExit(0 if struct.calcsize('P') == 8 else 1)"
if errorlevel 1 (
    echo ERROR: ChessCheat needs 64-bit Python because the Stockfish engine is x86-64.
    pause
    exit /b 1
)

:: ---- 3. Create lightweight isolated build environment --------------
if not exist ".build_venv\Scripts\python.exe" (
    echo [2/5] Creating local Python build environment...
    %PYTHON_CMD% -m venv .build_venv
    if errorlevel 1 (
        echo ERROR: Could not create the Python virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/5] Reusing the existing local build environment.
)

set "BUILD_PY=%PROJECT_DIR%.build_venv\Scripts\python.exe"
"%BUILD_PY%" -m pip install --disable-pip-version-check --quiet --upgrade pip
if errorlevel 1 (
    echo ERROR: pip could not be updated. Check internet access to pypi.org.
    pause
    exit /b 1
)
"%BUILD_PY%" -m pip install --disable-pip-version-check -r requirements.txt pyinstaller
if errorlevel 1 (
    echo ERROR: Python dependencies could not be installed.
    echo        Check internet access to pypi.org and try again.
    pause
    exit /b 1
)

:: ---- 4. Package the desktop application -----------------------------
echo [3/5] Building ChessCheat.exe with PyInstaller...
"%BUILD_PY%" -m PyInstaller --noconfirm --clean --onefile --windowed --name ChessCheat --hidden-import tkinter.ttk --hidden-import chess.pgn --add-data "assets\pieces;assets\pieces" --distpath dist --workpath .build\pyinstaller main.py
if errorlevel 1 (
    echo ERROR: PyInstaller could not build the Windows application.
    pause
    exit /b 1
)

:: ---- 5. Download Stockfish and place it beside the app ---------------
echo [4/5] Downloading the official Stockfish Windows engine...
if not exist "dist" mkdir "dist"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; $zip=Join-Path $env:TEMP 'ChessCheat-stockfish.zip'; $extract=Join-Path $env:TEMP 'ChessCheat-stockfish'; if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }; $release=Invoke-RestMethod -Uri 'https://api.github.com/repos/official-stockfish/Stockfish/releases/latest'; $asset=$release.assets | Where-Object { $_.name -match 'stockfish-windows-x86-64-universal\.zip$' } | Select-Object -First 1; if (-not $asset) { $asset=$release.assets | Where-Object { $_.name -match 'windows-x86-64.*\.zip$' } | Select-Object -First 1 }; if (-not $asset) { throw 'No Windows x86-64 Stockfish release asset was found.' }; Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip; Expand-Archive -Path $zip -DestinationPath $extract -Force; $engine=Get-ChildItem -Path $extract -Recurse -Filter '*.exe' | Where-Object { $_.Name -match 'stockfish' } | Sort-Object { if ($_.Name -match 'avx2') { 0 } else { 1 } } | Select-Object -First 1; if (-not $engine) { throw 'The Stockfish archive did not contain an executable.' }; Copy-Item $engine.FullName (Join-Path (Resolve-Path 'dist').Path 'stockfish.exe') -Force; Get-ChildItem -Path $engine.DirectoryName -Filter '*.nnue' -File | Copy-Item -Destination (Resolve-Path 'dist').Path -Force; Remove-Item $zip -Force; Remove-Item $extract -Recurse -Force; Write-Host ('Stockfish engine ready: '+$asset.name)"
if errorlevel 1 (
    echo ERROR: Stockfish download or extraction failed.
    echo        Check GitHub access, then run the build again.
    pause
    exit /b 1
)
if not exist "dist\ChessCheat.exe" (
    echo ERROR: The ChessCheat executable was not produced.
    pause
    exit /b 1
)
if not exist "dist\stockfish.exe" (
    echo ERROR: The Stockfish engine was not placed beside ChessCheat.exe.
    pause
    exit /b 1
)

:: Remove bulky temporary PyInstaller build files; keep the venv so a
:: future rebuild only downloads/installs what has changed.
if exist ".build\pyinstaller" rmdir /s /q ".build\pyinstaller"
if exist "ChessCheat.spec" del /q "ChessCheat.spec"

echo.
echo [5/5] BUILD COMPLETE
echo.
echo   App:    %PROJECT_DIR%dist\ChessCheat.exe
echo   Engine: %PROJECT_DIR%dist\stockfish.exe
echo   Data:   %LOCALAPPDATA%\ChessCheat\chesscheat_brain.db
echo.
echo Run dist\ChessCheat.exe. You can copy the complete dist folder to another PC.
echo Stockfish is GPL-licensed; see README.md for attribution.
echo.
pause
