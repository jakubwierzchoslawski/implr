@echo off
REM implr installer (Windows CMD)
REM Usage:
REM   install.bat            install skills + agents to .\.claude\
REM   install.bat --global   install skills + agents to %USERPROFILE%\.claude\
REM Run from your project root, then run /implr-init inside Claude Code.

setlocal

set "SCRIPT_DIR=%~dp0"
set "SKILLS_SRC=%SCRIPT_DIR%skills"
set "AGENTS_SRC=%SCRIPT_DIR%.claude\agents"
set "GLOBAL=0"

:parseargs
if "%~1"=="" goto afterargs
if /I "%~1"=="--global" set "GLOBAL=1"
shift
goto parseargs
:afterargs

if "%GLOBAL%"=="1" (
  set "SKILLS_DEST=%USERPROFILE%\.claude\skills"
  set "AGENTS_DEST=%USERPROFILE%\.claude\agents"
) else (
  set "SKILLS_DEST=%CD%\.claude\skills"
  set "AGENTS_DEST=%CD%\.claude\agents"
)

echo implr installer
echo ===============
echo Skills -^> %SKILLS_DEST%
echo Agents -^> %AGENTS_DEST%

if not exist "%SKILLS_DEST%" mkdir "%SKILLS_DEST%"

for %%S in (implr-init doc-ingest arch-gen ba-requirements-gen ba-cr dev-planner dev-executor dev-code-review) do (
  if not exist "%SKILLS_SRC%\%%S" (
    echo ERROR: Missing skill source: %%S
    exit /b 1
  )
  if exist "%SKILLS_DEST%\%%S" rmdir /s /q "%SKILLS_DEST%\%%S"
  xcopy /e /i /q /y "%SKILLS_SRC%\%%S" "%SKILLS_DEST%\%%S" >nul
  echo   installed %%S
)

if not exist "%AGENTS_SRC%" (
  echo ERROR: Missing agents source: %AGENTS_SRC%
  exit /b 1
)
if not exist "%AGENTS_DEST%" mkdir "%AGENTS_DEST%"
for %%A in ("%AGENTS_SRC%\*.md") do (
  copy /y "%%A" "%AGENTS_DEST%\" >nul
)
echo   installed agents

echo.
echo ===============================================
echo implr installed.
echo   Skills and agents are in .claude\
echo.
echo Next step:
echo   Open your project in Claude Code and run: /implr-init
echo   This scaffolds docs\implr\ and sets up your config.
echo ===============================================
endlocal
