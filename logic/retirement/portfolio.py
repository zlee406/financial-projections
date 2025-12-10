from typing import Optional, Tuple

from logic.retirement.models import PrivateStock, WithdrawalResult


class Portfolio:
    """
    Manages liquid (taxable) and retirement (tax-deferred) assets.
    
    Tracks cost basis for liquid assets to properly calculate capital gains
    on withdrawals. Handles withdrawal ordering (liquid first, then retirement)
    and applies early withdrawal penalties when applicable.
    """
    
    def __init__(self, liquid_assets: float, retirement_assets: float):
        self.liquid = liquid_assets
        self.retirement = retirement_assets
        self.liquid_basis = liquid_assets  # Assume starting liquid is post-tax principal

    @property
    def total_value(self) -> float:
        return self.liquid + self.retirement

    @property
    def basis_ratio(self) -> float:
        """Returns the proportion of liquid assets that is cost basis (not gains)."""
        if self.liquid > 0:
            return self.liquid_basis / self.liquid
        return 1.0

    def apply_market_return(self, weighted_return: float) -> None:
        """Apply market returns to both liquid and retirement accounts."""
        self.liquid *= (1 + weighted_return)
        self.retirement *= (1 + weighted_return)
        # Basis does not change with market return

    def deposit_liquid(self, amount: float) -> None:
        """Add post-tax cash to liquid assets (increases basis 1:1)."""
        if amount > 0:
            self.liquid += amount
            self.liquid_basis += amount

    def withdraw(
        self,
        amount: float,
        current_age: int,
        access_age: int = 60,
        allow_early_retirement_access: bool = True,
        early_withdrawal_penalty_rate: float = 0.10
    ) -> WithdrawalResult:
        """
        Withdraw funds, taking from liquid first then retirement.
        
        Args:
            amount: Amount to withdraw
            current_age: Current age of retiree
            access_age: Age at which retirement accounts can be accessed penalty-free
            allow_early_retirement_access: If True, allows retirement access before access_age with penalty
            early_withdrawal_penalty_rate: Penalty rate for early withdrawal (default 10%)
        
        Returns:
            WithdrawalResult with success status and breakdown of withdrawal sources
        """
        if amount <= 0:
            return WithdrawalResult(success=True)
        
        result = WithdrawalResult(success=False)
        remaining = amount
            
        # 1. Take from Liquid first
        if self.liquid > 0:
            from_liquid = min(self.liquid, remaining)
            
            # Calculate gains portion for tax purposes
            gains_ratio = 1.0 - self.basis_ratio
            result.liquid_gains = from_liquid * gains_ratio
            
            # Track Basis Reduction
            basis_reduction = from_liquid * self.basis_ratio
            self.liquid_basis = max(0, self.liquid_basis - basis_reduction)
            
            self.liquid -= from_liquid
            result.from_liquid = from_liquid
            remaining -= from_liquid
        
        if remaining <= 0:
            result.success = True
            return result
        
        # 2. Take from Retirement
        can_access_retirement = current_age >= access_age or allow_early_retirement_access
        
        if can_access_retirement and self.retirement > 0:
            from_retirement = min(self.retirement, remaining)
            self.retirement -= from_retirement
            result.from_retirement = from_retirement
            remaining -= from_retirement
            
            # Apply early withdrawal penalty if under access age
            if current_age < access_age:
                result.early_withdrawal_penalty = from_retirement * early_withdrawal_penalty_rate
        
        result.success = remaining <= 0
        return result
    
    def withdraw_simple(
        self,
        amount: float,
        current_age: int,
        access_age: int = 60,
        allow_early_retirement_access: bool = True
    ) -> bool:
        """Simple withdraw that returns just success/failure for backward compatibility."""
        result = self.withdraw(amount, current_age, access_age, allow_early_retirement_access)
        return result.success


class PrivateStockManager:
    """
    Manages private stock holdings, IPO timing, and diversification schedules.
    
    Tracks share count, current price (which can grow relative to market),
    and handles scheduled sales based on IPO year and diversification plans.
    """
    
    def __init__(self, private_stock: Optional[PrivateStock]):
        self.stock = private_stock
        self.shares_remaining = private_stock.shares if private_stock else 0.0
        self.ipo_price = private_stock.ipo_price if private_stock else 0.0
        self.current_price = self.ipo_price
        self.growth_multiplier = private_stock.growth_multiplier if private_stock else 1.0

    @property
    def current_value(self) -> float:
        return self.shares_remaining * self.current_price

    def apply_market_return(self, market_return: float) -> None:
        """Apply market-relative growth to the private stock price."""
        if self.shares_remaining > 0 and self.growth_multiplier != 0:
            adjusted_return = market_return * self.growth_multiplier
            self.current_price *= (1 + adjusted_return)

    def check_for_sales(self, current_year: int) -> Tuple[float, float]:
        """
        Check if stock should be sold in the current year based on IPO/diversification schedule.
        
        Returns:
            Tuple of (proceeds, gains) from any stock sales
        """
        if not self.stock or self.shares_remaining <= 0:
            return 0.0, 0.0
            
        if current_year < self.stock.ipo_year:
            return 0.0, 0.0
            
        shares_to_sell = 0.0
        
        if self.stock.diversification_duration:
            # Scheduled sale over diversification period
            start = self.stock.diversification_start_year
            if start and current_year >= start:
                end_div_year = start + self.stock.diversification_duration - 1
                if current_year <= end_div_year:
                    # Linear schedule: Total / Duration
                    shares_to_sell = self.stock.shares / self.stock.diversification_duration
                    shares_to_sell = min(shares_to_sell, self.shares_remaining)
        elif current_year == self.stock.ipo_year:
            # Immediate full sale if no diversification schedule
            shares_to_sell = self.shares_remaining
             
        if shares_to_sell > 0:
            proceed_val = shares_to_sell * self.current_price
            cost_val = 0  # Assume 0 cost basis for options/founder stock
            gain_val = proceed_val - cost_val
            
            self.shares_remaining -= shares_to_sell
            return proceed_val, gain_val
            
        return 0.0, 0.0

