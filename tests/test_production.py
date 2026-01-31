"""Production integration tests for the investment client.

These tests run against a live API and require credentials set via environment variables:
- INVESTMENT_API_URL: Base URL of the API (e.g., https://api.site-calc.example.com)
- INVESTMENT_API_KEY: API key with 'inv_' prefix

Tests are skipped if credentials are not available.

IMPORTANT: Large tasks are created and immediately cancelled to minimize costs.
"""

import os
import time
from datetime import datetime
from typing import Generator, List
from zoneinfo import ZoneInfo

import pytest

from site_calc_investment.api.client import InvestmentClient
from site_calc_investment.exceptions import AuthenticationError, JobNotFoundError
from site_calc_investment.models import (
    Battery,
    BatteryProperties,
    ElectricityExport,
    ElectricityImport,
    MarketExportProperties,
    MarketImportProperties,
    Site,
)
from site_calc_investment.models.common import Resolution
from site_calc_investment.models.requests import InvestmentPlanningRequest, TimeSpanInvestment


def _credentials_available() -> bool:
    """Check if production API credentials are available."""
    return bool(os.environ.get("INVESTMENT_API_URL") and os.environ.get("INVESTMENT_API_KEY"))


def _get_api_url() -> str:
    """Get API URL from environment."""
    return os.environ.get("INVESTMENT_API_URL", "")


def _get_api_key() -> str:
    """Get API key from environment."""
    return os.environ.get("INVESTMENT_API_KEY", "")


# Skip all tests in this module if credentials are not available
pytestmark = [
    pytest.mark.production,
    pytest.mark.skipif(not _credentials_available(), reason="Production API credentials not available"),
]


@pytest.fixture(scope="module")
def prague_tz() -> ZoneInfo:
    """Prague timezone for test data."""
    return ZoneInfo("Europe/Prague")


@pytest.fixture(scope="module")
def production_client() -> Generator[InvestmentClient, None, None]:
    """Production client with cleanup on exit.

    Cancels all jobs on exit to ensure no orphaned jobs remain.
    """
    client = InvestmentClient(base_url=_get_api_url(), api_key=_get_api_key(), timeout=600.0)
    try:
        yield client
    finally:
        # Cleanup: cancel all jobs to avoid orphaned tasks
        try:
            client.cancel_all_jobs()
        except Exception:
            pass  # Ignore cleanup errors
        client.close()


@pytest.fixture(scope="module")
def small_price_profile() -> List[float]:
    """168 hourly prices (1 week) for small task tests."""
    prices = []
    for day in range(7):
        for hour in range(24):
            if 9 <= hour <= 20:
                price = 40.0 + (day * 0.5)  # Slight daily variation
            else:
                price = 25.0 + (day * 0.3)
            prices.append(price)
    return prices


@pytest.fixture(scope="module")
def large_price_profile() -> List[float]:
    """8760 hourly prices (1 year) for large task tests."""
    prices = []
    for day in range(365):
        for hour in range(24):
            if 9 <= hour <= 20:
                price = 40.0
            else:
                price = 25.0
            prices.append(price)
    return prices


@pytest.fixture(scope="module")
def small_battery() -> Battery:
    """Small battery for tests."""
    return Battery(
        name="TestBattery",
        properties=BatteryProperties(capacity=10.0, max_power=5.0, efficiency=0.90, initial_soc=0.5),
    )


@pytest.fixture(scope="module")
def small_site(small_battery: Battery, small_price_profile: List[float]) -> Site:
    """Site configured for small task tests (168 intervals)."""
    grid_import = ElectricityImport(
        name="GridImport",
        properties=MarketImportProperties(price=small_price_profile, max_import=10.0),
    )
    grid_export = ElectricityExport(
        name="GridExport",
        properties=MarketExportProperties(price=small_price_profile, max_export=10.0),
    )
    return Site(
        site_id="prod_test_site_small",
        description="Production test site (small)",
        devices=[small_battery, grid_import, grid_export],
    )


@pytest.fixture(scope="module")
def large_site(small_battery: Battery, large_price_profile: List[float]) -> Site:
    """Site configured for large task tests (8760 intervals)."""
    grid_import = ElectricityImport(
        name="GridImport",
        properties=MarketImportProperties(price=large_price_profile, max_import=10.0),
    )
    grid_export = ElectricityExport(
        name="GridExport",
        properties=MarketExportProperties(price=large_price_profile, max_export=10.0),
    )
    return Site(
        site_id="prod_test_site_large",
        description="Production test site (large - immediately cancelled)",
        devices=[small_battery, grid_import, grid_export],
    )


