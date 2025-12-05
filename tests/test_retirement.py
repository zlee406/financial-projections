import unittest
import pandas as pd
import numpy as np
from logic.retirement import BacktestEngine, ConstantDollarStrategy, PercentPortfolioStrategy
from logic.market_data import get_market_data
import os

class TestRetirementEngine(unittest.TestCase):

    def test_should_initialize_engine_given_datetime_index(self):
        # Precondition: DataFrame has DatetimeIndex
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        df = pd.DataFrame({'Close': np.random.rand(100)}, index=dates)
        
        # Under test
        engine = BacktestEngine(df)
        
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
            engine = BacktestEngine(df)
            # Postcondition
            self.assertIsInstance(engine.market_data.index, pd.DatetimeIndex)
            self.assertFalse(engine.monthly_data.empty)
        except Exception as e:
            self.fail(f"Engine raised unexpected exception with string index: {e}")

    def test_should_calculate_withdrawal_given_constant_dollar(self):
        strategy = ConstantDollarStrategy(inflation_rate=0.03)
        # Year 0
        w0 = strategy.calculate_withdrawal(1000000, 0, 40000, 40000)
        self.assertAlmostEqual(w0, 40000)
        # Year 1
        w1 = strategy.calculate_withdrawal(960000, 1, 40000, 40000)
        self.assertAlmostEqual(w1, 40000 * 1.03)

    def test_should_calculate_withdrawal_given_percent_portfolio(self):
        strategy = PercentPortfolioStrategy(percentage=0.04)
        # Year 0
        w0 = strategy.calculate_withdrawal(1000000, 0, 0, 0) # initial_withdrawal ignored
        self.assertAlmostEqual(w0, 40000)

    def test_should_drain_liquid_before_retirement_assets(self):
        # Precondition: 1 year simulation, flat market
        # Start Age 50, so cannot access 401k
        dates = pd.date_range(start='2020-01-01', periods=20, freq='ME')
        df = pd.DataFrame({'Close': [100.0] * 20}, index=dates) # Flat returns
        engine = BacktestEngine(df, stock_alloc=1.0, bond_return=0.0)
        
        strategy = ConstantDollarStrategy(inflation_rate=0.0)
        
        # Liquid: 100k, 401k: 100k
        # Withdraw 120k total
        res = engine.run_simulation(
            initial_portfolio=100000, 
            duration_years=1, 
            withdrawal_strategy=strategy, 
            initial_annual_withdrawal=120000,
            initial_401k=100000,
            current_age=50
        )
        
        # Postcondition: 
        # Since Age < 60, we should FAIL when liquid runs out.
        # Liquid 100k - 120k needed -> Fail. 401k untouched (or zeroed on fail).
        final_bal = res.balances.iloc[0, -1]
        self.assertEqual(final_bal, 0.0) # Should fail/zero out

    def test_should_access_retirement_assets_if_age_appropriate(self):
        # Precondition: Age 65, can access 401k
        dates = pd.date_range(start='2020-01-01', periods=20, freq='ME')
        df = pd.DataFrame({'Close': [100.0] * 20}, index=dates)
        engine = BacktestEngine(df, stock_alloc=1.0, bond_return=0.0)
        
        strategy = ConstantDollarStrategy(inflation_rate=0.0)
        
        # Liquid: 100k, 401k: 100k. Withdraw 150k.
        res = engine.run_simulation(
            initial_portfolio=100000, 
            duration_years=1, 
            withdrawal_strategy=strategy, 
            initial_annual_withdrawal=150000,
            initial_401k=100000,
            current_age=65
        )
        
        # Postcondition:
        # Liquid drained (100k), remaining 50k taken from 401k (100k -> 50k)
        # Total remaining should be ~50k
        final_bal = res.balances.iloc[0, -1]
        self.assertAlmostEqual(final_bal, 50000, delta=100)
        
if __name__ == '__main__':
    unittest.main()
