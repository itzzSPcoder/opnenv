@echo off
setlocal

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage
if "%~4"=="" goto :usage

set GH_USERNAME=%~1
set GH_REPO=%~2
set HF_USERNAME=%~3
set HF_SPACE=%~4
set COMMIT_MSG=%~5
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Sync GitHub and HuggingFace

call scripts\deploy_github.cmd %GH_USERNAME% %GH_REPO% "%COMMIT_MSG%"
if errorlevel 1 exit /b 1

call scripts\deploy_hf.cmd %HF_USERNAME% %HF_SPACE% "%COMMIT_MSG%"
if errorlevel 1 exit /b 1

echo Synced to both remotes.
exit /b 0

:usage
echo Usage: scripts\push_both.cmd ^<gh_user^> ^<gh_repo^> ^<hf_user^> ^<hf_space^> [commit_message]
exit /b 1
