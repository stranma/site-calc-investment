"""Tests for scenario comparison utilities."""

import pytest
from io import StringIO
import sys

from site_calc_investment.analysis.comparison import compare_scenarios, print_comparison
from site_calc_investment.models.responses import InvestmentPlanningResponse


class TestCompareScenarios:
    """Tests for compare_scenarios function."""

    def test_compare_scenarios_basic(self, mock_job_completed_response):
        """Test basic scenario comparison with 2 scenarios."""
        # Create two mock results with different NPVs
        result1_data = mock_job_completed_response.copy()
        result1 = InvestmentPlanningResponse(**result1_data)

        result2_data = mock_job_completed_response.copy()
        result2_data["summary"]["investment_metrics"]["npv"] = 1500000.0
        result2_data["summary"]["investment_metrics"]["irr"] = 0.14
        result2 = InvestmentPlanningResponse(**result2_data)

        comparison = compare_scenarios([result1, result2], names=["Scenario A", "Scenario B"])

        # Check structure
        assert len(comparison["names"]) == 2
        assert comparison["names"] == ["Scenario A", "Scenario B"]

        # Check NPV values
        assert comparison["npv"][0] == 1250000.0
        assert comparison["npv"][1] == 1500000.0

        # Check IRR values
        assert comparison["irr"][0] == 0.12
        assert comparison["irr"][1] == 0.14

    def test_compare_scenarios_default_names(self, mock_job_completed_response):
        """Test scenario comparison with default names."""
        result1 = InvestmentPlanningResponse(**mock_job_completed_response)
        result2 = InvestmentPlanningResponse(**mock_job_completed_response)
        result3 = InvestmentPlanningResponse(**mock_job_completed_response)

        comparison = compare_scenarios([result1, result2, result3])

        assert comparison["names"] == ["Scenario 1", "Scenario 2", "Scenario 3"]

    def test_compare_scenarios_custom_names(self, mock_job_completed_response):
        """Test scenario comparison with custom names."""
        result1 = InvestmentPlanningResponse(**mock_job_completed_response)
        result2 = InvestmentPlanningResponse(**mock_job_completed_response)

        comparison = compare_scenarios(
            [result1, result2],
            names=["10 MW Battery", "20 MW Battery"]
        )

        assert comparison["names"] == ["10 MW Battery", "20 MW Battery"]

    def test_compare_scenarios_no_scenarios(self):
        """Test error when no scenarios provided."""
        with pytest.raises(ValueError, match="At least one scenario is required"):
            compare_scenarios([])

    def test_compare_scenarios_mismatched_names(self, mock_job_completed_response):
        """Test error when number of names doesn't match scenarios."""
        result1 = InvestmentPlanningResponse(**mock_job_completed_response)
        result2 = InvestmentPlanningResponse(**mock_job_completed_response)

        with pytest.raises(ValueError, match="Number of names"):
            compare_scenarios([result1, result2], names=["Only One Name"])

    def test_compare_scenarios_all_metrics(self, mock_job_completed_response):
        """Test that all metrics are extracted."""
        result = InvestmentPlanningResponse(**mock_job_completed_response)

        comparison = compare_scenarios([result])

        # Check all expected keys
        expected_keys = {
            "names", "total_revenue", "total_costs", "profit",
            "npv", "irr", "payback_years", "solve_time_seconds", "solver_status"
        }
        assert set(comparison.keys()) == expected_keys

        # Check all lists have same length
        for key, values in comparison.items():
            assert len(values) == 1, f"{key} should have 1 element"

    def test_compare_scenarios_investment_metrics(self, mock_job_completed_response):
        """Test investment metrics extraction."""
        result = InvestmentPlanningResponse(**mock_job_completed_response)

        comparison = compare_scenarios([result])

        # Investment metrics from mock
        assert comparison["npv"][0] == 1250000.0
        assert comparison["irr"][0] == 0.12
        assert comparison["payback_years"][0] == 6.2

    def test_compare_scenarios_revenue_and_costs(self, mock_job_completed_response):
        """Test revenue and cost extraction."""
        result = InvestmentPlanningResponse(**mock_job_completed_response)

        comparison = compare_scenarios([result])

        # From mock response
        inv_metrics = mock_job_completed_response["summary"]["investment_metrics"]
        assert comparison["total_revenue"][0] == inv_metrics["total_revenue_period"]
        assert comparison["total_costs"][0] == mock_job_completed_response["summary"]["total_cost"]
        assert comparison["profit"][0] == mock_job_completed_response["summary"]["expected_profit"]

    def test_compare_scenarios_solver_info(self, mock_job_completed_response):
        """Test solver information extraction."""
        result = InvestmentPlanningResponse(**mock_job_completed_response)

        comparison = compare_scenarios([result])

        assert comparison["solve_time_seconds"][0] == 127.3
        assert comparison["solver_status"][0] == "optimal"

    def test_compare_scenarios_none_metrics(self, mock_job_completed_response):
        """Test handling of None investment metrics."""
        # Create response without investment metrics
        result_data = mock_job_completed_response.copy()
        result_data["summary"]["investment_metrics"] = None
        result = InvestmentPlanningResponse(**result_data)

        comparison = compare_scenarios([result])

        # Should have None for investment metrics
        assert comparison["npv"][0] is None
        assert comparison["irr"][0] is None
        assert comparison["payback_years"][0] is None

        # Revenue should fall back to profit + cost
        expected_revenue = (
            mock_job_completed_response["summary"]["expected_profit"] +
            mock_job_completed_response["summary"]["total_cost"]
        )
        assert comparison["total_revenue"][0] == expected_revenue

    def test_compare_scenarios_multiple_varied(self, mock_job_completed_response):
        """Test comparison with multiple scenarios with varied metrics."""
        # Scenario 1: Low NPV
        result1_data = mock_job_completed_response.copy()
        result1_data["summary"]["investment_metrics"]["npv"] = 500000.0
        result1_data["summary"]["investment_metrics"]["irr"] = 0.08
        result1 = InvestmentPlanningResponse(**result1_data)

        # Scenario 2: Medium NPV
        result2_data = mock_job_completed_response.copy()
        result2_data["summary"]["investment_metrics"]["npv"] = 1250000.0
        result2_data["summary"]["investment_metrics"]["irr"] = 0.12
        result2 = InvestmentPlanningResponse(**result2_data)

        # Scenario 3: High NPV
        result3_data = mock_job_completed_response.copy()
        result3_data["summary"]["investment_metrics"]["npv"] = 2000000.0
        result3_data["summary"]["investment_metrics"]["irr"] = 0.16
        result3 = InvestmentPlanningResponse(**result3_data)

        comparison = compare_scenarios(
            [result1, result2, result3],
            names=["Small", "Medium", "Large"]
        )

        # Check NPV progression
        assert comparison["npv"][0] == 500000.0
        assert comparison["npv"][1] == 1250000.0
        assert comparison["npv"][2] == 2000000.0

        # Check IRR progression
        assert comparison["irr"][0] == 0.08
        assert comparison["irr"][1] == 0.12
        assert comparison["irr"][2] == 0.16


