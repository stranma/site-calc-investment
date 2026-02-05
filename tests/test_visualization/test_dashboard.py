"""Tests for dashboard assembly and HTML generation."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from site_calc_investment.models.responses import InvestmentPlanningResponse
from site_calc_investment.visualization._template import PLOTLY_CDN_URL
from site_calc_investment.visualization.dashboard import (
    _get_output_path,
    generate_dashboard,
)


class TestGenerateDashboard:
    """Tests for generate_dashboard()."""

    def test_creates_html_file(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        with patch("site_calc_investment.visualization.dashboard.webbrowser"):
            result = generate_dashboard("test_job_1", response_1year, open_browser=False, output_dir=str(tmp_path))

        file_path = result["file_path"]
        assert Path(file_path).exists()
        assert file_path.endswith(".html")

    def test_returns_file_path(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        result = generate_dashboard("test_job_1", response_1year, open_browser=False, output_dir=str(tmp_path))
        assert "file_path" in result
        assert "test_job_1" in result["file_path"]

    def test_returns_charts_generated(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        result = generate_dashboard("test_job_1", response_1year, open_browser=False, output_dir=str(tmp_path))
        assert "charts_generated" in result
        assert "kpi_cards" in result["charts_generated"]
        assert "energy_balance" in result["charts_generated"]

    def test_returns_summary_with_metrics(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        result = generate_dashboard("test_job_1", response_1year, open_browser=False, output_dir=str(tmp_path))
        summary = result["summary"]
        assert "npv" in summary
        assert "irr" in summary
        assert summary["npv"] == 850000.0

    def test_returns_message(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        result = generate_dashboard("test_job_1", response_1year, open_browser=False, output_dir=str(tmp_path))
        assert "message" in result
        assert "Dashboard saved" in result["message"]

    def test_includes_investment_charts(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        result = generate_dashboard("test_job_1", response_1year, open_browser=False, output_dir=str(tmp_path))
        assert "annual_revenue_costs" in result["charts_generated"]
        assert "cumulative_cash_flow" in result["charts_generated"]

    def test_no_investment_charts_without_metrics(
        self, response_no_investment: InvestmentPlanningResponse, tmp_path: Path
    ) -> None:
        result = generate_dashboard("test_job_2", response_no_investment, open_browser=False, output_dir=str(tmp_path))
        assert "annual_revenue_costs" not in result["charts_generated"]
        assert "cumulative_cash_flow" not in result["charts_generated"]

    def test_summary_profit_only_without_metrics(
        self, response_no_investment: InvestmentPlanningResponse, tmp_path: Path
    ) -> None:
        result = generate_dashboard("test_job_2", response_no_investment, open_browser=False, output_dir=str(tmp_path))
        summary = result["summary"]
        assert "npv" not in summary
        assert "expected_profit" in summary

    def test_includes_drill_down(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        result = generate_dashboard("test_job_1", response_1year, open_browser=False, output_dir=str(tmp_path))
        assert "device_drill_down" in result["charts_generated"]


class TestHtmlContent:
    """Tests for the generated HTML content."""

    def _get_html(self, response: InvestmentPlanningResponse, tmp_path: Path) -> str:
        result = generate_dashboard("test_html", response, open_browser=False, output_dir=str(tmp_path))
        return Path(result["file_path"]).read_text(encoding="utf-8")

    def test_contains_plotly_cdn_script(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        html = self._get_html(response_1year, tmp_path)
        assert PLOTLY_CDN_URL in html

    def test_contains_three_tab_divs(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        html = self._get_html(response_1year, tmp_path)
        assert 'id="tab-financial"' in html
        assert 'id="tab-energy"' in html
        assert 'id="tab-device-detail"' in html

    def test_contains_valid_json_in_script(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        html = self._get_html(response_1year, tmp_path)
        # Find the annual revenue JSON assignment
        marker = "var annualRevenueData = "
        idx = html.index(marker)
        start = idx + len(marker)
        # Find the semicolon at end of assignment
        end = html.index(";", start)
        json_str = html[start:end]
        parsed = json.loads(json_str)
        assert "traces" in parsed
        assert "layout" in parsed

    def test_kpi_values_in_html(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        html = self._get_html(response_1year, tmp_path)
        assert "850,000" in html  # NPV
        assert "15.0%" in html  # IRR
        assert "4.5 years" in html  # Payback

    def test_energy_kpi_values_in_html(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        html = self._get_html(response_1year, tmp_path)
        assert "Total Generation" in html
        assert "Total Consumption" in html
        assert "Net Grid Position" in html

    def test_job_id_in_html(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        html = self._get_html(response_1year, tmp_path)
        assert "test_html" in html


class TestBrowserOpening:
    """Tests for browser opening behavior."""

    def test_open_browser_false_does_not_call(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        with patch("site_calc_investment.visualization.dashboard.webbrowser") as mock_wb:
            generate_dashboard("test_job", response_1year, open_browser=False, output_dir=str(tmp_path))
            mock_wb.open.assert_not_called()

    def test_open_browser_true_calls(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        with patch("site_calc_investment.visualization.dashboard.webbrowser") as mock_wb:
            generate_dashboard("test_job", response_1year, open_browser=True, output_dir=str(tmp_path))
            mock_wb.open.assert_called_once()


class TestOutputPath:
    """Tests for _get_output_path()."""

    def test_with_output_dir(self, tmp_path: Path) -> None:
        path = _get_output_path("job123", output_dir=str(tmp_path))
        assert path.parent == tmp_path
        assert "job123" in path.name
        assert path.suffix == ".html"

    def test_filename_includes_job_id(self) -> None:
        path = _get_output_path("my_job_id", output_dir="/tmp/test")
        assert "my_job_id" in path.name

    def test_filename_includes_timestamp(self) -> None:
        path = _get_output_path("job123", output_dir="/tmp/test")
        # Timestamp format: YYYYMMDD_HHMMSS
        name = path.name
        assert "dashboard_job123_" in name
        # After job_id_ there should be a timestamp
        parts = name.replace("dashboard_job123_", "").replace(".html", "")
        assert len(parts) == 15  # YYYYMMDD_HHMMSS

    def test_with_investment_data_dir_env(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"INVESTMENT_DATA_DIR": str(tmp_path)}):
            path = _get_output_path("job123")
        assert "dashboards" in str(path)
        assert tmp_path in path.parents or path.parent.parent == tmp_path

    def test_without_env_uses_cwd(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            # Remove INVESTMENT_DATA_DIR if set
            os.environ.pop("INVESTMENT_DATA_DIR", None)
            path = _get_output_path("job123")
        assert "dashboards" in str(path)

    def test_sanitizes_path_traversal_in_job_id(self) -> None:
        path = _get_output_path("../../etc/passwd", output_dir="/tmp/test")
        assert ".." not in path.name
        # Path separators should be stripped
        assert path.parent == Path("/tmp/test")

    def test_sanitizes_special_chars_in_job_id(self) -> None:
        path = _get_output_path("job<script>alert(1)</script>", output_dir="/tmp/test")
        assert "<" not in path.name
        assert ">" not in path.name


class TestJsonSafety:
    """Tests for JSON embedding safety."""

    def test_script_tag_escaped_in_html(self, response_1year: InvestmentPlanningResponse, tmp_path: Path) -> None:
        result = generate_dashboard("test_xss", response_1year, open_browser=False, output_dir=str(tmp_path))
        html = Path(result["file_path"]).read_text(encoding="utf-8")
        # The embedded JSON should not contain raw < or > that could break script tags
        # Find a JSON block and verify it doesn't have raw angle brackets
        marker = "var energyBalanceData = "
        idx = html.index(marker)
        start = idx + len(marker)
        end = html.index(";", start)
        json_str = html[start:end]
        assert "</script>" not in json_str
