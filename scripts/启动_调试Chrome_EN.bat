@echo off
rem ============================================================
rem  GEO Sampling Chrome (debug mode) - English version
rem  Starts a dedicated Chrome with remote debugging on port 9222.
rem  Login to engines once; cookies are saved in .geo-chrome-profile
rem  Keep this Chrome window OPEN while running the sampling script.
rem ============================================================

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
    echo [ERROR] Chrome not found. Edit CHROME path in this script.
    pause
    exit /b 1
)

set "PROFILE=%~dp0.geo-chrome-profile"
if not exist "%PROFILE%" mkdir "%PROFILE%"

netstat -ano | findstr ":9222" >nul 2>&1
if %errorlevel%==0 (
    echo [INFO] Port 9222 already in use. A dedicated Chrome may be running already.
    echo        Close the old dedicated Chrome window first if you want to restart it.
    pause
    exit /b 0
)

echo Starting GEO dedicated Chrome...
echo   Debug port: http://127.0.0.1:9222
echo   Profile dir: %PROFILE%
echo.
echo Log in to these engines in the new Chrome window (once each):
echo   Doubao   https://www.doubao.com
echo   Baidu AI https://yiyan.baidu.com
echo   Kimi     https://kimi.moonshot.cn
echo   Tongyi   https://tongyi.aliyun.com
echo   Yuanbao  https://yuanbao.tencent.com
echo.
echo Keep this Chrome window OPEN, then run the GEO sampling script.
echo.
start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check "https://www.doubao.com"

timeout /t 5 >nul

powershell -NoProfile -Command "try { $r = Invoke-RestMethod 'http://127.0.0.1:9222/json/version' -TimeoutSec 5; Write-Host ('[OK] Debug endpoint ready. Chrome: ' + $r.Browser) } catch { Write-Host '[WARN] Debug endpoint not responding yet. Check http://127.0.0.1:9222 later.' }"

pause
