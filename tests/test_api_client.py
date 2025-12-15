"""Tests for InvestmentClient API client with mocked HTTP."""

import pytest
from unittest.mock import Mock, patch
import httpx

from site_calc_investment.api.client import InvestmentClient
from site_calc_investment.models.requests import InvestmentPlanningRequest, TimeSpanInvestment
from site_calc_investment.models.responses import Job, InvestmentPlanningResponse
from site_calc_investment.models.common import Resolution
from site_calc_investment.exceptions import (
    ValidationError,
    AuthenticationError,
    ForbiddenFeatureError,
    LimitExceededError,
    TimeoutError,
    OptimizationError,
    JobNotFoundError,
)


class TestInvestmentClientInitialization:
    """Tests for client initialization."""

    def test_client_initialization(self):
        """Test basic client initialization."""
        client = InvestmentClient(
            base_url="https://api.example.com",
            api_key="inv_test_key"
        )

        assert client.base_url == "https://api.example.com"
        assert client.api_key == "inv_test_key"
        assert client.max_intervals == 100_000

    def test_client_requires_inv_prefix(self):
        """Test that API key must start with 'inv_'."""
        # Valid
        InvestmentClient(
            base_url="https://api.example.com",
            api_key="inv_valid_key"
        )

        # Invalid: wrong prefix
        with pytest.raises(ValueError, match="must start with 'inv_'"):
            InvestmentClient(
                base_url="https://api.example.com",
                api_key="op_wrong_prefix"
            )

        # Invalid: no prefix
        with pytest.raises(ValueError, match="must start with 'inv_'"):
            InvestmentClient(
                base_url="https://api.example.com",
                api_key="no_prefix"
            )

    def test_client_context_manager(self):
        """Test client as context manager."""
        with InvestmentClient("https://api.example.com", "inv_test") as client:
            assert client.api_key == "inv_test"

    def test_client_custom_timeout(self):
        """Test client with custom timeout."""
        client = InvestmentClient(
            base_url="https://api.example.com",
            api_key="inv_test",
            timeout=7200.0  # 2 hours
        )

        assert client.timeout == 7200.0


class TestCreatePlanningJob:
    """Tests for create_planning_job method."""

    @patch('httpx.Client.request')
    def test_create_planning_job_success(
        self,
        mock_request,
        simple_site,
        prague_tz,
        mock_job_response
    ):
        """Test successful job creation."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = mock_job_response
        mock_request.return_value = mock_response

        # Create client and request
        client = InvestmentClient("https://api.example.com", "inv_test")
        from datetime import datetime
        timespan = TimeSpanInvestment(
            start=datetime(2025, 1, 1, 0, 0, 0, tzinfo=prague_tz),
            intervals=8760,
            resolution=Resolution.HOUR_1
        )
        request = InvestmentPlanningRequest(
            sites=[simple_site],
            timespan=timespan
        )

        # Make request
        job = client.create_planning_job(request)

        # Verify
        assert isinstance(job, Job)
        assert job.job_id == "test_job_123"
        assert job.status == "pending"
        mock_request.assert_called_once()

    @patch('httpx.Client.request')
    def test_create_planning_job_validation_error(self, mock_request):
        """Test validation error response."""
        # Setup mock for validation error
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {
                "code": "validation_error",
                "message": "Invalid request",
                "details": {"field": "timespan.intervals"}
            }
        }
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")

        # This would normally be a valid request, but server returns validation error
        with patch.object(client, '_client') as mock_client:
            mock_client.request.return_value = mock_response

            with pytest.raises(ValidationError, match="Invalid request"):
                # Dummy request
                from site_calc_investment.models.requests import InvestmentPlanningRequest
                mock_request_obj = Mock(spec=InvestmentPlanningRequest)
                mock_request_obj.model_dump_for_api.return_value = {}
                client.create_planning_job(mock_request_obj)

    @patch('httpx.Client.request')
    def test_create_planning_job_forbidden_feature(self, mock_request):
        """Test forbidden feature error (e.g., using ANS)."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": {
                "code": "forbidden_feature",
                "message": "Ancillary services not available for investment clients"
            }
        }
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")

        with patch.object(client, '_client') as mock_client:
            mock_client.request.return_value = mock_response

            with pytest.raises(ForbiddenFeatureError, match="Ancillary services"):
                mock_request_obj = Mock()
                mock_request_obj.model_dump_for_api.return_value = {}
                client.create_planning_job(mock_request_obj)

    @patch('httpx.Client.request')
    def test_create_planning_job_limit_exceeded(self, mock_request):
        """Test limit exceeded error."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": {
                "code": "limit_exceeded",
                "message": "Investment clients limited to 100,000 intervals",
                "details": {"requested": 150000, "max_allowed": 100000}
            }
        }
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")

        with patch.object(client, '_client') as mock_client:
            mock_client.request.return_value = mock_response

            with pytest.raises(LimitExceededError) as exc_info:
                mock_request_obj = Mock()
                mock_request_obj.model_dump_for_api.return_value = {}
                client.create_planning_job(mock_request_obj)

            assert exc_info.value.requested == 150000
            assert exc_info.value.max_allowed == 100000


class TestGetJobStatus:
    """Tests for get_job_status method."""

    @patch('httpx.Client.request')
    def test_get_job_status_running(self, mock_request, mock_job_running_response):
        """Test getting running job status."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_job_running_response
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")
        job = client.get_job_status("test_job_123")

        assert job.status == "running"
        assert job.progress == 45

    @patch('httpx.Client.request')
    def test_get_job_status_not_found(self, mock_request):
        """Test job not found error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "error": {
                "code": "job_not_found",
                "message": "Job not found"
            }
        }
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")

        with pytest.raises(JobNotFoundError):
            client.get_job_status("nonexistent_job")


class TestGetJobResult:
    """Tests for get_job_result method."""

    @patch('httpx.Client.request')
    def test_get_job_result_success(self, mock_request, mock_job_completed_response):
        """Test getting completed job result."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_job_completed_response
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")
        result = client.get_job_result("test_job_123")

        assert isinstance(result, InvestmentPlanningResponse)
        assert result.status == "completed"
        assert result.summary.investment_metrics.npv == 1250000.0
        assert result.summary.investment_metrics.irr == 0.12

    @patch('httpx.Client.request')
    def test_get_job_result_not_completed(self, mock_request, mock_job_running_response):
        """Test getting result for non-completed job."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_job_running_response
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")

        with pytest.raises(Exception, match="not completed"):
            client.get_job_result("test_job_123")


class TestCancelJob:
    """Tests for cancel_job method."""

    @patch('httpx.Client.request')
    def test_cancel_job_success(self, mock_request):
        """Test successful job cancellation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "test_job_123",
            "status": "cancelled",
            "created_at": "2025-01-01T10:00:00+01:00"
        }
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")
        job = client.cancel_job("test_job_123")

        assert job.status == "cancelled"


