import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from logic import lifecycle, retirement, market_data

@dataclass
class ChildInput:
    name: str
    birth_year: int
    profile: Optional[str] = None
    phases: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class HousingProjectInput:
    name: str
    purchase_year: int
    price: float
    down_payment: float
    interest_rate: float
    term_years: int
    appreciation_rate: float
    sale_year: Optional[int] = None

@dataclass
class SpendingItemInput:
    name: str
    monthly_amount: float
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    is_essential: bool = True  # True = Essential (always withdrawn), False = Discretionary

@dataclass
class MortgageInput:
    monthly_payment: float
    years_remaining: int

@dataclass
class SpendingStrategyInputs:
    base_monthly_spend: float
    location: str
    children: List[ChildInput] = field(default_factory=list)
    child_profiles: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    has_mortgage: bool = False
    mortgage: Optional[MortgageInput] = None
    housing_projects: List[HousingProjectInput] = field(default_factory=list)
    spending_items: List[SpendingItemInput] = field(default_factory=list)
    base_essential_pct: float = 50.0  # Percentage of base spend that is essential (stored as 0-100)

@dataclass
class IncomeStreamInput:
    name: str
    start_year: int
    end_year: int
    annual_amount: float

@dataclass
class PortfolioStrategyInputs:
    liquid_assets: float
    retirement_assets: float
    stock_alloc_pct: float
    bond_return_pct: float
    current_age: int
    death_age: int
    strategy_type: str
    min_spend: float
    max_spend: float
    private_shares: float = 0
    private_ipo_price: float = 0
    private_ipo_year: Optional[int] = None
    diversification_start_year: Optional[int] = None
    diversification_duration: Optional[int] = None
    private_growth_multiplier: float = 1.0  # Growth rate relative to market (1.0 = same as market)
    income_streams: List[IncomeStreamInput] = field(default_factory=list)
    strategy_pct: float = 4.0
    gk_init_rate: float = 4.5
    flexible_spending: bool = False
    flexible_floor_pct: float = 0.75
    allow_early_retirement_access: bool = True
    early_withdrawal_penalty_rate: float = 0.10
    retirement_access_age: int = 60

def build_spending_model(inputs: SpendingStrategyInputs, current_age: int, death_age: int) -> lifecycle.SpendingModel:
    """
    Constructs a SpendingModel from structured inputs.
    """
    # Construct Children
    child_list = []
    
    for c in inputs.children:
         phases = []
         
         # Check if using a profile
         if c.profile and c.profile in inputs.child_profiles:
             # Use profile phases
             raw_phases = inputs.child_profiles[c.profile]
             for p in raw_phases:                     
                 phases.append(lifecycle.ChildCostPhase(
                     name=p["name"],
                     start_age=p["start_age"],
                     end_age=p["end_age"],
                     monthly_cost=p["monthly_cost"],
                     essential_portion=p.get("essential_portion", 1.0)  # Default 100% essential for backwards compat
                 ))
         else:
             # Use manual phases
             for p in c.phases:
                 phases.append(lifecycle.ChildCostPhase(
                     name=p["name"],
                     start_age=p["start_age"],
                     end_age=p["end_age"],
                     monthly_cost=p["monthly_cost"],
                     essential_portion=p.get("essential_portion", 1.0)  # Default 100% essential for backwards compat
                 ))
             
         child_list.append(lifecycle.Child(
             name=c.name, 
             birth_year=c.birth_year,
             phases=phases
         ))
    
    # Mortgage
    mortgage = None
    if inputs.has_mortgage and inputs.mortgage:
        mortgage = lifecycle.Mortgage(
            monthly_payment=inputs.mortgage.monthly_payment,
            years_remaining=inputs.mortgage.years_remaining
        )
        
    # Housing Projects
    housing_objs = []
    for hp in inputs.housing_projects:
        housing_objs.append(lifecycle.HousingProject(
            name=hp.name,
            purchase_year=hp.purchase_year,
            price=hp.price,
            down_payment=hp.down_payment,
            interest_rate=hp.interest_rate / 100.0,
            term_years=hp.term_years,
            appreciation_rate=hp.appreciation_rate,
            sale_year=hp.sale_year
        ))
    
    # Spending Items
    items = []
    for item in inputs.spending_items:
        items.append(lifecycle.SpendingItem(
            name=item.name,
            monthly_amount=item.monthly_amount,
            start_year=item.start_year,
            end_year=item.end_year,
            is_essential=item.is_essential
        ))
    
    return lifecycle.SpendingModel(
        current_age=current_age,
        death_age=death_age,
        base_monthly_spend=inputs.base_monthly_spend,
        current_year=datetime.now().year,
        children=child_list,
        mortgage=mortgage,
        housing_projects=housing_objs,
        spending_items=items,
        base_essential_pct=inputs.base_essential_pct / 100.0  # Convert from 0-100 to 0-1
    )