class TestPrintComparison:
    """Tests for print_comparison function."""

    def test_print_comparison_output(self, mock_job_completed_response, capsys):
        """Test print_comparison produces correct output."""
        result1 = InvestmentPlanningResponse(**mock_job_completed_response)
        result2_data = mock_job_completed_response.copy()
        result2_data["summary"]["investment_metrics"]["npv"] = 1500000.0
        result2 = InvestmentPlanningResponse(**result2_data)

        comparison = compare_scenarios([result1, result2], names=["Scenario A", "Scenario B"])
        print_comparison(comparison)

        captured = capsys.readouterr()
        output = captured.out

        # Check headers
        assert "SCENARIO COMPARISON" in output
        assert "=" * 80 in output

        # Check scenario names
        assert "Scenario A:" in output
        assert "Scenario B:" in output

        # Check metrics labels
        assert "Total Revenue:" in output
        assert "Total Costs:" in output
        assert "Profit:" in output
        assert "NPV:" in output
        assert "IRR:" in output
        assert "Payback:" in output
        assert "Solve Time:" in output
        assert "Solver Status:" in output

        # Check best scenario
        assert "Best Scenario (by NPV): Scenario B" in output

    def test_print_comparison_formatting(self, mock_job_completed_response, capsys):
        """Test print_comparison number formatting."""
        result = InvestmentPlanningResponse(**mock_job_completed_response)
        comparison = compare_scenarios([result])

        print_comparison(comparison)

        captured = capsys.readouterr()
        output = captured.out

        # Check currency formatting (should have commas)
        assert "€1,250,000" in output  # NPV

        # Check percentage formatting
        assert "12.00%" in output  # IRR

        # Check years formatting
        assert "6.2 years" in output  # Payback

        # Check time formatting
        assert "127.3s" in output  # Solve time

    def test_print_comparison_best_scenario(self, mock_job_completed_response, capsys):
        """Test best scenario identification."""
        # Create 3 scenarios with different NPVs
        result1_data = mock_job_completed_response.copy()
        result1_data["summary"]["investment_metrics"]["npv"] = 1000000.0
        result1 = InvestmentPlanningResponse(**result1_data)

        result2_data = mock_job_completed_response.copy()
        result2_data["summary"]["investment_metrics"]["npv"] = 2000000.0
        result2 = InvestmentPlanningResponse(**result2_data)

        result3_data = mock_job_completed_response.copy()
        result3_data["summary"]["investment_metrics"]["npv"] = 1500000.0
        result3 = InvestmentPlanningResponse(**result3_data)

        comparison = compare_scenarios(
            [result1, result2, result3],
            names=["Small", "Large", "Medium"]
        )
        print_comparison(comparison)

        captured = capsys.readouterr()
        output = captured.out

        # Best should be "Large" with NPV = 2,000,000
        assert "Best Scenario (by NPV): Large" in output
        assert "NPV: €2,000,000" in output

    def test_print_comparison_no_investment_metrics(self, mock_job_completed_response, capsys):
        """Test print_comparison with no investment metrics."""
        result_data = mock_job_completed_response.copy()
        result_data["summary"]["investment_metrics"] = None
        result = InvestmentPlanningResponse(**result_data)

        comparison = compare_scenarios([result])
        print_comparison(comparison)

        captured = capsys.readouterr()
        output = captured.out

        # Should still show basic metrics
        assert "Total Revenue:" in output
        assert "Total Costs:" in output
        assert "Profit:" in output

        # Investment metrics should NOT appear
        assert "NPV:" not in output
        assert "IRR:" not in output
        assert "Payback:" not in output

        # No best scenario section
        assert "Best Scenario (by NPV):" not in output

    def test_print_comparison_single_scenario(self, mock_job_completed_response, capsys):
        """Test print_comparison with single scenario."""
        result = InvestmentPlanningResponse(**mock_job_completed_response)
        comparison = compare_scenarios([result], names=["Only Scenario"])

        print_comparison(comparison)

        captured = capsys.readouterr()
        output = captured.out

        # Should show scenario
        assert "Only Scenario:" in output

        # Should show best scenario (even if only one)
        assert "Best Scenario (by NPV): Only Scenario" in output

    def test_print_comparison_mixed_none_metrics(self, mock_job_completed_response, capsys):
        """Test print_comparison with some None metrics."""
        # Scenario 1: Full metrics
        result1 = InvestmentPlanningResponse(**mock_job_completed_response)

        # Scenario 2: No investment metrics
        result2_data = mock_job_completed_response.copy()
        result2_data["summary"]["investment_metrics"] = None
        result2 = InvestmentPlanningResponse(**result2_data)

        comparison = compare_scenarios([result1, result2], names=["With Metrics", "Without Metrics"])
        print_comparison(comparison)

        captured = capsys.readouterr()
        output = captured.out

        # First scenario should show investment metrics
        lines = output.split("\n")
        with_metrics_idx = next(i for i, line in enumerate(lines) if "With Metrics:" in line)
        without_metrics_idx = next(i for i, line in enumerate(lines) if "Without Metrics:" in line)
        footer_idx = next(i for i, line in enumerate(lines[without_metrics_idx:]) if "Best Scenario" in line)

        # Extract sections (excluding footer)
        with_metrics_section = "\n".join(lines[with_metrics_idx:without_metrics_idx])
        without_metrics_section = "\n".join(lines[without_metrics_idx:without_metrics_idx + footer_idx])

        # First scenario should have NPV, IRR, Payback
        assert "NPV:" in with_metrics_section
        assert "IRR:" in with_metrics_section
        assert "Payback:" in with_metrics_section

        # Second scenario should NOT have them (in its own section, footer may have NPV)
        assert "NPV:" not in without_metrics_section
        assert "IRR:" not in without_metrics_section
        assert "Payback:" not in without_metrics_section


