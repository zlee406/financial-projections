import pandas as pd
import numpy as np
from typing import Protocol, List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from logic import tax, tax_rules

@dataclass
class PrivateStock:
    shares: float
    ipo_year: int
    ipo_price: float
    diversification_start_year: Optional[int] = None
    diversification_duration: Optional[int] = None

@dataclass
class IncomeStream:
    name: str
    start_year: int
    end_year: int
    annual_amount: float
    taxable: bool = True

@dataclass
class SimulationResult:
    balances: pd.DataFrame  # Rows: simulations, Cols: months
    withdrawals: pd.DataFrame # Rows: simulations, Cols: years (Annual amounts)
    taxes: pd.DataFrame # Rows: simulations, Cols: years (Annual tax liability)
    total_income: pd.DataFrame # Rows: simulations, Cols: years (Total Gross Income from all sources)
    start_dates: List[pd.Timestamp] # Start date for each simulation

class WithdrawalStrategy(Protocol):
    def calculate_withdrawal(self, current_portfolio_value: float, year: int, initial_withdrawal: float, previous_withdrawal: float, spending_schedule: Optional[pd.Series] = None) -> float:
        """
        Calculates the withdrawal amount for the current year.
        spending_schedule: Series of REAL required spending for each year [0..duration].
        """
        ...
    
    def get_min_max_limits(self) -> Tuple[Optional[float], Optional[float]]:
        return None, None

class BaseStrategy:
    def __init__(self, min_withdrawal: Optional[float] = None, max_withdrawal: Optional[float] = None):
        self.min_withdrawal = min_withdrawal
        self.max_withdrawal = max_withdrawal

    def apply_limits(self, amount: float) -> float:
        if self.min_withdrawal is not None:
            amount = max(amount, self.min_withdrawal)
        if self.max_withdrawal is not None:
            amount = min(amount, self.max_withdrawal)
        return amount

    def get_min_max_limits(self) -> Tuple[Optional[float], Optional[float]]:
        return self.min_withdrawal, self.max_withdrawal

class ConstantDollarStrategy(BaseStrategy):
    def __init__(self, inflation_rate: float = 0.03, min_withdrawal: Optional[float] = None, max_withdrawal: Optional[float] = None):
        super().__init__(min_withdrawal, max_withdrawal)
        self.inflation_rate = inflation_rate

    def calculate_withdrawal(self, current_portfolio_value: float, year: int, initial_withdrawal: float, previous_withdrawal: float, spending_schedule: Optional[pd.Series] = None) -> float:
        if spending_schedule is not None:
            # If schedule provided, target that specific year's Real need
            # The schedule is in Real $, so we adjust for Cumulative Inflation
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = (1 + self.inflation_rate) ** year
            val = required_real * cumulative_inflation
        else:
            # Fallback to flat initial
            if year == 0:
                val = initial_withdrawal
            else:
                val = previous_withdrawal * (1 + self.inflation_rate)
                
        # Apply Strategy limits first (Min/Max)
        val = self.apply_limits(val)
        
        # Override with Floor from Schedule (Hard Requirement)
        if spending_schedule is not None:
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = (1 + self.inflation_rate) ** year
            floor_val = required_real * cumulative_inflation
            val = max(val, floor_val)
            
        return val

class PercentPortfolioStrategy(BaseStrategy):
    def __init__(self, percentage: float, inflation_rate: float = 0.03, min_withdrawal: Optional[float] = None, max_withdrawal: Optional[float] = None):
        super().__init__(min_withdrawal, max_withdrawal)
        self.percentage = percentage
        self.inflation_rate = inflation_rate

    def calculate_withdrawal(self, current_portfolio_value: float, year: int, initial_withdrawal: float, previous_withdrawal: float, spending_schedule: Optional[pd.Series] = None) -> float:
        val = current_portfolio_value * self.percentage
        
        # Apply Strategy limits first (Min/Max)
        val = self.apply_limits(val)
        
        # Override with Floor from Schedule
        if spending_schedule is not None:
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = (1 + self.inflation_rate) ** year
            floor_val = required_real * cumulative_inflation
            val = max(val, floor_val)
            
        return val