def run_simulation(spending_inputs: SpendingStrategyInputs, portfolio_inputs: PortfolioStrategyInputs, df_market: pd.DataFrame):
    """
    Runs the retirement simulation based on structured inputs and market data.
    Uses historical inflation data aligned with market returns.
    """
    current_age = portfolio_inputs.current_age
    death_age = portfolio_inputs.death_age
    
    spend_model = build_spending_model(spending_inputs, current_age, death_age)
    
    schedule_df = spend_model.generate_schedule()
    
    spending_schedule = schedule_df["Required_Real_Spend"]
    # Initial spend req uses the schedule's first value
    initial_spend_req = spending_schedule.iloc[0] if not spending_schedule.empty else (spend_model.base_monthly_spend * 12)
    
    # Get monthly inflation data for backtesting
    monthly_inflation = market_data.get_monthly_inflation_rates()
    
    # Withdrawal Strategy
    w_strategy = None
    if portfolio_inputs.strategy_type == "Schedule Only":
        w_strategy = retirement.ScheduleOnlyStrategy()
    elif portfolio_inputs.strategy_type == "Constant Dollar (Targets Schedule)":
        w_strategy = retirement.ConstantDollarStrategy(
            min_withdrawal=portfolio_inputs.min_spend,
            max_withdrawal=portfolio_inputs.max_spend,
            flexible_spending=portfolio_inputs.flexible_spending,
            flexible_floor_pct=portfolio_inputs.flexible_floor_pct
        )
    elif portfolio_inputs.strategy_type == "Percent of Portfolio":
        w_strategy = retirement.PercentPortfolioStrategy(
            percentage=portfolio_inputs.strategy_pct / 100.0,
            min_withdrawal=portfolio_inputs.min_spend,
            max_withdrawal=portfolio_inputs.max_spend,
            flexible_spending=portfolio_inputs.flexible_spending,
            flexible_floor_pct=portfolio_inputs.flexible_floor_pct
        )
    elif portfolio_inputs.strategy_type == "VPW":
        w_strategy = retirement.VPWStrategy(
            start_age=current_age,
            max_age=death_age,
            min_withdrawal=portfolio_inputs.min_spend,
            max_withdrawal=portfolio_inputs.max_spend,
            flexible_spending=portfolio_inputs.flexible_spending,
            flexible_floor_pct=portfolio_inputs.flexible_floor_pct
        )
    elif portfolio_inputs.strategy_type == "Guyton-Klinger":
        w_strategy = retirement.GuytonKlingerStrategy(
            initial_rate=portfolio_inputs.gk_init_rate / 100.0,
            portfolio_value=portfolio_inputs.liquid_assets + portfolio_inputs.retirement_assets,
            guardrail_upper=0.20,
            guardrail_lower=0.20,
            min_withdrawal=portfolio_inputs.min_spend,
            max_withdrawal=portfolio_inputs.max_spend,
            flexible_spending=portfolio_inputs.flexible_spending,
            flexible_floor_pct=portfolio_inputs.flexible_floor_pct
        )
    elif portfolio_inputs.strategy_type == "Essential + Discretionary":
        w_strategy = retirement.EssentialDiscretionaryStrategy(
            capacity_rate=portfolio_inputs.strategy_pct / 100.0,  # Use strategy_pct as capacity rate
            spending_schedule_df=schedule_df
        )

    engine = retirement.BacktestEngine(
        market_data=df_market,
        stock_alloc=portfolio_inputs.stock_alloc_pct / 100.0,
        bond_return=portfolio_inputs.bond_return_pct / 100.0,
        monthly_inflation=monthly_inflation
    )
    
    # Construct Private Stock
    ps = None
    if portfolio_inputs.private_shares > 0:
        ps = retirement.PrivateStock(
            shares=portfolio_inputs.private_shares,
            ipo_year=portfolio_inputs.private_ipo_year,
            ipo_price=portfolio_inputs.private_ipo_price,
            diversification_start_year=portfolio_inputs.diversification_start_year,
            diversification_duration=portfolio_inputs.diversification_duration,
            growth_multiplier=portfolio_inputs.private_growth_multiplier
        )

    # Income Streams
    income_streams = []
    for stream in portfolio_inputs.income_streams:
        income_streams.append(retirement.IncomeStream(
            name=stream.name,
            start_year=stream.start_year,
            end_year=stream.end_year,
            annual_amount=stream.annual_amount,
            taxable=True
        ))

    # Build config with all required parameters
    config = retirement.SimulationConfig(
        initial_portfolio=portfolio_inputs.liquid_assets,
        duration_years=death_age - current_age,
        initial_annual_withdrawal=initial_spend_req,
        spending_schedule=spending_schedule,
        initial_401k=portfolio_inputs.retirement_assets,
        current_age=current_age,
        private_stock=ps,
        income_streams=income_streams,
        location=spending_inputs.location,
        start_year=datetime.now().year,
        allow_early_retirement_access=portfolio_inputs.allow_early_retirement_access,
        early_withdrawal_penalty_rate=portfolio_inputs.early_withdrawal_penalty_rate,
        access_age=portfolio_inputs.retirement_access_age,
        spending_schedule_df=schedule_df  # Full DataFrame for Essential+Discretionary strategy
    )

    # Run simulation
    result = engine.run_simulation(config, w_strategy)
    return result, engine.calculate_stats(result), schedule_df

