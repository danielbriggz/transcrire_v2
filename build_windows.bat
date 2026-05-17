@echo off
echo ============================================================
echo  Transcrire — Windows Build Script
echo ============================================================
echo.

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Clean previous build artifacts
echo Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Run PyInstaller
echo Building executable...
pyinstaller transcrire.spec --noconfirm

:: Verify output
if exist dist\Transcrire.exe (
    echo.
    echo ============================================================
    echo  Build successful: dist\Transcrire.exe
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo  Build FAILED — Transcrire.exe not found in dist\
    echo ============================================================
    exit /b 1
)