@echo off
cd /d "%~dp0"
echo Starting IRC Hosting 2 server...
echo Loading IRC and Treasury XML data (takes about 30 seconds)...
echo Browser will open automatically when ready.
echo.
echo Press Ctrl+C to stop the server.
echo.
py -3.14 server.py
pause
