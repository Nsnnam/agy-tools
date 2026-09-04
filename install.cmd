@echo off
setlocal
echo Installing agy-resume (agyr)...

set "SCRIPT_DIR=%~dp0"
set "BIN_DIR=%LOCALAPPDATA%\agy\bin"

if not exist "%BIN_DIR%" (
    mkdir "%BIN_DIR%"
)

set "TARGET_SCRIPT=%SCRIPT_DIR%agy_resume.py"

(
echo @echo off
echo python "%TARGET_SCRIPT%" %%*
) > "%BIN_DIR%\agyr.cmd"

(
echo @echo off
echo python "%TARGET_SCRIPT%" %%*
) > "%BIN_DIR%\agy-resume.cmd"

echo [OK] Shortcuts installed to %BIN_DIR%:
echo      - agyr.cmd
echo      - agy-resume.cmd
echo.
echo You can now use 'agyr' from any command prompt or PowerShell window!
pause
