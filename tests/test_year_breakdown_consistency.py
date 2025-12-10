"""
Test file to reproduce and diagnose the year-by-year breakdown inconsistency issue.

Problem Statement:
For a simulation starting in 1932 with Midrange IPO portfolio and Moderate Spending,
the year 0 breakdown shows:
- Net Change: -$924,711
- Required Spend: $102,600

The net change seems too large given the required spend. This test investigates
whether the year-by-year breakdown values are internally consistent.

Expected consistency checks:
1. Total Value (EOY) should equal Diversified Portfolio + Concentrated Stock
2. Net Change should equal sum of: Gains - Spending - Taxes + Income + IPO Proceeds
3. Gain calculations should accurately reflect market returns
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime

from logic.retirement import (
    BacktestEngine, ConstantDollarStrategy, PrivateStock, IncomeStream, Portfolio, SimulationConfig
)
from logic.lifecycle import SpendingModel
from logic.simulation_bridge import (
    SpendingStrategyInputs, PortfolioStrategyInputs, IncomeStreamInput,
    run_simulation
)
from logic.market_data import get_market_data


def build_midrange_ipo_portfolio_inputs() -> PortfolioStrategyInputs:
    """Build the Midrange IPO portfolio configuration."""
    return PortfolioStrategyInputs(
        liquid_assets=400000.0,
        retirement_assets=300000.0,
        stock_alloc_pct=100.0,
        bond_return_pct=4.0,
        current_age=30,
        death_age=100,
        strategy_type="Constant Dollar (Targets Schedule)",
        min_spend=50000.0,
        max_spend=250000.0,
        private_shares=18000.0,
        private_ipo_price=300.0,
        private_ipo_year=2026,
        diversification_start_year=2027,
        diversification_duration=10,
        private_growth_multiplier=1.0,
        income_streams=[
            IncomeStreamInput(
                name="Low Range Startup",
                start_year=2025,
                end_year=2030,
                annual_amount=250000.0
            )
        ],
        strategy_pct=4.0,
        gk_init_rate=4.5,
        flexible_spending=False,
        flexible_floor_pct=0.75,
        allow_early_retirement_access=True,
        early_withdrawal_penalty_rate=0.10,
        retirement_access_age=60
    )


def build_moderate_spending_inputs() -> SpendingStrategyInputs:
    """Build the Moderate Spending strategy configuration (simplified for test)."""
    return SpendingStrategyInputs(
        base_monthly_spend=8550.0,  # Approx to get ~$102,600 annual
        location="Alabama",
        children=[],
        child_profiles={},
        has_mortgage=False,
        mortgage=None,
        housing_projects=[],
        spending_items=[]
    )


def get_simulation_for_year_1932(df_market: pd.DataFrame, spending_inputs: SpendingStrategyInputs,
                                   portfolio_inputs: PortfolioStrategyInputs):
    """
    Find the simulation that starts in 1932.
    Returns the simulation index.
    """
    # Run simulation
    result, stats, schedule_df = run_simulation(spending_inputs, portfolio_inputs, df_market)
    
    # Find the 1932 simulation
    sim_1932_idx = None
    for idx, start_date in enumerate(result.start_dates):
        if start_date.year == 1932:
            sim_1932_idx = idx
            break
    
    return result, schedule_df, sim_1932_idx


class TestYearBreakdownConsistency(unittest.TestCase):
    """Tests to verify the year-by-year breakdown is internally consistent."""
    
    @classmethod
    def setUpClass(cls):
        """Load market data once for all tests."""
        cls.df_market = get_market_data()
    
    def test_should_have_matching_total_value_and_component_sum_given_year_0(self):
        """
        Verify Total Value (EOY) equals Diversified Portfolio + Concentrated Stock.
        
        This tests whether the balances DataFrame and the detailed breakdown
        DataFrames are properly aligned (no off-by-one errors).
        """
        # Preconditions
        portfolio_inputs = build_midrange_ipo_portfolio_inputs()
        spending_inputs = build_moderate_spending_inputs()
        
        result, schedule_df, sim_idx = get_simulation_for_year_1932(
            self.df_market, spending_inputs, portfolio_inputs
        )
        
        # Under test: Check year 0
        self.assertIsNotNone(sim_idx, "Could not find 1932 simulation")
        
        # Get balances (monthly, includes initial value at index 0)
        sim_balances = result.balances.iloc[sim_idx, :]
        
        # Get detailed breakdown (annual)
        sim_portfolio_values = result.portfolio_values.iloc[sim_idx, :]
        sim_private_stock_values = result.private_stock_values.iloc[sim_idx, :]
        
        # For year 0, end of year balance
        # The issue: month_idx calculation in year_analysis.py uses (year+1)*12 - 1
        # But path_balances has an extra initial value at index 0
        
        # What year_analysis.py currently does:
        month_idx_buggy = (0 + 1) * 12 - 1  # = 11
        total_value_buggy = sim_balances.iloc[month_idx_buggy]
        
        # What it should be:
        month_idx_correct = (0 + 1) * 12  # = 12
        total_value_correct = sim_balances.iloc[month_idx_correct]
        
        # Get component values
        portfolio_value = sim_portfolio_values.iloc[0]
        private_stock_value = sim_private_stock_values.iloc[0]
        component_sum = portfolio_value + private_stock_value
        
        # Postcondition: component sum should match total value
        # With buggy index:
        print(f"\n=== Year 0 Consistency Check ===")
        print(f"month_idx (buggy):    {month_idx_buggy}")
        print(f"month_idx (correct):  {month_idx_correct}")
        print(f"Total Value (buggy):  ${total_value_buggy:,.0f}")
        print(f"Total Value (correct): ${total_value_correct:,.0f}")
        print(f"Diversified Portfolio: ${portfolio_value:,.0f}")
        print(f"Concentrated Stock:   ${private_stock_value:,.0f}")
        print(f"Component Sum:        ${component_sum:,.0f}")
        print(f"Difference (buggy):   ${total_value_buggy - component_sum:,.0f}")
        print(f"Difference (correct): ${total_value_correct - component_sum:,.0f}")
        
        # The correct index should give matching values
        self.assertAlmostEqual(
            total_value_correct, component_sum, delta=1.0,
            msg=f"Total Value (correct index) should equal component sum. "
                f"Got {total_value_correct:,.0f} vs {component_sum:,.0f}"
        )
        
        # The buggy index gives a different value - documenting why the fix matters
        # In some market conditions these may be closer, so just verify the correct one works
        print(f"Note: Buggy index gives ~${abs(total_value_buggy - component_sum):,.0f} difference")
    
    def test_should_have_consistent_net_change_given_year_0_components(self):
        """
        Verify Net Change equals the sum of all cash flows and gains.
        
        Net Change = Diversified Gains + Concentrated Gains + W2 Income 
                     + IPO Proceeds - Spending - Taxes
        
        Note: This is conceptually what the net change SHOULD be, but
        there may be issues with how gains are calculated.
        """
        # Preconditions
        portfolio_inputs = build_midrange_ipo_portfolio_inputs()
        spending_inputs = build_moderate_spending_inputs()
        
        result, schedule_df, sim_idx = get_simulation_for_year_1932(
            self.df_market, spending_inputs, portfolio_inputs
        )
        
        self.assertIsNotNone(sim_idx, "Could not find 1932 simulation")
        
        # Under test: Year 0 components
        sim_balances = result.balances.iloc[sim_idx, :]
        initial_value = sim_balances.iloc[0]
        end_year_value = sim_balances.iloc[12]  # Correct index for end of year 0
        
        actual_net_change = end_year_value - initial_value
        
        # Get component values
        portfolio_gains = result.portfolio_gains.iloc[sim_idx, 0]
        private_stock_gains = result.private_stock_gains.iloc[sim_idx, 0]
        ipo_proceeds = result.ipo_proceeds.iloc[sim_idx, 0]
        withdrawals = result.withdrawals.iloc[sim_idx, 0]  # Spending target
        taxes = result.taxes.iloc[sim_idx, 0]
        total_income = result.total_income.iloc[sim_idx, 0]
        gross_withdrawals = result.gross_withdrawals.iloc[sim_idx, 0]
        
        # W2 income = total_income - ipo_proceeds - gross_withdrawals
        w2_income = total_income - ipo_proceeds - gross_withdrawals
        if w2_income < 0:
            w2_income = 0
        
        # Expected net change based on components
        # This is the accounting equation that SHOULD hold:
        # Net Change = Investment Returns + Income Received - Spending - Taxes
        expected_net_change = (
            portfolio_gains + private_stock_gains  # Investment returns
            + w2_income + ipo_proceeds  # External income
            - withdrawals  # Spending
            - taxes  # Taxes
        )
        
        print(f"\n=== Year 0 Net Change Analysis ===")
        print(f"Initial Value:        ${initial_value:,.0f}")
        print(f"End Year Value:       ${end_year_value:,.0f}")
        print(f"Actual Net Change:    ${actual_net_change:,.0f}")
        print(f"---")
        print(f"Diversified Gains:    ${portfolio_gains:,.0f}")
        print(f"Concentrated Gains:   ${private_stock_gains:,.0f}")
        print(f"W2 Income:            ${w2_income:,.0f}")
        print(f"IPO Proceeds:         ${ipo_proceeds:,.0f}")
        print(f"Spending (target):    ${withdrawals:,.0f}")
        print(f"Gross Withdrawals:    ${gross_withdrawals:,.0f}")
        print(f"Taxes:                ${taxes:,.0f}")
        print(f"Total Income:         ${total_income:,.0f}")
        print(f"---")
        print(f"Expected Net Change:  ${expected_net_change:,.0f}")
        print(f"Discrepancy:          ${actual_net_change - expected_net_change:,.0f}")
        
        # Postcondition: check if there's a significant discrepancy
        discrepancy = abs(actual_net_change - expected_net_change)
        self.assertLess(
            discrepancy, 1000,  # Allow small rounding differences
            f"Net change discrepancy too large: ${discrepancy:,.0f}. "
            f"Actual: ${actual_net_change:,.0f}, Expected: ${expected_net_change:,.0f}"
        )
    
    def test_should_calculate_portfolio_gain_correctly_given_deposits(self):
        """
        Verify portfolio gain calculation accounts for deposits correctly.
        
        The current gain formula is:
            portfolio_gain = end_value - start_value + gross_withdrawal
        
        But this doesn't account for deposits (from IPO proceeds or income surplus).
        The correct formula should be:
            portfolio_gain = end_value - start_value + gross_withdrawal - deposits
        
        Where deposits = max(0, post_tax_income - spending_requirement)
        """
        # Preconditions
        portfolio_inputs = build_midrange_ipo_portfolio_inputs()
        spending_inputs = build_moderate_spending_inputs()
        
        result, schedule_df, sim_idx = get_simulation_for_year_1932(
            self.df_market, spending_inputs, portfolio_inputs
        )
        
        self.assertIsNotNone(sim_idx, "Could not find 1932 simulation")
        
        # Under test: Check if gain calculation is correct
        sim_portfolio_values = result.portfolio_values.iloc[sim_idx, :]
        
        # Get year 0 values
        portfolio_gain_reported = result.portfolio_gains.iloc[sim_idx, 0]
        gross_withdrawal = result.gross_withdrawals.iloc[sim_idx, 0]
        total_income = result.total_income.iloc[sim_idx, 0]
        ipo_proceeds = result.ipo_proceeds.iloc[sim_idx, 0]
        taxes = result.taxes.iloc[sim_idx, 0]
        withdrawal_target = result.withdrawals.iloc[sim_idx, 0]
        
        # Calculate what was deposited vs withdrawn
        # When there's a surplus (income > spending + taxes), the surplus is deposited
        w2_income = total_income - ipo_proceeds - gross_withdrawal
        if w2_income < 0:
            w2_income = 0
        
        post_tax_income = w2_income + ipo_proceeds - taxes
        net_cash_flow = post_tax_income - withdrawal_target
        
        print(f"\n=== Portfolio Gain Analysis ===")
        print(f"Post-tax Income:      ${post_tax_income:,.0f}")
        print(f"Withdrawal Target:    ${withdrawal_target:,.0f}")
        print(f"Net Cash Flow:        ${net_cash_flow:,.0f}")
        print(f"Gross Withdrawal:     ${gross_withdrawal:,.0f}")
        
        if net_cash_flow > 0:
            # Surplus was deposited
            print(f"Deposit Amount:       ${net_cash_flow:,.0f}")
            print(f"(Income surplus deposited to portfolio)")
        else:
            # Deficit was withdrawn
            print(f"Withdrawal needed:    ${-net_cash_flow:,.0f}")
        
        print(f"---")
        print(f"Reported Portfolio Gain: ${portfolio_gain_reported:,.0f}")
        
        # The gain formula currently doesn't account for deposits properly
        # This is informational - we're documenting the issue
        
    def test_should_trace_initial_portfolio_composition(self):
        """
        Verify the initial portfolio composition matches expected values.
        
        Midrange IPO:
        - Liquid assets: $400,000
        - Retirement assets: $300,000
        - Private shares: 18,000 @ $300 = $5,400,000
        - Total: $6,100,000
        """
        # Preconditions
        portfolio_inputs = build_midrange_ipo_portfolio_inputs()
        spending_inputs = build_moderate_spending_inputs()
        
        result, schedule_df, sim_idx = get_simulation_for_year_1932(
            self.df_market, spending_inputs, portfolio_inputs
        )
        
        self.assertIsNotNone(sim_idx, "Could not find 1932 simulation")
        
        # Under test: Initial portfolio value
        initial_value = result.balances.iloc[sim_idx, 0]
        
        expected_liquid = 400000.0
        expected_retirement = 300000.0
        expected_private = 18000.0 * 300.0  # shares * price
        expected_total = expected_liquid + expected_retirement + expected_private
        
        print(f"\n=== Initial Portfolio Composition ===")
        print(f"Expected Liquid:      ${expected_liquid:,.0f}")
        print(f"Expected Retirement:  ${expected_retirement:,.0f}")
        print(f"Expected Private:     ${expected_private:,.0f}")
        print(f"Expected Total:       ${expected_total:,.0f}")
        print(f"Actual Initial:       ${initial_value:,.0f}")
        
        # Postcondition
        self.assertAlmostEqual(
            initial_value, expected_total, delta=1.0,
            msg=f"Initial portfolio should be ${expected_total:,.0f}, got ${initial_value:,.0f}"
        )


class TestGainCalculationLogic(unittest.TestCase):
    """Tests to verify the gain calculation logic in retirement.py."""
    
    def test_should_track_deposits_in_gain_calculation(self):
        """
        Demonstrate that the current gain calculation doesn't account for deposits.
        
        The formula:
            portfolio_gain = end_value - start_value + gross_withdrawal
        
        Doesn't capture the full picture when there are deposits.
        
        Correct formula should be:
            investment_return = end_value - (start_value + deposits - withdrawals)
        """
        # Preconditions: Simple scenario with known values
        portfolio = Portfolio(liquid_assets=100000, retirement_assets=0)
        
        start_value = portfolio.total_value  # 100,000
        
        # Simulate: deposit $50,000 (from income surplus)
        portfolio.deposit_liquid(50000)
        
        # Now value is 150,000
        
        # Apply 10% return
        portfolio.apply_market_return(0.10)
        
        # End value should be 165,000
        end_value = portfolio.total_value
        
        # Under test: Calculate gain using current formula
        gross_withdrawal = 0  # No withdrawals in this scenario
        current_formula_gain = end_value - start_value + gross_withdrawal
        # = 165,000 - 100,000 + 0 = 65,000
        
        # But the ACTUAL investment return is:
        # (150,000 * 1.10) - 150,000 = 15,000
        # Or equivalently: end - (start + deposits - withdrawals)
        # = 165,000 - (100,000 + 50,000 - 0) = 15,000
        correct_gain = end_value - (start_value + 50000 - gross_withdrawal)
        
        print(f"\n=== Gain Calculation Issue ===")
        print(f"Start Value:          ${start_value:,.0f}")
        print(f"Deposit:              $50,000")
        print(f"End Value:            ${end_value:,.0f}")
        print(f"---")
        print(f"Current Formula Gain: ${current_formula_gain:,.0f}")
        print(f"Correct Gain:         ${correct_gain:,.0f}")
        print(f"---")
        print(f"The current formula overstates gains by the deposit amount!")
        
        # Postconditions
        self.assertAlmostEqual(end_value, 165000, delta=1)
        self.assertAlmostEqual(current_formula_gain, 65000, delta=1)
        self.assertAlmostEqual(correct_gain, 15000, delta=1)
        
        # The current formula is wrong by the deposit amount
        self.assertAlmostEqual(current_formula_gain - correct_gain, 50000, delta=1)


class TestOffByOneError(unittest.TestCase):
    """Tests to verify the off-by-one error in balance indexing."""
    
    @classmethod
    def setUpClass(cls):
        """Load market data for tests."""
        cls.df_market = get_market_data()
    
    def test_should_demonstrate_off_by_one_in_month_index(self):
        """
        Demonstrate the off-by-one error in year_analysis.py.
        
        The balances DataFrame has an initial value at index 0,
        then monthly values appended. So:
        - Index 0: Initial balance (before any processing)
        - Index 1: Balance after month 0
        - Index 12: Balance after month 11 (end of year 0)
        
        But year_analysis.py uses:
            month_idx = (year_idx + 1) * 12 - 1
        
        For year 0: month_idx = 11, which is the balance after month 10, not month 11!
        
        The correct formula is:
            month_idx = (year_idx + 1) * 12
        """
        # Use real market data for sufficient history
        engine = BacktestEngine(self.df_market, stock_alloc=1.0, bond_return=0.0)
        strategy = ConstantDollarStrategy(
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        
        config = SimulationConfig(
            initial_portfolio=100000,
            duration_years=2,  # 2 years minimum
            initial_annual_withdrawal=0,  # No withdrawals to keep math simple
            spending_schedule=None,
            initial_401k=0,
            current_age=30,
            private_stock=None,
            income_streams=[],
            location="California",
            start_year=2025,
            allow_early_retirement_access=True,
            early_withdrawal_penalty_rate=0.10,
            access_age=60
        )
        result = engine.run_simulation(config, strategy)
        
        # Skip if no simulations
        if result.balances.empty:
            self.skipTest("No simulation data available")
        
        # Under test
        balances = result.balances.iloc[0, :]
        
        print(f"\n=== Off-by-One Error Demonstration ===")
        print(f"Balances length: {len(balances)}")
        print(f"Index 0 (initial): ${balances.iloc[0]:,.2f}")
        print(f"Index 11 (buggy):  ${balances.iloc[11]:,.2f}")
        print(f"Index 12 (correct): ${balances.iloc[12]:,.2f}")
        
        # The year_analysis.py formula
        year_idx = 0
        buggy_month_idx = (year_idx + 1) * 12 - 1  # = 11
        correct_month_idx = (year_idx + 1) * 12  # = 12
        
        print(f"---")
        print(f"For year_idx=0:")
        print(f"  Buggy formula gives:   month_idx = {buggy_month_idx}")
        print(f"  Correct formula gives: month_idx = {correct_month_idx}")
        
        # The portfolio_values are recorded at m % 12 == 11
        # which happens when m = 11, and the balance is appended AFTER processing
        # So portfolio_values[0] should match balances[12]
        if result.portfolio_values is not None and not result.portfolio_values.empty:
            portfolio_value_year_0 = result.portfolio_values.iloc[0, 0]
            print(f"---")
            print(f"portfolio_values[0]: ${portfolio_value_year_0:,.2f}")
            print(f"balances[11]:        ${balances.iloc[11]:,.2f}")
            print(f"balances[12]:        ${balances.iloc[12]:,.2f}")
            
            # portfolio_values should match balances at the CORRECT index
            self.assertAlmostEqual(
                portfolio_value_year_0, balances.iloc[12], delta=1,
                msg="portfolio_values[0] should match balances[12], not balances[11]"
            )


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)

