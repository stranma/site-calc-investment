"""Fail closed on named-zone submission while keeping legacy reads available."""

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, Mock, patch
from zoneinfo import ZoneInfo

import httpx
import pytest

from site_calc_investment import ForbiddenFeatureError, InvestmentClient, __version__
from site_calc_investment.models import InvestmentPlanningRequest, Site, TimeSpanInvestment

API_VERSION = ".".join(__version__.split(".")[:2])


@pytest.fixture(autouse=True)
def mock_server_health() -> None:
    """Disable the shared health mock: test actual HTTP routing and call counts."""


@pytest.fixture
def planning_request(simple_site: Site) -> InvestmentPlanningRequest:
    return InvestmentPlanningRequest(
        sites=[simple_site],
        timespan=TimeSpanInvestment(start=datetime(2026, 1, 1, tzinfo=ZoneInfo("Europe/Prague")), intervals=24),
    )


def install_transport(client: InvestmentClient, health: object, calls: list[httpx.Request]) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/health":
            if isinstance(health, Exception):
                raise health
            if isinstance(health, httpx.Response):
                return health
            return httpx.Response(200, json=health)
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "new", "status": "pending"})
        if request.url.path.endswith("/result"):
            return httpx.Response(
                200,
                json={
                    "job_id": "old",
                    "status": "completed",
                    "result": {"sites": {}, "summary": {"solver_status": "optimal", "solve_time_seconds": 0}},
                },
            )
        return httpx.Response(200, json={"job_id": "old", "status": "running"})

    client._client.close()
    client._client = httpx.Client(base_url=client.base_url, transport=httpx.MockTransport(handle))


@pytest.mark.parametrize(
    "health",
    [
        {"api_version": API_VERSION},
        {"features": []},
        {"features": ["other"]},
        {"features": None},
        {"features": "planning_timezone"},
        {"features": {"planning_timezone": True}},
        {"features": ["planning_timezone", None]},
        {"supported_features": ["planning_timezone"]},
        None,
        [],
        httpx.Response(503, json={"features": ["planning_timezone"]}),
        httpx.Response(200, text="not json"),
        httpx.ConnectError("health unavailable"),
    ],
)
def test_missing_or_unavailable_capability_blocks_post_and_allows_reads(
    health: object, planning_request: InvestmentPlanningRequest
) -> None:
    calls: list[httpx.Request] = []
    with InvestmentClient("https://api.example.com", "inv_test") as client:
        install_transport(client, health, calls)
        for _ in range(2):
            with pytest.raises(ForbiddenFeatureError, match="No job submitted.*planning_timezone") as caught:
                client.create_planning_job(planning_request)
            assert caught.value.code == "planning_timezone_unsupported"
            assert "new InvestmentClient" in str(caught.value)
        assert [(call.method, call.url.path) for call in calls] == [("GET", "/health")]
        assert client.get_job_status("old").status == "running"
        assert client.get_job_result("old").timespan is None
    assert all(call.method == "GET" for call in calls)
    assert sum(call.url.path == "/health" for call in calls) == 1


@pytest.mark.parametrize("read_first", [False, True])
def test_positive_capability_is_cached_and_named_zone_sent(
    planning_request: InvestmentPlanningRequest, read_first: bool
) -> None:
    import json

    calls: list[httpx.Request] = []
    with InvestmentClient("https://api.example.com", "inv_test") as client:
        install_transport(client, {"api_version": API_VERSION, "features": ["planning_timezone"]}, calls)
        if read_first:
            client.get_job_status("old")
        for _ in range(2):
            assert client.create_planning_job(planning_request).status == "pending"
    assert sum(call.url.path == "/health" for call in calls) == 1
    posts = [call for call in calls if call.method == "POST"]
    assert len(posts) == 2
    assert all(json.loads(call.content)["timespan"]["timezone"] == "Europe/Prague" for call in posts)
    assert calls[0].url.path == "/health"


@pytest.mark.parametrize("health", [MagicMock(), {"features": MagicMock()}, {"features": [MagicMock()]}])
def test_mock_truthiness_cannot_grant_capability(health: Any, planning_request: InvestmentPlanningRequest) -> None:
    with InvestmentClient("https://api.example.com", "inv_test") as client:
        with patch.object(client._client, "get", return_value=Mock(status_code=200, json=Mock(return_value=health))):
            with patch.object(client._client, "request") as send:
                with pytest.raises(ForbiddenFeatureError):
                    client.create_planning_job(planning_request)
                send.assert_not_called()


def test_version_warning_preserved_and_does_not_replace_feature_gate(
    planning_request: InvestmentPlanningRequest,
) -> None:
    calls: list[httpx.Request] = []
    with InvestmentClient("https://api.example.com", "inv_test") as client:
        install_transport(client, {"api_version": "0.0", "features": ["planning_timezone"]}, calls)
        with pytest.warns(UserWarning, match="may not be compatible"):
            assert client.create_planning_job(planning_request).status == "pending"
    assert [call.method for call in calls] == ["GET", "POST"]


@pytest.mark.parametrize("supported", [False, True])
def test_mcp_submission_uses_same_capability_gate(monkeypatch: pytest.MonkeyPatch, supported: bool) -> None:
    from site_calc_investment.mcp import server
    from site_calc_investment.mcp.scenario import ScenarioStore

    store = ScenarioStore()
    sid = store.create(name="Capability gate")
    store.set_timespan(sid, start_year=2026, intervals=1)
    store.add_device(sid, "electricity_import", "Grid", {"price": 50.0, "max_import": 1.0})
    calls: list[httpx.Request] = []
    with InvestmentClient("https://api.example.com", "inv_test") as client:
        install_transport(client, {"features": ["planning_timezone"] if supported else []}, calls)
        monkeypatch.setattr(server, "_client", client)
        monkeypatch.setattr(server, "_store", store)
        if supported:
            assert server.submit_scenario(sid) == {"job_id": "new", "status": "pending"}
            assert store.get(sid).jobs == ["new"]
        else:
            with pytest.raises(ForbiddenFeatureError, match="No job submitted"):
                server.submit_scenario(sid)
            assert store.get(sid).jobs == []
    assert [call.method for call in calls] == (["GET", "POST"] if supported else ["GET"])
