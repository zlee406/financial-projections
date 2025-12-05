<!-- 2999689c-4f34-4d1f-872e-64377bce6854 ce5365d2-dfe4-4361-8923-9636d4f2f87a -->
# Create Project Summary and Handover Documentation

We will document the entire "Retirement Planning" feature overhaul into a single markdown file (`project_summary_handover.md`).

## 1. Content Structure

- **Project Overview**: High-level goal (Financial Dashboard with Tax & Retirement focus).
- **Features Implemented**:
    - **Historical Backtesting Engine**: Python-based (Pandas), cached S&P 500 data (`yfinance`).
    - **Advanced Strategies**: Constant Dollar, Percent Portfolio, Endowment, VPW, Guyton-Klinger Guardrails.
    - **Granular Lifecycle Spending**: Spending Builder (Children, Mortgage, Phases).
    - **Advisor Dashboard**: Single-view UI, "Cone of Uncertainty" charts, auto-running simulations.
    - **Min/Max Guardrails**: Global caps on withdrawal amounts.
    - **Unit Tests**: Robust testing for engine and strategies.
- **Design & UI Tradeoffs**:
    - **Auto-Run vs Button**: Switched to auto-run for responsiveness, but potential performance cost on slow machines.
    - **Complexity vs Clarity**: "Spending Builder" adds complexity but realism; UI tries to hide it in expanders.
    - **Data Source**: Using `yfinance` (S&P 500) vs Shiller Data (Total Return). Limitations on Bond data (fixed return assumption).
- **Future Proposals / Roadmap**:
    - **Real Bond Data**: Integrate historical bond returns (10-year Treasury) instead of fixed %.
    - **Tax Integration**: Connect `logic/tax.py` to `logic/retirement.py` to model *post-tax* spending power.
    - **Social Security**: Add Social Security claiming strategies to the Lifecycle model.
    - **Persistence**: Save/Load specific scenarios (JSON/SQLite).

## 2. File Creation

- Create `project_summary_handover.md` in the root directory.

## 3. Execution

- No code changes, just documentation generation.

### To-dos

- [x] Create logic/lifecycle.py for constructing age-based spending schedules
- [x] Update BacktestEngine to accept variable spending schedules
- [x] Update app.py UI with Spending Builder and Timeline inputs