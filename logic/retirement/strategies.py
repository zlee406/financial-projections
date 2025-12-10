import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, List


# Strategy descriptions for UI display
STRATEGY_DESCRIPTIONS: Dict[str, str] = {
    "Schedule Only": (
        "Withdraws exactly what your spending schedule requires each year, adjusted for inflation. "
        "No min/max limits or guardrails are applied. This is the simplest strategy and shows "
        "whether your portfolio can sustain your planned spending without any adjustments."
    ),
    "Constant Dollar (Targets Schedule)": (
        "Targets your spending schedule but applies min/max withdrawal limits. If your portfolio "
        "drops significantly, the strategy will still withdraw at least the minimum amount. "
        "Good for retirees who want predictable spending with some guardrails."
    ),
    "Percent of Portfolio": (
        "Withdraws a fixed percentage of your current portfolio value each year (e.g., 4%). "
        "Spending automatically adjusts with market performance - you spend more in good years "
        "and less in bad years. Highly sustainable but can lead to variable income."
    ),
    "VPW": (
        "Variable Percentage Withdrawal adjusts your withdrawal rate based on remaining life "
        "expectancy. Younger retirees withdraw less; older retirees withdraw more. Designed "
        "to deplete your portfolio smoothly over your lifetime while maximizing spending."
    ),
    "Guyton-Klinger": (
        "Uses 'guardrails' to adjust spending when your withdrawal rate drifts too far from "
        "target. If markets drop and your rate exceeds the upper guardrail, spending is cut 10%. "
        "If markets rise and your rate falls below the lower guardrail, spending increases 10%. "
        "Balances stability with portfolio preservation."
    ),
    "Essential + Discretionary": (
        "Always withdraws Essential costs (mortgage, taxes, groceries, utilities) regardless of "
        "market performance. Discretionary costs (travel, dining, gifts) are only withdrawn if "
        "portfolio 'capacity' allows (based on a safe withdrawal rate). During market crashes, "
        "this automatically cuts vacations but keeps bills paid - modeling realistic retiree behavior."
    ),
}


def get_strategy_description(strategy_name: str) -> str:
    """Get the description for a withdrawal strategy by name."""
    return STRATEGY_DESCRIPTIONS.get(strategy_name, "No description available.")


def get_all_strategy_names() -> list:
    """Get list of all available strategy names."""
    return list(STRATEGY_DESCRIPTIONS.keys())


def calculate_cumulative_inflation(annual_inflation_rates: List[float], year: int) -> float:
    """
    Calculate cumulative inflation factor from year 0 to the given year.
    
    Args:
        annual_inflation_rates: List of annual inflation rates for each year
        year: The year offset (0-indexed) to calculate cumulative inflation for
        
    Returns:
        Cumulative inflation factor (multiply real dollars by this to get nominal)
    """
    if year == 0 or not annual_inflation_rates:
        return 1.0
    
    # Product of (1 + rate) for years 0 through year-1
    cumulative = 1.0
    for i in range(min(year, len(annual_inflation_rates))):
        cumulative *= (1 + annual_inflation_rates[i])
    
    return cumulative


