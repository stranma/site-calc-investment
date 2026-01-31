"""Investment Client for Site-Calc API."""

import time
from typing import Any, Optional

import httpx

from site_calc_investment.exceptions import (
    ApiError,
    AuthenticationError,
    ForbiddenFeatureError,
    JobNotFoundError,
    LimitExceededError,
    OptimizationError,
    SiteCalcError,
    TimeoutError,
    ValidationError,
)
from site_calc_investment.models.requests import InvestmentPlanningRequest
from site_calc_investment.models.responses import InvestmentPlanningResponse, Job


class InvestmentClient:
    """Client for Site-Calc investment planning API.

    This client is specifically for long-term capacity planning and
    investment ROI analysis. It:
    - Only supports 1-hour resolution
    - Maximum 100,000 intervals (~11 years)
    - Does NOT support ancillary services
    - Only has access to /device-planning endpoint

    Example:
        >>> client = InvestmentClient(
        ...     base_url="https://api.site-calc.example.com",
        ...     api_key="inv_your_key_here"
        ... )
        >>> job = client.create_planning_job(request)
        >>> result = client.wait_for_completion(job.job_id, timeout=7200)
        >>> print(f"NPV: €{result.summary.investment_metrics.npv:,.0f}")
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 3600.0,
        max_retries: int = 3,
    ):
        """Initialize the investment client.

        Args:
            base_url: Base URL of the API (e.g., "https://api.site-calc.example.com")
            api_key: API key with 'inv_' prefix (investment client)
            timeout: Default request timeout in seconds (default: 1 hour)
            max_retries: Maximum number of retry attempts for failed requests

        Raises:
            ValueError: If API key doesn't start with 'inv_'
        """
        if not api_key.startswith("inv_"):
            raise ValueError("API key must start with 'inv_' for investment client")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_intervals = 100_000

        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    def __enter__(self) -> "InvestmentClient":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle API error responses.

        Args:
            response: HTTP response with error status

        Raises:
            Appropriate exception based on status code and error details
        """
        try:
            error_data = response.json()
            error = error_data.get("error", {})
            code = error.get("code")
            message = error.get("message", "Unknown error")
            details = error.get("details")
        except Exception:
            message = response.text or f"HTTP {response.status_code}"
            code = None
            details = None

        if response.status_code == 400:
            raise ValidationError(message, code, details)
        elif response.status_code == 401:
            raise AuthenticationError(message, code, details)
        elif response.status_code == 403:
            if code == "forbidden_feature":
                raise ForbiddenFeatureError(message, code, details)
            elif code == "limit_exceeded" or code == "invalid_resolution":
                requested = details.get("requested") if details else None
                max_allowed = details.get("max_allowed") if details else None
                raise LimitExceededError(message, requested, max_allowed, code, details)
            else:
                raise ApiError(message, code, details)
        elif response.status_code == 404:
            if "job" in message.lower():
                raise JobNotFoundError(message, code, details)
            raise ApiError(message, code, details)
        elif response.status_code == 408 or response.status_code == 504:
            raise TimeoutError(message, code=code)
        elif response.status_code >= 500:
            raise ApiError(f"Server error: {message}", code, details)
        else:
            raise ApiError(message, code, details)

    def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, DELETE)
            path: API path
            **kwargs: Additional arguments for httpx

        Returns:
            HTTP response

        Raises:
            Various exceptions based on response status
        """
        last_exception: SiteCalcError | None = None

        for attempt in range(self.max_retries):
            try:
                response = self._client.request(method, path, **kwargs)

                if response.status_code < 400:
                    return response

                # Don't retry client errors (4xx) except timeouts
                if 400 <= response.status_code < 500 and response.status_code not in [408, 429]:
                    self._handle_error(response)

                # Retry server errors (5xx) and specific client errors
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff
                    time.sleep(wait_time)
                    continue

                self._handle_error(response)

            except httpx.TimeoutException:
                last_exception = TimeoutError(f"Request timeout after {self.timeout}s", timeout=self.timeout)
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise last_exception
            except httpx.RequestError as e:
                last_exception = ApiError(f"Request failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise last_exception

        if last_exception:
            raise last_exception
        raise ApiError("Request failed after retries")

    def create_planning_job(self, request: InvestmentPlanningRequest) -> Job:
        """Create a long-term investment planning job.

        Args:
            request: Investment planning request

        Returns:
            Job object with job_id and initial status

        Raises:
            ValidationError: If request is invalid
            ForbiddenFeatureError: If using forbidden features (ANS)
            LimitExceededError: If exceeding client limits
            AuthenticationError: If API key is invalid

        Example:
            >>> request = InvestmentPlanningRequest(
            ...     sites=[site],
            ...     timespan=TimeSpan.for_years(2025, 10),
            ...     investment_parameters=inv_params
            ... )
            >>> job = client.create_planning_job(request)
            >>> print(f"Job ID: {job.job_id}")
        """
        payload = request.model_dump_for_api()

        response = self._request_with_retry(
            "POST",
            "/api/v1/jobs/device-planning",
            json=payload,
        )

        return Job(**response.json())

    def get_job_status(self, job_id: str) -> Job:
        """Get current job status.

        Args:
            job_id: Job identifier

        Returns:
            Job object with current status

        Raises:
            JobNotFoundError: If job doesn't exist

        Example:
            >>> job = client.get_job_status(job_id)
            >>> print(f"Status: {job.status}, Progress: {job.progress}%")
        """
        response = self._request_with_retry(
            "GET",
            f"/api/v1/jobs/{job_id}",
        )

        return Job(**response.json())

    def get_job_result(self, job_id: str) -> InvestmentPlanningResponse:
        """Get job result (must be completed).

        Args:
            job_id: Job identifier

        Returns:
            Complete optimization result

        Raises:
            JobNotFoundError: If job doesn't exist
            ApiError: If job is not completed

        Example:
            >>> result = client.get_job_result(job_id)
            >>> print(f"NPV: €{result.investment_metrics.npv:,.0f}")
        """
        response = self._request_with_retry(
            "GET",
            f"/api/v1/jobs/{job_id}/result",
        )

        data = response.json()

        # Extract result from wrapper and flatten
        result_data = {
            "job_id": str(data.get("job_id")),
            "status": data.get("status"),
            **data.get("result", {}),
        }

        return InvestmentPlanningResponse(**result_data)

    def cancel_job(self, job_id: str) -> Job:
        """Cancel a running job.

        Args:
            job_id: Job identifier

        Returns:
            Job object with cancelled status

        Raises:
            JobNotFoundError: If job doesn't exist
            ApiError: If job cannot be cancelled (already completed)

        Example:
            >>> cancelled = client.cancel_job(job_id)
            >>> print(f"Status: {cancelled.status}")
        """
        response = self._request_with_retry(
            "DELETE",
            f"/api/v1/jobs/{job_id}",
        )

        return Job(**response.json())

    def cancel_all_jobs(self) -> dict[str, object]:
        """Cancel all pending or running jobs.

        Cancels all jobs that are currently pending or running for the
        authenticated user. Useful for cleanup when shutting down or
        when jobs are no longer needed.

        Returns:
            Dictionary with:
                - cancelled_count: Number of jobs cancelled
                - cancelled_jobs: List of cancelled job IDs
                - message: Status message

        Raises:
            AuthenticationError: If API key is invalid

        Example:
            >>> result = client.cancel_all_jobs()
            >>> print(f"Cancelled {result['cancelled_count']} jobs")
        """
        response = self._request_with_retry(
            "DELETE",
            "/api/v1/jobs",
        )

        result: dict[str, object] = response.json()
        return result

    def wait_for_completion(
        self,
        job_id: str,
        poll_interval: float = 30,
        timeout: Optional[float] = 7200,
    ) -> InvestmentPlanningResponse:
        """Wait for job to complete and return result.

        Polls the job status at regular intervals until completion or timeout.

        Args:
            job_id: Job identifier
            poll_interval: Seconds between status checks (default: 30s)
            timeout: Maximum wait time in seconds (default: 2 hours, None=unlimited)

        Returns:
            Complete optimization result

        Raises:
            TimeoutError: If timeout is exceeded
            JobNotFoundError: If job doesn't exist
            OptimizationError: If job fails

        Example:
            >>> result = client.wait_for_completion(
            ...     job_id,
            ...     poll_interval=30,
            ...     timeout=7200
            ... )
            >>> print(f"Solved in {result.summary.solve_time_seconds:.1f}s")
        """
        start_time = time.time()

        while True:
            job = self.get_job_status(job_id)

            if job.status == "completed":
                return self.get_job_result(job_id)
            elif job.status == "failed":
                error_msg: str = str(job.error.get("message", "Unknown error")) if job.error else "Unknown error"
                error_code = job.error.get("code") if job.error else None
                error_details = job.error.get("details") if job.error else None
                raise OptimizationError(error_msg, error_code, error_details)
            elif job.status == "cancelled":
                raise ApiError("Job was cancelled")

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"Job did not complete within {timeout}s", timeout=timeout)

            # Wait before next poll
            time.sleep(poll_interval)
