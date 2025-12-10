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

def calculate_purchasing_power(result: SimulationResult) -> pd.DataFrame:
    """
    Converts nominal withdrawals to real (inflation-adjusted) withdrawals.
    Uses historical inflation data from each simulation path.
    Returns a DataFrame of Real Withdrawals.
    """
    real_withdrawals = result.withdrawals.copy()
    
    if result.annual_inflation_rates is not None and len(result.annual_inflation_rates) > 0:
        # Use historical inflation for each simulation path
        for sim_idx in range(len(result.annual_inflation_rates)):
            inflation_rates = result.annual_inflation_rates[sim_idx]
            cumulative = 1.0
            for year_idx in range(real_withdrawals.shape[1]):
                if year_idx > 0 and year_idx <= len(inflation_rates):
                    cumulative *= (1 + inflation_rates[year_idx - 1])
                real_withdrawals.iloc[sim_idx, year_idx] = real_withdrawals.iloc[sim_idx, year_idx] / cumulative
    
    return real_withdrawals