class WithdrawalStrategy(ABC):
    """
    Abstract base class for all withdrawal strategies.
    
    All strategies must implement calculate_withdrawal(). The base class provides
    default implementations for limits and flexible spending that can be overridden.
    
    Strategies receive annual inflation rates as a list, one rate per year of simulation.
    This allows using historical inflation data aligned with each backtest period.
    """
    
    # Default values - overridden by BaseStrategy and subclasses
    flexible_spending: bool = False
    flexible_floor_pct: float = 0.75
    annual_inflation_rates: List[float] = []
    
    @abstractmethod
    def calculate_withdrawal(
        self,
        current_portfolio_value: float,
        year: int,
        initial_withdrawal: float,
        previous_withdrawal: float,
        spending_schedule: Optional[pd.Series] = None
    ) -> float:
        """
        Calculates the withdrawal amount for the current year.
        
        Args:
            current_portfolio_value: Current total portfolio value
            year: Year offset from start (0-indexed)
            initial_withdrawal: First year's withdrawal amount
            previous_withdrawal: Last year's withdrawal amount
            spending_schedule: Series of REAL required spending for each year [0..duration]
        
        Returns:
            Withdrawal amount for the current year (nominal dollars)
        """
        ...
    
    def set_inflation_rates(self, rates: List[float]) -> None:
        """Set the annual inflation rates for this simulation period."""
        self.annual_inflation_rates = rates
    
    def get_cumulative_inflation(self, year: int) -> float:
        """Get cumulative inflation factor from year 0 to given year."""
        return calculate_cumulative_inflation(self.annual_inflation_rates, year)
    
    def get_year_inflation(self, year: int) -> float:
        """Get the inflation rate for a specific year."""
        if not self.annual_inflation_rates or year >= len(self.annual_inflation_rates):
            return 0.03  # Fallback to 3% if no data
        return self.annual_inflation_rates[year]
    
    def apply_limits(self, amount: float) -> float:
        """Apply min/max limits to withdrawal. Default is no-op."""
        return amount
    
    def get_min_max_limits(self) -> Tuple[Optional[float], Optional[float]]:
        """Return (min_withdrawal, max_withdrawal) tuple."""
        return None, None


class BaseStrategy(WithdrawalStrategy):
    """
    Base implementation with configurable limits and flexible spending support.
    
    Provides common functionality for min/max limits and spending schedule floors.
    All concrete strategies should inherit from this class.
    """
    
    def __init__(
        self,
        min_withdrawal: Optional[float],
        max_withdrawal: Optional[float],
        flexible_spending: bool,
        flexible_floor_pct: float
    ):
        self.min_withdrawal = min_withdrawal
        self.max_withdrawal = max_withdrawal
        self.flexible_spending = flexible_spending
        self.flexible_floor_pct = flexible_floor_pct
        self.annual_inflation_rates: List[float] = []

    def apply_limits(self, amount: float) -> float:
        """Apply min/max withdrawal limits."""
        if self.min_withdrawal is not None:
            amount = max(amount, self.min_withdrawal)
        if self.max_withdrawal is not None:
            amount = min(amount, self.max_withdrawal)
        return amount
    
    def apply_schedule_floor(
        self,
        amount: float,
        spending_schedule: Optional[pd.Series],
        year: int
    ) -> float:
        """
        Apply spending schedule floor with flexibility option.
        
        If flexible_spending is True, allows spending to drop to flexible_floor_pct
        of the scheduled amount. Otherwise enforces the full scheduled spending.
        Uses historical inflation rates for the simulation period.
        """
        if spending_schedule is None:
            return amount
            
        required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
        cumulative_inflation = self.get_cumulative_inflation(year)
        floor_val = required_real * cumulative_inflation
        
        if self.flexible_spending:
            flexible_floor = floor_val * self.flexible_floor_pct
            return max(amount, flexible_floor)
        else:
            return max(amount, floor_val)

    def get_min_max_limits(self) -> Tuple[Optional[float], Optional[float]]:
        return self.min_withdrawal, self.max_withdrawal


class ConstantDollarStrategy(BaseStrategy):
    """
    Withdraws a constant real amount, adjusted for inflation each year.
    
    If a spending schedule is provided, targets each year's scheduled real spending.
    Otherwise inflates the initial withdrawal amount each year using historical inflation.
    """

    def calculate_withdrawal(
        self,
        current_portfolio_value: float,
        year: int,
        initial_withdrawal: float,
        previous_withdrawal: float,
        spending_schedule: Optional[pd.Series] = None
    ) -> float:
        if spending_schedule is not None:
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = self.get_cumulative_inflation(year)
            val = required_real * cumulative_inflation
        else:
            if year == 0:
                val = initial_withdrawal
            else:
                year_inflation = self.get_year_inflation(year - 1)
                val = previous_withdrawal * (1 + year_inflation)
        
        val = self.apply_limits(val)
        val = self.apply_schedule_floor(val, spending_schedule, year)
        return val


