import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from logic import market_data, simulation_bridge
from ui.utils import load_market_data

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
            st.number_input("Current Age", 30, 80, 40, key="current_age")
        with col_age2:
            st.number_input("Life Expectancy", 70, 110, 95, key="death_age")
        
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
        st.selectbox("Method", ["Constant Dollar (Targets Schedule)", "Percent of Portfolio", "VPW", "Guyton-Klinger"], key="strategy_type")
        
        # Dynamic Strategy Inputs
        st_type = st.session_state.strategy_type
        if st_type in ["Percent of Portfolio", "VPW", "Guyton-Klinger"]:
             if st_type == "Guyton-Klinger":
                  st.slider("Initial Rate (%)", 3.0, 6.0, 4.5, 0.1, key="gk_init_rate")
             elif st_type == "Percent of Portfolio":
                  st.slider("Withdrawal %", 1.0, 10.0, 4.0, 0.1, key="strategy_pct")
        
        c_l, c_r = st.columns(2)
        c_l.number_input("Min Spend Floor ($)", value=30000.0, step=1000.0, key="min_spend")
        c_r.number_input("Max Spend Ceiling ($)", value=200000.0, step=1000.0, key="max_spend")

    st.divider()

    # Run
    # Only run if we have a valid strategy selected
    if selected_strat and selected_strat in st.session_state.spending_strategies and selected_port and selected_port in st.session_state.portfolio_strategies:
        # Construct Inputs Dict combining Portfolio Strategy + Timeline inputs
        p_data = st.session_state.portfolio_strategies[selected_port]
        
        current_port_inputs = {
            "liquid_assets": p_data.get("liquid_assets"),
            "retirement_assets": p_data.get("retirement_assets"),
            "private_shares": p_data.get("private_shares"),
            "private_ipo_price": p_data.get("private_ipo_price"), # Consolidated Price
            "private_ipo_year": p_data.get("private_ipo_year"),
            "diversification_start_year": p_data.get("diversification_start_year"),
            "diversification_duration": p_data.get("diversification_duration"),
            "stock_alloc_pct": p_data.get("stock_alloc_pct"),
            "bond_return_pct": p_data.get("bond_return_pct"),
            "inflation_rate": p_data.get("inflation_rate", 0.03),
            "income_streams": p_data.get("income_streams", []),
            
            "current_age": st.session_state.current_age,
            # "retirement_age": st.session_state.retirement_age, # Removed
            "death_age": st.session_state.death_age,
            "strategy_type": st.session_state.strategy_type,
            "min_spend": st.session_state.min_spend,
            "max_spend": st.session_state.max_spend,
            "strategy_pct": st.session_state.get("strategy_pct", 4.0),
            "gk_init_rate": st.session_state.get("gk_init_rate", 4.5)
        }
        
        selected_spend_data = st.session_state.spending_strategies[selected_strat]
        
        # Pass df_market to wrapper
        res, stats, sched_df = simulation_bridge.run_simulation_wrapper(selected_spend_data, current_port_inputs, df_market)
        
        # Results
        r1, r2, r3 = st.columns(3)
        r1.metric("Success Probability", f"{stats['success_rate']:.1%}", 
                 delta="Safe" if stats['success_rate'] > 0.95 else "Risky" if stats['success_rate'] < 0.8 else "Caution")
        r2.metric("Median Ending Wealth", f"${stats['median_end_value']:,.0f}")
        r3.metric("Lowest Annual Spend (Real)", f"${stats.get('min_annual_spend', 0):,.0f}")

        # Explanation for Basis
        with st.expander("ℹ️ Tax & Basis Methodology (Simple Average)"):
            st.markdown("""
            **Cost Basis Method: Simple Average**
            
            This simulation uses a simplified "Average Cost Basis" method for the Liquid Portfolio to estimate taxes.
            
            1. **Tracking**: We track the Total Value and Total Cost Basis of the liquid portfolio.
            2. **Deposits**: New savings (from W2 surplus or IPO) are added to the Basis 1:1.
            3. **Withdrawals**: When you withdraw, we assume you are selling a slice of the portfolio containing a proportional mix of Basis and Gains.
               - `Basis Ratio = Total Basis / Total Value`
               - `Realized Gain = Withdrawal * (1 - Basis Ratio)`
            4. **Tax Calculation**: 
               - **W2 Income**: Taxed as Ordinary Income + Payroll Tax.
               - **Withdrawals**: The "Gain" portion is taxed as Long Term Capital Gains (LTCG).
               - **Gross Up**: Withdrawals are automatically "Grossed Up" to cover the estimated tax bill, ensuring your net spending power matches your Spending Schedule.
            """)
        
        # Charts
        
        # Row 1: Spending & Portfolio
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Spending Schedule")
            # Melt for stacked bar
            sched_melt = sched_df.melt(id_vars=["Age"], value_vars=["Base_Real", "Items_Real", "Mortgage_Real", "Housing_Real", "Child_Real"], var_name="Category", value_name="Amount")
            st.plotly_chart(px.bar(sched_melt, x="Age", y="Amount", color="Category", title="Projected Needs"), use_container_width=True)
        with g2:
            st.subheader("Portfolio Cone")
            if not res.balances.empty:
                df_bal = res.balances.T
                p10 = df_bal.quantile(0.1, axis=1)
                p50 = df_bal.quantile(0.5, axis=1)
                p90 = df_bal.quantile(0.9, axis=1)
                
                fig_cone = go.Figure()
                fig_cone.add_trace(go.Scatter(x=p90.index, y=p90, mode='lines', line=dict(width=0), showlegend=False))
                fig_cone.add_trace(go.Scatter(x=p10.index, y=p10, mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(0,100,80,0.2)', name='10th-90th Range'))
                fig_cone.add_trace(go.Scatter(x=p50.index, y=p50, mode='lines', line=dict(color='rgb(0,100,80)'), name='Median'))
                st.plotly_chart(fig_cone, use_container_width=True)
        
        # Row 2: Tax Analysis (Moved from Tab 2)
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
                st.plotly_chart(fig_tax, use_container_width=True)
            
            with c_t2:
                # 2. Effective Tax Rate
                fig_rate = px.line(x=ages, y=eff_rate, title="Median Effective Tax Rate", labels={"x": "Age", "y": "Tax Rate"})
                fig_rate.update_yaxes(tickformat=".1%")
                st.plotly_chart(fig_rate, use_container_width=True)
        else:
            st.info("No tax data available from simulation.")
        
        # Row 3: Metrics (from Tab 3)
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
    else:
        st.info("👈 Please define and select both a Portfolio and a Spending Strategy.")

