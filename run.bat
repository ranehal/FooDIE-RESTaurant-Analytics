@echo off
title FoodiEATS // Restaurant Intelligence
cd /d "%~dp0"

echo  ==========================================
echo   FoodiEATS // Restaurant Intelligence
echo  ==========================================
echo.
echo  [1] Run Scraper
echo  [2] Start Dashboard
echo  [3] Run Scraper + Dashboard
echo  [4] Scrape + Open Dashboard
echo.
set /p choice="Select (1-4): "

if "%choice%"=="1" goto scraper
if "%choice%"=="2" goto dashboard
if "%choice%"=="3" goto both
if "%choice%"=="4" goto scrapeopen
goto dashboard

:scraper
echo.
echo [SCRAPER] Starting menu scraper...
python scrape_menus.py
echo.
echo [SCRAPER] Done. Press any key to exit.
pause >nul
exit /b 0

:dashboard
echo.
echo [DASHBOARD] Starting on http://localhost:8080
echo [DASHBOARD] Press Ctrl+C to stop.
echo.
cd /d "%~dp0restaurant_dashboard"
python -m http.server 8080
pause
exit /b 0

:both
echo.
echo [SCRAPER] Running scraper first...
python scrape_menus.py
echo.
echo [DASHBOARD] Starting dashboard on http://localhost:8080
echo.
cd /d "%~dp0restaurant_dashboard"
python -m http.server 8080
pause
exit /b 0

:scrapeopen
echo.
echo [SCRAPER] Running scraper first...
python scrape_menus.py
echo.
echo [DASHBOARD] Starting dashboard on http://localhost:8080
echo [DASHBOARD] Opening browser...
start "" http://localhost:8080
cd /d "%~dp0restaurant_dashboard"
python -m http.server 8080
pause
exit /b 0
