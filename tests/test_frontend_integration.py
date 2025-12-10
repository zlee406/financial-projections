"""
Integration tests that simulate the complete frontend-to-backend round trip.

These tests construct inputs exactly as the UI (ui/analysis.py) would,
pass them through the simulation bridge, and verify the results are correct.

This catches issues where:
- Required parameters are missing from the frontend
- Default values are silently injected
- The contract between frontend and backend is broken
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime


from logic import simulation_bridge


def create_flat_market_data(years: int = 5) -> pd.DataFrame:
    """Create market data with 0% returns for predictable testing."""
    months = years * 12
    dates = pd.date_range(start='2020-01-01', periods=months, freq='ME')
    return pd.DataFrame({'Close': [100.0] * months}, index=dates)


def create_simple_growth_market_data(years: int = 5, annual_return: float = 0.10) -> pd.DataFrame:
    """Create market data with consistent growth for predictable testing."""
    months = years * 12
    monthly_return = (1 + annual_return) ** (1/12) - 1
    dates = pd.date_range(start='2020-01-01', periods=months, freq='ME')
    prices = [100.0]
    for _ in range(months - 1):
        prices.append(prices[-1] * (1 + monthly_return))
    return pd.DataFrame({'Close': prices}, index=dates)


def build_minimal_spending_inputs() -> dict:
    """
    Build spending inputs with minimal configuration.
    This mirrors what the frontend would construct.
    """
    return {
        "base_monthly_spend": 5000.0,  # $60k/year
        "location": "California",
        "children": [],
        "child_profiles": {},
        "has_mortgage": False,
        "mortgage": None,
        "housing_projects": [],
        "spending_items": []
    }


def build_complete_portfolio_inputs(
    liquid_assets: float = 1_000_000.0,
    retirement_assets: float = 0.0,
    current_age: int = 50,
    death_age: int = 55,
    strategy_type: str = "Constant Dollar (Targets Schedule)",
    min_spend: float = 0.0,
    max_spend: float = 999999999.0,
    stock_alloc_pct: float = 100.0,
    bond_return_pct: float = 0.0,
    inflation_rate: float = 0.0,
    allow_early_retirement_access: bool = True,
    early_withdrawal_penalty_rate: float = 0.10,
    retirement_access_age: int = 60,
) -> dict:
    """
    Build portfolio inputs with ALL required fields explicitly set.
    This mirrors what the frontend (ui/analysis.py) constructs.
    
    All fields are explicitly set - no defaults should be applied by backend.
    """
    return {
        # Portfolio assets
        "liquid_assets": liquid_assets,
        "retirement_assets": retirement_assets,
        
        # Asset allocation
        "stock_alloc_pct": stock_alloc_pct,
        "bond_return_pct": bond_return_pct,
        "inflation_rate": inflation_rate,
        
        # Private stock (none for simple tests)
        "private_shares": 0,
        "private_ipo_price": 0,
        "private_ipo_year": None,
        "diversification_start_year": None,
        "diversification_duration": None,
        "private_growth_multiplier": 1.0,
        
        # Income streams
        "income_streams": [],
        
        # Timeline
        "current_age": current_age,
        "death_age": death_age,
        
        # Withdrawal strategy
        "strategy_type": strategy_type,
        "min_spend": min_spend,
        "max_spend": max_spend,
        "strategy_pct": 4.0,
        "gk_init_rate": 4.5,
        
        # Flexible spending
        "flexible_spending": False,
        "flexible_floor_pct": 0.75,
        
        # Early retirement access
        "allow_early_retirement_access": allow_early_retirement_access,
        "early_withdrawal_penalty_rate": early_withdrawal_penalty_rate,
        "retirement_access_age": retirement_access_age
    }


class TestFrontendIntegrationBasic(unittest.TestCase):
    """Basic integration tests with simple, predictable inputs."""
    
    def test_should_complete_simulation_given_minimal_inputs(self):
        """
        Verify that the simulation completes successfully with minimal valid inputs.
        This catches missing required parameters.
        """
        # Preconditions: Build inputs exactly as frontend would
        spending_inputs = build_minimal_spending_inputs()
        portfolio_inputs = build_complete_portfolio_inputs(
            liquid_assets=1_000_000.0,
            current_age=50,
            death_age=52  # Short 2-year simulation
        )
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, schedule_df = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions
        self.assertIsNotNone(result)
        self.assertIsNotNone(stats)
        self.assertIsNotNone(schedule_df)
        self.assertIn("success_rate", stats)
        self.assertFalse(result.balances.empty)
    
    def test_should_have_100pct_success_given_wealthy_portfolio_flat_market(self):
        """
        With a wealthy portfolio and flat market, success should be 100%.
        """
        # Preconditions
        spending_inputs = build_minimal_spending_inputs()  # $60k/year
        portfolio_inputs = build_complete_portfolio_inputs(
            liquid_assets=10_000_000.0,  # $10M - very wealthy
            current_age=50,
            death_age=52,  # 2 years = ~$120k needed
            stock_alloc_pct=100.0,
            bond_return_pct=0.0,
            inflation_rate=0.0
        )
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, _ = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions
        self.assertEqual(stats["success_rate"], 1.0, 
                        "100% success expected with wealthy portfolio")
        self.assertGreater(stats["median_end_value"], 9_500_000,
                          "Should have most of portfolio remaining")


class TestFrontendIntegrationWithdrawals(unittest.TestCase):
    """Tests that verify withdrawal amounts are calculated correctly."""
    
    def test_should_withdraw_scheduled_amount_given_constant_dollar_strategy(self):
        """
        Constant Dollar strategy should withdraw according to spending schedule.
        With 0% inflation, withdrawals should stay constant.
        """
        # Preconditions
        spending_inputs = build_minimal_spending_inputs()  # $60k/year
        portfolio_inputs = build_complete_portfolio_inputs(
            liquid_assets=1_000_000.0,
            current_age=50,
            death_age=53,  # 3 years
            strategy_type="Constant Dollar (Targets Schedule)",
            inflation_rate=0.0  # No inflation - withdrawals stay constant
        )
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, schedule_df = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions
        # Should have 3 years of withdrawals
        self.assertEqual(result.withdrawals.shape[1], 3)
        
        # First simulation path's first year withdrawal should be ~$60k
        first_withdrawal = result.withdrawals.iloc[0, 0]
        self.assertAlmostEqual(first_withdrawal, 60000, delta=100,
                              msg="Year 0 withdrawal should be ~$60k (12 * $5k)")
        
        # With 0% inflation, all years should be similar
        year_1 = result.withdrawals.iloc[0, 1]
        self.assertAlmostEqual(year_1, 60000, delta=100,
                              msg="Year 1 should also be ~$60k with 0% inflation")
    
    def test_should_apply_inflation_given_nonzero_rate(self):
        """
        Withdrawals should increase with inflation each year.
        """
        # Preconditions
        inflation_rate = 0.03  # 3% inflation
        spending_inputs = build_minimal_spending_inputs()  # $60k/year base
        portfolio_inputs = build_complete_portfolio_inputs(
            liquid_assets=5_000_000.0,
            current_age=50,
            death_age=53,  # 3 years
            strategy_type="Constant Dollar (Targets Schedule)",
            inflation_rate=inflation_rate
        )
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, _ = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions
        year_0 = result.withdrawals.iloc[0, 0]
        year_1 = result.withdrawals.iloc[0, 1]
        year_2 = result.withdrawals.iloc[0, 2]
        
        # Year 1 should be ~3% higher than Year 0
        expected_year_1 = year_0 * (1 + inflation_rate)
        self.assertAlmostEqual(year_1, expected_year_1, delta=100,
                              msg="Year 1 should be inflated by 3%")
        
        # Year 2 should be ~6.09% higher than Year 0 (compounded)
        expected_year_2 = year_0 * (1 + inflation_rate) ** 2
        self.assertAlmostEqual(year_2, expected_year_2, delta=100,
                              msg="Year 2 should be inflated by ~6%")


class TestFrontendIntegrationPortfolioBalance(unittest.TestCase):
    """Tests that verify portfolio balance tracking is correct."""
    
    def test_should_track_correct_ending_balance_given_known_withdrawals(self):
        """
        With flat market and known withdrawals, ending balance should be predictable.
        """
        # Preconditions
        initial_assets = 500_000.0
        annual_spend = 60000.0  # $5k/month
        years = 2
        
        spending_inputs = build_minimal_spending_inputs()  # $60k/year
        portfolio_inputs = build_complete_portfolio_inputs(
            liquid_assets=initial_assets,
            current_age=50,
            death_age=50 + years,
            inflation_rate=0.0
        )
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, _ = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions
        # With flat market and no taxes (only liquid assets), 
        # ending balance should be approximately: initial - (annual_spend * years)
        # But we need to account for taxes on capital gains
        
        # At minimum, check the general magnitude
        expected_min = initial_assets - (annual_spend * years * 1.5)  # Allow for taxes
        expected_max = initial_assets - (annual_spend * years * 0.8)  # No taxes
        
        final_balance = result.balances.iloc[0, -1]
        self.assertGreater(final_balance, expected_min,
                          msg=f"Final balance {final_balance} should be > {expected_min}")
        self.assertLess(final_balance, expected_max,
                       msg=f"Final balance {final_balance} should be < {expected_max}")


class TestFrontendIntegrationStrategies(unittest.TestCase):
    """Tests for different withdrawal strategies."""
    
    def test_should_use_percent_of_portfolio_given_strategy_type(self):
        """
        Percent of Portfolio strategy should withdraw % of current value.
        """
        # Preconditions
        initial_assets = 1_000_000.0
        withdrawal_pct = 4.0
        
        spending_inputs = build_minimal_spending_inputs()
        portfolio_inputs = build_complete_portfolio_inputs(
            liquid_assets=initial_assets,
            current_age=50,
            death_age=52,
            strategy_type="Percent of Portfolio",
            min_spend=0.0,
            max_spend=999999999.0
        )
        portfolio_inputs["strategy_pct"] = withdrawal_pct
        
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, _ = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions
        # First year withdrawal should be ~4% of $1M = $40k
        # But may be floored by spending schedule
        first_withdrawal = result.withdrawals.iloc[0, 0]
        
        # The strategy should have calculated based on portfolio value
        # (actual may be higher due to schedule floor)
        self.assertGreaterEqual(first_withdrawal, initial_assets * (withdrawal_pct / 100) - 1000)
    
    def test_should_respect_min_spend_floor(self):
        """
        Withdrawal strategies should not go below min_spend floor.
        """
        # Preconditions - Percent of Portfolio with very low %
        initial_assets = 1_000_000.0
        min_spend = 50000.0
        
        spending_inputs = {
            "base_monthly_spend": 1000.0,  # Only $12k/year scheduled
            "location": "California",
            "children": [],
            "child_profiles": {},
            "has_mortgage": False,
            "mortgage": None,
            "housing_projects": [],
            "spending_items": []
        }
        portfolio_inputs = build_complete_portfolio_inputs(
            liquid_assets=initial_assets,
            current_age=50,
            death_age=52,
            strategy_type="Percent of Portfolio",
            min_spend=min_spend,  # $50k floor
            max_spend=999999999.0
        )
        portfolio_inputs["strategy_pct"] = 1.0  # Only 1% = $10k, below floor
        
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, _ = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions - should withdraw at least min_spend
        first_withdrawal = result.withdrawals.iloc[0, 0]
        self.assertGreaterEqual(first_withdrawal, min_spend,
                               msg=f"Withdrawal {first_withdrawal} should be >= min_spend {min_spend}")


class TestFrontendIntegration401k(unittest.TestCase):
    """Tests for 401k/retirement account behavior."""
    
    def test_should_access_401k_early_with_penalty_when_enabled(self):
        """
        When early 401k access is enabled and liquid is depleted,
        should access retirement with penalty and not fail.
        """
        # Preconditions - only 401k, high spending
        spending_inputs = build_minimal_spending_inputs()  # $60k/year
        portfolio_inputs = build_complete_portfolio_inputs(
            liquid_assets=50000.0,  # Only $50k liquid
            retirement_assets=500000.0,  # But $500k in 401k
            current_age=50,  # Under retirement age
            death_age=52,
            allow_early_retirement_access=True,
            early_withdrawal_penalty_rate=0.10,
            retirement_access_age=60
        )
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, _ = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions - should succeed since early access is allowed
        self.assertEqual(stats["success_rate"], 1.0,
                        "Should succeed with 401k early access enabled")
        self.assertGreater(stats["median_end_value"], 0,
                          "Should have positive ending balance")
    
    def test_should_fail_when_early_access_disabled_and_liquid_depleted(self):
        """
        When early 401k access is disabled and liquid runs out before age 60,
        the simulation should fail (0% success or 0 ending balance).
        """
        # Preconditions - only 401k, high spending, early access DISABLED
        spending_inputs = build_minimal_spending_inputs()  # $60k/year
        portfolio_inputs = build_complete_portfolio_inputs(
            liquid_assets=30000.0,  # Only $30k liquid - not enough for 1 year
            retirement_assets=500000.0,  # Plenty in 401k but can't access
            current_age=50,  # Under retirement age
            death_age=52,
            allow_early_retirement_access=False,  # DISABLED
            retirement_access_age=60
        )
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, _ = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions - should fail since liquid runs out
        # Either 0% success rate or 0 ending balance
        final_balance = result.balances.iloc[0, -1]
        self.assertEqual(final_balance, 0.0,
                        "Should fail (0 balance) when liquid depleted and early access disabled")


class TestFrontendIntegrationSchedule(unittest.TestCase):
    """Tests that verify spending schedule generation."""
    
    def test_should_generate_schedule_matching_base_spend(self):
        """
        The spending schedule should reflect the base monthly spend.
        """
        # Preconditions
        base_monthly = 5000.0  # $5k/month = $60k/year
        
        spending_inputs = {
            "base_monthly_spend": base_monthly,
            "location": "California",
            "children": [],
            "child_profiles": {},
            "has_mortgage": False,
            "mortgage": None,
            "housing_projects": [],
            "spending_items": []
        }
        portfolio_inputs = build_complete_portfolio_inputs(
            current_age=50,
            death_age=53
        )
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, schedule_df = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions
        # Schedule should have the base spend
        self.assertIn("Base_Real", schedule_df.columns)
        self.assertAlmostEqual(
            schedule_df["Base_Real"].iloc[0],
            base_monthly * 12,
            delta=1,
            msg="Schedule should reflect $60k annual base spend"
        )
    
    def test_should_include_spending_items_in_schedule(self):
        """
        Additional spending items should be reflected in the schedule.
        """
        # Preconditions
        spending_inputs = {
            "base_monthly_spend": 5000.0,  # $60k/year base
            "location": "California",
            "children": [],
            "child_profiles": {},
            "has_mortgage": False,
            "mortgage": None,
            "housing_projects": [],
            "spending_items": [
                {
                    "name": "Health Insurance",
                    "monthly_amount": 1000.0,  # $12k/year additional
                    "start_year": None,
                    "end_year": None
                }
            ]
        }
        portfolio_inputs = build_complete_portfolio_inputs(
            current_age=50,
            death_age=53
        )
        df_market = create_flat_market_data(years=5)
        
        # Under test
        result, stats, schedule_df = simulation_bridge.run_simulation_wrapper(
            spending_inputs, portfolio_inputs, df_market
        )
        
        # Postconditions
        # Total required spend should be base + items = $72k
        total_required = schedule_df["Required_Real_Spend"].iloc[0]
        expected = (5000 + 1000) * 12  # $72k
        self.assertAlmostEqual(total_required, expected, delta=100,
                              msg="Schedule should include spending items")


if __name__ == '__main__':
    unittest.main()

