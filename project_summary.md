# Project Status & Handover Notes

## Overview
This project is a local, privacy-focused financial planning dashboard built with **Streamlit** and **Python**. It replicates and extends the functionality of tools like `ficalc.app`, focusing on historical backtesting for retirement planning, tax modeling (ISO/AMT), and granular lifecycle expense modeling.

## Features Implemented

### 1. Retirement Planning Engine (`logic/retirement.py`)
-   **Historical Backtesting**: Simulates portfolio survival using S&P 500 data (`^GSPC`) fetched via `yfinance` (cached in `data/`).
-   **Rolling Cohort Analysis**: Tests every possible 30+ year period in history to determine success rates.
-   **Portfolio Buckets**:
    -   **Liquid Assets**: Primary withdrawal source.
    -   **Retirement Assets (401k)**: Accessed only after age 59.5.
    -   **Private Stock**: Models future windfall (IPO/Exit) events.
-   **Withdrawal Strategies**:
    -   **Constant Dollar**: Traditional "4% Rule" style (inflation-adjusted).
    -   **Percent of Portfolio**: Variable withdrawal based on current value.
    -   **VPW (Variable Percentage Withdrawal)**: Bogleheads strategy based on mortality/life expectancy.
    -   **Guyton-Klinger Guardrails**: Dynamic spending rules (Prosperity/Capital Preservation) to adjust spending in extreme markets.

### 2. Scenario & Strategy Management (`app.py`, `logic/lifecycle.py`)
-   **Decoupled Architecture**: Separation of "Spending Needs" from "Portfolio Composition".
-   **Spending Strategies**:
    -   Create named profiles (e.g., "Lean FIRE", "Fat FIRE", "Alabama Relocation").
    -   **Granular Inputs**: Base Spend, Location (Tax impact), Mortgage (drop-off logic), Children (Age-based costs), Future Home Purchases.
-   **Portfolio Strategies**:
    -   Create named portfolios (e.g., "Aggressive Growth", "Cash Heavy").
    -   **Inputs**: Liquid/Retirement split, Stock Allocation, Bond Return, Inflation Rate, Private Stock Valuation.
-   **Persistence**: Automatic saving/loading of all strategies to `data/strategies.json`.

### 3. Analytics & Visualization (`app.py`)
-   **Retirement Analysis Tab**: Run simulations by mixing and matching any Portfolio Strategy with any Spending Strategy.
-   **Compare Strategies Tab**: Side-by-side comparison of success rates, median ending wealth, and wealth trajectories for multiple scenarios.
-   **Visualizations**:
    -   **Cone of Uncertainty**: 10th/50th/90th percentile portfolio paths.
    -   **Spending Schedule**: Bar chart of projected future real costs.
    -   **Portfolio Breakdown**: Donut chart of current net worth components.

### 4. Tax Engine (`logic/tax.py`)
-   **Tax Engine**: Detailed calculation of Federal, State (CA/AL), and AMT taxes.
-   **Dynamic Integration**: Tax location is pulled directly from the active Spending Strategy.

## Architecture & File Structure

```text
/home/zach/finances/
├── app.py                  # Main Streamlit application (UI & State Management)
├── logic/
│   ├── retirement.py       # BacktestEngine, Withdrawal Strategies, Bucket Logic
│   ├── lifecycle.py        # SpendingModel (Kids, Mortgage, Future Purchases)
│   ├── market_data.py      # yfinance wrapper and caching
│   ├── analytics.py        # Cohort stats and Purchasing Power calcs
│   ├── tax.py              # Tax calculation engine
│   ├── tax_rules.py        # Tax bracket definitions
│   └── equity.py           # Stock compensation logic
├── data/                   
│   ├── strategies.json     # Persisted user scenarios
│   └── *.csv               # Market data caches
└── tests/                  # Unit tests
```

## Design Trade-offs & Assumptions

1.  **Market Data**:
    -   *Current*: Uses `yfinance` for S&P 500 data.
    -   *Limitation*: Lacks historical Total Bond Market data (uses a fixed annual return assumption for bonds).
    -   *Tradeoff*: Simplicity and speed vs. perfect historical accuracy for the bond portion.

2.  **Inflation**:
    -   *Current*: Inflation rate is a configurable input per Portfolio Strategy.
    -   *Tradeoff*: Doesn't use historical CPI data yet, meaning 1970s scenarios might be slightly less punishing than reality regarding inflation volatility.

3.  **Buckets**:
    -   *Assumption*: Liquid assets are drained first. If liquid assets hit $0 before age 60, the simulation fails (strict penalty avoidance).

## Future Proposals & Next Steps

1.  **Historical Data Improvements**:
    -   Integrate **Shiller CPI data** to use actual historical inflation instead of a fixed rate.
    -   Integrate **Historical Bond Yields** (10-year Treasury or similar).

2.  **Tax Integration in Simulation**:
    -   Currently, the Backtest runs on *gross* withdrawals vs. *net* spending needs is an approximation.
    -   *Goal*: Calculate tax liability dynamically each year of the simulation (handling RMDs, capital gains brackets, etc.) to true-up "After-Tax Spend".

3.  **Social Security**:
    -   Add Social Security claiming strategies (Age 62 vs 67 vs 70) to the Lifecycle model as an income stream.

## How to Run
1.  Activate environment: `conda activate finances`
2.  Run app: `streamlit run app.py`
3.  Run tests: `python -m unittest discover tests`
