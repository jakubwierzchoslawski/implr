@echo off
REM implr installer (Windows CMD fallback)
REM Usage:
REM   install.bat              install skills to .\.claude\skills and scaffold .\docs\implr
REM   install.bat --global     install skills to %USERPROFILE%\.claude\skills
REM   install.bat --skills-only  skills only, no scaffold
REM Run from your project root.

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SKILLS_SRC=%SCRIPT_DIR%skills"
set "GLOBAL=0"
set "SKILLS_ONLY=0"

:parseargs
if "%~1"=="" goto afterargs
if /I "%~1"=="--global" set "GLOBAL=1"
if /I "%~1"=="--skills-only" set "SKILLS_ONLY=1"
shift
goto parseargs
:afterargs

if "%GLOBAL%"=="1" (
  set "SKILLS_DEST=%USERPROFILE%\.claude\skills"
) else (
  set "SKILLS_DEST=%CD%\.claude\skills"
)

echo implr installer
echo ===============
echo Skills -^> %SKILLS_DEST%

if not exist "%SKILLS_DEST%" mkdir "%SKILLS_DEST%"

for %%S in (implr-init doc-ingest arch-gen ba-requirements-gen dev-planner dev-executor dev-code-review) do (
  if not exist "%SKILLS_SRC%\%%S" (
    echo Missing skill source: %%S
    exit /b 1
  )
  if exist "%SKILLS_DEST%\%%S" rmdir /s /q "%SKILLS_DEST%\%%S"
  xcopy /e /i /q /y "%SKILLS_SRC%\%%S" "%SKILLS_DEST%\%%S" >nul
  echo   installed %%S
)

if "%SKILLS_ONLY%"=="1" (
  echo Skills installed. Run /implr-init inside Claude Code to scaffold the project.
  exit /b 0
)

set "ASSETS=%SKILLS_SRC%\implr-init\assets"
set "ROOT=%CD%"

echo.
echo Scaffolding project workspace under %ROOT%\docs

for %%D in (
  "docs\kb"
  "docs\implr\config"
  "docs\implr\schemas"
  "docs\implr\templates"
  "docs\implr\kb-index\cache"
  "docs\implr\kb-index\digests\per-doc"
  "docs\implr\kb-index\domains"
  "docs\implr\requirements\functional"
  "docs\implr\requirements\non-functional"
  "docs\implr\plans\functional"
  "docs\implr\plans\non-functional"
  "docs\implr\reviews"
) do (
  if not exist "%ROOT%\%%~D" mkdir "%ROOT%\%%~D"
)

for %%K in (
  "docs\kb"
  "docs\implr\kb-index\cache"
  "docs\implr\kb-index\digests\per-doc"
  "docs\implr\kb-index\domains"
  "docs\implr\requirements\functional"
  "docs\implr\requirements\non-functional"
  "docs\implr\plans\functional"
  "docs\implr\plans\non-functional"
  "docs\implr\reviews"
) do (
  if not exist "%ROOT%\%%~K\.gitkeep" type nul > "%ROOT%\%%~K\.gitkeep"
)

copy /y "%ASSETS%\schemas\*.md" "%ROOT%\docs\implr\schemas\" >nul
copy /y "%ASSETS%\templates\*.md" "%ROOT%\docs\implr\templates\" >nul
echo   schemas and templates copied

if not exist "%ROOT%\docs\implr\config\implr.config.yaml" (
  copy /y "%ASSETS%\config\implr.config.yaml" "%ROOT%\docs\implr\config\" >nul
  echo   created docs\implr\config\implr.config.yaml
) else (
  echo   kept existing implr.config.yaml
)

if not exist "%ROOT%\docs\implr\config\DEV-STANDARDS.md" (
  copy /y "%ASSETS%\config\DEV-STANDARDS.md" "%ROOT%\docs\implr\config\" >nul
  echo   created docs\implr\config\DEV-STANDARDS.md
) else (
  echo   kept existing DEV-STANDARDS.md
)

if not exist "%ROOT%\CLAUDE.md" (
  copy /y "%ASSETS%\templates\CLAUDE-template.md" "%ROOT%\CLAUDE.md" >nul
  echo   created CLAUDE.md
) else (
  echo   kept existing CLAUDE.md
)

echo.
echo ===============================================
echo implr installed.
echo.
echo Next steps:
echo   1. Fill in [FILL IN] sections of docs\implr\config\DEV-STANDARDS.md
echo   2. Edit docs\implr\config\implr.config.yaml (project name, stack)
echo   3. Add documentation to docs\kb\
echo   4. In Claude Code run: /doc-ingest then /arch-gen then /ba-requirements-gen
echo ===============================================
endlocal