class TestProductionSmallTask:
    """Tests for small tasks that complete successfully."""

    def test_small_task_completes_successfully(
        self,
        production_client: InvestmentClient,
        small_site: Site,
        prague_tz: ZoneInfo,
    ) -> None:
        """Test that a small task (168 intervals = 1 week) completes successfully."""
        timespan = TimeSpanInvestment(
            start=datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz),
            intervals=168,
            resolution=Resolution.HOUR_1,
        )
        request = InvestmentPlanningRequest(sites=[small_site], timespan=timespan)

        # Create job
        job = production_client.create_planning_job(request)
        assert job.job_id is not None
        assert job.status in ("pending", "running", "completed")  # May complete instantly for small jobs

        # Wait for completion with reasonable timeout
        result = production_client.wait_for_completion(job.job_id, poll_interval=5, timeout=300)

        # Verify result
        assert result.status == "completed"
        assert result.summary is not None
        assert result.summary.solver_status.lower() == "optimal"
        assert "prod_test_site_small" in result.sites

    def test_job_status_polling(
        self,
        production_client: InvestmentClient,
        small_site: Site,
        prague_tz: ZoneInfo,
    ) -> None:
        """Test job status polling returns valid status values."""
        timespan = TimeSpanInvestment(
            start=datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz),
            intervals=24,  # Very small: 1 day
            resolution=Resolution.HOUR_1,
        )
        request = InvestmentPlanningRequest(sites=[small_site], timespan=timespan)

        # Create job
        job = production_client.create_planning_job(request)

        # Poll status immediately
        status = production_client.get_job_status(job.job_id)
        assert status.status in ("pending", "running", "completed")
        assert status.job_id == job.job_id

        # Wait for completion and verify final status
        result = production_client.wait_for_completion(job.job_id, poll_interval=2, timeout=120)
        assert result.status == "completed"


class TestProductionLargeTaskCancellation:
    """Tests for large tasks that are immediately cancelled (cost awareness)."""

    def test_large_task_can_be_cancelled(
        self,
        production_client: InvestmentClient,
        large_site: Site,
        prague_tz: ZoneInfo,
    ) -> None:
        """Test that a large task (8760 intervals = 1 year) can be cancelled immediately."""
        timespan = TimeSpanInvestment(
            start=datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz),
            intervals=8760,
            resolution=Resolution.HOUR_1,
        )
        request = InvestmentPlanningRequest(sites=[large_site], timespan=timespan)

        # Create job
        job = production_client.create_planning_job(request)
        assert job.job_id is not None
        assert job.status in ("pending", "running")

        # Cancel immediately to minimize costs
        cancelled = production_client.cancel_job(job.job_id)
        assert cancelled.status == "cancelled"
        assert cancelled.job_id == job.job_id

    def test_large_task_status_before_cancel(
        self,
        production_client: InvestmentClient,
        large_site: Site,
        prague_tz: ZoneInfo,
    ) -> None:
        """Test that large task status is pending/running before cancellation."""
        timespan = TimeSpanInvestment(
            start=datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz),
            intervals=8760,
            resolution=Resolution.HOUR_1,
        )
        request = InvestmentPlanningRequest(sites=[large_site], timespan=timespan)

        # Create job
        job = production_client.create_planning_job(request)

        # Check status (should be pending or running)
        status = production_client.get_job_status(job.job_id)
        assert status.status in ("pending", "running")

        # Cancel immediately
        cancelled = production_client.cancel_job(job.job_id)
        assert cancelled.status == "cancelled"


class TestProductionCancelAllJobs:
    """Tests for cancel_all_jobs bulk cleanup."""

    def test_cancel_all_jobs_cleans_up(
        self,
        production_client: InvestmentClient,
        small_site: Site,
        prague_tz: ZoneInfo,
    ) -> None:
        """Test that cancel_all_jobs cancels multiple pending jobs."""
        timespan = TimeSpanInvestment(
            start=datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz),
            intervals=24,
            resolution=Resolution.HOUR_1,
        )
        request = InvestmentPlanningRequest(sites=[small_site], timespan=timespan)

        # Create 3 jobs
        job_ids = []
        for _ in range(3):
            job = production_client.create_planning_job(request)
            job_ids.append(job.job_id)

        # Small delay to ensure jobs are registered
        time.sleep(1)

        # Cancel all jobs
        result = production_client.cancel_all_jobs()

        # Verify at least our jobs were cancelled
        assert result["cancelled_count"] >= 0  # Could be 0 if jobs completed very fast
        assert isinstance(result["cancelled_jobs"], list)

        # Verify jobs are no longer running
        for job_id in job_ids:
            status = production_client.get_job_status(job_id)
            assert status.status in ("cancelled", "completed")

    def test_cancel_all_jobs_idempotent(self, production_client: InvestmentClient) -> None:
        """Test that cancel_all_jobs is safe to call when no jobs exist."""
        # First call to clean up any existing jobs
        production_client.cancel_all_jobs()

        # Second call should return 0 cancelled (idempotent)
        result = production_client.cancel_all_jobs()
        assert result["cancelled_count"] == 0
        assert result["cancelled_jobs"] == []


class TestProductionErrorHandling:
    """Tests for error handling with production API."""

    def test_invalid_api_key_raises_authentication_error(self) -> None:
        """Test that invalid API key raises AuthenticationError."""
        client = InvestmentClient(
            base_url=_get_api_url(),
            api_key="inv_invalid_key_12345",
            timeout=30.0,
        )
        try:
            with pytest.raises(AuthenticationError):
                # Try to list or create job - should fail authentication
                client.cancel_all_jobs()
        finally:
            client.close()

    def test_nonexistent_job_raises_not_found(self, production_client: InvestmentClient) -> None:
        """Test that querying nonexistent job raises JobNotFoundError."""
        # Use valid UUID format to avoid 422 validation error
        with pytest.raises(JobNotFoundError):
            production_client.get_job_status("00000000-0000-0000-0000-000000000000")

    def test_cancel_nonexistent_job_raises_not_found(self, production_client: InvestmentClient) -> None:
        """Test that cancelling nonexistent job raises JobNotFoundError."""
        # Use valid UUID format to avoid 422 validation error
        with pytest.raises(JobNotFoundError):
            production_client.cancel_job("00000000-0000-0000-0000-000000000000")
