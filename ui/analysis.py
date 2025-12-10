import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from logic import market_data, simulation_bridge
from logic.retirement import get_all_strategy_names, get_strategy_description
from ui.utils import load_market_data
from ui.year_analysis import render_by_year_view, render_by_simulation_view

def render_analysis():
    st.header("Retirement Analysis")
    
    # Load Data
    with st.spinner("Loading Historical Market Data..."):
        df_market = load_market_data()

    # Inputs Layout
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Timeline")
        col_age1, col_age2 = st.columns(2)
        with col_age1:
            st.number_input("Current Age", 0, 80, 30, key="current_age")
        with col_age2:
            st.number_input("Life Expectancy", 0, 150, 95, key="death_age")
        
        st.divider()
        st.subheader("2. Select Portfolio")
        port_opts = list(st.session_state.portfolio_strategies.keys())
        if port_opts:
            selected_port = st.selectbox("Portfolio Strategy", port_opts, key="selected_portfolio_strategy")
        else:
            st.warning("No portfolio strategies. Create one in 'Portfolio & Spending Builder'.")
            selected_port = None
        
    with c2:
        st.subheader("3. Select Spending Strategy")
        strat_options = list(st.session_state.spending_strategies.keys())
        if not strat_options:
            st.warning("⚠️ No spending strategies found. Create one in 'Portfolio & Spending Builder'.")
            selected_strat = None
        else:
            selected_strat = st.selectbox("Spending Profile", strat_options, key="selected_spending_strategy")
        
        st.subheader("4. Withdrawal Method")
        st.selectbox("Method", get_all_strategy_names(), key="strategy_type")
        
        # Show strategy description
        st_type = st.session_state.strategy_type
        st.caption(get_strategy_description(st_type))
        
        # Dynamic Strategy Inputs
        if st_type in ["Percent of Portfolio", "VPW", "Guyton-Klinger", "Essential + Discretionary"]:
             if st_type == "Guyton-Klinger":
                  st.slider("Initial Rate (%)", 3.0, 6.0, 4.5, 0.1, key="gk_init_rate")
             elif st_type == "Percent of Portfolio":
                  st.slider("Withdrawal %", 0.0, 10.0, 4.0, 0.1, key="strategy_pct")
             elif st_type == "Essential + Discretionary":
                  st.slider("Capacity Rate (%)", 3.0, 6.0, 4.0, 0.1, key="strategy_pct",
                           help="Safe withdrawal rate to determine discretionary spending capacity")
        
        # Min/Max limits don't apply to Schedule Only
        if st_type != "Schedule Only":
            c_l, c_r = st.columns(2)
            c_l.number_input("Min Spend Floor ($)", value=30000.0, step=1000.0, key="min_spend")
            c_r.number_input("Max Spend Ceiling ($)", value=200000.0, step=1000.0, key="max_spend")
            
            # Flexible Spending Options
            st.markdown("##### Spending Flexibility")
            st.checkbox("Allow Flexible Spending (reduce in downturns)", value=False, key="flexible_spending",
                        help="If enabled, allows spending to drop below the schedule during market downturns")
            if st.session_state.get("flexible_spending", False):
                st.slider("Minimum Spending Floor (%)", 50, 100, 75, 5, key="flexible_floor_pct_slider",
                          help="Lowest percentage of scheduled spending allowed during downturns")
        
        # Early Retirement Access Options
        st.markdown("##### Early Retirement Access")
        st.checkbox("Allow Early 401k Access (with penalty)", value=True, key="allow_early_retirement_access",
                    help="If enabled, allows accessing 401k before age 59.5 with 10% early withdrawal penalty. If disabled, simulation fails when liquid assets run out before access age.")
        c_acc1, c_acc2 = st.columns(2)
        c_acc1.number_input("401k Access Age", 55, 65, 60, key="retirement_access_age",
                           help="Age at which retirement accounts can be accessed penalty-free (typically 59.5)")
        c_acc2.slider("Early Withdrawal Penalty (%)", 0, 20, 10, key="early_withdrawal_penalty_pct",
                      help="Penalty rate for early 401k withdrawal (default 10%)")

    st.divider()

    # Run
    # Only run if we have a valid strategy selected
    if selected_strat and selected_strat in st.session_state.spending_strategies and selected_port and selected_port in st.session_state.portfolio_strategies:
        # Construct Inputs Dict combining Portfolio Strategy + Timeline inputs
        p_data = st.session_state.portfolio_strategies[selected_port]
        
        # Get flexible spending settings
        flexible_spending = st.session_state.get("flexible_spending", False)
        flexible_floor_pct = st.session_state.get("flexible_floor_pct_slider", 75) / 100.0 if flexible_spending else 0.75
        
        current_port_inputs = {
            "liquid_assets": p_data.get("liquid_assets"),
            "retirement_assets": p_data.get("retirement_assets"),
            "private_shares": p_data.get("private_shares"),
            "private_ipo_price": p_data.get("private_ipo_price"), # Consolidated Price
            "private_ipo_year": p_data.get("private_ipo_year"),
            "private_growth_multiplier": p_data.get("private_growth_multiplier", 1.0),
            "diversification_start_year": p_data.get("diversification_start_year"),
            "diversification_duration": p_data.get("diversification_duration"),
            "stock_alloc_pct": p_data.get("stock_alloc_pct"),
            "bond_return_pct": p_data.get("bond_return_pct"),
            "income_streams": p_data.get("income_streams", []),
            
            "current_age": st.session_state.current_age,
            "death_age": st.session_state.death_age,
            "strategy_type": st.session_state.strategy_type,
            "min_spend": st.session_state.get("min_spend", 0),
            "max_spend": st.session_state.get("max_spend", 999999999),
            "strategy_pct": st.session_state.get("strategy_pct", 4.0),
            "gk_init_rate": st.session_state.get("gk_init_rate", 4.5),
            
            # New flexible spending settings
            "flexible_spending": flexible_spending,
            "flexible_floor_pct": flexible_floor_pct,
            
            # New early retirement access settings
            "allow_early_retirement_access": st.session_state.get("allow_early_retirement_access", True),
            "early_withdrawal_penalty_rate": st.session_state.get("early_withdrawal_penalty_pct", 10) / 100.0,
            "retirement_access_age": st.session_state.get("retirement_access_age", 60)
        }
        
        selected_spend_data = st.session_state.spending_strategies[selected_strat]
        
        # Pass df_market to wrapper
        res, stats, sched_df = simulation_bridge.run_simulation_wrapper(selected_spend_data, current_port_inputs, df_market)
        
        # Store results in session state
        st.session_state.sim_result = res
        st.session_state.sim_stats = stats
        st.session_state.sched_df = sched_df
        
        # Results Summary (always visible)
        r1, r2, r3 = st.columns(3)
        r1.metric("Success Probability", f"{stats['success_rate']:.1%}", 
                 delta="Safe" if stats['success_rate'] > 0.95 else "Risky" if stats['success_rate'] < 0.8 else "Caution")
        r2.metric("Median Ending Wealth", f"${stats['median_end_value']:,.0f}")
        r3.metric("Lowest Annual Spend (Real)", f"${stats.get('min_annual_spend', 0):,.0f}")
        
        st.divider()
        
        # Sub-tabs for different views
        view_tab1, view_tab2, view_tab3 = st.tabs(["📈 Overall Aggregate", "📊 By Year", "🔍 By Simulation Path"])
        
        with view_tab1:
            render_aggregate_view(res, stats, sched_df, current_port_inputs, selected_port, selected_strat, selected_spend_data)
        
        with view_tab2:
            current_age = current_port_inputs["current_age"]
            death_age = current_port_inputs["death_age"]
            num_years = death_age - current_age
            render_by_year_view(res, sched_df, current_age, death_age, num_years)
        
        with view_tab3:
            current_age = current_port_inputs["current_age"]
            death_age = current_port_inputs["death_age"]
            num_years = death_age - current_age
            render_by_simulation_view(res, sched_df, current_age, death_age, num_years)
    else:
        st.info("👈 Please define and select both a Portfolio and a Spending Strategy.")


