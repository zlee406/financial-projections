"""
Retirement simulation package.

This package provides tools for backtesting retirement withdrawal strategies
using historical market data, with support for taxes, income streams,
private stock holdings, and various withdrawal strategies.

All public classes are re-exported here for backward compatibility.
"""

# Models
from logic.retirement.models import (
    PrivateStock,
    IncomeStream,
    WithdrawalResult,
    SimulationResult,
    SimulationConfig,
    YearState,
)

# Strategies
from logic.retirement.strategies import (
    WithdrawalStrategy,
    BaseStrategy,
    ConstantDollarStrategy,
    PercentPortfolioStrategy,
    EndowmentStrategy,
    VPWStrategy,
    FloorCeilingStrategy,
    GuytonKlingerStrategy,
    ScheduleOnlyStrategy,
    EssentialDiscretionaryStrategy,
    STRATEGY_DESCRIPTIONS,
    get_strategy_description,
    get_all_strategy_names,
)

# Portfolio management
from logic.retirement.portfolio import (
    Portfolio,
    PrivateStockManager,
)

# Engine
from logic.retirement.engine import (
    BacktestEngine,
)

__all__ = [
    # Models
    "PrivateStock",
    "IncomeStream",
    "WithdrawalResult",
    "SimulationResult",
    "SimulationConfig",
    "YearState",
    # Strategies
    "WithdrawalStrategy",
    "BaseStrategy",
    "ConstantDollarStrategy",
    "PercentPortfolioStrategy",
    "EndowmentStrategy",
    "VPWStrategy",
    "FloorCeilingStrategy",
    "GuytonKlingerStrategy",
    "ScheduleOnlyStrategy",
    "EssentialDiscretionaryStrategy",
    "STRATEGY_DESCRIPTIONS",
    "get_strategy_description",
    "get_all_strategy_names",
    # Portfolio
    "Portfolio",
    "PrivateStockManager",
    # Engine
    "BacktestEngine",
]
