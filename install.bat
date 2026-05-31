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
set "SCAFFOLD_SRC=%SCRIPT_DIR%scaffold"
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
if not exist "%SCAFFOLD_SRC%" (
  echo ERROR: Missing scaffold source: %SCAFFOLD_SRC%
  exit /b 1
)
if not exist "%AGENTS_DEST%" mkdir "%AGENTS_DEST%"
for %%A in ("%AGENTS_SRC%\*.md") do (
  copy /y "%%A" "%AGENTS_DEST%\" >nul
)
echo   installed agents

REM Workspace scaffolding always targets the current project (CWD), regardless of --global.
call :scaffold_workspace

echo.
echo ===============================================
echo implr installed.
echo   Skills and agents are in .claude\
echo.
echo Next step:
echo   Open your project in Claude Code and run: /implr-init
echo   This configures your project name, stack, and standards.
echo ===============================================
goto :end_main

:scaffold_workspace
echo.
echo Scaffolding workspace...

if not exist "docs\kb" mkdir "docs\kb"
if not exist "docs\kb\change-requests" mkdir "docs\kb\change-requests"
if not exist "docs\implr\config" mkdir "docs\implr\config"
if not exist "docs\implr\schemas" mkdir "docs\implr\schemas"
if not exist "docs\implr\templates" mkdir "docs\implr\templates"
if not exist "docs\implr\kb-index\cache" mkdir "docs\implr\kb-index\cache"
if not exist "docs\implr\kb-index\digests\per-doc" mkdir "docs\implr\kb-index\digests\per-doc"
if not exist "docs\implr\kb-index\domains" mkdir "docs\implr\kb-index\domains"
if not exist "docs\implr\requirements\functional" mkdir "docs\implr\requirements\functional"
if not exist "docs\implr\requirements\non-functional" mkdir "docs\implr\requirements\non-functional"
if not exist "docs\implr\plans\functional" mkdir "docs\implr\plans\functional"
if not exist "docs\implr\plans\non-functional" mkdir "docs\implr\plans\non-functional"
if not exist "docs\implr\reviews" mkdir "docs\implr\reviews"

for %%F in ("%SCAFFOLD_SRC%\schemas\*.md") do copy /y "%%F" "docs\implr\schemas\" >nul
for %%F in ("%SCAFFOLD_SRC%\templates\*.md") do copy /y "%%F" "docs\implr\templates\" >nul
echo   schemas and templates installed

if not exist "docs\implr\config\implr.config.yaml" (
    copy /y "%SCAFFOLD_SRC%\config\implr.config.yaml" "docs\implr\config\implr.config.yaml" >nul
    echo   created docs\implr\config\implr.config.yaml
) else (
    echo   kept existing docs\implr\config\implr.config.yaml
)
if not exist "docs\implr\config\DEV-STANDARDS.md" (
    copy /y "%SCAFFOLD_SRC%\config\DEV-STANDARDS.md" "docs\implr\config\DEV-STANDARDS.md" >nul
    echo   created docs\implr\config\DEV-STANDARDS.md
) else (
    echo   kept existing docs\implr\config\DEV-STANDARDS.md
)

if not exist "CLAUDE.md" (
    copy /y "%SCAFFOLD_SRC%\templates\CLAUDE-template.md" "CLAUDE.md" >nul
    echo   created CLAUDE.md
) else (
    echo   kept existing CLAUDE.md
)

if not exist "docs\implr\requirements\cr-index.md" (
    copy /y "%SCAFFOLD_SRC%\seeds\cr-index.md" "docs\implr\requirements\cr-index.md" >nul
    echo   created docs\implr\requirements\cr-index.md
) else (
    echo   kept existing docs\implr\requirements\cr-index.md
)

echo   workspace scaffolded
goto :eof

:end_main
endlocal
