import pandas as pd
from datetime import datetime
from logic import lifecycle, retirement

def build_spending_model_from_dict(inputs: dict, current_age: int, death_age: int) -> lifecycle.SpendingModel:
    """
    Constructs a SpendingModel from a dictionary of inputs (UI state).
    """
    # Construct Children
    child_profiles = inputs.get("child_profiles", {})
    child_list = []
    
    for c in inputs.get("children", []):
         phases = []
         
            # Check if using a profile
         profile_name = c.get("profile")
         if profile_name and profile_name in child_profiles:
             # Use profile phases
             raw_phases = child_profiles[profile_name]
             for p in raw_phases:
                 # Handle migration from annual_cost to monthly_cost
                 m_cost = p.get("monthly_cost")
                 if m_cost is None:
                     m_cost = p.get("annual_cost", 0) / 12.0
                     
                 phases.append(lifecycle.ChildCostPhase(
                     name=p["name"],
                     start_age=p["start_age"],
                     end_age=p["end_age"],
                     monthly_cost=m_cost
                 ))
         else:
             # Fallback to manual phases
             for p in c.get("phases", []):
                 m_cost = p.get("monthly_cost")
                 if m_cost is None:
                     m_cost = p.get("annual_cost", 0) / 12.0
                     
                 phases.append(lifecycle.ChildCostPhase(
                     name=p["name"],
                     start_age=p["start_age"],
                     end_age=p["end_age"],
                     monthly_cost=m_cost
                 ))
             
             # Fallback for old children without phases (simple cost model)
             if not phases and "phases" not in c:
                 phases.append(lifecycle.ChildCostPhase("Default", 0, 18, 500.0))
             
         child_list.append(lifecycle.Child(
             name=c.get("name", "Child"), 
             birth_year=c.get("birth_year", 2025),
             phases=phases
         ))
    
    # Mortgage
    mortgage = None
    if inputs.get("has_mortgage"):
        mortgage = lifecycle.Mortgage(
            monthly_payment=inputs.get("mortgage_payment", 0),
            years_remaining=inputs.get("mortgage_years", 0)
        )
        
    # Housing Projects
    housing_objs = []
    # New list
    for hp in inputs.get("housing_projects", []):
        housing_objs.append(lifecycle.HousingProject(
            name=hp.get("name", "House"),
            purchase_year=hp.get("purchase_year"),
            price=hp.get("price"),
            down_payment=hp.get("down_payment"),
            interest_rate=hp.get("interest_rate") / 100.0,
            term_years=hp.get("term_years"),
            appreciation_rate=hp.get("appreciation_rate", 0.03),
            sale_year=hp.get("sale_year")
        ))
    
    # Spending Items
    items = []
    for item in inputs.get("spending_items", []):
        items.append(lifecycle.SpendingItem(
            name=item.get("name", "Item"),
            monthly_amount=item.get("monthly_amount", 0),
            start_year=item.get("start_year"),
            end_year=item.get("end_year")
        ))
    
    # Base Monthly
    base_monthly = inputs.get("base_monthly_spend")
    if base_monthly is None:
        base_monthly = inputs.get("base_spend", 0) / 12.0

    return lifecycle.SpendingModel(
        current_age=current_age,
        death_age=death_age,
        base_monthly_spend=base_monthly,
        current_year=datetime.now().year,
        children=child_list,
        mortgage=mortgage,
        housing_projects=housing_objs,
        spending_items=items
    )

def run_simulation_wrapper(strategy_inputs: dict, portfolio_inputs: dict, df_market: pd.DataFrame):
    """
    Runs the retirement simulation based on inputs and market data.
    """
    current_age = portfolio_inputs.get("current_age", 40)
    death_age = portfolio_inputs.get("death_age", 95)
    
    spend_model = build_spending_model_from_dict(strategy_inputs, current_age, death_age)
    
    # Inflation now comes from Portfolio Strategy and passed to generate_schedule
    inf_rate = portfolio_inputs.get("inflation_rate", 0.03)
    
    schedule_df = spend_model.generate_schedule(inflation_rate=inf_rate)
    
    spending_schedule = schedule_df["Required_Real_Spend"]
    # Initial spend req uses the schedule's first value
    initial_spend_req = spending_schedule.iloc[0] if not spending_schedule.empty else (spend_model.base_monthly_spend * 12)
    
    # Withdrawal Strategy
    st_type = portfolio_inputs.get("strategy_type")
    min_s = portfolio_inputs.get("min_spend")
    max_s = portfolio_inputs.get("max_spend")
    
    w_strategy = None
    if st_type == "Constant Dollar (Targets Schedule)":
        w_strategy = retirement.ConstantDollarStrategy(inflation_rate=inf_rate, min_withdrawal=min_s, max_withdrawal=max_s)
    elif st_type == "Percent of Portfolio":
        pct = portfolio_inputs.get("strategy_pct", 4.0) / 100.0
        w_strategy = retirement.PercentPortfolioStrategy(percentage=pct, inflation_rate=inf_rate, min_withdrawal=min_s, max_withdrawal=max_s)
    elif st_type == "VPW":
        w_strategy = retirement.VPWStrategy(start_age=current_age, max_age=100, inflation_rate=inf_rate, min_withdrawal=min_s, max_withdrawal=max_s)
    elif st_type == "Guyton-Klinger":
        init_rate = portfolio_inputs.get("gk_init_rate", 4.5) / 100.0
        w_strategy = retirement.GuytonKlingerStrategy(initial_rate=init_rate, portfolio_value=portfolio_inputs.get("liquid_assets") + portfolio_inputs.get("retirement_assets"), min_withdrawal=min_s, max_withdrawal=max_s, inflation_rate=inf_rate)

    engine = retirement.BacktestEngine(df_market, stock_alloc=portfolio_inputs.get("stock_alloc_pct")/100.0, bond_return=portfolio_inputs.get("bond_return_pct")/100.0)
    
    # Construct Private Stock
    ps = None
    if portfolio_inputs.get("private_shares", 0) > 0:
        ps = retirement.PrivateStock(
            shares=portfolio_inputs.get("private_shares"),
            ipo_year=portfolio_inputs.get("private_ipo_year"),
            ipo_price=portfolio_inputs.get("private_ipo_price"),
            diversification_start_year=portfolio_inputs.get("diversification_start_year"),
            diversification_duration=portfolio_inputs.get("diversification_duration")
        )

    # Income Streams
    income_streams = []
    for stream in portfolio_inputs.get("income_streams", []):
        income_streams.append(retirement.IncomeStream(
            name=stream.get("name", "Job"),
            start_year=stream.get("start_year", 2025),
            end_year=stream.get("end_year", 2025),
            annual_amount=stream.get("annual_amount", 0.0),
            taxable=True
        ))

    # Initial Portfolio - Now passing buckets
    # For compatibility with engine signature, we pass liquid as initial, and 401k separate
    result = engine.run_simulation(
        initial_portfolio=portfolio_inputs.get("liquid_assets"),
        duration_years=death_age - current_age,
        withdrawal_strategy=w_strategy,
        initial_annual_withdrawal=initial_spend_req,
        spending_schedule=spending_schedule,
        initial_401k=portfolio_inputs.get("retirement_assets"),
        current_age=current_age,
        private_stock=ps,
        income_streams=income_streams,
        location=strategy_inputs.get("location", "California"),
        start_year=datetime.now().year
    )
    return result, engine.calculate_stats(result, inflation_rate=inf_rate), schedule_df