def render_aggregate_view(res, stats, sched_df, current_port_inputs, selected_port, selected_strat, selected_spend_data):
    """Render the overall aggregate analysis view."""
    
    # Explanation for Basis
    with st.expander("ℹ️ Tax & Retirement Access Methodology"):
        st.markdown("""
        **Tax Treatment**
        
        This simulation uses realistic tax treatment for different account types:
        
        1. **Liquid (Taxable) Accounts**: 
           - Uses "Average Cost Basis" method
           - The gain portion of withdrawals is taxed as Long Term Capital Gains (LTCG)
           - `Realized Gain = Withdrawal * (1 - Basis Ratio)`
        
        2. **Retirement Accounts (401k/IRA)**: 
           - ALL withdrawals taxed as Ordinary Income
           - If accessing before the access age (default 60), a 10% early withdrawal penalty applies
        
        3. **Gross-Up**: Withdrawals are automatically "grossed up" to cover taxes, ensuring net spending matches your schedule.
        
        **Early Retirement Access**
        
        - **Allow Early Access**: When enabled, the simulation can access 401k funds before age 60 (with penalty)
        - This models strategies like paying the 10% penalty rather than failing
        - When disabled, the simulation fails if liquid assets deplete before the access age
        
        **Flexible Spending**
        
        - When enabled, spending can drop during market downturns to preserve the portfolio
        - The "Minimum Floor %" determines how much spending can decrease (e.g., 75% = spending can drop to 75% of scheduled amount)
        - This models "tightening the belt" during bad years rather than forcing fixed withdrawals
        """)
    
    # Charts
    
    # Row 1: Spending & Portfolio
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Spending Schedule")
        
        # Show Essential vs Discretionary stacked bar chart if available (primary view)
        if "Essential_Real_Spend" in sched_df.columns and "Discretionary_Real_Spend" in sched_df.columns:
            # Create stacked bar chart: Essential (bottom, red) + Discretionary (top, blue)
            ess_disc_melt = sched_df.melt(
                id_vars=["Age"], 
                value_vars=["Essential_Real_Spend", "Discretionary_Real_Spend"], 
                var_name="Type", 
                value_name="Amount"
            )
            # Rename for cleaner legend
            ess_disc_melt["Type"] = ess_disc_melt["Type"].replace({
                "Essential_Real_Spend": "Essential (Always Paid)",
                "Discretionary_Real_Spend": "Discretionary (If Capacity)"
            })
            fig_ess_disc = px.bar(
                ess_disc_melt, 
                x="Age", 
                y="Amount", 
                color="Type",
                title="Essential vs Discretionary Spending",
                color_discrete_map={
                    "Essential (Always Paid)": "#C0392B",  # Red - floor, always covered
                    "Discretionary (If Capacity)": "#3498DB"  # Blue - ceiling, cut in downturns
                },
                category_orders={"Type": ["Essential (Always Paid)", "Discretionary (If Capacity)"]}
            )
            fig_ess_disc.update_layout(
                barmode='stack',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_ess_disc, use_container_width=True)
            
            # Show detailed category breakdown in expander
            with st.expander("📊 Detailed Category Breakdown"):
                value_cols = ["Base_Real", "Items_Real", "Mortgage_Real", "Housing_Real", "Child_Real"]
                sched_melt = sched_df.melt(id_vars=["Age"], value_vars=value_cols, var_name="Category", value_name="Amount")
                st.plotly_chart(px.bar(sched_melt, x="Age", y="Amount", color="Category", title="By Category"), use_container_width=True)
        else:
            # Fallback: show category breakdown if Essential/Discretionary not available
            value_cols = ["Base_Real", "Items_Real", "Mortgage_Real", "Housing_Real", "Child_Real"]
            sched_melt = sched_df.melt(id_vars=["Age"], value_vars=value_cols, var_name="Category", value_name="Amount")
            st.plotly_chart(px.bar(sched_melt, x="Age", y="Amount", color="Category", title="Projected Needs"), use_container_width=True)
    with g2:
        st.subheader("Portfolio Cone")
        if not res.balances.empty:
            df_bal = res.balances.T
            p10 = df_bal.quantile(0.1, axis=1)
            p50 = df_bal.quantile(0.5, axis=1)
            p90 = df_bal.quantile(0.9, axis=1)
            
            # Construct Age Axis
            start_age = current_port_inputs["current_age"]
            months = len(p50)
            age_axis = [start_age + m/12.0 for m in range(months)]
            
            fig_cone = go.Figure()
            fig_cone.add_trace(go.Scatter(x=age_axis, y=p90, mode='lines', line=dict(width=0), showlegend=False))
            fig_cone.add_trace(go.Scatter(x=age_axis, y=p10, mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(0,100,80,0.2)', name='10th-90th Range'))
            fig_cone.add_trace(go.Scatter(x=age_axis, y=p50, mode='lines', line=dict(color='rgb(0,100,80)'), name='Median'))
            
            fig_cone.update_layout(xaxis_title="Age", yaxis_title="Portfolio Value ($)")
            st.plotly_chart(fig_cone, width='stretch')
    
    # Row 2: Tax Analysis
    st.divider()
    st.subheader("Tax Liability Analysis")
    if not res.taxes.empty and not res.total_income.empty:
        # Calculate Median Annual Tax and Median Effective Rate
        # Transpose so rows are years
        df_taxes = res.taxes.T 
        df_income = res.total_income.T
        
        # Get Median Path
        median_taxes = df_taxes.median(axis=1)
        median_income = df_income.median(axis=1)
        
        # Construct Plot DF
        # Use schedule age if possible, else just range
        ages = sched_df["Age"].values[:len(median_taxes)]
        
        # Effective Rate = Tax / Income
        # Avoid division by zero
        eff_rate = []
        for t, i in zip(median_taxes, median_income):
            if i > 100:
                eff_rate.append(t / i)
            else:
                eff_rate.append(0.0)
        
        c_t1, c_t2 = st.columns(2)
        
        with c_t1:
            # 1. Taxes vs Income Stack (or just Overlay)
            fig_tax = go.Figure()
            fig_tax.add_trace(go.Bar(x=ages, y=median_taxes, name="Tax Liability", marker_color='red'))
            fig_tax.add_trace(go.Scatter(x=ages, y=median_income, name="Total Gross Inflow", mode='lines', line=dict(dash='dot', color='gray')))
            fig_tax.update_layout(title="Median Annual Tax Liability vs Gross Inflow", xaxis_title="Age", yaxis_title="$ Amount")
            st.plotly_chart(fig_tax, width='stretch')
        
        with c_t2:
            # 2. Effective Tax Rate
            fig_rate = px.line(x=ages, y=eff_rate, title="Median Effective Tax Rate", labels={"x": "Age", "y": "Tax Rate"})
            fig_rate.update_yaxes(tickformat=".1%")
            st.plotly_chart(fig_rate, width='stretch')
    else:
        st.info("No tax data available from simulation.")
    
    # Row 3: Final Metrics
    st.divider()
    st.metric("Median Ending Wealth", f"${stats['median_end_value']:,.0f}")
    st.metric("Lowest Annual Spend (Real)", f"${stats.get('min_annual_spend', 0):,.0f}")
        
    # Add Comparison Button
    if st.button("➕ Add Result to Comparison"):
        # We save a snapshot of everything needed to re-run
        snapshot = {
            "name": f"{selected_port} + {selected_strat}",
            "spending_inputs": selected_spend_data,
            "portfolio_inputs": current_port_inputs
        }
        if "comparison_scenarios" not in st.session_state:
            st.session_state.comparison_scenarios = []
        st.session_state.comparison_scenarios.append(snapshot)
        st.success("Added to Compare Tab")