class TestComparisonIntegration:
    """Integration tests for scenario comparison workflow."""

    def test_full_comparison_workflow(self, mock_job_completed_response, capsys):
        """Test complete comparison workflow from results to output."""
        # Create 3 different battery sizes
        small_data = mock_job_completed_response.copy()
        small_data["summary"]["investment_metrics"]["npv"] = 800000.0
        small_data["summary"]["investment_metrics"]["irr"] = 0.10
        small_data["summary"]["investment_metrics"]["payback_period_years"] = 7.5
        small_data["summary"]["solve_time_seconds"] = 45.2
        small = InvestmentPlanningResponse(**small_data)

        medium_data = mock_job_completed_response.copy()
        medium_data["summary"]["investment_metrics"]["npv"] = 1250000.0
        medium_data["summary"]["investment_metrics"]["irr"] = 0.12
        medium_data["summary"]["investment_metrics"]["payback_period_years"] = 6.2
        medium_data["summary"]["solve_time_seconds"] = 127.3
        medium = InvestmentPlanningResponse(**medium_data)

        large_data = mock_job_completed_response.copy()
        large_data["summary"]["investment_metrics"]["npv"] = 1100000.0
        large_data["summary"]["investment_metrics"]["irr"] = 0.09
        large_data["summary"]["investment_metrics"]["payback_period_years"] = 8.1
        large_data["summary"]["solve_time_seconds"] = 234.7
        large = InvestmentPlanningResponse(**large_data)

        # Compare
        comparison = compare_scenarios(
            [small, medium, large],
            names=["10 MWh Battery", "20 MWh Battery", "30 MWh Battery"]
        )

        # Verify comparison data
        assert comparison["npv"] == [800000.0, 1250000.0, 1100000.0]
        assert comparison["irr"] == [0.10, 0.12, 0.09]

        # Print comparison
        print_comparison(comparison)

        captured = capsys.readouterr()
        output = captured.out

        # Check all scenarios listed
        assert "10 MWh Battery:" in output
        assert "20 MWh Battery:" in output
        assert "30 MWh Battery:" in output

        # Best should be medium (highest NPV)
        assert "Best Scenario (by NPV): 20 MWh Battery" in output
        assert "€1,250,000" in output

    def test_comparison_data_suitable_for_dataframe(self, mock_job_completed_response):
        """Test comparison dict can be converted to DataFrame."""
        result1 = InvestmentPlanningResponse(**mock_job_completed_response)
        result2 = InvestmentPlanningResponse(**mock_job_completed_response)

        comparison = compare_scenarios([result1, result2])

        # All lists should have same length
        lengths = [len(v) for v in comparison.values()]
        assert len(set(lengths)) == 1, "All lists should have same length"

        # Should have consistent structure for DataFrame
        assert all(isinstance(v, list) for v in comparison.values())

        # Test manual DataFrame-like usage
        for i in range(len(comparison["names"])):
            row = {key: comparison[key][i] for key in comparison.keys()}
            # Should be able to extract a row
            assert row["names"] == f"Scenario {i+1}"
            assert isinstance(row["npv"], (float, type(None)))
