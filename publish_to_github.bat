@echo off
REM Publish client-investment to new GitHub repository using gh CLI

setlocal EnableDelayedExpansion

set REPO_NAME=site-calc-investment
set REPO_DESCRIPTION=Python client for Site-Calc investment planning API - long-term capacity planning and ROI analysis

echo ========================================================================
echo Publishing Site-Calc Investment Client to GitHub
echo ========================================================================

REM Check if gh CLI is installed
where gh >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: GitHub CLI (gh) is not installed
    echo Install from: https://cli.github.com/
    exit /b 1
)

REM Check if user is authenticated
gh auth status >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Not authenticated with GitHub
    echo Run: gh auth login
    exit /b 1
)

echo.
echo Step 1: Creating GitHub repository...
gh repo create %REPO_NAME% --public --description "%REPO_DESCRIPTION%" --source=. --remote=origin --push=false

if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Repository creation failed - may already exist
)

echo.
echo Step 2: Initializing git repository...
if not exist .git (
    git init
    echo Git repository initialized
) else (
    echo Git repository already exists
)

echo.
echo Step 3: Adding files...
git add .

echo.
echo Step 4: Creating initial commit...
git commit -m "Initial commit: Site-Calc Investment Client v1.0.0" -m "Features:" -m "- Complete Pydantic V2 models for investment planning" -m "- API client with retry logic and exponential backoff" -m "- Financial analysis (NPV, IRR, payback period)" -m "- Scenario comparison utilities" -m "- 10 device types (Battery, CHP, HeatAccumulator, PV, Demand, Market)" -m "- 120 tests with 93%% code coverage" -m "- Full documentation and examples" -m "- GitHub Actions CI/CD" -m "" -m "Capabilities:" -m "- 10-year optimization horizon (100,000 intervals max)" -m "- 1-hour resolution only" -m "- Investment-specific features (no ANS)" -m "- Multi-site optimization (max 50 sites)"

echo.
echo Step 5: Setting up remote and pushing...
git branch -M main

REM Get GitHub username
for /f "tokens=*" %%i in ('gh api user --jq .login') do set GH_USER=%%i

git remote remove origin 2>nul
git remote add origin https://github.com/%GH_USER%/%REPO_NAME%.git
git push -u origin main

echo.
echo ========================================================================
echo SUCCESS! Repository published to GitHub
echo ========================================================================
echo.
echo Repository URL: https://github.com/%GH_USER%/%REPO_NAME%
echo.
echo Next steps:
echo   1. Visit your repository on GitHub
echo   2. Configure branch protection rules (optional)
echo   3. Enable GitHub Actions (should auto-enable)
echo   4. Add topics/tags for discoverability
echo   5. (Optional) Publish to PyPI - see READY_TO_PUBLISH.md
echo.

endlocal
