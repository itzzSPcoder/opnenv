@echo off
setlocal

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set GH_USERNAME=%~1
set GH_REPO=%~2
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

git remote remove origin >nul 2>nul
git remote add origin https://github.com/%GH_USERNAME%/%GH_REPO%.git
git push -u origin main

if errorlevel 1 (
  echo Push failed. If prompted, use your GitHub username and PAT token.
  exit /b 1
)

echo Push complete: https://github.com/%GH_USERNAME%/%GH_REPO%
exit /b 0

:usage
echo Usage: scripts\deploy_github.cmd ^<github_username^> ^<repo_name^> [commit_message]
exit /b 1
