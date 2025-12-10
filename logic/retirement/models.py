import pandas as pd
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class PrivateStock:
    """Configuration for private/concentrated stock holdings."""
    shares: float
    ipo_year: int
    ipo_price: float
    diversification_start_year: Optional[int] = None
    diversification_duration: Optional[int] = None
    growth_multiplier: float = 1.0  # Multiplier relative to market returns (1.0 = same as market, 0.0 = no growth)


@dataclass
class IncomeStream:
    """Represents a source of income over a time period."""
    name: str
    start_year: int
    end_year: int
    annual_amount: float
    taxable: bool = True


@dataclass
class WithdrawalResult:
    """Tracks the source and amounts of a withdrawal for proper tax treatment."""
    success: bool
    from_liquid: float = 0.0
    from_retirement: float = 0.0
    liquid_gains: float = 0.0  # Taxable gains from liquid withdrawal
    early_withdrawal_penalty: float = 0.0  # 10% penalty if applicable


@dataclass
class SimulationResult:
    """Contains all outputs from a retirement simulation run."""
    balances: pd.DataFrame  # Rows: simulations, Cols: months (total portfolio + private stock)
    withdrawals: pd.DataFrame  # Rows: simulations, Cols: years (Annual amounts)
    taxes: pd.DataFrame  # Rows: simulations, Cols: years (Annual tax liability)
    total_income: pd.DataFrame  # Rows: simulations, Cols: years (Total Gross Income from all sources)
    gross_withdrawals: pd.DataFrame  # Rows: simulations, Cols: years (Actual gross withdrawal amount)
    start_dates: List[pd.Timestamp]  # Start date for each simulation
    # Detailed tracking fields
    portfolio_values: pd.DataFrame = None  # Rows: simulations, Cols: years (liquid + retirement, end of year)
    private_stock_values: pd.DataFrame = None  # Rows: simulations, Cols: years (concentrated stock value, end of year)
    portfolio_gains: pd.DataFrame = None  # Rows: simulations, Cols: years (annual investment gain on diversified portfolio)
    private_stock_gains: pd.DataFrame = None  # Rows: simulations, Cols: years (annual $ gain on concentrated stock)
    ipo_proceeds: pd.DataFrame = None  # Rows: simulations, Cols: years (proceeds from stock sales)
    deposits: pd.DataFrame = None  # Rows: simulations, Cols: years (deposits from income surplus)


@dataclass
class SimulationConfig:
    """Bundles all simulation parameters into a single configuration object."""
    initial_portfolio: float
    duration_years: int
    initial_annual_withdrawal: float
    spending_schedule: Optional[pd.Series]
    initial_401k: float
    current_age: int
    private_stock: Optional[PrivateStock]
    income_streams: List[IncomeStream]
    location: str
    start_year: int
    allow_early_retirement_access: bool
    early_withdrawal_penalty_rate: float
    access_age: int


@dataclass
class YearState:
    """Tracks mutable state during annual processing within a simulation."""
    calendar_year: int
    year_offset: int
    age: int
    previous_withdrawal: float
    monthly_draw: float = 0.0