class EndowmentStrategy(BaseStrategy):
    def __init__(self, percentage: float, min_withdrawal: Optional[float] = None, max_withdrawal: Optional[float] = None):
        super().__init__(min_withdrawal, max_withdrawal)
        self.percentage = percentage

    def calculate_withdrawal(self, current_portfolio_value: float, year: int, initial_withdrawal: float, previous_withdrawal: float, spending_schedule: Optional[pd.Series] = None) -> float:
        # Same as PercentPortfolioStrategy for now, but could include smoothing logic later
        return self.apply_limits(current_portfolio_value * self.percentage)

class VPWStrategy(BaseStrategy):
    def __init__(self, start_age: int = 40, max_age: int = 100, inflation_rate: float = 0.03, min_withdrawal: Optional[float] = None, max_withdrawal: Optional[float] = None):
        super().__init__(min_withdrawal, max_withdrawal)
        self.start_age = start_age
        self.max_age = max_age
        self.inflation_rate = inflation_rate

    def calculate_withdrawal(self, current_portfolio_value: float, year: int, initial_withdrawal: float, previous_withdrawal: float, spending_schedule: Optional[pd.Series] = None) -> float:
        # Simplified VPW: 1 / remaining_years
        current_age = self.start_age + year
        remaining_years = max(1, self.max_age - current_age)
        rate = 1.0 / remaining_years
        
        # Assume 5% real return for the 'schedule'
        assumed_real_return = 0.05
        if assumed_real_return == 0:
            rate = 1.0 / remaining_years
        else:
            rate = assumed_real_return / (1 - (1 + assumed_real_return) ** -remaining_years)
            
        val = current_portfolio_value * rate
        
        # Apply Strategy limits first
        val = self.apply_limits(val)
        
        # Override with Floor from Schedule
        if spending_schedule is not None:
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = (1 + self.inflation_rate) ** year
            floor_val = required_real * cumulative_inflation
            val = max(val, floor_val)

        return val

class FloorCeilingStrategy(BaseStrategy):
    def __init__(self, 
                 inflation_rate: float = 0.03, 
                 floor_pct: float = 0.85, 
                 ceiling_pct: float = 1.15,
                 min_withdrawal: Optional[float] = None,
                 max_withdrawal: Optional[float] = None):
        super().__init__(min_withdrawal, max_withdrawal)
        self.inflation_rate = inflation_rate
        self.floor_pct = floor_pct
        self.ceiling_pct = ceiling_pct
        self.base_real_withdrawal = None 

    def calculate_withdrawal(self, current_portfolio_value: float, year: int, initial_withdrawal: float, previous_withdrawal: float, spending_schedule: Optional[pd.Series] = None) -> float:
        # Implementation detail omitted for brevity as it wasn't the main focus, usually handled by generic BaseStrategy limits
        return self.apply_limits(initial_withdrawal) # Placeholder

class GuytonKlingerStrategy(BaseStrategy):
    def __init__(self, 
                 initial_rate: float, 
                 portfolio_value: float, 
                 inflation_rate: float = 0.03,
                 guardrail_upper: float = 0.20, 
                 guardrail_lower: float = 0.20,
                 min_withdrawal: Optional[float] = None,
                 max_withdrawal: Optional[float] = None):
        super().__init__(min_withdrawal, max_withdrawal)
        self.initial_rate_pct = initial_rate
        self.inflation_rate = inflation_rate
        self.guardrail_upper_threshold = initial_rate * (1 - guardrail_upper) 
        self.guardrail_lower_threshold = initial_rate * (1 + guardrail_lower)
        
    def calculate_withdrawal(self, current_portfolio_value: float, year: int, initial_withdrawal: float, previous_withdrawal: float, spending_schedule: Optional[pd.Series] = None) -> float:
        if current_portfolio_value <= 0:
            return 0.0
            
        # Calculate "Proposed" - if schedule exists, use that, else inflation adjust previous
        if spending_schedule is not None:
            # This is tricky for GK because GK depends on "Inflation Adjusted INITIAL". 
            # If the "Initial" (Requirement) changes every year, GK logic needs adaptation.
            # Simplified: Use the Schedule as the "Proposed", then apply GK cuts/raises to THAT.
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = (1 + self.inflation_rate) ** year
            proposed_withdrawal = required_real * cumulative_inflation
        else:
            proposed_withdrawal = previous_withdrawal * (1 + self.inflation_rate)
            
        current_wr = proposed_withdrawal / current_portfolio_value
        
        final_amount = proposed_withdrawal
        
        if current_wr > self.guardrail_lower_threshold:
            final_amount = final_amount * 0.90
        elif current_wr < self.guardrail_upper_threshold:
            final_amount = final_amount * 1.10
            
        # Apply Strategy limits first
        final_amount = self.apply_limits(final_amount)
            
        # Override with Floor from Schedule
        if spending_schedule is not None:
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = (1 + self.inflation_rate) ** year
            floor_val = required_real * cumulative_inflation
            final_amount = max(final_amount, floor_val)
            
        return final_amount

