import pandas as pd
from typing import List, Tuple

from logic import tax
from logic.retirement.models import (
    SimulationResult,
    SimulationConfig,
    YearState,
    IncomeStream,
)
from logic.retirement.portfolio import Portfolio, PrivateStockManager
from logic.retirement.strategies import WithdrawalStrategy


class BacktestEngine:
    """
    Runs historical backtests of retirement withdrawal strategies.
    
    Uses actual market data to simulate portfolio performance across
    multiple starting periods, accounting for taxes, income streams,
    private stock, and various withdrawal strategies.
    """
    
    def __init__(
        self,
        market_data: pd.DataFrame,
        stock_alloc: float = 0.8,
        bond_return: float = 0.04
    ):
        """
        Initialize the backtest engine with market data.
        
        Args:
            market_data: DataFrame with datetime index and 'Close' column for stocks
            stock_alloc: Stock allocation (0.0 to 1.0)
            bond_return: Fixed annual return for bonds (simplified)
        """
        self.market_data = market_data.copy()
        
        # Ensure index is DatetimeIndex
        if not isinstance(self.market_data.index, pd.DatetimeIndex):
            self.market_data.index = pd.to_datetime(self.market_data.index, utc=True)

        self.market_data = self.market_data.sort_index()
        self.stock_alloc = stock_alloc
        self.bond_return = bond_return
        
        # Resample to monthly for month-by-month simulation
        self.monthly_data = self.market_data['Close'].resample('ME').ffill().pct_change().dropna()

    def _calculate_gross_withdrawal_needed(
        self,
        tax_engine: tax.TaxEngine,
        target_net_deficit: float,
        base_ordinary_income: float,
        base_ltcg_income: float,
        portfolio: Portfolio,
        base_total_tax: float,
        current_age: int,
        access_age: int,
        allow_early_retirement_access: bool,
        early_withdrawal_penalty_rate: float
    ) -> Tuple[float, float, float, float]:
        """
        Iteratively solve for gross withdrawal such that:
        Gross - IncrementalTax(Gross) - Penalty = Target Net
        
        Returns:
            Tuple of (gross_withdrawal, additional_tax, penalty, estimated_from_retirement)
        """
        if target_net_deficit <= 0:
            return 0.0, 0.0, 0.0, 0.0
            
        low = target_net_deficit
        high = target_net_deficit * 3.0
        
        def simulate_withdrawal_tax(gross_amt: float) -> Tuple[float, float, float, float]:
            """Simulate the tax impact of a withdrawal."""
            remaining = gross_amt
            
            from_liquid = min(portfolio.liquid, remaining)
            remaining -= from_liquid
            
            from_retirement = min(portfolio.retirement, remaining) if remaining > 0 else 0.0
            
            liquid_gains = from_liquid * (1 - portfolio.basis_ratio) if from_liquid > 0 else 0.0
            retirement_ordinary = from_retirement
            
            penalty = 0.0
            if from_retirement > 0 and current_age < access_age:
                penalty = from_retirement * early_withdrawal_penalty_rate
            
            proj_tax = tax_engine.run_projection(
                ordinary_income=base_ordinary_income + retirement_ordinary,
                ltcg_income=base_ltcg_income + liquid_gains
            )
            incremental_tax = proj_tax.total_tax - base_total_tax
            
            net_received = gross_amt - incremental_tax - penalty
            return net_received, incremental_tax, penalty, from_retirement

        best_gross = target_net_deficit
        best_tax = 0.0
        best_penalty = 0.0
        best_from_retirement = 0.0
        
        for _ in range(25):
            mid = (low + high) / 2.0
            net, incr_tax, penalty, from_ret = simulate_withdrawal_tax(mid)
            
            if abs(net - target_net_deficit) < 1.0:
                return mid, incr_tax, penalty, from_ret
            
            if net < target_net_deficit:
                low = mid
            else:
                high = mid
                best_gross = mid
                best_tax = incr_tax
                best_penalty = penalty
                best_from_retirement = from_ret
                
        return best_gross, best_tax, best_penalty, best_from_retirement

    def _process_annual_cashflows(
        self,
        portfolio: Portfolio,
        ps_manager: PrivateStockManager,
        withdrawal_strategy: WithdrawalStrategy,
        config: SimulationConfig,
        tax_engine: tax.TaxEngine,
        year_state: YearState,
        initial_withdrawal: float,
        income_streams: List[IncomeStream]
    ) -> Tuple[float, float, float, float, float, float, float, float]:
        """
        Handle start-of-year logic: strategy calculation, income, IPOs, taxes, net cash flow.
        
        Returns:
            Tuple of (annual_draw, gross_withdrawal, total_tax, total_income, 
                     monthly_draw, new_previous_withdrawal, ipo_proceeds, deposit_amount)
        """
        # 1. Calculate Required Spend (Strategy)
        if year_state.year_offset == 0:
            annual_draw = initial_withdrawal
        else:
            annual_draw = withdrawal_strategy.calculate_withdrawal(
                current_portfolio_value=portfolio.total_value,
                year=year_state.year_offset,
                initial_withdrawal=initial_withdrawal,
                previous_withdrawal=year_state.previous_withdrawal,
                spending_schedule=config.spending_schedule
            )
        
        # 2. W2 Income
        annual_w2_income = 0.0
        for stream in income_streams:
            if stream.start_year <= year_state.calendar_year <= stream.end_year:
                annual_w2_income += stream.annual_amount

        # 3. IPO & Diversification
        ipo_proceeds, ipo_gains = ps_manager.check_for_sales(year_state.calendar_year)

        # 4. Tax Estimation & Cash Flow
        estimated_tax_res = tax_engine.run_projection(
            ordinary_income=annual_w2_income,
            ltcg_income=ipo_gains
        )
        total_tax_liability = estimated_tax_res.total_tax
        
        post_tax_income = (annual_w2_income + ipo_proceeds) - total_tax_liability
        net_cash_flow = post_tax_income - annual_draw
        
        gross_withdrawal = 0.0
        monthly_draw = 0.0
        deposit_amount = 0.0
        
        if net_cash_flow > 0:
            # Surplus -> Save to Liquid
            deposit_amount = net_cash_flow
            portfolio.deposit_liquid(deposit_amount)
            monthly_draw = 0
        else:
            # Deficit -> Withdraw from portfolio
            deficit = -net_cash_flow
            
            gross_withdrawal, additional_tax, penalty, _ = self._calculate_gross_withdrawal_needed(
                tax_engine=tax_engine,
                target_net_deficit=deficit,
                base_ordinary_income=annual_w2_income,
                base_ltcg_income=ipo_gains,
                portfolio=portfolio,
                base_total_tax=total_tax_liability,
                current_age=year_state.age,
                access_age=config.access_age,
                allow_early_retirement_access=config.allow_early_retirement_access,
                early_withdrawal_penalty_rate=config.early_withdrawal_penalty_rate
            )
            
            monthly_draw = gross_withdrawal / 12.0
            total_tax_liability += additional_tax + penalty

        total_gross_inflow = annual_w2_income + ipo_proceeds + gross_withdrawal
        
        return (annual_draw, gross_withdrawal, total_tax_liability, total_gross_inflow,
                monthly_draw, annual_draw, ipo_proceeds, deposit_amount)

    def _compute_initial_withdrawal(
        self,
        config: SimulationConfig,
        strategy: WithdrawalStrategy
    ) -> float:
        """Compute the initial withdrawal amount based on schedule and strategy limits."""
        initial = config.initial_annual_withdrawal
        
        if config.spending_schedule is not None:
            initial = config.spending_schedule.iloc[0]
        
        # Apply strategy limits
        initial = strategy.apply_limits(initial)
        
        # Apply schedule floor
        if config.spending_schedule is not None:
            if strategy.flexible_spending:
                flexible_floor = config.spending_schedule.iloc[0] * strategy.flexible_floor_pct
                initial = max(initial, flexible_floor)
            else:
                initial = max(initial, config.spending_schedule.iloc[0])
        
        return initial

    def _run_single_simulation(
        self,
        config: SimulationConfig,
        strategy: WithdrawalStrategy,
        tax_engine: tax.TaxEngine,
        period_returns: pd.Series,
        bond_monthly_rate: float,
        initial_withdrawal: float
    ) -> dict:
        """
        Run a single simulation path.
        
        Returns:
            Dictionary containing all tracked values for this simulation path
        """
        # Initialize state
        portfolio = Portfolio(
            liquid_assets=config.initial_portfolio,
            retirement_assets=config.initial_401k
        )
        ps_manager = PrivateStockManager(config.private_stock)
        
        # Tracking lists
        path_balances = [portfolio.total_value + ps_manager.current_value]
        path_withdrawals = []
        path_gross_withdrawals = []
        path_taxes = []
        path_incomes = []
        path_portfolio_values = []
        path_private_stock_values = []
        path_portfolio_gains = []
        path_private_stock_gains = []
        path_ipo_proceeds = []
        path_deposits = []
        
        # Year tracking
        year_start_portfolio_value = portfolio.total_value
        year_start_private_stock_value = ps_manager.current_value
        
        year_state = YearState(
            calendar_year=config.start_year,
            year_offset=0,
            age=config.current_age,
            previous_withdrawal=initial_withdrawal,
            monthly_draw=0.0
        )
        
        failed = False
        year_ipo_proceeds = 0.0
        year_deposit = 0.0
        gross_withdrawal = 0.0

        for m, stock_ret in enumerate(period_returns):
            year_state.year_offset = m // 12
            year_state.age = config.current_age + year_state.year_offset
            year_state.calendar_year = config.start_year + year_state.year_offset
            
            # --- Annual Logic (Start of Year) ---
            if m % 12 == 0:
                year_start_portfolio_value = portfolio.total_value
                year_start_private_stock_value = ps_manager.current_value
                
                (annual_draw, gross_withdrawal, total_tax, total_income,
                 year_state.monthly_draw, year_state.previous_withdrawal,
                 year_ipo_proceeds, year_deposit) = self._process_annual_cashflows(
                    portfolio=portfolio,
                    ps_manager=ps_manager,
                    withdrawal_strategy=strategy,
                    config=config,
                    tax_engine=tax_engine,
                    year_state=year_state,
                    initial_withdrawal=initial_withdrawal,
                    income_streams=config.income_streams
                )
                
                path_withdrawals.append(annual_draw)
                path_gross_withdrawals.append(gross_withdrawal)
                path_taxes.append(total_tax)
                path_incomes.append(total_income)
                path_ipo_proceeds.append(year_ipo_proceeds)
                path_deposits.append(year_deposit)

            # Withdraw FIRST (before returns)
            if not failed:
                result = portfolio.withdraw(
                    year_state.monthly_draw,
                    year_state.age,
                    config.access_age,
                    allow_early_retirement_access=config.allow_early_retirement_access,
                    early_withdrawal_penalty_rate=config.early_withdrawal_penalty_rate
                )
                if not result.success:
                    failed = True

            # THEN apply Investment Return
            weighted_return = (stock_ret * self.stock_alloc) + (bond_monthly_rate * (1 - self.stock_alloc))
            portfolio.apply_market_return(weighted_return)
            ps_manager.apply_market_return(stock_ret)

            if failed:
                portfolio.liquid = 0
                portfolio.retirement = 0
            
            total_balance = portfolio.total_value + ps_manager.current_value
            path_balances.append(total_balance)
            
            # --- End of Year Logic ---
            if m % 12 == 11:
                path_portfolio_values.append(portfolio.total_value)
                path_private_stock_values.append(ps_manager.current_value)
                
                portfolio_gain = (portfolio.total_value - year_start_portfolio_value
                                  + gross_withdrawal - year_deposit)
                private_stock_gain = (ps_manager.current_value - year_start_private_stock_value
                                      + year_ipo_proceeds)
                
                path_portfolio_gains.append(portfolio_gain)
                path_private_stock_gains.append(private_stock_gain)
        
        return {
            'balances': path_balances,
            'withdrawals': path_withdrawals,
            'gross_withdrawals': path_gross_withdrawals,
            'taxes': path_taxes,
            'incomes': path_incomes,
            'portfolio_values': path_portfolio_values,
            'private_stock_values': path_private_stock_values,
            'portfolio_gains': path_portfolio_gains,
            'private_stock_gains': path_private_stock_gains,
            'ipo_proceeds': path_ipo_proceeds,
            'deposits': path_deposits
        }

    def run_simulation(
        self,
        initial_portfolio: float,
        duration_years: int,
        withdrawal_strategy: WithdrawalStrategy,
        initial_annual_withdrawal: float,
        spending_schedule: pd.Series = None,
        initial_401k: float = 0.0,
        current_age: int = 40,
        private_stock=None,
        income_streams: List[IncomeStream] = None,
        location: str = "California",
        start_year: int = 2025,
        allow_early_retirement_access: bool = True,
        early_withdrawal_penalty_rate: float = 0.10,
        access_age: int = 60
    ) -> SimulationResult:
        """
        Run backtests with realistic retirement account access rules.
        
        This method maintains the original signature for backward compatibility.
        Internally it creates a SimulationConfig and delegates to _run_single_simulation.
        """
        if income_streams is None:
            income_streams = []
            
        config = SimulationConfig(
            initial_portfolio=initial_portfolio,
            duration_years=duration_years,
            initial_annual_withdrawal=initial_annual_withdrawal,
            spending_schedule=spending_schedule,
            initial_401k=initial_401k,
            current_age=current_age,
            private_stock=private_stock,
            income_streams=income_streams,
            location=location,
            start_year=start_year,
            allow_early_retirement_access=allow_early_retirement_access,
            early_withdrawal_penalty_rate=early_withdrawal_penalty_rate,
            access_age=access_age
        )
        
        return self.run_simulation_with_config(config, withdrawal_strategy)

    def run_simulation_with_config(
        self,
        config: SimulationConfig,
        withdrawal_strategy: WithdrawalStrategy
    ) -> SimulationResult:
        """
        Run backtests using a SimulationConfig object.
        
        This is the preferred method for new code.
        """
        months_needed = config.duration_years * 12
        available_months = len(self.monthly_data)
        
        if available_months < months_needed:
            return SimulationResult(
                pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
                pd.DataFrame(), pd.DataFrame(), [],
                pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
                pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            )

        # Collect results from all simulation paths
        sim_balances = []
        sim_withdrawals = []
        sim_gross_withdrawals = []
        sim_taxes = []
        sim_incomes = []
        start_dates = []
        sim_portfolio_values = []
        sim_private_stock_values = []
        sim_portfolio_gains = []
        sim_private_stock_gains = []
        sim_ipo_proceeds = []
        sim_deposits = []
        
        tax_engine = tax.TaxEngine(config.location)
        bond_monthly_rate = (1 + self.bond_return) ** (1/12) - 1
        initial_withdrawal = self._compute_initial_withdrawal(config, withdrawal_strategy)

        for start_idx in range(0, available_months - months_needed, 12):
            start_date = self.monthly_data.index[start_idx]
            start_dates.append(start_date)
            
            period_returns = self.monthly_data.iloc[start_idx:start_idx + months_needed]
            
            path_result = self._run_single_simulation(
                config=config,
                strategy=withdrawal_strategy,
                tax_engine=tax_engine,
                period_returns=period_returns,
                bond_monthly_rate=bond_monthly_rate,
                initial_withdrawal=initial_withdrawal
            )
            
            sim_balances.append(path_result['balances'])
            sim_withdrawals.append(path_result['withdrawals'])
            sim_gross_withdrawals.append(path_result['gross_withdrawals'])
            sim_taxes.append(path_result['taxes'])
            sim_incomes.append(path_result['incomes'])
            sim_portfolio_values.append(path_result['portfolio_values'])
            sim_private_stock_values.append(path_result['private_stock_values'])
            sim_portfolio_gains.append(path_result['portfolio_gains'])
            sim_private_stock_gains.append(path_result['private_stock_gains'])
            sim_ipo_proceeds.append(path_result['ipo_proceeds'])
            sim_deposits.append(path_result['deposits'])
            
        return SimulationResult(
            balances=pd.DataFrame(sim_balances),
            withdrawals=pd.DataFrame(sim_withdrawals),
            taxes=pd.DataFrame(sim_taxes),
            total_income=pd.DataFrame(sim_incomes),
            gross_withdrawals=pd.DataFrame(sim_gross_withdrawals),
            start_dates=start_dates,
            portfolio_values=pd.DataFrame(sim_portfolio_values),
            private_stock_values=pd.DataFrame(sim_private_stock_values),
            portfolio_gains=pd.DataFrame(sim_portfolio_gains),
            private_stock_gains=pd.DataFrame(sim_private_stock_gains),
            ipo_proceeds=pd.DataFrame(sim_ipo_proceeds),
            deposits=pd.DataFrame(sim_deposits)
        )

    def calculate_stats(self, result: SimulationResult, inflation_rate: float = 0.0) -> dict:
        """Calculate summary statistics from simulation results."""
        if result.balances.empty:
            return {}
            
        final_values = result.balances.iloc[:, -1]
        success_count = (final_values > 0).sum()
        total_sims = len(final_values)
        
        # Convert nominal withdrawals to real for stats
        real_withdrawals = result.withdrawals.copy()
        if inflation_rate != 0.0:
            for col in real_withdrawals.columns:
                year = int(col)
                deflator = (1 + inflation_rate) ** year
                real_withdrawals[col] = real_withdrawals[col] / deflator
        
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

