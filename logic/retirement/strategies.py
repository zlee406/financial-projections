import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class WithdrawalStrategy(ABC):
    """
    Abstract base class for all withdrawal strategies.
    
    All strategies must implement calculate_withdrawal(). The base class provides
    default implementations for limits and flexible spending that can be overridden.
    """
    
    # Default values - overridden by BaseStrategy and subclasses
    flexible_spending: bool = False
    flexible_floor_pct: float = 0.75
    inflation_rate: float = 0.03
    
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
        inflation_rate: float = 0.03,
        min_withdrawal: Optional[float] = None,
        max_withdrawal: Optional[float] = None,
        flexible_spending: bool = False,
        flexible_floor_pct: float = 0.75
    ):
        self.inflation_rate = inflation_rate
        self.min_withdrawal = min_withdrawal
        self.max_withdrawal = max_withdrawal
        self.flexible_spending = flexible_spending
        self.flexible_floor_pct = flexible_floor_pct

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
        """
        if spending_schedule is None:
            return amount
            
        required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
        cumulative_inflation = (1 + self.inflation_rate) ** year
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
    Otherwise inflates the initial withdrawal amount each year.
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
            cumulative_inflation = (1 + self.inflation_rate) ** year
            val = required_real * cumulative_inflation
        else:
            if year == 0:
                val = initial_withdrawal
            else:
                val = previous_withdrawal * (1 + self.inflation_rate)
        
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
        inflation_rate: float = 0.03,
        min_withdrawal: Optional[float] = None,
        max_withdrawal: Optional[float] = None,
        flexible_spending: bool = False,
        flexible_floor_pct: float = 0.75
    ):
        super().__init__(inflation_rate, min_withdrawal, max_withdrawal, flexible_spending, flexible_floor_pct)
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
        inflation_rate: float = 0.03,
        min_withdrawal: Optional[float] = None,
        max_withdrawal: Optional[float] = None
    ):
        super().__init__(inflation_rate, min_withdrawal, max_withdrawal)
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
        start_age: int = 40,
        max_age: int = 100,
        inflation_rate: float = 0.03,
        min_withdrawal: Optional[float] = None,
        max_withdrawal: Optional[float] = None,
        flexible_spending: bool = False,
        flexible_floor_pct: float = 0.75
    ):
        super().__init__(inflation_rate, min_withdrawal, max_withdrawal, flexible_spending, flexible_floor_pct)
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
        inflation_rate: float = 0.03,
        floor_pct: float = 0.85,
        ceiling_pct: float = 1.15,
        min_withdrawal: Optional[float] = None,
        max_withdrawal: Optional[float] = None
    ):
        super().__init__(inflation_rate, min_withdrawal, max_withdrawal)
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
        inflation_rate: float = 0.03,
        guardrail_upper: float = 0.20,
        guardrail_lower: float = 0.20,
        min_withdrawal: Optional[float] = None,
        max_withdrawal: Optional[float] = None,
        flexible_spending: bool = False,
        flexible_floor_pct: float = 0.75
    ):
        super().__init__(inflation_rate, min_withdrawal, max_withdrawal, flexible_spending, flexible_floor_pct)
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
            
        # Calculate proposed withdrawal
        if spending_schedule is not None:
            required_real = spending_schedule.iloc[year] if year < len(spending_schedule) else spending_schedule.iloc[-1]
            cumulative_inflation = (1 + self.inflation_rate) ** year
            proposed_withdrawal = required_real * cumulative_inflation
        else:
            proposed_withdrawal = previous_withdrawal * (1 + self.inflation_rate)
            
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

