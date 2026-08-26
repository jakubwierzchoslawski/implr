@echo off
REM implr installer (Windows CMD)
REM Usage:
REM   install.bat            install skills + agents to .\.claude\
REM   install.bat --global   install skills + agents to %USERPROFILE%\.claude\
REM Run from your project root, then run /implr-init inside Claude Code.

setlocal

set "SCRIPT_DIR=%~dp0"
set "PLUGIN_SRC=%SCRIPT_DIR%plugin"
set "SKILLS_SRC=%PLUGIN_SRC%\skills"
set "AGENTS_SRC=%PLUGIN_SRC%\agents"
set "VALIDATE_PKG=%SCRIPT_DIR%packages\implr_validate"
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
if not exist "%PLUGIN_SRC%" (
  echo ERROR: Missing plugin payload: %PLUGIN_SRC%
  exit /b 1
)
if not exist "%VALIDATE_PKG%\pyproject.toml" (
  echo ERROR: Missing implr-validate package: %VALIDATE_PKG%
  exit /b 1
)
if not exist "%AGENTS_DEST%" mkdir "%AGENTS_DEST%"
for %%A in ("%AGENTS_SRC%\*.md") do (
  copy /y "%%A" "%AGENTS_DEST%\" >nul
)
echo   installed agents

if exist "%AGENTS_DEST%\executor-worker.md" (
    del /Q "%AGENTS_DEST%\executor-worker.md"
    echo   removed deprecated agent: executor-worker.md (replaced by plan-runner.md in v3)
)

REM Workspace provisioning always targets the current project (CWD), regardless of --global.
call :provision_workspace

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

:provision_workspace
echo.
echo Provisioning workspace...

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

for %%F in ("%PLUGIN_SRC%\schemas\*.md") do copy /y "%%F" "docs\implr\schemas\" >nul
for %%F in ("%PLUGIN_SRC%\schemas\*.json") do copy /y "%%F" "docs\implr\schemas\" >nul
for %%F in ("%PLUGIN_SRC%\templates\*.md") do copy /y "%%F" "docs\implr\templates\" >nul
echo   schemas and templates installed

REM implr-validate is a package, not a copied directory: a target project pins a
REM version instead of receiving a snapshot that nothing will ever update.
where pip >nul 2>&1
if %ERRORLEVEL%==0 (
    REM A plain path, not a file:// URL: pip does not accept file:// with a
    REM drive-lettered Windows path.
    pip install --quiet --upgrade "%VALIDATE_PKG%"
    echo   implr-validate installed
) else (
    echo   WARNING: pip not found - install implr-validate manually:
    echo     pip install %VALIDATE_PKG%
)

if not exist "docs\implr\config\implr.config.yaml" (
    copy /y "%PLUGIN_SRC%\config\implr.config.yaml" "docs\implr\config\implr.config.yaml" >nul
    echo   created docs\implr\config\implr.config.yaml
) else (
    echo   kept existing docs\implr\config\implr.config.yaml
)
if not exist "docs\implr\config\DEV-STANDARDS.md" (
    copy /y "%PLUGIN_SRC%\config\DEV-STANDARDS.md" "docs\implr\config\DEV-STANDARDS.md" >nul
    echo   created docs\implr\config\DEV-STANDARDS.md
) else (
    echo   kept existing docs\implr\config\DEV-STANDARDS.md
)

if not exist "CLAUDE.md" (
    copy /y "%PLUGIN_SRC%\templates\CLAUDE-template.md" "CLAUDE.md" >nul
    echo   created CLAUDE.md
) else (
    echo   kept existing CLAUDE.md
)

if not exist "docs\implr\requirements\cr-index.md" (
    copy /y "%PLUGIN_SRC%\seeds\cr-index.md" "docs\implr\requirements\cr-index.md" >nul
    echo   created docs\implr\requirements\cr-index.md
) else (
    echo   kept existing docs\implr\requirements\cr-index.md
)

if not exist "docs\implr\requirements\resolved-contradictions.md" (
    copy /y "%PLUGIN_SRC%\seeds\resolved-contradictions.md" "docs\implr\requirements\resolved-contradictions.md" >nul
    echo   created docs\implr\requirements\resolved-contradictions.md
) else (
    echo   kept existing docs\implr\requirements\resolved-contradictions.md
)

if not exist "docs\implr\DOD.md" (
    copy /Y "%PLUGIN_SRC%\seeds\DOD.md" "docs\implr\DOD.md" >nul
    echo   created docs\implr\DOD.md
) else (
    echo   kept existing docs\implr\DOD.md
)

echo   workspace provisioned
goto :eof

:end_main
endlocal
