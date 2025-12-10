import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np


def get_end_of_year_balance_index(year_idx: int) -> int:
    """
    Calculate the correct balance index for end of year.
    
    The balances DataFrame has an initial value at index 0, then monthly
    values appended. So:
    - Index 0: Initial balance (before any months processed)
    - Index 1: Balance after month 0
    - Index 12: Balance after month 11 (end of year 0)
    - Index 24: Balance after month 23 (end of year 1)
    
    Formula: (year_idx + 1) * 12
    """
    return (year_idx + 1) * 12


def render_by_year_view(res, sched_df, current_age, death_age, num_years):
    """Render the aggregate view for a specific year across all simulations."""
    
    st.subheader("Select Year to Analyze")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_year = st.slider(
            "Year of Retirement",
            min_value=0,
            max_value=num_years - 1,
            value=0,
            help="Year 0 is the first year of retirement"
        )
    with col2:
        selected_age = current_age + selected_year
        st.metric("Age at Selected Year", f"{selected_age}")
    
    st.divider()
    
    # Extract data for the selected year
    # Balances are monthly, so we need to convert year to month index
    # We'll look at the end of the year (month 12, 24, 36, etc.)
    month_idx = get_end_of_year_balance_index(selected_year)
    if month_idx >= len(res.balances.columns):
        month_idx = len(res.balances.columns) - 1
    
    # Get data across all simulations for this year
    year_balances = res.balances.iloc[:, month_idx]
    
    # Withdrawals, taxes, and income are annual (indexed by year)
    if selected_year < len(res.withdrawals.columns):
        year_withdrawals = res.withdrawals.iloc[:, selected_year]
        year_taxes = res.taxes.iloc[:, selected_year]
        year_income = res.total_income.iloc[:, selected_year]
    else:
        year_withdrawals = pd.Series([0] * len(res.withdrawals))
        year_taxes = pd.Series([0] * len(res.taxes))
        year_income = pd.Series([0] * len(res.total_income))
    
    # Calculate median values
    median_balance = year_balances.median()
    median_withdrawal = year_withdrawals.median()
    median_taxes = year_taxes.median()
    median_income = year_income.median()
    
    # Display key metrics
    st.subheader(f"Year {selected_year} Summary (Age {selected_age})")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Median Portfolio", f"${median_balance:,.0f}")
    m2.metric("Median Withdrawal", f"${median_withdrawal:,.0f}")
    m3.metric("Median Tax Paid", f"${median_taxes:,.0f}")
    m4.metric("Median Gross Income", f"${median_income:,.0f}")
    
    st.divider()
    
    # Row 1: Income Sources & Tax Breakdown
    st.subheader("Income & Tax Analysis")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("#### Income Sources")
        
        portfolio_withdrawal = median_withdrawal
        other_income = median_income - median_withdrawal if median_income > median_withdrawal else 0
        
        income_data = pd.DataFrame({
            'Source': ['Portfolio Withdrawal', 'Other Income (W2, IPO, etc.)'],
            'Amount': [portfolio_withdrawal, other_income]
        })
        
        fig_income = px.bar(
            income_data,
            x='Source',
            y='Amount',
            title=f"Income Sources (Year {selected_year})",
            color='Source',
            color_discrete_map={
                'Portfolio Withdrawal': '#1f77b4',
                'Other Income (W2, IPO, etc.)': '#2ca02c'
            }
        )
        fig_income.update_layout(showlegend=False, yaxis_title="Amount ($)")
        st.plotly_chart(fig_income, use_container_width=True)
    
    with c2:
        st.markdown("#### Tax Liability")
        
        if median_income > 0:
            effective_rate = median_taxes / median_income
        else:
            effective_rate = 0
        
        tax_data = pd.DataFrame({
            'Category': ['Taxes Paid', 'After-Tax Income'],
            'Amount': [median_taxes, median_income - median_taxes]
        })
        
        fig_tax = px.bar(
            tax_data,
            x='Category',
            y='Amount',
            title=f"Tax Burden (Year {selected_year})",
            color='Category',
            color_discrete_map={
                'Taxes Paid': '#d62728',
                'After-Tax Income': '#9467bd'
            }
        )
        fig_tax.update_layout(showlegend=False, yaxis_title="Amount ($)")
        st.plotly_chart(fig_tax, use_container_width=True)
        
        st.metric("Effective Tax Rate", f"{effective_rate:.1%}")
    
    st.divider()
    
    # Row 2: Spending Breakdown
    st.subheader("Spending Breakdown")
    
    if selected_year < len(sched_df):
        year_sched = sched_df.iloc[selected_year]
        
        spending_categories = {}
        if 'Base_Real' in year_sched:
            spending_categories['Base Spending'] = year_sched['Base_Real']
        if 'Items_Real' in year_sched:
            spending_categories['Special Items'] = year_sched['Items_Real']
        if 'Mortgage_Real' in year_sched:
            spending_categories['Mortgage'] = year_sched['Mortgage_Real']
        if 'Housing_Real' in year_sched:
            spending_categories['Housing Projects'] = year_sched['Housing_Real']
        if 'Child_Real' in year_sched:
            spending_categories['Children Costs'] = year_sched['Child_Real']
        
        spending_categories = {k: v for k, v in spending_categories.items() if v > 0}
        
        if spending_categories:
            spend_df = pd.DataFrame({
                'Category': list(spending_categories.keys()),
                'Amount': list(spending_categories.values())
            })
            
            fig_spend = px.pie(
                spend_df,
                values='Amount',
                names='Category',
                title=f"Spending Breakdown (Year {selected_year}, Real $)"
            )
            st.plotly_chart(fig_spend, use_container_width=True)
            
            st.markdown("#### Spending Details")
            spend_table = spend_df.copy()
            spend_table['Amount'] = spend_table['Amount'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(spend_table, hide_index=True, use_container_width=True)
            st.info(f"**Total Required Spending (Real):** ${spend_df['Amount'].sum():,.0f}")
        else:
            st.info("No spending data available for this year.")
    else:
        st.warning("Selected year is beyond the spending schedule.")
    
    st.divider()
    
    # Row 3: Portfolio Distribution
    st.subheader("Portfolio Value Distribution")
    
    fig_dist = go.Figure()
    fig_dist.add_trace(go.Histogram(
        x=year_balances,
        nbinsx=30,
        name="Portfolio Value",
        marker_color='steelblue'
    ))
    fig_dist.update_layout(
        title=f"Distribution of Portfolio Values Across Simulations (Year {selected_year})",
        xaxis_title="Portfolio Value ($)",
        yaxis_title="Number of Simulations",
        showlegend=False
    )
    fig_dist.add_vline(x=median_balance, line_dash="dash", line_color="red", 
                       annotation_text=f"Median: ${median_balance:,.0f}")
    
    st.plotly_chart(fig_dist, use_container_width=True)
    
    st.markdown("#### Portfolio Value Percentiles")
    percentiles = [10, 25, 50, 75, 90]
    percentile_values = [year_balances.quantile(p/100) for p in percentiles]
    
    perc_df = pd.DataFrame({
        'Percentile': [f"{p}th" for p in percentiles],
        'Portfolio Value': [f"${v:,.0f}" for v in percentile_values]
    })
    
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        st.dataframe(perc_df, hide_index=True, use_container_width=True)
    
    survival_rate = (year_balances > 0).sum() / len(year_balances)
    st.metric("Portfolios Still Solvent", f"{survival_rate:.1%}")


def render_by_simulation_view(res, sched_df, current_age, death_age, num_years):
    """Render a specific simulation path across all years."""
    
    st.subheader("Select Simulation to Analyze")
    
    # Calculate percentile-based indices
    final_values = res.balances.iloc[:, -1]
    num_sims = len(final_values)
    
    # Get simulation indices for key percentiles
    worst_idx = final_values.idxmin()
    best_idx = final_values.idxmax()
    p10_idx = final_values.quantile(0.10)
    p50_idx = final_values.quantile(0.50)
    p90_idx = final_values.quantile(0.90)
    
    # Find closest simulations to percentiles
    # Handle edge case where final_values are all NaN or 0
    if num_sims > 0:
         p10_sim = (final_values - p10_idx).abs().idxmin()
         p50_sim = (final_values - p50_idx).abs().idxmin()
         p90_sim = (final_values - p90_idx).abs().idxmin()
    else:
         p10_sim = 0
         p50_sim = 0
         p90_sim = 0

    # Selection method
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### Quick Select by Outcome")
        percentile_choice = st.radio(
            "Select outcome type:",
            ["Worst Case", "10th Percentile", "Median (50th)", "90th Percentile", "Best Case"],
            index=2
        )
        
        # Map choice to simulation index
        percentile_map = {
            "Worst Case": worst_idx,
            "10th Percentile": p10_sim,
            "Median (50th)": p50_sim,
            "90th Percentile": p90_sim,
            "Best Case": best_idx
        }
        selected_sim_from_percentile = percentile_map[percentile_choice]
    
    with col2:
        st.markdown("#### Or Browse by Number")
        selected_sim_manual = st.number_input(
            "Simulation #",
            min_value=0,
            max_value=num_sims - 1,
            value=int(selected_sim_from_percentile),
            help=f"Choose any simulation from 0 to {num_sims - 1}"
        )
    
    # Use manual selection if different from percentile
    selected_sim = int(selected_sim_manual)
    
    st.divider()
    
    # Extract data for the selected simulation
    sim_balances_monthly = res.balances.iloc[selected_sim, :]
    sim_withdrawals = res.withdrawals.iloc[selected_sim, :] # Spending Target
    sim_gross_withdrawals = res.gross_withdrawals.iloc[selected_sim, :] # Actual from Portfolio
    sim_taxes = res.taxes.iloc[selected_sim, :]
    sim_income = res.total_income.iloc[selected_sim, :]
    
    # Extract new detailed tracking data (if available)
    sim_portfolio_values = None
    sim_private_stock_values = None
    sim_portfolio_gains = None
    sim_private_stock_gains = None
    sim_ipo_proceeds = None
    
    if res.portfolio_values is not None and not res.portfolio_values.empty:
        sim_portfolio_values = res.portfolio_values.iloc[selected_sim, :]
        if isinstance(sim_portfolio_values, pd.DataFrame): sim_portfolio_values = sim_portfolio_values.squeeze()
    if res.private_stock_values is not None and not res.private_stock_values.empty:
        sim_private_stock_values = res.private_stock_values.iloc[selected_sim, :]
        if isinstance(sim_private_stock_values, pd.DataFrame): sim_private_stock_values = sim_private_stock_values.squeeze()
    if res.portfolio_gains is not None and not res.portfolio_gains.empty:
        sim_portfolio_gains = res.portfolio_gains.iloc[selected_sim, :]
        if isinstance(sim_portfolio_gains, pd.DataFrame): sim_portfolio_gains = sim_portfolio_gains.squeeze()
    if res.private_stock_gains is not None and not res.private_stock_gains.empty:
        sim_private_stock_gains = res.private_stock_gains.iloc[selected_sim, :]
        if isinstance(sim_private_stock_gains, pd.DataFrame): sim_private_stock_gains = sim_private_stock_gains.squeeze()
    if res.ipo_proceeds is not None and not res.ipo_proceeds.empty:
        sim_ipo_proceeds = res.ipo_proceeds.iloc[selected_sim, :]
        if isinstance(sim_ipo_proceeds, pd.DataFrame): sim_ipo_proceeds = sim_ipo_proceeds.squeeze()
    
    # Ensure Series (handle single row DataFrame if any)
    if isinstance(sim_withdrawals, pd.DataFrame): sim_withdrawals = sim_withdrawals.squeeze()
    if isinstance(sim_gross_withdrawals, pd.DataFrame): sim_gross_withdrawals = sim_gross_withdrawals.squeeze()
    if isinstance(sim_taxes, pd.DataFrame): sim_taxes = sim_taxes.squeeze()
    if isinstance(sim_income, pd.DataFrame): sim_income = sim_income.squeeze()

    # Get simulation metadata
    final_value = sim_balances_monthly.iloc[-1]
    initial_value = sim_balances_monthly.iloc[0]
    success = final_value > 0
    
    if len(res.start_dates) > selected_sim:
        start_date = res.start_dates[selected_sim]
        start_date_str = start_date.strftime("%Y-%m-%d")
    else:
        start_date_str = "N/A"
    
    # Display simulation metadata
    st.subheader(f"Simulation #{selected_sim} Overview")
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Start Date", start_date_str)
    m2.metric("Initial Portfolio", f"${initial_value:,.0f}")
    m3.metric("Final Portfolio", f"${final_value:,.0f}")
    m4.metric("Status", "✅ Success" if success else "❌ Failed")
    
    # Calculate total taxes and withdrawals
    total_taxes = sim_taxes.sum()
    total_withdrawals = sim_withdrawals.sum()
    m5.metric("Total Taxes Paid", f"${total_taxes:,.0f}")
    
    st.divider()
    
    # Timeline Charts
    st.subheader("Timeline Analysis")
    
    # Prepare age axis for annual data
    ages_annual = [current_age + i for i in range(len(sim_withdrawals))]
    
    # Prepare age axis for monthly data (portfolio balance)
    months_total = len(sim_balances_monthly)
    ages_monthly = [current_age + m/12.0 for m in range(months_total)]
    
    # Chart 1: Portfolio Balance Over Time
    c1, c2 = st.columns(2)
    
    with c1:
        fig_portfolio = go.Figure()
        fig_portfolio.add_trace(go.Scatter(
            x=ages_monthly,
            y=sim_balances_monthly,
            mode='lines',
            name='Portfolio Value',
            line=dict(color='steelblue', width=2)
        ))
        fig_portfolio.update_layout(
            title="Portfolio Value Over Time",
            xaxis_title="Age",
            yaxis_title="Portfolio Value ($)",
            hovermode='x unified'
        )
        # Add zero line
        fig_portfolio.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.5)
        st.plotly_chart(fig_portfolio, use_container_width=True)
    
    with c2:
        # Chart 2: Annual Withdrawals
        fig_withdrawals = go.Figure()
        fig_withdrawals.add_trace(go.Bar(
            x=ages_annual,
            y=sim_withdrawals,
            name='Withdrawal',
            marker_color='lightblue'
        ))
        fig_withdrawals.update_layout(
            title="Annual Withdrawals",
            xaxis_title="Age",
            yaxis_title="Withdrawal Amount ($)",
            hovermode='x unified'
        )
        st.plotly_chart(fig_withdrawals, use_container_width=True)
    
    # Chart 3 & 4: Taxes and Income
    c3, c4 = st.columns(2)
    
    with c3:
        fig_taxes = go.Figure()
        fig_taxes.add_trace(go.Bar(
            x=ages_annual,
            y=sim_taxes,
            name='Taxes',
            marker_color='coral'
        ))
        fig_taxes.update_layout(
            title="Annual Taxes Paid",
            xaxis_title="Age",
            yaxis_title="Tax Amount ($)",
            hovermode='x unified'
        )
        st.plotly_chart(fig_taxes, use_container_width=True)
    
    with c4:
        # Chart 4: Income breakdown (stacked)
        # sim_income = W2 + IPO + GrossWithdrawal
        # We want to show Sources: [W2 + IPO] and [Portfolio Withdrawal]
        
        # Ensure numpy arrays for calculation
        gross_withdrawals_arr = np.array(sim_gross_withdrawals.values)
        total_income_arr = np.array(sim_income.values)
        
        # Shape check - if mismatch, truncate or pad (though they should match)
        min_len = min(len(gross_withdrawals_arr), len(total_income_arr))
        gross_withdrawals_arr = gross_withdrawals_arr[:min_len]
        total_income_arr = total_income_arr[:min_len]
        
        # Derive External Income (W2 + IPO)
        # external = total - gross_withdrawal
        external_income_arr = np.maximum(total_income_arr - gross_withdrawals_arr, 0)
        
        fig_income = go.Figure()
        fig_income.add_trace(go.Bar(
            x=ages_annual,
            y=external_income_arr,
            name='External Income (W2, IPO)',
            marker_color='lightgreen'
        ))
        fig_income.add_trace(go.Bar(
            x=ages_annual,
            y=gross_withdrawals_arr,
            name='Portfolio Withdrawal (Gross)',
            marker_color='steelblue'
        ))
        fig_income.update_layout(
            title="Annual Income Sources (Stacked)",
            xaxis_title="Age",
            yaxis_title="Income ($)",
            barmode='stack',
            hovermode='x unified'
        )
        st.plotly_chart(fig_income, use_container_width=True)
    
    st.divider()
    
    # Year-by-Year Table
    st.subheader("Year-by-Year Breakdown")
    
    # Build comprehensive dataframe with detailed breakdown
    table_data = []
    prev_total_value = sim_balances_monthly.iloc[0] if len(sim_balances_monthly) > 0 else 0
    
    for year_idx in range(len(sim_withdrawals)):
        age = current_age + year_idx
        
        # Get end-of-year portfolio value
        month_idx = get_end_of_year_balance_index(year_idx)
        if month_idx >= len(sim_balances_monthly):
            month_idx = len(sim_balances_monthly) - 1
        
        total_value = sim_balances_monthly.iloc[month_idx]
        withdrawal = sim_withdrawals.iloc[year_idx]
        gross_withdrawal = sim_gross_withdrawals.iloc[year_idx] if year_idx < len(sim_gross_withdrawals) else 0
        tax = sim_taxes.iloc[year_idx]
        income = sim_income.iloc[year_idx]
        
        # Get detailed breakdown (if available)
        portfolio_value = sim_portfolio_values.iloc[year_idx] if sim_portfolio_values is not None and year_idx < len(sim_portfolio_values) else total_value
        private_stock_value = sim_private_stock_values.iloc[year_idx] if sim_private_stock_values is not None and year_idx < len(sim_private_stock_values) else 0
        portfolio_gain = sim_portfolio_gains.iloc[year_idx] if sim_portfolio_gains is not None and year_idx < len(sim_portfolio_gains) else 0
        private_stock_gain = sim_private_stock_gains.iloc[year_idx] if sim_private_stock_gains is not None and year_idx < len(sim_private_stock_gains) else 0
        ipo_proceeds = sim_ipo_proceeds.iloc[year_idx] if sim_ipo_proceeds is not None and year_idx < len(sim_ipo_proceeds) else 0
        
        # Calculate percentages
        start_of_year_portfolio = prev_total_value if year_idx == 0 else table_data[year_idx - 1]['Total Value (EOY)']
        portfolio_gain_pct = (portfolio_gain / start_of_year_portfolio * 100) if start_of_year_portfolio > 0 else 0
        
        # For private stock gain %, use start-of-year private stock value if available
        prev_private_stock = 0
        if sim_private_stock_values is not None and year_idx > 0 and year_idx - 1 < len(sim_private_stock_values):
            prev_private_stock = sim_private_stock_values.iloc[year_idx - 1]
        elif sim_private_stock_values is not None and year_idx == 0:
            # Estimate initial private stock value
            prev_private_stock = private_stock_value - private_stock_gain if private_stock_value > 0 else 0
        private_stock_gain_pct = (private_stock_gain / prev_private_stock * 100) if prev_private_stock > 0 else 0
        
        # Get spending requirement from schedule
        if year_idx < len(sched_df):
            required_spend = sched_df.iloc[year_idx].get('Required_Real_Spend', 0)
        else:
            required_spend = 0
        
        # W2 Income calculation (income - ipo_proceeds - gross_withdrawal = w2 income approximately)
        w2_income = income - ipo_proceeds - gross_withdrawal
        if w2_income < 0:
            w2_income = 0
        
        # Net change in portfolio
        net_change = total_value - prev_total_value
        
        table_data.append({
            'Year': year_idx,
            'Age': age,
            'Total Value (EOY)': total_value,
            'Diversified Portfolio': portfolio_value,
            'Concentrated Stock': private_stock_value,
            'Diversified Gains': portfolio_gain,
            'Diversified Gain %': portfolio_gain_pct,
            'Concentrated Gains': private_stock_gain,
            'Concentrated Gain %': private_stock_gain_pct,
            'IPO Proceeds': ipo_proceeds,
            'W2 Income': w2_income,
            'Spending': -withdrawal,  # Negative because it reduces net worth
            'Taxes': -tax,  # Negative because it reduces net worth
            'Net Change': net_change,
            'Required Spend': required_spend
        })
        
        prev_total_value = total_value
    
    table_df = pd.DataFrame(table_data)
    
    # Format for display with color coding
    def format_currency(x):
        if pd.isna(x) or x == 0:
            return "$0"
        elif x > 0:
            return f"+${x:,.0f}"
        else:
            return f"-${abs(x):,.0f}"
    
    def format_currency_neutral(x):
        if pd.isna(x) or x == 0:
            return "$0"
        return f"${x:,.0f}"
    
    def format_pct(x):
        if pd.isna(x) or x == 0:
            return "0%"
        elif x > 0:
            return f"+{x:.1f}%"
        else:
            return f"{x:.1f}%"
    
    display_df = table_df.copy()
    
    # Neutral values (just display amount)
    for col in ['Total Value (EOY)', 'Diversified Portfolio', 'Concentrated Stock', 'Required Spend']:
        display_df[col] = display_df[col].apply(format_currency_neutral)
    
    # Positive/negative values (show +/- sign)
    for col in ['Diversified Gains', 'Concentrated Gains', 'IPO Proceeds', 'W2 Income', 'Spending', 'Taxes', 'Net Change']:
        display_df[col] = display_df[col].apply(format_currency)
    
    # Percentages
    for col in ['Diversified Gain %', 'Concentrated Gain %']:
        display_df[col] = display_df[col].apply(format_pct)
    
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)
    
    # Download option
    csv = table_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Table as CSV",
        data=csv,
        file_name=f"simulation_{selected_sim}_breakdown.csv",
        mime="text/csv"
    )
    
    st.divider()
    
    # Spending Breakdown Table
    st.subheader("Spending Breakdown by Year")
    
    spending_breakdown_data = []
    for year_idx in range(len(sim_withdrawals)):
        age = current_age + year_idx
        
        if year_idx < len(sched_df):
            year_sched = sched_df.iloc[year_idx]
            
            spending_breakdown_data.append({
                'Year': year_idx,
                'Age': age,
                'Base Spending': year_sched.get('Base_Real', 0),
                'Special Items': year_sched.get('Items_Real', 0),
                'Mortgage': year_sched.get('Mortgage_Real', 0),
                'Housing Projects': year_sched.get('Housing_Real', 0),
                'Children': year_sched.get('Child_Real', 0),
                'Total Required': year_sched.get('Required_Real_Spend', 0)
            })
    
    if spending_breakdown_data:
        spending_df = pd.DataFrame(spending_breakdown_data)
        
        # Format for display
        spending_display_df = spending_df.copy()
        for col in ['Base Spending', 'Special Items', 'Mortgage', 'Housing Projects', 'Children', 'Total Required']:
            spending_display_df[col] = spending_display_df[col].apply(lambda x: f"${x:,.0f}" if x > 0 else "-")
        
        st.dataframe(spending_display_df, use_container_width=True, hide_index=True, height=400)
        
        # Download option for spending breakdown
        spending_csv = spending_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Spending Breakdown as CSV",
            data=spending_csv,
            file_name=f"simulation_{selected_sim}_spending_breakdown.csv",
            mime="text/csv"
        )
    else:
        st.info("No spending breakdown data available.")


def render_year_analysis():
    """Main entry point for year analysis tab."""
    st.header("Detailed Analysis")
    
    # Check if simulation results are available
    if "sim_result" not in st.session_state or st.session_state.sim_result is None:
        st.info("👈 Please run a Retirement Analysis first to view detailed breakdowns.")
        return
    
    if "sched_df" not in st.session_state or st.session_state.sched_df is None:
        st.info("No spending schedule data available.")
        return
    
    res = st.session_state.sim_result
    sched_df = st.session_state.sched_df
    
    # Get simulation parameters from session state
    current_age = st.session_state.get("current_age", 40)
    death_age = st.session_state.get("death_age", 95)
    
    # Calculate number of years in simulation
    num_years = death_age - current_age
    
    if res.balances.empty:
        st.warning("No simulation data available.")
        return
    
    # Create sub-tabs
    subtab1, subtab2 = st.tabs(["📊 By Year (Aggregate)", "🔍 By Simulation (Path)"])
    
    with subtab1:
        render_by_year_view(res, sched_df, current_age, death_age, num_years)
    
    with subtab2:
        render_by_simulation_view(res, sched_df, current_age, death_age, num_years)