class PercentPortfolioStrategy(BaseStrategy):
    """
    Withdraws a fixed percentage of current portfolio value each year.
    """
    
    def __init__(
        self,
        percentage: float,
        min_withdrawal: Optional[float],
        max_withdrawal: Optional[float],
        flexible_spending: bool,
        flexible_floor_pct: float
    ):
        super().__init__(min_withdrawal, max_withdrawal, flexible_spending, flexible_floor_pct)
        self.percentage = percentage

    def calculate_withdrawal(
        self,
        current_portfolio_value: float,
        year: int,
        initial_withdrawal: float,
        previous_withdrawal: float,
        spending_schedule: Optional[pd.Series] = None
    ) -> float:
        val = current_portfolio_value * self.percentage
        val = self.apply_limits(val)
        val = self.apply_schedule_floor(val, spending_schedule, year)
        return val


class EndowmentStrategy(BaseStrategy):
    """
    Withdraws a fixed percentage of portfolio, similar to university endowments.
    
    Currently identical to PercentPortfolioStrategy but could include
    smoothing logic in the future.
    """
    
    def __init__(
        self,
        percentage: float,
        min_withdrawal: Optional[float],
        max_withdrawal: Optional[float],
        flexible_spending: bool,
        flexible_floor_pct: float
    ):
        super().__init__(min_withdrawal, max_withdrawal, flexible_spending, flexible_floor_pct)
        self.percentage = percentage

    def calculate_withdrawal(
        self,
        current_portfolio_value: float,
        year: int,
        initial_withdrawal: float,
        previous_withdrawal: float,
        spending_schedule: Optional[pd.Series] = None
    ) -> float:
        return self.apply_limits(current_portfolio_value * self.percentage)


class VPWStrategy(BaseStrategy):
    """
    Variable Percentage Withdrawal strategy based on remaining life expectancy.
    
    Calculates withdrawal rate using actuarial present value formula,
    assuming a 5% real return.
    """
    
    def __init__(
        self,
        start_age: int,
        max_age: int,
        min_withdrawal: Optional[float],
        max_withdrawal: Optional[float],
        flexible_spending: bool,
        flexible_floor_pct: float
    ):
        super().__init__(min_withdrawal, max_withdrawal, flexible_spending, flexible_floor_pct)
        self.start_age = start_age
        self.max_age = max_age

    def calculate_withdrawal(
        self,
        current_portfolio_value: float,
        year: int,
        initial_withdrawal: float,
        previous_withdrawal: float,
        spending_schedule: Optional[pd.Series] = None
    ) -> float:
        current_age = self.start_age + year
        remaining_years = max(1, self.max_age - current_age)
        
        # Assume 5% real return for the schedule
        assumed_real_return = 0.05
        if assumed_real_return == 0:
            rate = 1.0 / remaining_years
        else:
            rate = assumed_real_return / (1 - (1 + assumed_real_return) ** -remaining_years)
            
        val = current_portfolio_value * rate
        val = self.apply_limits(val)
        val = self.apply_schedule_floor(val, spending_schedule, year)
        return val


class FloorCeilingStrategy(BaseStrategy):
    """
    Maintains withdrawals within a floor/ceiling band around the initial amount.
    """
    
    def __init__(
        self,
        floor_pct: float,
        ceiling_pct: float,
        min_withdrawal: Optional[float],
        max_withdrawal: Optional[float],
        flexible_spending: bool,
        flexible_floor_pct: float
    ):
        super().__init__(min_withdrawal, max_withdrawal, flexible_spending, flexible_floor_pct)
        self.floor_pct = floor_pct
        self.ceiling_pct = ceiling_pct
        self.base_real_withdrawal = None

    def calculate_withdrawal(
        self,
        current_portfolio_value: float,
        year: int,
        initial_withdrawal: float,
        previous_withdrawal: float,
        spending_schedule: Optional[pd.Series] = None
    ) -> float:
        # Placeholder implementation
        return self.apply_limits(initial_withdrawal)


