import pandas as pd
import numpy as np
from typing import Tuple, Dict
from logic.retirement import BacktestEngine, ConstantDollarStrategy, SimulationConfig

class RetirementSolver:
    """
    Solver utility for finding optimal portfolio sizes and withdrawal rates.
    
    Note: This solver is a simplified utility that doesn't use spending schedules
    or complex configurations. It uses a basic ConstantDollarStrategy with
    historical inflation data from the engine.
    """
    
    def __init__(self, engine: BacktestEngine):
        self.engine = engine

    def solve_target_portfolio(self, 
                             desired_annual_spend: float, 
                             duration_years: int, 
                             stock_alloc: float = 0.8,
                             target_success_rate: float = 0.95,
                             current_age: int = 65,
                             location: str = "California") -> Tuple[float, Dict[str, float]]:
        """
        Calculates the required portfolio size to sustain 'desired_annual_spend' 
        with 'target_success_rate' confidence using a Constant Dollar strategy.
        
        Uses a binary search or simple iterative approximation. 
        Since linear scaling applies largely (ignoring sequence risk nuances), 
        we can approximate efficiently.
        """
        from datetime import datetime
        
        # Rough heuristic to start: 4% rule = 25x expenses.
        # We'll search between 10x and 60x expenses.
        low = desired_annual_spend * 10
        high = desired_annual_spend * 60
        
        # Binary search for the portfolio value that yields >= target_success_rate
        best_portfolio = high
        best_stats = {}
        
        for _ in range(10): # 10 iterations is usually plenty for financial precision
            mid = (low + high) / 2
            
            # Use ConstantDollarStrategy with no limits
            strategy = ConstantDollarStrategy(
                min_withdrawal=None,
                max_withdrawal=None,
                flexible_spending=False,
                flexible_floor_pct=0.75
            )
            
            config = SimulationConfig(
                initial_portfolio=mid,
                duration_years=duration_years,
                initial_annual_withdrawal=desired_annual_spend,
                spending_schedule=None,
                initial_401k=0,
                current_age=current_age,
                private_stock=None,
                income_streams=[],
                location=location,
                start_year=datetime.now().year,
                allow_early_retirement_access=True,
                early_withdrawal_penalty_rate=0.10,
                access_age=60
            )
            
            result = self.engine.run_simulation(config, strategy)
            stats = self.engine.calculate_stats(result)
            success = stats.get('success_rate', 0)
            
            if success >= target_success_rate:
                best_portfolio = mid
                best_stats = stats
                high = mid # Try smaller
            else:
                low = mid # Need more money
                
        return best_portfolio, best_stats

    def solve_safe_withdrawal_rate(self, 
                                 portfolio_value: float, 
                                 duration_years: int, 
                                 target_success_rate: float = 0.95,
                                 current_age: int = 65,
                                 location: str = "California") -> float:
        """
        Finds the maximum initial withdrawal rate that satisfies the success target.
        """
        from datetime import datetime
        
        low_rate = 0.01
        high_rate = 0.10
        best_rate = low_rate
        
        for _ in range(10):
            mid_rate = (low_rate + high_rate) / 2
            withdrawal_amount = portfolio_value * mid_rate
            
            strategy = ConstantDollarStrategy(
                min_withdrawal=None,
                max_withdrawal=None,
                flexible_spending=False,
                flexible_floor_pct=0.75
            )
            
            config = SimulationConfig(
                initial_portfolio=portfolio_value,
                duration_years=duration_years,
                initial_annual_withdrawal=withdrawal_amount,
                spending_schedule=None,
                initial_401k=0,
                current_age=current_age,
                private_stock=None,
                income_streams=[],
                location=location,
                start_year=datetime.now().year,
                allow_early_retirement_access=True,
                early_withdrawal_penalty_rate=0.10,
                access_age=60
            )
            
            result = self.engine.run_simulation(config, strategy)
            stats = self.engine.calculate_stats(result)
            success = stats.get('success_rate', 0)
            
            if success >= target_success_rate:
                best_rate = mid_rate
                low_rate = mid_rate # Try higher spending
            else:
                high_rate = mid_rate # Too risky
                
        return best_rate

