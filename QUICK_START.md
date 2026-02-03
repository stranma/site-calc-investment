# Quick Start: Publish to GitHub in 2 Minutes

The fastest way to publish this package to GitHub using the GitHub CLI.

## Prerequisites

1. **Install GitHub CLI** (if not already installed):
   - Windows: `winget install --id GitHub.cli`
   - macOS: `brew install gh`
   - Linux: https://github.com/cli/cli/blob/trunk/docs/install_linux.md

2. **Authenticate** (if not already authenticated):
   ```bash
   gh auth login
   ```
   Follow the prompts to authenticate with your GitHub account.

## Option 1: Automated Script (Recommended)

### On Windows:
```bash
cd client-investment
.\publish_to_github.bat
```

### On Linux/macOS:
```bash
cd client-investment
chmod +x publish_to_github.sh
./publish_to_github.sh
```

**Done!** Your repository is now live on GitHub.

## Option 2: Manual Commands

If you prefer to run commands manually:

```bash
# Navigate to the directory
cd client-investment

# Create GitHub repository
gh repo create site-calc-investment \
    --public \
    --description "Python client for Site-Calc investment planning API - long-term capacity planning and ROI analysis" \
    --source=. \
    --remote=origin

# Initialize git (if needed)
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Site-Calc Investment Client v1.0.0"

# Push to GitHub
git branch -M main
git push -u origin main
```

## What Happens Next?

1. **Repository Created**: Your code is now on GitHub
2. **CI Runs**: GitHub Actions will automatically run tests
3. **README Displays**: Your documentation is visible
4. **Ready to Use**: Others can clone and install your package

## View Your Repository

```bash
# Open repository in browser
gh repo view --web
```

Or visit: `https://github.com/YOUR-USERNAME/site-calc-investment`

## Next Steps

### 1. Configure Repository Settings

```bash
# Add topics for discoverability
gh repo edit --add-topic python,energy,optimization,investment-analysis,capacity-planning,roi-analysis

# Enable discussions (optional)
gh repo edit --enable-discussions

# Enable issues (should be on by default)
gh repo edit --enable-issues
```

### 2. Protect Main Branch

Go to repository Settings → Branches → Add rule for `main`:
- ✅ Require pull request reviews
- ✅ Require status checks to pass (CI)

### 3. Publish to PyPI (Optional)

To enable `pip install site-calc-investment`:

#### One-Time Setup:

1. **Create PyPI account**: https://pypi.org/account/register/

2. **Configure Trusted Publishing** on PyPI:
   - Go to: https://pypi.org/manage/account/publishing/
   - Click "Add a new pending publisher"
   - Fill in:
     - PyPI Project Name: `site-calc-investment`
     - Owner: `YOUR-GITHUB-USERNAME`
     - Repository name: `site-calc-investment`
     - Workflow name: `publish.yml`
     - Environment name: `pypi`

3. **Done!** No API tokens needed (uses trusted publishing)

#### Publishing a Release:

```bash
# Create a release (will auto-publish to PyPI)
gh release create v1.0.0 \
    --title "v1.0.0 - Initial Release" \
    --notes "$(cat CHANGELOG.md)"

# Or use the web interface:
gh repo view --web
# Click "Releases" → "Create a new release"
```

When you create a release, the `.github/workflows/publish.yml` workflow automatically:
- Builds the package
- Uploads to PyPI
- Users can install with: `pip install site-calc-investment`

## Troubleshooting

### "Repository already exists"
```bash
# If repo was partially created, delete it first:
gh repo delete YOUR-USERNAME/site-calc-investment --yes
# Then run the script again
```

### "Not authenticated"
```bash
gh auth login
# Follow the prompts
```

### "Git not initialized"
```bash
cd client-investment
git init
git add .
git commit -m "Initial commit"
git push -u origin main
```

### CI Failing
- Check GitHub Actions tab in your repository
- Tests should all pass (120/120)
- If failing, check platform-specific issues

## Files Overview

After publishing, your repository will have:

```
site-calc-investment/
├── .github/
│   └── workflows/
│       ├── ci.yml          # Tests on push/PR
│       └── publish.yml     # Auto-publish to PyPI on release
├── site_calc_investment/   # Package source
├── tests/                  # 120 tests
├── examples/               # 3 usage examples
├── README.md              # Main documentation
├── LICENSE                # MIT License
├── CHANGELOG.md           # Version history
├── CONTRIBUTING.md        # Contribution guide
└── pyproject.toml         # Package config
```

## Support

- **Issues**: https://github.com/YOUR-USERNAME/site-calc-investment/issues
- **Discussions**: https://github.com/YOUR-USERNAME/site-calc-investment/discussions
- **CI Status**: https://github.com/YOUR-USERNAME/site-calc-investment/actions

---

**That's it!** Your package is now open source and ready for the world to use. 🚀