class GuytonKlingerStrategy(BaseStrategy):
    """
    Guyton-Klinger decision rules with guardrails.
    
    Adjusts withdrawals up or down by 10% when current withdrawal rate
    crosses upper or lower guardrails relative to the initial rate.
    """
    
    def __init__(
        self,
        initial_rate: float,
        portfolio_value: float,
        guardrail_upper: float,
        guardrail_lower: float,
        min_withdrawal: Optional[float],
        max_withdrawal: Optional[float],
        flexible_spending: bool,
        flexible_floor_pct: float
    ):
        super().__init__(min_withdrawal, max_withdrawal, flexible_spending, flexible_floor_pct)
        self.initial_rate_pct = initial_rate
        self.guardrail_upper_threshold = initial_rate * (1 - guardrail_upper)
        self.guardrail_lower_threshold = initial_rate * (1 + guardrail_lower)

    def calculate_withdrawal(
        self,
        current_portfolio_value: float,
        year: int,
        initial_withdrawal: float,
        previous_withdrawal: float,
        spending_schedule: Optional[pd.Series] = None
    ) -> float:
        if current_portfolio_value <= 0:
            return 0.0
            
        # Calculate proposed withdrawal using historical inflation
        if spending_schedule is not None:
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = self.get_cumulative_inflation(year)
            proposed_withdrawal = required_real * cumulative_inflation
        else:
            year_inflation = self.get_year_inflation(year - 1) if year > 0 else 0.0
            proposed_withdrawal = previous_withdrawal * (1 + year_inflation)
            
        current_wr = proposed_withdrawal / current_portfolio_value
        final_amount = proposed_withdrawal
        
        # Apply guardrail adjustments
        if current_wr > self.guardrail_lower_threshold:
            final_amount = final_amount * 0.90
        elif current_wr < self.guardrail_upper_threshold:
            final_amount = final_amount * 1.10
            
        final_amount = self.apply_limits(final_amount)
        final_amount = self.apply_schedule_floor(final_amount, spending_schedule, year)
        return final_amount


class ScheduleOnlyStrategy(WithdrawalStrategy):
    """
    Withdraws exactly the spending schedule amount with no adjustments.
    
    This is the simplest strategy - it takes the scheduled real spending for each
    year and adjusts it for historical inflation. No min/max limits, no flexible floors,
    no guardrails. Useful as a baseline to see if your portfolio can sustain
    your planned spending without any safety mechanisms.
    """
    
    def __init__(self):
        self.flexible_spending = False
        self.flexible_floor_pct = 1.0  # Not used, but required by base class interface
        self.annual_inflation_rates: List[float] = []

    def calculate_withdrawal(
        self,
        current_portfolio_value: float,
        year: int,
        initial_withdrawal: float,
        previous_withdrawal: float,
        spending_schedule: Optional[pd.Series] = None
    ) -> float:
        """
        Returns exactly the scheduled spending amount, adjusted for historical inflation.
        
        If no schedule is provided, inflates the initial withdrawal each year.
        """
        if spending_schedule is not None:
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = self.get_cumulative_inflation(year)
            return required_real * cumulative_inflation
        else:
            # No schedule - just inflate the initial withdrawal
            if year == 0:
                return initial_withdrawal
            else:
                year_inflation = self.get_year_inflation(year - 1)
                return previous_withdrawal * (1 + year_inflation)

    def apply_limits(self, amount: float) -> float:
        """No limits applied - returns amount unchanged."""
        return amount

    def get_min_max_limits(self) -> Tuple[Optional[float], Optional[float]]:
        """No limits configured."""
        return None, None


