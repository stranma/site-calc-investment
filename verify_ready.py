#!/usr/bin/env python3
"""Verify that the package is ready for publishing to a new repository."""

import sys
from pathlib import Path


def check_file(path: str, description: str) -> bool:
    """Check if a file exists."""
    exists = Path(path).exists()
    status = "[OK]" if exists else "[MISS]"
    print(f"{status} {description}: {path}")
    return exists


def check_dir(path: str, description: str) -> bool:
    """Check if a directory exists."""
    exists = Path(path).is_dir()
    status = "[OK]" if exists else "[MISS]"
    print(f"{status} {description}: {path}")
    return exists


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("Site-Calc Investment Client - Repository Readiness Check")
    print("=" * 70)

    checks = []

    print("\n[Documentation Files]")
    checks.append(check_file("README.md", "README"))
    checks.append(check_file("LICENSE", "License"))
    checks.append(check_file("CHANGELOG.md", "Changelog"))
    checks.append(check_file("CONTRIBUTING.md", "Contributing guide"))
    checks.append(check_file("MIGRATION_GUIDE.md", "Migration guide"))
    checks.append(check_file("READY_TO_PUBLISH.md", "Publishing checklist"))
    checks.append(check_file("QUICK_START.md", "Quick start guide"))

    print("\n[Configuration Files]")
    checks.append(check_file("pyproject.toml", "Package configuration"))
    checks.append(check_file(".gitignore", "Git ignore"))
    checks.append(check_file(".github/workflows/ci.yml", "CI workflow"))
    checks.append(check_file(".github/workflows/publish.yml", "PyPI publish workflow"))

    print("\n[Publishing Scripts]")
    checks.append(check_file("publish_to_github.sh", "GitHub publish script (bash)"))
    checks.append(check_file("publish_to_github.bat", "GitHub publish script (Windows)"))

    print("\n[Package Structure]")
    checks.append(check_dir("site_calc_investment", "Main package"))
    checks.append(check_dir("site_calc_investment/models", "Models"))
    checks.append(check_dir("site_calc_investment/api", "API client"))
    checks.append(check_dir("site_calc_investment/analysis", "Analysis"))
    checks.append(check_file("site_calc_investment/exceptions.py", "Exceptions"))

    print("\n[Tests]")
    checks.append(check_dir("tests", "Test directory"))
    checks.append(check_file("tests/conftest.py", "Test fixtures"))
    checks.append(check_file("tests/test_common_models.py", "Common models tests"))
    checks.append(check_file("tests/test_device_models.py", "Device models tests"))
    checks.append(check_file("tests/test_request_models.py", "Request models tests"))
    checks.append(check_file("tests/test_api_client.py", "API client tests"))
    checks.append(check_file("tests/test_financial_analysis.py", "Financial analysis tests"))
    checks.append(check_file("tests/test_scenario_comparison.py", "Scenario comparison tests"))

    print("\n[Examples]")
    checks.append(check_dir("examples", "Examples directory"))
    checks.append(check_file("examples/01_basic_capacity_planning.py", "Capacity planning example"))
    checks.append(check_file("examples/02_scenario_comparison.py", "Scenario comparison example"))
    checks.append(check_file("examples/03_financial_analysis.py", "Financial analysis example"))

    print("\n" + "=" * 70)

    total = len(checks)
    passed = sum(checks)
    failed = total - passed

    print(f"\nResults: {passed}/{total} checks passed")

    if failed > 0:
        print(f"[FAIL] {failed} checks failed - repository not ready")
        return 1
    else:
        print("[PASS] All checks passed - repository is ready to publish!")
        print("\nNext steps:")
        print("   1. Read MIGRATION_GUIDE.md for detailed instructions")
        print("   2. Create new GitHub repository")
        print("   3. Run: git init && git add . && git commit -m 'Initial commit'")
        print("   4. Run: git remote add origin <your-repo-url>")
        print("   5. Run: git push -u origin main")
        return 0


if __name__ == "__main__":
    sys.exit(main())