class BacktestEngine:
    def __init__(self, market_data: pd.DataFrame, stock_alloc: float = 0.8, bond_return: float = 0.04):
        """
        market_data: DataFrame with datetime index and 'Close' column for Stocks.
        stock_alloc: 0.0 to 1.0
        bond_return: Fixed annual return for bonds (simplified).
        """
        self.market_data = market_data.copy()
        
        # Ensure index is DatetimeIndex
        if not isinstance(self.market_data.index, pd.DatetimeIndex):
            try:
                self.market_data.index = pd.to_datetime(self.market_data.index, utc=True)
            except Exception as e:
                raise ValueError(f"Could not convert index to DatetimeIndex: {e}")

        self.market_data = self.market_data.sort_index()
        self.stock_alloc = stock_alloc
        self.bond_return = bond_return
        # Resample to monthly for month-by-month simulation
        # using 'ME' (Month End) to avoid FutureWarning
        self.monthly_data = self.market_data['Close'].resample('ME').ffill().pct_change().dropna()

    def run_simulation(self, 
                      initial_portfolio: float, 
                      duration_years: int, 
                      withdrawal_strategy: Any,
                      initial_annual_withdrawal: float,
                      spending_schedule: Optional[pd.Series] = None,
                      initial_401k: float = 0.0,
                      current_age: int = 40,
                      private_stock: Optional[PrivateStock] = None,
                      income_streams: List[IncomeStream] = [],
                      location: str = "California",
                      start_year: int = 2025) -> SimulationResult:
        """
        Runs backtests.
        spending_schedule: Optional Series of REAL required spending per year.
        initial_401k: Amount in 401k/Restricted accounts (not accessible until 59.5 without penalty, or simulated failure).
        current_age: Starting age for 401k access logic.
        private_stock: Optional future windfall event.
        income_streams: List of pre-tax W2 income streams.
        location: Tax jurisdiction.
        start_year: The calendar year the simulation effectively "starts" (for IPO logic).
        """
        # Limit: we need enough data for 'duration_years'
        months_needed = duration_years * 12
        available_months = len(self.monthly_data)
        
        if available_months < months_needed:
            return SimulationResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [])

        sim_balances = []
        sim_withdrawals = []
        sim_taxes = []
        sim_incomes = []
        start_dates = []
        
        # Access Age
        ACCESS_AGE = 60 # Simplified 59.5
        
        # Tax Engine
        tax_engine = tax.TaxEngine(location)

        # Iterate through all possible start dates (annual cohorts)
        for start_idx in range(0, available_months - months_needed, 12): 
            start_date = self.monthly_data.index[start_idx]
            start_dates.append(start_date)

            # Buckets
            liquid_bal = initial_portfolio # "initial_portfolio" passed in is now treated as "Liquid Assets"
            retirement_bal = initial_401k
            
            # Basis Tracking (Simple Average)
            liquid_basis = liquid_bal # Assume starting liquid is post-tax principal (basis = value)
            
            # Private Stock Tracking
            # We track shares separately so we can handle diversification schedule
            ps_shares_remaining = 0.0
            ps_ipo_price = 0.0
            if private_stock:
                ps_shares_remaining = private_stock.shares
                ps_ipo_price = private_stock.ipo_price
            
            path_balances = [liquid_bal + retirement_bal]
            path_withdrawals = []
            path_taxes = []
            path_incomes = []
            
            # Extract returns
            period_returns = self.monthly_data.iloc[start_idx : start_idx + months_needed]
            bond_monthly_rate = (1 + self.bond_return)**(1/12) - 1
            
            # Initial withdrawal calc
            # If schedule exists, start with Schedule[0]
            if spending_schedule is not None:
                current_initial_withdrawal = spending_schedule.iloc[0]
            else:
                current_initial_withdrawal = initial_annual_withdrawal
                
            # Apply limits to initial
            if hasattr(withdrawal_strategy, 'apply_limits'):
                current_initial_withdrawal = withdrawal_strategy.apply_limits(current_initial_withdrawal)
            
            # Override with Floor from Schedule (Initial Year 0)
            if spending_schedule is not None:
                # Year 0 Nominal Floor = Real Requirement (since Deflator = 1)
                floor_val = spending_schedule.iloc[0]
                current_initial_withdrawal = max(current_initial_withdrawal, floor_val)
                
            previous_withdrawal = current_initial_withdrawal
            annual_draw = current_initial_withdrawal
            monthly_draw = annual_draw / 12.0

            failed = False

            for m, stock_ret in enumerate(period_returns):
                current_year_offset = m // 12
                sim_age = current_age + current_year_offset
                sim_calendar_year = start_year + current_year_offset
                
                # --- Annual Logic (Start of Year) ---
                if m % 12 == 0:
                    # 1. Update Portfolio Value for Withdrawal Calc
                    total_pv = liquid_bal + retirement_bal
                    
                    # 2. Calculate Required Spend (Strategy)
                    if m == 0:
                         annual_draw = current_initial_withdrawal
                    else:
                         # Pass schedule to strategy
                         annual_draw = withdrawal_strategy.calculate_withdrawal(
                             current_portfolio_value=total_pv, 
                             year=current_year_offset, 
                             initial_withdrawal=current_initial_withdrawal,
                             previous_withdrawal=previous_withdrawal,
                             spending_schedule=spending_schedule
                         )
                    
                    previous_withdrawal = annual_draw
                    
                    # 3. Handle W2 Income & Taxes
                    # Calculate total annual W2 for this year
                    annual_w2_income = 0.0
                    for stream in income_streams:
                        if stream.start_year <= sim_calendar_year <= stream.end_year:
                             annual_w2_income += stream.annual_amount
                    
                    # 4. Handle IPO & Diversification
                    ipo_proceeds = 0.0
                    ipo_gains = 0.0
                    
                    if private_stock and ps_shares_remaining > 0:
                        # Check if IPO happened or is happening
                        if sim_calendar_year >= private_stock.ipo_year:
                            # Determine shares to sell
                            shares_to_sell = 0.0
                            
                            if private_stock.diversification_duration:
                                # Scheduled sale
                                if private_stock.diversification_start_year and sim_calendar_year >= private_stock.diversification_start_year:
                                    # Simple linear schedule: Total / Duration
                                    # But we need to stop when duration ends
                                    end_div_year = private_stock.diversification_start_year + private_stock.diversification_duration - 1
                                    if sim_calendar_year <= end_div_year:
                                        shares_to_sell = private_stock.shares / private_stock.diversification_duration
                                        shares_to_sell = min(shares_to_sell, ps_shares_remaining)
                            elif sim_calendar_year == private_stock.ipo_year:
                                # Immediate full sale if no schedule
                                shares_to_sell = ps_shares_remaining
                                
                            if shares_to_sell > 0:
                                proceed_val = shares_to_sell * ps_ipo_price
                                cost_val = 0 # Assume 0 cost basis for options/founder stock for simplicity unless provided
                                gain_val = proceed_val - cost_val
                                
                                ipo_proceeds = proceed_val
                                ipo_gains = gain_val
                                ps_shares_remaining -= shares_to_sell

                    # 5. Net "Cash Flow" for the year
                    # We need to cover 'annual_draw' (Post-Tax Need)
                    # We have W2 Income (Pre-Tax)
                    # We have IPO Proceeds (Pre-Tax)
                    
                    # Estimate Tax on W2 + IPO first
                    # We treat IPO gains as LTCG
                    estimated_tax_res = tax_engine.run_projection(
                        ordinary_income=annual_w2_income,
                        ltcg_income=ipo_gains
                    )
                    
                    total_tax_liability = estimated_tax_res.total_tax
                    
                    # Available Post-Tax Cash from Income/Events
                    post_tax_income = (annual_w2_income + ipo_proceeds) - total_tax_liability
                    
                    # Remaining Need
                    # If Income > Need -> Add to Liquid
                    # If Income < Need -> Withdraw from Liquid
                    net_cash_flow = post_tax_income - annual_draw
                    
                    path_withdrawals.append(annual_draw) # Log the Consumption Target
                    
                    gross_withdrawal = 0.0
                    
                    if net_cash_flow > 0:
                        # Surplus -> Save to Liquid
                        liquid_bal += net_cash_flow
                        liquid_basis += net_cash_flow # Added cash increases basis 1:1
                        monthly_draw = 0 # Covered by income
                        
                        # Tax on withdrawals is 0
                    else:
                        # Deficit -> Need to withdraw from portfolio
                        deficit = -net_cash_flow
                        
                        # We need to withdraw 'deficit' amount NET of taxes.
                        # This requires an iterative solve or gross-up because withdrawal triggers LTCG tax.
                        # Simplified Gross-Up:
                        # 1. Calculate Basis Ratio
                        if liquid_bal > 0:
                            basis_ratio = liquid_basis / liquid_bal
                        else:
                            basis_ratio = 1.0 # Fallback
                            
                        # 2. Assume marginal LTCG rate (e.g., 15% Fed + 9.3% CA ~ 25%)
                        # Better: Use TaxEngine to check marginal impact.
                        # For speed in sim loop, we'll use a simplified gross up if we have gains.
                        # Gain portion = (1 - basis_ratio)
                        
                        # Quick check on marginal bracket from the TaxResult above
                        # If we have room in 0% LTCG, great. Assume 20% blended for safety if not 0.
                        # Note: This is an approximation. A perfect solver is too slow for MC.
                        marginal_tax_rate = 0.0
                        
                        # Estimate Taxable Gain
                        est_gain = deficit * (1 - basis_ratio)
                        if est_gain > 0:
                            # We assume the gain stacks on top of the existing W2/IPO Income
                            # We can estimate the tax on this specific gain by asking TaxEngine
                            # We pass 'ipo_gains' (which is current base LTCG) + est_gain as the total LTCG
                            
                            base_ordinary = annual_w2_income
                            base_ltcg = ipo_gains
                            
                            # Run projection with the withdrawal included
                            proj_tax_res = tax_engine.run_projection(
                                ordinary_income=base_ordinary,
                                ltcg_income=base_ltcg + est_gain
                            )
                            
                            # Marginal Tax = (New Total Tax - Base Total Tax)
                            incremental_tax = proj_tax_res.total_tax - total_tax_liability
                            
                            # Effective Marginal Rate on the Gain
                            if incremental_tax > 0:
                                marginal_tax_rate = incremental_tax / est_gain
                                # Cap rate to avoid explosions (e.g. > 100%)
                                if marginal_tax_rate > 0.8: marginal_tax_rate = 0.8
                        
                        # Gross Up Formula:
                        # Withdrawal = NetNeeded + Tax
                        # Tax = (Withdrawal * (1 - BasisRatio)) * TaxRate
                        # Withdrawal = NetNeeded + (Withdrawal * (1 - BasisRatio) * TaxRate)
                        # Withdrawal * (1 - (1 - BasisRatio) * TaxRate) = NetNeeded
                        # Withdrawal = NetNeeded / (1 - (1 - BasisRatio) * TaxRate)
                        
                        denom = 1 - (1 - basis_ratio) * marginal_tax_rate
                        if denom <= 0.01: denom = 0.01 # Safety
                        
                        gross_withdrawal = deficit / denom
                        
                        monthly_draw = gross_withdrawal / 12.0
                        
                        # Add withdrawal tax to total tax liability
                        tax_on_withdrawal = gross_withdrawal - deficit
                        total_tax_liability += tax_on_withdrawal

                    # Log Taxes and Total Gross Income
                    path_taxes.append(total_tax_liability)
                    
                    # Total Gross Income = W2 + IPO Proceeds + Gross Withdrawal
                    # (Note: Technically "Income" for tax purposes is W2 + Gains, but "Cash Flow Income" usually includes Principal return too for metrics)
                    # Let's track "Total Gross Cash Inflow" before Tax
                    total_gross_inflow = annual_w2_income + ipo_proceeds + gross_withdrawal
                    path_incomes.append(total_gross_inflow)

                # Investment Return
                weighted_return = (stock_ret * self.stock_alloc) + (bond_monthly_rate * (1 - self.stock_alloc))
                
                # Apply returns to both buckets
                liquid_bal = liquid_bal * (1 + weighted_return)
                retirement_bal = retirement_bal * (1 + weighted_return)
                
                # Update Liquid Basis (Does not change with market value, only deposits/withdrawals)
                # No change to basis from market returns
                
                # Withdraw Logic (Monthly)
                # 1. Take from Liquid
                draw_needed = monthly_draw
                
                if liquid_bal >= draw_needed:
                    # Track Basis Reduction
                    if liquid_bal > 0:
                        basis_ratio = liquid_basis / liquid_bal
                        basis_reduction = draw_needed * basis_ratio
                        liquid_basis = max(0, liquid_basis - basis_reduction)
                        
                    liquid_bal -= draw_needed
                    draw_needed = 0
                else:
                    # Drain liquid
                    amount_taken = liquid_bal
                    if amount_taken > 0:
                         # Basis goes to 0
                         liquid_basis = 0
                    
                    draw_needed -= liquid_bal
                    liquid_bal = 0
                
                # 2. If still need money, try Retirement
                if draw_needed > 0:
                    if sim_age >= ACCESS_AGE:
                        if retirement_bal >= draw_needed:
                            retirement_bal -= draw_needed
                            draw_needed = 0
                        else:
                            draw_needed -= retirement_bal
                            retirement_bal = 0
                            failed = True # Ran out of money completely
                    else:
                        # Cannot access retirement yet -> Failure or massive penalty
                        # User selected "Separate buckets (Liquid vs 401k). Withdraw from Liquid first. If Liquid runs out before 65, fail"
                        failed = True
                
                if failed:
                    liquid_bal = 0
                    retirement_bal = 0
                
                total_balance = liquid_bal + retirement_bal
                path_balances.append(total_balance)
            
            sim_balances.append(path_balances)
            sim_withdrawals.append(path_withdrawals)
            sim_taxes.append(path_taxes)
            sim_incomes.append(path_incomes)
            
        return SimulationResult(
            balances=pd.DataFrame(sim_balances),
            withdrawals=pd.DataFrame(sim_withdrawals),
            taxes=pd.DataFrame(sim_taxes),
            total_income=pd.DataFrame(sim_incomes),
            start_dates=start_dates
        )

    def calculate_stats(self, result: SimulationResult, inflation_rate: float = 0.0):
        if result.balances.empty:
            return {}
            
        final_values = result.balances.iloc[:, -1]
        success_count = (final_values > 0).sum()
        total_sims = len(final_values)
        
        # Convert Nominal Withdrawals to Real for stats
        real_withdrawals = result.withdrawals.copy()
        if inflation_rate != 0.0:
            for col in real_withdrawals.columns:
                try:
                    year = int(col)
                    deflator = (1 + inflation_rate) ** year
                    real_withdrawals[col] = real_withdrawals[col] / deflator
                except:
                    pass # Should be int columns 0..N
        
        min_annual_spend = real_withdrawals.min().min()
        median_annual_spend = real_withdrawals.median().median()

        return {
            "success_rate": success_count / total_sims if total_sims > 0 else 0,
            "median_end_value": final_values.median(),
            "min_end_value": final_values.min(),
            "max_end_value": final_values.max(),
            "min_annual_spend": min_annual_spend,
            "median_annual_spend": median_annual_spend
        }
