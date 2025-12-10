import unittest
import pandas as pd
import numpy as np
from logic.retirement import BacktestEngine, ConstantDollarStrategy, PercentPortfolioStrategy, Portfolio, SimulationConfig
from logic.market_data import get_market_data
import os

class TestRetirementEngine(unittest.TestCase):

    def test_should_initialize_engine_given_datetime_index(self):
        # Precondition: DataFrame has DatetimeIndex
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        df = pd.DataFrame({'Close': np.random.rand(100)}, index=dates)
        
        # Under test
        engine = BacktestEngine(df, stock_alloc=0.8, bond_return=0.04)
        
        # Postcondition
        self.assertIsInstance(engine.monthly_data.index, pd.DatetimeIndex)
        self.assertFalse(engine.monthly_data.empty)

    def test_should_handle_given_string_index_gracefully(self):
        # Precondition: DataFrame has String Index (simulating the bug)
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        # Convert dates to strings
        date_strings = dates.strftime('%Y-%m-%d') 
        df = pd.DataFrame({'Close': np.random.rand(100)}, index=date_strings)
        
        # Under test
        try:
            engine = BacktestEngine(df, stock_alloc=0.8, bond_return=0.04)
            # Postcondition
            self.assertIsInstance(engine.market_data.index, pd.DatetimeIndex)
            self.assertFalse(engine.monthly_data.empty)
        except Exception as e:
            self.fail(f"Engine raised unexpected exception with string index: {e}")

    def test_should_calculate_withdrawal_given_constant_dollar(self):
        strategy = ConstantDollarStrategy(
            inflation_rate=0.03,
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        # Year 0
        w0 = strategy.calculate_withdrawal(1000000, 0, 40000, 40000)
        self.assertAlmostEqual(w0, 40000)
        # Year 1
        w1 = strategy.calculate_withdrawal(960000, 1, 40000, 40000)
        self.assertAlmostEqual(w1, 40000 * 1.03)

    def test_should_calculate_withdrawal_given_percent_portfolio(self):
        strategy = PercentPortfolioStrategy(
            percentage=0.04,
            inflation_rate=0.03,
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        # Year 0
        w0 = strategy.calculate_withdrawal(1000000, 0, 0, 0) # initial_withdrawal ignored
        self.assertAlmostEqual(w0, 40000)

    def test_should_fail_when_early_access_disabled_and_liquid_depleted(self):
        # Precondition: 1 year simulation, flat market
        # Start Age 50, early access DISABLED
        dates = pd.date_range(start='2020-01-01', periods=20, freq='ME')
        df = pd.DataFrame({'Close': [100.0] * 20}, index=dates) # Flat returns
        engine = BacktestEngine(df, stock_alloc=1.0, bond_return=0.0)
        
        strategy = ConstantDollarStrategy(
            inflation_rate=0.0,
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        
        # Build config
        config = SimulationConfig(
            initial_portfolio=100000,
            duration_years=1,
            initial_annual_withdrawal=120000,
            spending_schedule=None,
            initial_401k=100000,
            current_age=50,
            private_stock=None,
            income_streams=[],
            location="California",
            start_year=2025,
            allow_early_retirement_access=False,  # DISABLED
            early_withdrawal_penalty_rate=0.10,
            access_age=60
        )
        
        res = engine.run_simulation(config, strategy)
        
        # Postcondition: 
        # Since early access is DISABLED and Age < 60, should FAIL when liquid runs out.
        final_bal = res.balances.iloc[0, -1]
        self.assertEqual(final_bal, 0.0)  # Should fail/zero out
    
    def test_should_access_401k_early_with_penalty_when_early_access_enabled(self):
        # Precondition: Age 50, early access ENABLED (default)
        dates = pd.date_range(start='2020-01-01', periods=20, freq='ME')
        df = pd.DataFrame({'Close': [100.0] * 20}, index=dates)
        engine = BacktestEngine(df, stock_alloc=1.0, bond_return=0.0)
        
        strategy = ConstantDollarStrategy(
            inflation_rate=0.0,
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        
        # Build config
        config = SimulationConfig(
            initial_portfolio=100000,
            duration_years=1,
            initial_annual_withdrawal=120000,
            spending_schedule=None,
            initial_401k=100000,
            current_age=50,
            private_stock=None,
            income_streams=[],
            location="California",
            start_year=2025,
            allow_early_retirement_access=True,  # ENABLED
            early_withdrawal_penalty_rate=0.10,
            access_age=60
        )
        
        res = engine.run_simulation(config, strategy)
        
        # Postcondition:
        # With early access enabled, should succeed by accessing 401k with penalty
        # Liquid drained (100k), extra 20k from 401k + penalty
        final_bal = res.balances.iloc[0, -1]
        self.assertGreater(final_bal, 0)  # Should not fail

    def test_should_access_retirement_assets_if_age_appropriate(self):
        # Precondition: Age 65, can access 401k penalty-free
        dates = pd.date_range(start='2020-01-01', periods=20, freq='ME')
        df = pd.DataFrame({'Close': [100.0] * 20}, index=dates)
        engine = BacktestEngine(df, stock_alloc=1.0, bond_return=0.0)
        
        strategy = ConstantDollarStrategy(
            inflation_rate=0.0,
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        
        # Build config
        config = SimulationConfig(
            initial_portfolio=100000,
            duration_years=1,
            initial_annual_withdrawal=150000,
            spending_schedule=None,
            initial_401k=100000,
            current_age=65,
            private_stock=None,
            income_streams=[],
            location="California",
            start_year=2025,
            allow_early_retirement_access=True,
            early_withdrawal_penalty_rate=0.10,
            access_age=60
        )
        
        res = engine.run_simulation(config, strategy)
        
        # Postcondition:
        # Liquid drained (100k), rest from 401k with taxes.
        # 401k withdrawals are now taxed as ordinary income, so gross withdrawal > 50k
        # Expected final balance is lower due to tax gross-up on 401k
        final_bal = res.balances.iloc[0, -1]
        # Should have some balance remaining (401k not fully drained) and should not fail
        self.assertGreater(final_bal, 0)
        self.assertLess(final_bal, 60000)  # But less than if no taxes

    def test_should_return_withdrawal_breakdown_from_portfolio(self):
        # Test the new WithdrawalResult for proper tax tracking
        portfolio = Portfolio(liquid_assets=50000, retirement_assets=100000)
        
        # Withdraw $75k at age 50 (early access enabled)
        result = portfolio.withdraw(
            amount=75000,
            current_age=50,
            access_age=60,
            allow_early_retirement_access=True,
            early_withdrawal_penalty_rate=0.10
        )
        
        # Postcondition: Should succeed
        self.assertTrue(result.success)
        self.assertEqual(result.from_liquid, 50000)  # Drained all liquid
        self.assertEqual(result.from_retirement, 25000)  # Rest from retirement
        self.assertEqual(result.early_withdrawal_penalty, 2500)  # 10% of 25k
        
    def test_should_track_liquid_gains_properly(self):
        # Test capital gains tracking in withdrawals
        portfolio = Portfolio(liquid_assets=100000, retirement_assets=0)
        
        # Simulate market gain: liquid doubles but basis stays same
        portfolio.liquid = 200000  # Value doubled
        # Basis is still 100000, so basis_ratio = 0.5
        
        result = portfolio.withdraw(
            amount=50000,
            current_age=65,
            access_age=60,
            allow_early_retirement_access=True,
            early_withdrawal_penalty_rate=0.10
        )
        
        # Postcondition: Should track gains correctly
        self.assertTrue(result.success)
        self.assertEqual(result.from_liquid, 50000)
        self.assertEqual(result.liquid_gains, 25000)  # 50% of withdrawal is gains
        
if __name__ == '__main__':
    unittest.main()
