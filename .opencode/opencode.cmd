@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
cd /d "%PROJECT_DIR%"

where opencode.exe >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  opencode.exe . --agent aistudio %*
  exit /b %ERRORLEVEL%
)

where opencode.cmd >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  for /f "delims=" %%I in ('where opencode.cmd') do (
    if /I not "%%~fI"=="%~f0" (
      "%%~fI" . --agent aistudio %*
      exit /b %ERRORLEVEL%
    )
  )
)

echo real opencode command was not found in PATH
exit /b 1
