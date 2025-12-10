import unittest
import pandas as pd
import numpy as np
from logic import retirement, simulation_bridge

class TestChartIntegration(unittest.TestCase):
    def test_metric_consistency_real_spend(self):
        # Setup: 300k Real Need, 3% Inflation
        market_data = pd.DataFrame({
            'Close': [100.0, 105.0, 110.0] # dummy market data
        }, index=pd.to_datetime(['2020-01-31', '2020-02-29', '2020-03-31'], utc=True))
        
        engine = retirement.BacktestEngine(market_data, stock_alloc=1.0, bond_return=0.0)
        
        inflation_rate = 0.03
        # Mock SimulationResult with known Nominal withdrawals
        # Year 0: 300k (Real=300k)
        # Year 1: 309k (Real=300k)
        sim_withdrawals = pd.DataFrame({
            0: [300000.0, 300000.0], # Year 0 for 2 sims
            1: [309000.0, 309000.0]  # Year 1 for 2 sims
        })
        sim_balances = pd.DataFrame({0: [100], 1: [100]}) # Dummy balances

        mock_result = retirement.SimulationResult(
            balances=sim_balances,
            withdrawals=sim_withdrawals,
            taxes=pd.DataFrame(),
            total_income=pd.DataFrame(),
            gross_withdrawals=sim_withdrawals,  # Same as withdrawals for this test
            start_dates=[]
        )
        
        stats = engine.calculate_stats(mock_result, inflation_rate=inflation_rate)
        
        self.assertAlmostEqual(stats["min_annual_spend"], 300000.0, delta=1.0, 
                               msg="Lowest Annual Spend (Real) should be ~300k")
        
    def test_bridge_integration(self):
        # This tests the whole flow from bridge inputs to stats
        # Verify that passing a high need and low ceiling results in floor being respected
        
        # Mock Data
        df_market = pd.DataFrame({
            'Close': [100.0] * 360 # Flat market for 30 years
        }, index=pd.date_range(start='1990-01-01', periods=360, freq='ME'))
        
        strategy_inputs = {
            "base_monthly_spend": 25000.0, # 300k annual
            "location": "Texas"
        }
        
        portfolio_inputs = {
            "liquid_assets": 10000000.0, # Lots of money
            "retirement_assets": 0,
            "stock_alloc_pct": 100,
            "bond_return_pct": 0,
            "inflation_rate": 0.03,
            "current_age": 60,
            "death_age": 62, # Short sim
            "strategy_type": "Constant Dollar (Targets Schedule)",
            "min_spend": 0.0,
            "max_spend": 200000.0, # CEILING lower than NEED (300k)
        }
        
        result, stats, schedule_df = simulation_bridge.run_simulation_wrapper(
            strategy_inputs, portfolio_inputs, df_market
        )
        
        # Verify Schedule has 300k
        self.assertAlmostEqual(schedule_df["Required_Real_Spend"].iloc[0], 300000.0)
        
        # Verify Stats (Min Spend Real) should be 300k (floor respected)
        # If logic was wrong, it would be 200k (capped by ceiling)
        self.assertAlmostEqual(stats["min_annual_spend"], 300000.0, delta=100.0)
        
        # Verify first withdrawal in result is Nominal 300k
        self.assertAlmostEqual(result.withdrawals.iloc[0, 0], 300000.0, delta=1.0)
        # Verify second withdrawal is Nominal 309k
        self.assertAlmostEqual(result.withdrawals.iloc[0, 1], 309000.0, delta=1.0)

if __name__ == '__main__':
    unittest.main()



