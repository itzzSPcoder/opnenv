@echo off
setlocal

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set HF_USERNAME=%~1
set HF_SPACE=%~2
set COMMIT_MSG=%~3
if "%COMMIT_MSG%"=="" set COMMIT_MSG=OpenEnv submission

if not exist .git (
  git init -b main
)

git add .

git diff --cached --quiet
if errorlevel 1 (
  git commit -m "%COMMIT_MSG%"
)

git remote remove hf >nul 2>nul
if not "%HF_TOKEN%"=="" (
  git remote add hf https://%HF_USERNAME%:%HF_TOKEN%@huggingface.co/spaces/%HF_USERNAME%/%HF_SPACE%
) else (
  git remote add hf https://huggingface.co/spaces/%HF_USERNAME%/%HF_SPACE%
)
git push -u hf main

if errorlevel 1 (
  echo Push failed. If prompted, login with your Hugging Face username and token.
  exit /b 1
)

echo Push complete: https://huggingface.co/spaces/%HF_USERNAME%/%HF_SPACE%
exit /b 0

:usage
echo Usage: scripts\deploy_hf.cmd ^<hf_username^> ^<space_name^> [commit_message]
exit /b 1
