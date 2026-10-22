@echo off
setlocal
cd /d "%~dp0"
py -3 poker_tournament_director.py
if errorlevel 1 (
  echo.
  echo MyPoker Tournament did not start. Confirm Python 3 is installed and try again.
  pause
)
endlocal