class TestWaitForCompletion:
    """Tests for wait_for_completion method."""

    @patch('httpx.Client.request')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_wait_for_completion_success(
        self,
        mock_sleep,
        mock_request,
        mock_job_running_response,
        mock_job_completed_response
    ):
        """Test waiting for job completion."""
        # First call: get_job_status returns "running"
        # Second call: get_job_status returns "completed" (job object without full results)
        # Third call: get_job_result returns full results
        mock_response_running = Mock()
        mock_response_running.status_code = 200
        mock_response_running.json.return_value = mock_job_running_response

        # For the second call, we need a job object with status "completed" but minimal data
        mock_job_status_completed = {
            "job_id": "test_job_123",
            "status": "completed",
            "created_at": "2025-01-01T10:00:00+01:00"
        }
        mock_response_status_completed = Mock()
        mock_response_status_completed.status_code = 200
        mock_response_status_completed.json.return_value = mock_job_status_completed

        # Third call returns full results
        mock_response_full_result = Mock()
        mock_response_full_result.status_code = 200
        mock_response_full_result.json.return_value = mock_job_completed_response

        mock_request.side_effect = [
            mock_response_running,
            mock_response_status_completed,
            mock_response_full_result
        ]

        client = InvestmentClient("https://api.example.com", "inv_test")
        result = client.wait_for_completion("test_job_123", poll_interval=1, timeout=60)

        assert isinstance(result, InvestmentPlanningResponse)
        assert result.status == "completed"
        assert mock_sleep.called

    @patch('httpx.Client.request')
    @patch('time.sleep')
    def test_wait_for_completion_failed(
        self,
        mock_sleep,
        mock_request,
        mock_job_failed_response
    ):
        """Test waiting for failed job."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_job_failed_response
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")

        with pytest.raises(OptimizationError, match="infeasible"):
            client.wait_for_completion("test_job_123", poll_interval=1, timeout=60)

    @patch('httpx.Client.request')
    @patch('time.time')
    @patch('time.sleep')
    def test_wait_for_completion_timeout(
        self,
        mock_sleep,
        mock_time,
        mock_request,
        mock_job_running_response
    ):
        """Test timeout while waiting for completion."""
        # Mock time to simulate timeout
        mock_time.side_effect = [0, 100]  # Start time, then exceed timeout

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_job_running_response
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test")

        with pytest.raises(TimeoutError, match="did not complete"):
            client.wait_for_completion("test_job_123", poll_interval=1, timeout=50)


class TestRetryLogic:
    """Tests for retry logic."""

    @patch('httpx.Client.request')
    @patch('time.sleep')
    def test_retry_on_server_error(self, mock_sleep, mock_request):
        """Test retry on 500 server error."""
        # First call fails, second succeeds
        mock_responses = [
            Mock(status_code=500, text="Server error"),
            Mock(status_code=200, json=lambda: {"job_id": "test", "status": "pending", "created_at": "2025-01-01T10:00:00+01:00"})
        ]
        mock_request.side_effect = mock_responses

        client = InvestmentClient("https://api.example.com", "inv_test", max_retries=3)

        # Should succeed after retry
        job = client.get_job_status("test_job")
        assert job.status == "pending"
        assert mock_sleep.called  # Exponential backoff sleep

    @patch('httpx.Client.request')
    @patch('time.sleep')
    def test_no_retry_on_client_error(self, mock_sleep, mock_request):
        """Test no retry on 4xx client errors."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"code": "validation_error", "message": "Invalid"}
        }
        mock_request.return_value = mock_response

        client = InvestmentClient("https://api.example.com", "inv_test", max_retries=3)

        with pytest.raises(ValidationError):
            client.get_job_status("test_job")

        # Should NOT retry on 400
        assert mock_request.call_count == 1
        assert not mock_sleep.called
