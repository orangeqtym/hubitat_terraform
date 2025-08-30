@echo off
echo Running Device Discovery and Health Check...
echo =====================================

cd /d "%~dp0"
python device_discovery.py

echo.
echo =====================================
echo Discovery Complete!
echo.
echo If you see errors:
echo 1. Check that devices are powered on
echo 2. Verify .env file has correct API credentials
echo 3. Check network connectivity
echo.
pause