# Helper functions to convert from dict to dataclass (for frontend compatibility)
def dict_to_spending_inputs(data: dict) -> SpendingStrategyInputs:
    """Convert dictionary to SpendingStrategyInputs dataclass."""
    children = []
    for c in data.get("children", []):
        children.append(ChildInput(
            name=c["name"],
            birth_year=c["birth_year"],
            profile=c.get("profile"),
            phases=c.get("phases", [])
        ))
    
    housing_projects = []
    for hp in data.get("housing_projects", []):
        housing_projects.append(HousingProjectInput(
            name=hp["name"],
            purchase_year=hp["purchase_year"],
            price=hp["price"],
            down_payment=hp["down_payment"],
            interest_rate=hp["interest_rate"],
            term_years=hp["term_years"],
            appreciation_rate=hp["appreciation_rate"],
            sale_year=hp.get("sale_year")
        ))
    
    spending_items = []
    for item in data.get("spending_items", []):
        spending_items.append(SpendingItemInput(
            name=item["name"],
            monthly_amount=item["monthly_amount"],
            start_year=item.get("start_year"),
            end_year=item.get("end_year"),
            is_essential=item.get("is_essential", True)  # Default to essential for backwards compatibility
        ))
    
    mortgage = None
    if data.get("has_mortgage") and "mortgage_payment" in data:
        mortgage = MortgageInput(
            monthly_payment=data["mortgage_payment"],
            years_remaining=data["mortgage_years"]
        )
    
    return SpendingStrategyInputs(
        base_monthly_spend=data["base_monthly_spend"],
        location=data["location"],
        children=children,
        child_profiles=data.get("child_profiles", {}),
        has_mortgage=data.get("has_mortgage", False),
        mortgage=mortgage,
        housing_projects=housing_projects,
        spending_items=spending_items,
        base_essential_pct=data.get("base_essential_pct", 50.0)  # Default 50% essential
    )

def dict_to_portfolio_inputs(data: dict) -> PortfolioStrategyInputs:
    """Convert dictionary to PortfolioStrategyInputs dataclass.
    
    All values must be provided by the caller - no defaults are applied.
    Note: inflation_rate is no longer used - historical data is used instead.
    """
    income_streams = []
    for stream in data.get("income_streams", []):
        income_streams.append(IncomeStreamInput(
            name=stream["name"],
            start_year=stream["start_year"],
            end_year=stream["end_year"],
            annual_amount=stream["annual_amount"]
        ))
    
    return PortfolioStrategyInputs(
        liquid_assets=data["liquid_assets"],
        retirement_assets=data["retirement_assets"],
        stock_alloc_pct=data["stock_alloc_pct"],
        bond_return_pct=data["bond_return_pct"],
        current_age=data["current_age"],
        death_age=data["death_age"],
        strategy_type=data["strategy_type"],
        min_spend=data["min_spend"],
        max_spend=data["max_spend"],
        private_shares=data["private_shares"],
        private_ipo_price=data["private_ipo_price"],
        private_ipo_year=data["private_ipo_year"],
        diversification_start_year=data["diversification_start_year"],
        diversification_duration=data["diversification_duration"],
        private_growth_multiplier=data["private_growth_multiplier"],
        income_streams=income_streams,
        strategy_pct=data["strategy_pct"],
        gk_init_rate=data["gk_init_rate"],
        flexible_spending=data["flexible_spending"],
        flexible_floor_pct=data["flexible_floor_pct"],
        allow_early_retirement_access=data["allow_early_retirement_access"],
        early_withdrawal_penalty_rate=data["early_withdrawal_penalty_rate"],
        retirement_access_age=data["retirement_access_age"]
    )

def run_simulation_wrapper(strategy_inputs: dict, portfolio_inputs: dict, df_market: pd.DataFrame):
    """
    Backwards-compatible wrapper that converts dicts to dataclasses.
    This is for transition period only - frontends should eventually call run_simulation directly.
    """
    spending = dict_to_spending_inputs(strategy_inputs)
    portfolio = dict_to_portfolio_inputs(portfolio_inputs)
    return run_simulation(spending, portfolio, df_market)

