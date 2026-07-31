@echo off
setlocal
title Pickaboo Price Tracker

:menu
cls
echo.
echo  ╔══════════════════════════════════════╗
echo  ║     PICKABOO PRICE TRACKER           ║
echo  ║     CamelBoo - Price History Tool    ║
echo  ╚══════════════════════════════════════╝
echo.
echo   [1]  Scrape prices now (all categories)
echo   [2]  Scrape specific categories
echo   [3]  Launch dashboard only
echo   [4]  Scrape + Launch dashboard
echo   [5]  Exit
echo.
set /p choice= Enter choice (1-5): 

if "%choice%"=="1" goto scrape_all
if "%choice%"=="2" goto scrape_cats
if "%choice%"=="3" goto dashboard
if "%choice%"=="4" goto both
if "%choice%"=="5" exit /b
goto menu

:scrape_all
echo.
echo  Starting full scrape...
python scraper.py --delay 0.6
echo.
echo  Scrape complete!
pause
goto menu

:scrape_cats
echo.
set /p cats= Enter category IDs (comma-separated, e.g. 171,64,29): 
echo.
python scraper.py --categories %cats% --delay 0.6
echo.
echo  Scrape complete!
pause
goto menu

:dashboard
start "" http://localhost:5000
python dashboard.py
goto menu

:both
echo.
echo  Starting scraper in background...
start /B python scraper.py --delay 0.6
echo  Waiting 5 seconds before launching dashboard...
timeout /t 5 /nobreak >nul
start "" http://localhost:5000
python dashboard.py
goto menu