class EssentialDiscretionaryStrategy(WithdrawalStrategy):
    """
    Withdraws 100% of Essential costs always, Discretionary costs only if capacity allows.
    
    This strategy models realistic retiree behavior:
    - Essential costs (mortgage, taxes, groceries, utilities) are ALWAYS withdrawn
    - Discretionary costs (travel, dining, gifts) are only withdrawn if the portfolio
      has sufficient "capacity" based on a safe withdrawal rate
    
    During market crashes, this automatically cuts discretionary spending while
    keeping essential bills paid - you don't sell stocks at rock bottom to pay
    for a vacation you wouldn't actually take.
    
    Decision Rules:
    1. If Capacity >= (Essential + Discretionary): Withdraw full target
    2. If Capacity <= Essential: Withdraw Essential only (portfolio takes a hit but bills are paid)
    3. If Essential < Capacity < Full: Withdraw Capacity (pay bills + partial discretionary)
    """
    
    def __init__(
        self,
        capacity_rate: float = 0.04,
        spending_schedule_df: Optional[pd.DataFrame] = None
    ):
        """
        Args:
            capacity_rate: Safe withdrawal rate used to determine capacity (e.g., 0.04 = 4%)
            spending_schedule_df: Full DataFrame with Essential_Real_Spend and Discretionary_Real_Spend columns
        """
        self.capacity_rate = capacity_rate
        self.spending_schedule_df = spending_schedule_df
        self.flexible_spending = False
        self.flexible_floor_pct = 1.0
        self.annual_inflation_rates: List[float] = []

    def calculate_withdrawal(
        self,
        current_portfolio_value: float,
        year: int,
        initial_withdrawal: float,
        previous_withdrawal: float,
        spending_schedule: Optional[pd.Series] = None
    ) -> float:
        """
        Calculate withdrawal using Essential + Discretionary logic.
        
        Always withdraws Essential, then adds Discretionary only if capacity allows.
        """
        # 1. Get Real Costs from DataFrame columns
        if self.spending_schedule_df is not None and year < len(self.spending_schedule_df):
            essential_real = self.spending_schedule_df.iloc[year]['Essential_Real_Spend']
            discretionary_real = self.spending_schedule_df.iloc[year]['Discretionary_Real_Spend']
        elif spending_schedule is not None and year < len(spending_schedule):
            # Fallback: if no DF, use the regular schedule and assume 60/40 split
            total_real = spending_schedule.iloc[year]
            essential_real = total_real * 0.6
            discretionary_real = total_real * 0.4
        else:
            # Last resort fallback
            essential_real = initial_withdrawal * 0.6
            discretionary_real = initial_withdrawal * 0.4
        
        # 2. Convert to Nominal (adjust for inflation)
        cumulative_inflation = self.get_cumulative_inflation(year)
        nom_essential = essential_real * cumulative_inflation
        nom_discretionary = discretionary_real * cumulative_inflation
        
        # 3. Calculate Capacity (safe amount available based on portfolio value)
        capacity = current_portfolio_value * self.capacity_rate
        
        # 4. Decision Rule
        full_target = nom_essential + nom_discretionary
        
        if capacity >= full_target:
            # Portfolio can support full spending
            return full_target
        elif capacity <= nom_essential:
            # Portfolio capacity is below essential needs - withdraw essential anyway
            # Bills must be paid even if portfolio takes a hit
            return nom_essential
        else:
            # Essential < Capacity < Full: Pay essential + whatever discretionary we can afford
            return capacity

    def apply_limits(self, amount: float) -> float:
        """No additional limits applied."""
        return amount

    def get_min_max_limits(self) -> Tuple[Optional[float], Optional[float]]:
        """No limits configured for this strategy."""
        return None, None

