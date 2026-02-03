# Changelog

All notable changes to the Site-Calc Investment Client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-02-03

### Changed
- **Repository URLs**: Updated package metadata to point to official GitHub repository
- **CI/CD**: Added automatic PyPI publishing workflow on release tags

### Fixed
- Minor documentation improvements and URL corrections

---

## [1.1.0] - 2026-02-01

### Added
- **SOC Anchoring**: New optional fields `soc_anchor_interval_hours` and `soc_anchor_target`
  in `BatteryProperties` for improved long-term battery optimization
- **Version Validation**: Client automatically checks server version compatibility and warns
  if MAJOR.MINOR versions don't match
- **Timeout Control**: Jobs can now specify custom timeout limits

### Changed
- **Default Solver**: Changed from CBC to HiGHS for 30-40% faster optimization times
- Results are identical; no code changes required

### Notes
- All v1.0.x client code continues to work without modification
- SOC anchoring is opt-in via new optional fields
- Version warnings are informational only and don't affect functionality

---

## [1.0.0] - 2024-12-15

### Added
- Initial release of Site-Calc Investment Client
- Complete Pydantic V2 models for investment planning requests and responses
- 10 device types: Battery, CHP, HeatAccumulator, Photovoltaic, ElectricityDemand, HeatDemand, ElectricityImport, ElectricityExport, GasImport, HeatExport
- API client with automatic retry logic and exponential backoff
- Financial analysis functions: NPV, IRR (Newton-Raphson), payback period
- Scenario comparison utilities for evaluating multiple investment options
- Support for 10-year hourly optimization (up to 100,000 intervals)
- Comprehensive test suite with 120 tests and 93% coverage
- Three complete examples demonstrating capacity planning, scenario comparison, and financial analysis

### Features
- **Investment-Specific**: Designed exclusively for long-term capacity planning and ROI analysis
- **No Ancillary Services**: Investment client does not support ANS optimization (reserved for operational client)
- **1-Hour Resolution Only**: Optimized for multi-year planning horizons
- **Automatic Binary Relaxation**: CHP binary constraints automatically relaxed for tractability
- **Financial Metrics**: Built-in NPV, IRR, and payback period calculations
- **Type-Safe**: Full type hints with Pydantic V2 validation
- **Well-Tested**: 120 tests covering all major functionality with mocked HTTP responses

### Notes
- Requires API key with `inv_` prefix
- Maximum 100,000 intervals (~11 years at 1-hour resolution)
- Default timeout: 3600 seconds (1 hour)
- Python 3.10+ required
