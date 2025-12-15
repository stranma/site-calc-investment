# Contributing to Site-Calc Investment Client

Thank you for considering contributing to the Site-Calc Investment Client! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites
- Python 3.10 or higher
- `uv` package manager (recommended) or `pip`

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/site-calc/investment-client.git
   cd investment-client
   ```

2. **Create virtual environment**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   uv pip install -e ".[dev]"
   ```

## Development Workflow

### Running Tests

Run all tests:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest tests/ --cov=site_calc_investment --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_financial_analysis.py -v
```

### Code Style

We use `ruff` for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Type Checking

We use `mypy` for static type checking:

```bash
mypy site_calc_investment/
```

## Code Standards

### Style Guidelines
- **Line length**: 120 characters maximum
- **Type hints**: Required for all functions and methods
- **Docstrings**: Use reStructuredText format (PEP 257)
- **Imports**: Organized with `ruff` (stdlib, third-party, local)

### Testing Requirements
- All new features must include tests
- Maintain or improve code coverage (currently 93%)
- Use pytest fixtures for common test data
- Mock HTTP requests (no real API calls in tests)

### Commit Messages
Follow conventional commits format:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions or changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

Example:
```
feat: Add support for wind turbine devices

- Add WindTurbine device model
- Add generation profile validation
- Add tests for wind turbine
```

## Test-Driven Development (TDD)

We follow TDD methodology:

1. **Write tests first** - Define the interface and expected behavior
2. **Implement code** - Make tests pass
3. **Refactor** - Improve code quality while keeping tests green

Example workflow:
```python
# 1. Write test (tests/test_new_feature.py)
def test_wind_turbine_creation():
    turbine = WindTurbine(
        name="WT1",
        properties=WindTurbineProperties(capacity=5.0)
    )
    assert turbine.name == "WT1"

# 2. Run test (should fail)
pytest tests/test_new_feature.py::test_wind_turbine_creation

# 3. Implement feature (site_calc_investment/models/devices.py)
class WindTurbine(BaseModel):
    name: str
    properties: WindTurbineProperties

# 4. Run test again (should pass)
pytest tests/test_new_feature.py::test_wind_turbine_creation
```

## Pull Request Process

1. **Create a branch**
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes**
   - Follow TDD workflow
   - Add/update tests
   - Update documentation if needed

3. **Run quality checks**
   ```bash
   ruff check --fix .
   ruff format .
   mypy site_calc_investment/
   pytest tests/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: Add your feature description"
   ```

5. **Push and create PR**
   ```bash
   git push origin feat/your-feature-name
   ```

6. **PR Checklist**
   - [ ] Tests pass locally
   - [ ] Code coverage maintained or improved
   - [ ] Type hints added for all new code
   - [ ] Docstrings added for public functions/classes
   - [ ] CHANGELOG.md updated
   - [ ] No breaking changes (or clearly documented)

## Project Structure

```
client-investment/
├── site_calc_investment/       # Main package
│   ├── models/                 # Pydantic models
│   │   ├── common.py          # TimeSpan, Resolution, Location
│   │   ├── devices.py         # Device models
│   │   ├── requests.py        # Request models
│   │   └── responses.py       # Response models
│   ├── api/                   # API client
│   │   └── client.py          # InvestmentClient
│   ├── analysis/              # Financial analysis
│   │   ├── financial.py       # NPV, IRR, payback
│   │   └── comparison.py      # Scenario comparison
│   └── exceptions.py          # Custom exceptions
├── tests/                     # Test suite
│   ├── conftest.py           # Pytest fixtures
│   ├── test_*.py             # Test modules
├── examples/                  # Usage examples
└── docs/                      # Documentation (if added)
```

## Adding New Device Types

If adding a new device type:

1. **Define model** in `site_calc_investment/models/devices.py`
2. **Add tests** in `tests/test_device_models.py`
3. **Update examples** if relevant
4. **Update CHANGELOG.md**

## Questions or Issues?

- **Bug reports**: Open an issue with reproduction steps
- **Feature requests**: Open an issue describing the use case
- **Questions**: Check README.md first, then open a discussion

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
