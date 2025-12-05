import pandas as pd
import numpy as np
from typing import Callable, Tuple, Dict, Any
from logic.retirement import BacktestEngine, SimulationResult, ConstantDollarStrategy

class RetirementSolver:
    def __init__(self, engine: BacktestEngine):
        self.engine = engine

    def solve_target_portfolio(self, 
                             desired_annual_spend: float, 
                             duration_years: int, 
                             stock_alloc: float = 0.8,
                             target_success_rate: float = 0.95) -> Tuple[float, Dict[str, float]]:
        """
        Calculates the required portfolio size to sustain 'desired_annual_spend' 
        with 'target_success_rate' confidence using a Constant Dollar strategy.
        
        Uses a binary search or simple iterative approximation. 
        Since linear scaling applies largely (ignoring sequence risk nuances), 
        we can approximate efficiently.
        """
        
        # Rough heuristic to start: 4% rule = 25x expenses.
        # We'll search between 10x and 60x expenses.
        low = desired_annual_spend * 10
        high = desired_annual_spend * 60
        
        # Binary search for the portfolio value that yields >= target_success_rate
        best_portfolio = high
        best_stats = {}
        
        for _ in range(10): # 10 iterations is usually plenty for financial precision
            mid = (low + high) / 2
            
            # We assume constant dollar for the "Target Number" calculation usually
            strategy = ConstantDollarStrategy(inflation_rate=0.03)
            
            result = self.engine.run_simulation(
                initial_portfolio=mid,
                duration_years=duration_years,
                withdrawal_strategy=strategy,
                initial_annual_withdrawal=desired_annual_spend
            )
            
            stats = self.engine.calculate_stats(result)
            success = stats['success_rate']
            
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
                                 target_success_rate: float = 0.95) -> float:
        """
        Finds the maximum initial withdrawal rate that satisfies the success target.
        """
        low_rate = 0.01
        high_rate = 0.10
        best_rate = low_rate
        
        for _ in range(10):
            mid_rate = (low_rate + high_rate) / 2
            withdrawal_amount = portfolio_value * mid_rate
            
            strategy = ConstantDollarStrategy(inflation_rate=0.03)
            
            result = self.engine.run_simulation(
                initial_portfolio=portfolio_value,
                duration_years=duration_years,
                withdrawal_strategy=strategy,
                initial_annual_withdrawal=withdrawal_amount
            )
            
            stats = self.engine.calculate_stats(result)
            success = stats['success_rate']
            
            if success >= target_success_rate:
                best_rate = mid_rate
                low_rate = mid_rate # Try higher spending
            else:
                high_rate = mid_rate # Too risky
                
        return best_rate

