# Changelog

All notable changes to the Site-Calc Investment Client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
