import pandas as pd
import numpy as np
from logic.retirement import SimulationResult

def calculate_cohort_stats(result: SimulationResult) -> pd.DataFrame:
    """
    Analyzes which start years were the most dangerous.
    Returns a DataFrame indexed by Start Date with columns:
    - Success (Bool)
    - End Balance
    - Min Withdrawal
    """
    if result.balances.empty:
        return pd.DataFrame()
        
    # Extract final balances
    final_balances = result.balances.iloc[:, -1].values
    success = final_balances > 0
    
    # Extract min withdrawal for each simulation
    min_withdrawals = result.withdrawals.min(axis=1).values
    
    df = pd.DataFrame({
        "Start Date": result.start_dates,
        "Success": success,
        "End Balance": final_balances,
        "Min Annual Withdrawal": min_withdrawals
    })
    
    df.set_index("Start Date", inplace=True)
    return df

def get_failed_cohorts(cohort_stats: pd.DataFrame) -> pd.DataFrame:
    """
    Returns only the cohorts that failed.
    """
    return cohort_stats[~cohort_stats["Success"]].sort_values("End Balance")

def calculate_purchasing_power(result: SimulationResult, inflation_rate: float = 0.03) -> pd.DataFrame:
    """
    Converts nominal withdrawals to real (inflation-adjusted) withdrawals.
    Returns a DataFrame of Real Withdrawals.
    """
    real_withdrawals = result.withdrawals.copy()
    years = real_withdrawals.shape[1]
    
    # Apply deflation factor (1 / (1+inf)^year)
    for year in range(years):
        deflator = 1 / ((1 + inflation_rate) ** year)
        real_withdrawals.iloc[:, year] = real_withdrawals.iloc[:, year] * deflator
        
    return real_withdrawals

