@echo off
setlocal

rem ============================================================
rem  build.bat
rem
rem  Run this ONCE, on a Windows machine that has Python installed,
rem  from inside the FixtureDisplay project folder.
rem
rem  It produces three standalone .exe files in .\dist that do NOT
rem  need Python installed to run. Copy the whole .\dist folder to
rem  any other computer and it just works.
rem ============================================================

cd /d "%~dp0"

echo ============================
echo   FixtureDisplay Build
echo ============================
echo.

echo Installing build dependencies...
pip install --quiet flask requests beautifulsoup4 PyInstaller
if errorlevel 1 (
    echo.
    echo pip install failed. Make sure Python and pip are installed
    echo and available on PATH, then try again.
    pause
    exit /b 1
)

echo.
echo Cleaning up any previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist FixtureDisplay.spec del /q FixtureDisplay.spec
if exist Settings.spec del /q Settings.spec
if exist FixtureScraper.spec del /q FixtureScraper.spec

echo.
echo Building FixtureDisplay.exe (the display server)...
py -m PyInstaller --onefile --noconsole --name FixtureDisplay ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    app.py
if errorlevel 1 goto :build_failed

echo.
echo Building Settings.exe (the configuration GUI)...
py -m PyInstaller --onefile --noconsole --name Settings settings.py
if errorlevel 1 goto :build_failed

echo.
echo Building FixtureScraper.exe (the fixture downloader)...
rem kept with a console window so you can see it downloading, same as
rem double-clicking fixture-scraper2.py did before
py -m PyInstaller --onefile --name FixtureScraper fixture-scraper2.py
if errorlevel 1 goto :build_failed

echo.
echo Copying config.json and launchers into dist\...
copy /y config.json dist\config.json >nul
copy /y "Start Display.bat" dist\"Start Display.bat" >nul
copy /y "Stop Display.bat" dist\"Stop Display.bat" >nul

echo.
echo ============================
echo   Build complete!
echo ============================
echo.
echo Everything needed is now in the "dist" folder:
echo   FixtureDisplay.exe, Settings.exe, FixtureScraper.exe,
echo   config.json, Start Display.bat, Stop Display.bat
echo.
echo Copy that whole "dist" folder to any Windows PC and run
echo "Start Display.bat" -- no Python required on that machine.
echo.
pause
exit /b 0

:build_failed
echo.
echo Build failed. Scroll up to see which step errored.
pause
exit /b 1
