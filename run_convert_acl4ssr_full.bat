@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
set "LOG=%~dp0convert.log"
echo [%date% %time%] Start conversion > "%LOG%"

set "PYTHON="

if exist "%USERPROFILE%\AppData\Local\miniconda3\python.exe" (
  set "PYTHON=%USERPROFILE%\AppData\Local\miniconda3\python.exe"
)

if not defined PYTHON (
  where python >nul 2>nul
  if %errorlevel%==0 set "PYTHON=python"
)

if not defined PYTHON (
  where py >nul 2>nul
  if %errorlevel%==0 set "PYTHON=py -3"
)

if defined PYTHON (
  echo Using: %PYTHON% >> "%LOG%"
  set "ACL4SSR_SKIP_PY_PAUSE=1"
  %PYTHON% -X utf8 "%~dp0convert_txt_to_acl4ssr_full.py" >> "%LOG%" 2>&1
  set "EXITCODE=!errorlevel!"
  type "%LOG%"
  if not "!EXITCODE!"=="0" (
    echo.
    echo Conversion failed. See log: "%LOG%"
  ) else (
    echo.
    echo Conversion completed.
  )
  pause
  exit /b !EXITCODE!
)

echo Python was not found. Install Python 3 or add it to PATH.
echo Python was not found. >> "%LOG%"
pause
exit /b 1
