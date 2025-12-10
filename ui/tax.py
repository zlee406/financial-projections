import streamlit as st
from logic import tax

def render_tax():
    st.header("Annual Income & Tax Projection")
    
    # Need to know which location to use. 
    # Use selected spending strategy location if available, otherwise default.
    loc_setting = "California" # Default
    if st.session_state.get("selected_spending_strategy"):
        strat_name = st.session_state.selected_spending_strategy
        if strat_name in st.session_state.spending_strategies:
            loc_setting = st.session_state.spending_strategies[strat_name].get("location", "California")
    
    st.caption(f"Using Tax Location: **{loc_setting}** (from selected Spending Strategy)")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Income Sources")
        salary = st.number_input("Combined Base Salary ($)", value=200000, step=1000)
        rsu_vest_value = st.number_input("RSU Value Vesting This Year ($)", value=50000, step=1000)
        ordinary_income = salary + rsu_vest_value
        st.info(f"Total Ordinary Income: ${ordinary_income:,.2f}")
    with col2:
        st.subheader("ISO Strategy")
        
        # Need stock price for ISO calc
        # Use selected portfolio price if available, otherwise default
        curr_price_setting = 25.0
        if st.session_state.get("selected_portfolio_strategy"):
            port_name = st.session_state.selected_portfolio_strategy
            if port_name in st.session_state.portfolio_strategies:
                # Use private_ipo_price (which is now the Consolidated Price)
                curr_price_setting = st.session_state.portfolio_strategies[port_name].get("private_ipo_price", 25.0)
        
        st.caption(f"Using Stock Price: **${curr_price_setting}** (from selected Portfolio)")
        
        isos_to_exercise = st.slider("ISOs to Exercise", 0, 20000, 0)
        iso_strike_price = st.number_input("ISO Strike", value=2.0)
        iso_spread = max(0, (curr_price_setting - iso_strike_price) * isos_to_exercise)
        st.metric("ISO Spread", f"${iso_spread:,.2f}")
    
    engine = tax.TaxEngine(loc_setting)
    tax_result = engine.run_projection(ordinary_income=ordinary_income, iso_spread=iso_spread)
    st.metric("Total Tax Bill", f"${tax_result.total_tax:,.0f}")





