#!/bin/bash
# Publish client-investment to new GitHub repository using gh CLI

set -e  # Exit on error

REPO_NAME="site-calc-investment"
REPO_DESCRIPTION="Python client for Site-Calc investment planning API - long-term capacity planning and ROI analysis"

echo "========================================================================"
echo "Publishing Site-Calc Investment Client to GitHub"
echo "========================================================================"

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "ERROR: GitHub CLI (gh) is not installed"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

# Check if user is authenticated
if ! gh auth status &> /dev/null; then
    echo "ERROR: Not authenticated with GitHub"
    echo "Run: gh auth login"
    exit 1
fi

echo ""
echo "Step 1: Creating GitHub repository..."
gh repo create "$REPO_NAME" \
    --public \
    --description "$REPO_DESCRIPTION" \
    --source=. \
    --remote=origin \
    --push=false

echo ""
echo "Step 2: Initializing git repository..."
if [ ! -d .git ]; then
    git init
    echo "Git repository initialized"
else
    echo "Git repository already exists"
fi

echo ""
echo "Step 3: Adding files..."
git add .

echo ""
echo "Step 4: Creating initial commit..."
git commit -m "Initial commit: Site-Calc Investment Client v1.0.0

Features:
- Complete Pydantic V2 models for investment planning
- API client with retry logic and exponential backoff
- Financial analysis (NPV, IRR, payback period)
- Scenario comparison utilities
- 10 device types (Battery, CHP, HeatAccumulator, PV, Demand, Market)
- 120 tests with 93% code coverage
- Full documentation and examples
- GitHub Actions CI/CD

Capabilities:
- 10-year optimization horizon (100,000 intervals max)
- 1-hour resolution only
- Investment-specific features (no ANS)
- Multi-site optimization (max 50 sites)

Documentation:
- README.md with quickstart
- CONTRIBUTING.md with TDD workflow
- MIGRATION_GUIDE.md
- 3 complete examples"

echo ""
echo "Step 5: Setting up remote and pushing..."
git branch -M main
git remote add origin "https://github.com/$(gh api user --jq .login)/$REPO_NAME.git" 2>/dev/null || true
git push -u origin main

echo ""
echo "========================================================================"
echo "SUCCESS! Repository published to GitHub"
echo "========================================================================"
echo ""
echo "Repository URL: https://github.com/$(gh api user --jq .login)/$REPO_NAME"
echo ""
echo "Next steps:"
echo "  1. Visit your repository on GitHub"
echo "  2. Configure branch protection rules (optional)"
echo "  3. Enable GitHub Actions (should auto-enable)"
echo "  4. Add topics/tags for discoverability"
echo "  5. (Optional) Publish to PyPI - see READY_TO_PUBLISH.md"
echo ""
