import streamlit as st
import plotly.express as px
from logic import persistence

def update_housing_project_cb(strat_name, idx, field, key):
    """Persist housing project field change immediately."""
    if strat_name in st.session_state.spending_strategies:
        # Update the session state object with the new value from the widget
        val = st.session_state[key]
        projects = st.session_state.spending_strategies[strat_name].get("housing_projects", [])
        if 0 <= idx < len(projects):
            projects[idx][field] = val
            persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)

def render_builder():
    st.header("Portfolio & Spending Manager")
    
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("1. Portfolio Strategies")
        st.info("Define portfolios. Includes asset allocation and market assumptions.")
        
        # Create New Portfolio Strategy
        with st.expander("➕ Create New Portfolio", expanded=False):
            new_port_name = st.text_input("New Portfolio Name", placeholder="e.g., Aggressive Growth")
            if st.button("Create Portfolio"):
                if new_port_name and new_port_name not in st.session_state.portfolio_strategies:
                    st.session_state.portfolio_strategies[new_port_name] = {
                        "liquid_assets": 500000.0,
                        "retirement_assets": 500000.0,
                        "private_shares": 0.0,
                        "private_ipo_price": 25.0, # Used for both Current & IPO
                        "private_ipo_year": 2026,
                        "stock_alloc_pct": 80.0,
                        "bond_return_pct": 4.0
                    }
                    persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies) # Auto-save
                    st.success(f"Created '{new_port_name}'!")
                    st.rerun()
                elif not new_port_name:
                    st.error("Please enter a name.")
                else:
                    st.error("Portfolio name already exists.")
        
        port_names = list(st.session_state.portfolio_strategies.keys())
        
        if not port_names:
            st.warning("No portfolio strategies defined. Create one above.")
        else:
            selected_port_edit = st.selectbox("Select Portfolio to Edit", port_names)
            p_data = st.session_state.portfolio_strategies[selected_port_edit]
            
            with st.container(border=True):
                # Edit Fields
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    liq = st.number_input("Liquid Assets ($)", value=float(p_data.get("liquid_assets", 500000)), step=10000.0, key=f"edit_liq_{selected_port_edit}")
                    ret = st.number_input("Retirement Assets ($)", value=float(p_data.get("retirement_assets", 500000)), step=10000.0, key=f"edit_ret_{selected_port_edit}")
                with col_p2:
                    stk = st.number_input("Stocks Allocation (%)", 0.0, 100.0, float(p_data.get("stock_alloc_pct", 80.0)), step=5.0, key=f"edit_stk_{selected_port_edit}")
                    bnd = st.number_input("Bond Return (%)", value=float(p_data.get("bond_return_pct", 4.0)), step=0.1, key=f"edit_bnd_{selected_port_edit}")
                    st.caption("💡 Inflation uses historical data aligned with market returns")

                st.markdown("**Private Stock (Applied)**")
                c_ps1, c_ps2 = st.columns(2)
                with c_ps1:
                    sh = st.number_input("Shares Owned", value=float(p_data.get("private_shares", 0)), step=100.0, key=f"edit_sh_{selected_port_edit}")
                    
                    # Consolidate Price Logic: Use 'private_ipo_price' (or 'private_stock_price' concept)
                    # If 'current_private_price' exists in legacy data, we ignore/migrate it implicitly by just editing 'private_ipo_price'
                    # We will label it "Stock Price ($)"
                    
                    # Fallback to current_private_price if ipo_price is missing, but prefer ipo_price
                    default_price = float(p_data.get("private_ipo_price", 25.0))
                    
                    price = st.number_input("Stock Price ($)", value=default_price, step=1.0, key=f"edit_price_{selected_port_edit}", help="Used for both Current Value and Future IPO Windfall")
                    
                with c_ps2:
                    iy = st.number_input("Expected IPO Year", 2025, 2040, int(p_data.get("private_ipo_year", 2026)), key=f"edit_iy_{selected_port_edit}")

                # Diversification Schedule
                # Private Stock Growth Rate
                growth_mult = st.number_input(
                    "Growth Multiplier", 
                    0.5, 3.0, 
                    float(p_data.get("private_growth_multiplier", 1.0)), 
                    step=0.1, 
                    key=f"edit_gm_{selected_port_edit}",
                    help="Growth rate relative to market (1.0 = same as market, 1.5 = 50% faster)"
                )
                
                st.markdown("It is risky to hold single stock. Diversify after IPO?")
                div_duration = p_data.get("diversification_duration")
                has_div_sched = st.checkbox("Enable Diversification Schedule", value=bool(div_duration), key=f"chk_div_{selected_port_edit}")
                
                div_start = None
                div_dur = None
                
                if has_div_sched:
                    c_d1, c_d2 = st.columns(2)
                    default_start = p_data.get("diversification_start_year") or iy + 1
                    default_dur = p_data.get("diversification_duration") or 4
                    
                    div_start = c_d1.number_input("Start Selling (Year)", 2025, 2050, int(default_start), key=f"div_sy_{selected_port_edit}")
                    div_dur = c_d2.number_input("Duration (Years)", 1, 10, int(default_dur), key=f"div_dur_{selected_port_edit}", help="Sell 1/N shares each year")
                
                st.divider()
                st.subheader("Income Streams (W2)")
                st.info("Add pre-tax W2 income (in 2025 dollars). Taxes will be automatically deducted.")
                
                income_streams = p_data.get("income_streams", [])
                
                if st.button("Add Income Stream", key=f"add_inc_{selected_port_edit}"):
                    income_streams.append({"name": "Job", "start_year": 2025, "end_year": 2030, "annual_amount": 100000.0})
                    st.rerun()
                
                inc_remove = []
                for i, inc in enumerate(income_streams):
                    c_i1, c_i2, c_i3, c_i4, c_i5 = st.columns([2, 1, 1, 1.5, 0.5])
                    inc["name"] = c_i1.text_input("Name", inc["name"], key=f"inc_nm_{i}_{selected_port_edit}")
                    inc["start_year"] = c_i2.number_input("Start", 2025, 2060, int(inc["start_year"]), key=f"inc_sy_{i}_{selected_port_edit}")
                    inc["end_year"] = c_i3.number_input("End", 2025, 2060, int(inc["end_year"]), key=f"inc_ey_{i}_{selected_port_edit}")
                    inc["annual_amount"] = c_i4.number_input("Annual ($)", value=float(inc["annual_amount"]), step=5000.0, key=f"inc_amt_{i}_{selected_port_edit}")
                    
                    if c_i5.button("X", key=f"del_inc_{i}_{selected_port_edit}"):
                        inc_remove.append(i)
                
                for i in sorted(inc_remove, reverse=True):
                    income_streams.pop(i)
                
                col_upd, col_del = st.columns([3, 1])
                with col_upd:
                    if st.button("Update Portfolio", key=f"btn_upd_p_{selected_port_edit}"):
                        st.session_state.portfolio_strategies[selected_port_edit] = {
                            "liquid_assets": liq,
                            "retirement_assets": ret,
                            "private_shares": sh,
                            "private_ipo_price": price, # Save consolidated price here
                            "private_ipo_year": iy,
                            "private_growth_multiplier": growth_mult,
                            "diversification_start_year": div_start,
                            "diversification_duration": div_dur,
                            "stock_alloc_pct": stk,
                            "bond_return_pct": bnd,
                            "income_streams": income_streams
                        }
                        persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies) # Auto-save
                        st.success(f"Updated {selected_port_edit}!")
                        st.rerun() 
                
                with col_del:
                    if st.button("🗑️ Delete", key=f"btn_del_p_{selected_port_edit}", type="primary"):
                        del st.session_state.portfolio_strategies[selected_port_edit]
                        persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)
                        st.success(f"Deleted {selected_port_edit}!")
                        st.rerun() 
            
            # Visualization
            st.markdown("### Portfolio Breakdown")
            # Calculate values
            curr_val_liquid = p_data.get("liquid_assets", 0)
            curr_val_ret = p_data.get("retirement_assets", 0)
            
            # Use consolidated price
            # Fallback for display if key hasn't been updated yet
            curr_stock_p = p_data.get("private_ipo_price", 25.0) 
            curr_val_stock = p_data.get("private_shares", 0) * curr_stock_p
            
            total_curr = curr_val_liquid + curr_val_ret + curr_val_stock
            
            st.info(f"""
            **Total Current Value: ${total_curr:,.0f}**
            - Liquid: ${curr_val_liquid:,.0f}
            - Retirement: ${curr_val_ret:,.0f}
            - Private Stock: ${curr_val_stock:,.0f} ({p_data.get("private_shares", 0):,.0f} shares @ ${curr_stock_p:,.2f})
            """)
            
            fig_pie = px.pie(
                names=["Liquid", "Retirement", "Private Stock (Current Val)"],
                values=[curr_val_liquid, curr_val_ret, curr_val_stock],
                hole=0.4,
                title=f"Total: ${total_curr:,.0f}"
            )
            st.plotly_chart(fig_pie, width='stretch')


    with c2:
        st.subheader("2. Spending Strategies")
        st.info("Define different spending profiles (e.g. Location, Mortgage, Kids).")
        
        # Create New Strategy Section
        with st.expander("➕ Create New Spending Strategy", expanded=False):
            new_strat_name = st.text_input("New Strategy Name", placeholder="e.g., Lean FIRE (AL)")
            if st.button("Create Spending Strategy"):
                if new_strat_name and new_strat_name not in st.session_state.spending_strategies:
                    st.session_state.spending_strategies[new_strat_name] = {
                        "base_monthly_spend": 5000.0,
                        "location": "Alabama", 
                        "has_mortgage": False,
                        "housing_projects": [],
                        "children": [],
                        "child_profiles": {}, # Reusable profiles
                        "spending_items": []
                    }
                    persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies) # Auto-save
                    st.success(f"Created '{new_strat_name}'!")
                    st.rerun()
                elif not new_strat_name:
                    st.error("Please enter a name.")
                else:
                    st.error("Strategy name already exists.")

        strat_names = list(st.session_state.spending_strategies.keys())
        
        if not strat_names:
            st.warning("No spending strategies defined. Create one above.")
        else:
            selected_strat_edit = st.selectbox("Select Strategy to Edit", strat_names)
            
            # Load values for editing
            s_data = st.session_state.spending_strategies[selected_strat_edit]
            
            with st.container(border=True):
                # 1. Base Monthly Spend
                st.markdown("#### 1. Monthly Living Expenses (Real 2025$)")
                # Fallback for old data "base_spend" (annual) -> "base_monthly_spend"
                default_monthly = s_data.get("base_monthly_spend")
                if default_monthly is None:
                    default_monthly = s_data.get("base_spend", 60000.0) / 12.0
                
                new_base_monthly = st.number_input("General Monthly Spend ($)", value=float(default_monthly), step=100.0, key=f"edit_bm_{selected_strat_edit}")
                
                # Essential percentage slider for base spend
                default_essential_pct = s_data.get("base_essential_pct", 50)
                base_essential_pct = st.slider(
                    "% of Base Spend that is Essential", 
                    0, 100, 
                    int(default_essential_pct), 
                    5,
                    key=f"edit_ess_pct_{selected_strat_edit}",
                    help="Essential = groceries, utilities. Discretionary = dining out, entertainment. Only affects Essential+Discretionary strategy."
                )
                
                # Line Items
                spending_items = s_data.get("spending_items", [])
                with st.expander("Additional Line Items (e.g. Car, Utils)", expanded=False):
                    st.caption("💡 Mark items as 'Essential' for costs that must be paid (health insurance, car payment). Non-essential items (travel, dining) can be reduced in market downturns.")
                    if st.button("Add Line Item", key=f"add_li_{selected_strat_edit}"):
                        spending_items.append({"name": "New Item", "monthly_amount": 500.0, "start_year": 2025, "end_year": 2030, "is_essential": True})
                        st.rerun()
                    
                    items_to_remove = []
                    for i, item in enumerate(spending_items):
                        c_li0, c_li1, c_li2, c_li3, c_li4, c_li5 = st.columns([0.5, 2, 1.5, 1.5, 1.5, 0.5])
                        # Essential checkbox
                        item["is_essential"] = c_li0.checkbox("Ess.", value=item.get("is_essential", True), key=f"li_ess_{i}_{selected_strat_edit}", help="Essential = must withdraw")
                        item["name"] = c_li1.text_input("Name", item["name"], key=f"li_nm_{i}_{selected_strat_edit}")
                        item["monthly_amount"] = c_li2.number_input("Monthly ($)", value=float(item["monthly_amount"]), step=100.0, key=f"li_amt_{i}_{selected_strat_edit}")
                        
                        # Start Year
                        with c_li3:
                            is_immediate = item.get("start_year") is None
                            use_start_year = not st.checkbox("Immediate Start", value=is_immediate, key=f"li_is_{i}_{selected_strat_edit}")
                            if use_start_year:
                                val = item.get("start_year")
                                if val is None: val = 2025
                                item["start_year"] = st.number_input("Start Year", 2020, 2100, int(val), key=f"li_sy_{i}_{selected_strat_edit}")
                            else:
                                item["start_year"] = None

                        # End Year
                        with c_li4:
                            is_indefinite = item.get("end_year") is None
                            use_end_year = not st.checkbox("Indefinite End", value=is_indefinite, key=f"li_ie_{i}_{selected_strat_edit}")
                            if use_end_year:
                                val = item.get("end_year")
                                if val is None: val = 2030
                                item["end_year"] = st.number_input("End Year", 2020, 2100, int(val), key=f"li_ey_{i}_{selected_strat_edit}")
                            else:
                                item["end_year"] = None

                        if c_li5.button("X", key=f"li_del_{i}_{selected_strat_edit}"):
                            items_to_remove.append(i)
                    
                    for i in sorted(items_to_remove, reverse=True):
                        spending_items.pop(i)

                loc = st.selectbox("Location", ["California", "Alabama"], index=0 if s_data.get("location") == "California" else 1, key=f"edit_loc_{selected_strat_edit}")
                
                st.divider()
                st.markdown("#### 2. Housing")
                
                # Existing Mortgage
                has_m = st.checkbox("Has Existing Mortgage", value=s_data.get("has_mortgage", False), key=f"edit_hm_{selected_strat_edit}")
                m_pmt = 0.0
                m_yrs = 0
                if has_m:
                    c_m1, c_m2 = st.columns(2)
                    m_pmt = c_m1.number_input("Current Monthly P&I ($)", value=float(s_data.get("mortgage_payment", 3000)), key=f"edit_mp_{selected_strat_edit}", help="Nominal payment")
                    m_yrs = c_m2.number_input("Years Remaining", value=int(s_data.get("mortgage_years", 20)), key=f"edit_my_{selected_strat_edit}")

                # Housing Projects (Future Purchases)
                # Migration: if "has_future_house" was true and "housing_projects" is empty, create one.
                housing_projects = s_data.get("housing_projects", [])
                if s_data.get("has_future_house") and not housing_projects and "fp_year" in s_data:
                    # Migrate old single future house
                    housing_projects.append({
                        "name": "Future Home",
                        "purchase_year": s_data.get("fp_year"),
                        "price": s_data.get("fp_price"),
                        "down_payment": s_data.get("fp_down"),
                        "interest_rate": s_data.get("fp_rate"),
                        "term_years": s_data.get("fp_term"),
                        "appreciation_rate": 0.03,
                        "selling_costs": 0.06
                    })
                    if "housing_projects" not in s_data:
                         s_data["housing_projects"] = housing_projects
                    
                    # Prevent re-migration and persist
                    s_data["has_future_house"] = False
                    persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)
                
                with st.expander("Housing Projects (Purchases & Sales)", expanded=False):
                    if st.button("Add Housing Project", key=f"add_hp_{selected_strat_edit}"):
                        housing_projects.append({
                            "name": "New House",
                            "purchase_year": 2030,
                            "price": 500000.0,
                            "down_payment": 100000.0,
                            "interest_rate": 6.5,
                            "term_years": 30,
                            "appreciation_rate": 0.03,
                            "selling_costs": 0.06,
                            "sale_year": None
                        })
                        if "housing_projects" not in s_data:
                             s_data["housing_projects"] = housing_projects
                        persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)
                        st.rerun()
                    
                    hp_remove = []
                    for i, hp in enumerate(housing_projects):
                        st.markdown(f"**Project {i+1}: {hp.get('name', 'House')}**")
                        c_hp1, c_hp2, c_hp3 = st.columns(3)
                        
                        k_nm = f"hp_nm_{i}_{selected_strat_edit}"
                        hp["name"] = c_hp1.text_input("Name", hp.get("name", "House"), key=k_nm, on_change=update_housing_project_cb, kwargs={"strat_name": selected_strat_edit, "idx": i, "field": "name", "key": k_nm})
                        
                        k_py = f"hp_py_{i}_{selected_strat_edit}"
                        hp["purchase_year"] = c_hp2.number_input("Buy Year", 2025, 2060, int(hp.get("purchase_year", 2030)), key=k_py, on_change=update_housing_project_cb, kwargs={"strat_name": selected_strat_edit, "idx": i, "field": "purchase_year", "key": k_py})
                        
                        k_pr = f"hp_pr_{i}_{selected_strat_edit}"
                        hp["price"] = c_hp3.number_input("Price (2025$)", value=float(hp.get("price", 500000)), step=10000.0, key=k_pr, on_change=update_housing_project_cb, kwargs={"strat_name": selected_strat_edit, "idx": i, "field": "price", "key": k_pr})
                        
                        c_hp4, c_hp5, c_hp6 = st.columns(3)
                        k_dp = f"hp_dp_{i}_{selected_strat_edit}"
                        hp["down_payment"] = c_hp4.number_input("Down Pmt", value=float(hp.get("down_payment", 100000)), step=5000.0, key=k_dp, on_change=update_housing_project_cb, kwargs={"strat_name": selected_strat_edit, "idx": i, "field": "down_payment", "key": k_dp})
                        
                        k_ir = f"hp_ir_{i}_{selected_strat_edit}"
                        hp["interest_rate"] = c_hp5.number_input("Rate (%)", 0.0, 15.0, float(hp.get("interest_rate", 6.5)), step=0.125, key=k_ir, on_change=update_housing_project_cb, kwargs={"strat_name": selected_strat_edit, "idx": i, "field": "interest_rate", "key": k_ir})
                        
                        k_tm = f"hp_tm_{i}_{selected_strat_edit}"
                        hp["term_years"] = c_hp6.number_input("Term (Yrs)", 5, 40, int(hp.get("term_years", 30)), key=k_tm, on_change=update_housing_project_cb, kwargs={"strat_name": selected_strat_edit, "idx": i, "field": "term_years", "key": k_tm})
                        
                        # -- Expenses & Calculations --
                        c_ex1, c_ex2 = st.columns(2)
                        
                        # Property Tax
                        k_pt = f"hp_pt_{i}_{selected_strat_edit}"
                        # Logic default 0.01
                        current_pt = hp.get("property_tax_rate", 0.01)
                        # We need a special callback or handler because we are scaling percentages
                        # Let's use standard logic: read value, if changed, save.
                        new_pt_pct = c_ex1.number_input("Property Tax (%)", 0.0, 5.0, float(current_pt)*100, step=0.1, key=k_pt)
                        if abs((new_pt_pct/100.0) - current_pt) > 1e-5:
                             hp["property_tax_rate"] = new_pt_pct / 100.0
                             persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)

                        # Maintenance
                        k_mt = f"hp_mt_{i}_{selected_strat_edit}"
                        current_mt = hp.get("maintenance_rate", 0.01)
                        new_mt_pct = c_ex2.number_input("Maintenance (%)", 0.0, 5.0, float(current_mt)*100, step=0.1, key=k_mt)
                        if abs((new_mt_pct/100.0) - current_mt) > 1e-5:
                             hp["maintenance_rate"] = new_mt_pct / 100.0
                             persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)

                        # Show monthly estimates
                        # Simple mortgage calc
                        r = hp.get("interest_rate", 6.5) / 100.0 / 12.0
                        n = int(hp.get("term_years", 30)) * 12
                        p = hp.get("price", 500000) - hp.get("down_payment", 100000)
                        
                        if p > 0 and r > 0:
                            monthly_pi = p * (r * (1+r)**n) / ((1+r)**n - 1)
                        elif p > 0:
                            monthly_pi = p / n if n > 0 else 0
                        else:
                            monthly_pi = 0.0
                            
                        monthly_tax = (hp.get("price", 500000) * (new_pt_pct/100.0)) / 12.0
                        monthly_maint = (hp.get("price", 500000) * (new_mt_pct/100.0)) / 12.0
                        total_mo = monthly_pi + monthly_tax + monthly_maint
                        
                        st.caption(f"**Est. Monthly Cost (Yr 1): ${total_mo:,.0f}**")
                        st.caption(f"• P&I: ${monthly_pi:,.0f} | Tax: ${monthly_tax:,.0f} | Maint: ${monthly_maint:,.0f}")

                        # Sale Option
                        k_hs = f"hp_hs_{i}_{selected_strat_edit}"
                        # Checkbox change triggers this. But updating "sale_year" requires logic. 
                        # We will use on_change to set a default if checked, or None if unchecked.
                        # Actually simpler: standard handling, then if the user edits the expanded fields, they save.
                        has_sale = st.checkbox(f"Plan to Sell '{hp.get('name', 'House')}'?", value=bool(hp.get("sale_year")), key=k_hs)
                        
                        # If checkbox toggled off, we should probably clear it? 
                        # But checkbox returns boolean. We can just rely on the if has_sale block.
                        # The user asked for persistence. If they check it, they expect it to stay checked.
                        # If checkbox is checked, we need 'sale_year' to be non-None in the data.
                        if has_sale and hp.get("sale_year") is None:
                             hp["sale_year"] = int(hp["purchase_year"]) + 5
                             # Save immediately so it persists
                             persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)
                        elif not has_sale and hp.get("sale_year") is not None:
                             hp["sale_year"] = None
                             persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)

                        if has_sale:
                            c_sale1, c_sale2 = st.columns(2)
                            k_sy = f"hp_sy_{i}_{selected_strat_edit}"
                            hp["sale_year"] = c_sale1.number_input("Sale Year", int(hp["purchase_year"])+1, 2080, int(hp.get("sale_year") or hp["purchase_year"]+5), key=k_sy, on_change=update_housing_project_cb, kwargs={"strat_name": selected_strat_edit, "idx": i, "field": "sale_year", "key": k_sy})
                            
                            k_ar = f"hp_ar_{i}_{selected_strat_edit}"
                            # appreciation rate is stored as 0.03, input is 3.0. 
                            # The callback will receive the input value (e.g. 3.0). We need to handle scaling?
                            # Our callback takes raw value. 
                            # Let's adjust the callback or the input. 
                            # Input: value=float(...) * 100.
                            # If we use callback, we save 3.0 to json. Logic expects 0.03.
                            # Better: Don't use generic callback for appreciation if scaling needed. 
                            # Or just wrap logic.
                            appr_val = c_sale2.number_input("Appreciation (%)", 0.0, 10.0, float(hp.get("appreciation_rate", 0.03))*100, step=0.5, key=k_ar)
                            if appr_val / 100.0 != hp.get("appreciation_rate"):
                                hp["appreciation_rate"] = appr_val / 100.0
                                persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)
                            
                            hp["selling_costs"] = 0.06 # Fixed or hidden for simplicity, or add input
                        
                        if st.button("Remove House", key=f"del_hp_{i}_{selected_strat_edit}"):
                            hp_remove.append(i)
                        st.divider()
                    
                    if hp_remove:
                        for i in sorted(hp_remove, reverse=True):
                            housing_projects.pop(i)
                        persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)
                        st.rerun()

                st.divider()
                st.markdown("#### 3. Children")
                
                # --- Child Spending Profiles ---
                child_profiles = s_data.get("child_profiles", {})
                
                with st.expander("📂 Manage Child Spending Profiles", expanded=False):
                    st.caption("Define reusable spending tracks (e.g. 'Public School', 'Private School').")
                    
                    # Add Profile
                    with st.form(f"add_prof_form_{selected_strat_edit}", clear_on_submit=True):
                        new_prof_name = st.text_input("New Profile Name", placeholder="e.g. Private School")
                        submitted = st.form_submit_button("Add Profile")
                        
                        if submitted:
                            if new_prof_name and new_prof_name not in child_profiles:
                                child_profiles[new_prof_name] = [
                                    {"name": "Early Years", "start_age": 0, "end_age": 4, "monthly_cost": 1250.0, "essential_portion": 0.4},
                                    {"name": "School", "start_age": 5, "end_age": 18, "monthly_cost": 200.0, "essential_portion": 0.6}
                                ]
                                # Update session state immediately
                                if "child_profiles" not in s_data:
                                    s_data["child_profiles"] = child_profiles
                                
                                persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)
                                st.success(f"Added profile '{new_prof_name}'")
                                st.rerun()
                            elif not new_prof_name:
                                st.error("Please enter a profile name.")
                            else:
                                st.error(f"Profile '{new_prof_name}' already exists.")
                    
                    # Edit Profiles
                    prof_to_remove = []
                    for p_name, phases in child_profiles.items():
                        st.markdown(f"**{p_name}**")
                        
                        # Phases
                        if st.button(f"Add Phase to {p_name}", key=f"add_ph_p_{p_name}_{selected_strat_edit}"):
                            phases.append({"name": "New Phase", "start_age": 0, "end_age": 5, "monthly_cost": 500.0, "essential_portion": 0.4})
                            # Ensure persistence in session state if this was a fresh dict
                            st.rerun()
                        
                        ph_remove = []
                        for i, ph in enumerate(phases):
                             c1_ph, c2_ph, c3_ph, c4_ph, c5_ph, c6_ph = st.columns([2, 1, 1, 1.5, 1, 0.5])
                             ph["name"] = c1_ph.text_input("Name", ph["name"], key=f"pp_nm_{p_name}_{i}")
                             ph["start_age"] = c2_ph.number_input("Start", 0, 30, int(ph["start_age"]), key=f"pp_sa_{p_name}_{i}")
                             ph["end_age"] = c3_ph.number_input("End", 0, 30, int(ph["end_age"]), key=f"pp_ea_{p_name}_{i}")
                             
                             # Migrate/Fallback
                             val = ph.get("monthly_cost")
                             if val is None: val = ph.get("annual_cost", 0) / 12.0
                             
                             ph["monthly_cost"] = c4_ph.number_input("Cost/Mo", value=float(val), step=100.0, key=f"pp_ac_{p_name}_{i}")
                             if "annual_cost" in ph: del ph["annual_cost"]
                             
                             # Essential portion slider (default 100% for backwards compatibility)
                             ess_pct = int(ph.get("essential_portion", 1.0) * 100)
                             ph["essential_portion"] = c5_ph.number_input("Ess%", 0, 100, ess_pct, key=f"pp_ess_{p_name}_{i}", help="% fixed/essential") / 100.0
                             
                             if c6_ph.button("X", key=f"del_pp_{p_name}_{i}"):
                                 ph_remove.append(i)
                        
                        for i in sorted(ph_remove, reverse=True):
                            phases.pop(i)
                            if "child_profiles" not in s_data:
                                s_data["child_profiles"] = child_profiles
                            st.rerun()
                            
                        if st.button(f"Delete Profile '{p_name}'", key=f"del_prof_{p_name}"):
                            prof_to_remove.append(p_name)

                    if prof_to_remove:
                        for p in prof_to_remove:
                            del child_profiles[p]
                        if "child_profiles" not in s_data:
                            s_data["child_profiles"] = child_profiles
                        st.rerun()

                # --- Children List ---
                children_data = s_data.get("children", [])
                
                if st.button("Add Child", key=f"add_ch_{selected_strat_edit}"):
                    children_data.append({"name": "New Child", "birth_year": 2025, "phases": [], "profile": None})
                    if "children" not in s_data:
                        s_data["children"] = children_data
                    st.rerun()

                kids_remove = []
                for i, child in enumerate(children_data):
                    if "name" not in child: child["name"] = f"Child {i+1}"
                    
                    with st.expander(f"🧒 {child['name']} (Born {child.get('birth_year')})", expanded=False):
                        c_k1, c_k2 = st.columns(2)
                        child["name"] = c_k1.text_input("Name", child["name"], key=f"ch_nm_{i}_{selected_strat_edit}")
                        child["birth_year"] = c_k2.number_input("Birth Year", 1990, 2040, int(child.get("birth_year", 2025)), key=f"ch_by_{i}_{selected_strat_edit}")
                        
                        # Profile Selection
                        profile_opts = ["Custom (Manual Phases)"] + list(child_profiles.keys())
                        current_prof = child.get("profile")
                        if current_prof not in child_profiles:
                            current_prof = "Custom (Manual Phases)"
                        
                        selected_prof = st.selectbox("Spending Profile", profile_opts, index=profile_opts.index(current_prof), key=f"ch_prof_{i}_{selected_strat_edit}")
                        
                        if selected_prof != "Custom (Manual Phases)":
                            child["profile"] = selected_prof
                            st.info(f"Using '{selected_prof}' profile.")
                            # Preview
                            st.json(child_profiles[selected_prof], expanded=False)
                        else:
                            child["profile"] = None # Use manual phases
                            st.markdown("**Custom Phases**")
                            # Fallback/Manual Phases Logic
                            if "phases" not in child: child["phases"] = []
                            
                            if st.button("Add Phase", key=f"add_ph_{i}_{selected_strat_edit}"):
                                child["phases"].append({"name": "Phase", "start_age": 0, "end_age": 5, "monthly_cost": 500.0, "essential_portion": 0.4})
                            
                            if st.button("Apply Defaults", key=f"def_ph_{i}_{selected_strat_edit}"):
                                child["phases"] = [
                                    {"name": "Daycare", "start_age": 0, "end_age": 4, "monthly_cost": 1250.0, "essential_portion": 0.4},
                                    {"name": "School", "start_age": 5, "end_age": 18, "monthly_cost": 200.0, "essential_portion": 0.6}
                                ]

                            phases_remove = []
                            for p_idx, phase in enumerate(child["phases"]):
                                c_ph1, c_ph2, c_ph3, c_ph4, c_ph5, c_ph6 = st.columns([2, 1, 1, 1.2, 0.8, 0.5])
                                phase["name"] = c_ph1.text_input("Phase", phase["name"], key=f"ph_nm_{i}_{p_idx}_{selected_strat_edit}", label_visibility="collapsed")
                                phase["start_age"] = c_ph2.number_input("Start", 0, 30, int(phase["start_age"]), key=f"ph_sa_{i}_{p_idx}_{selected_strat_edit}", label_visibility="collapsed")
                                phase["end_age"] = c_ph3.number_input("End", 0, 30, int(phase["end_age"]), key=f"ph_ea_{i}_{p_idx}_{selected_strat_edit}", label_visibility="collapsed")
                                
                                # Migrate/Fallback
                                val = phase.get("monthly_cost")
                                if val is None: val = phase.get("annual_cost", 0) / 12.0
                                
                                phase["monthly_cost"] = c_ph4.number_input("Cost/Mo", value=float(val), step=100.0, key=f"ph_ac_{i}_{p_idx}_{selected_strat_edit}", label_visibility="collapsed")
                                if "annual_cost" in phase: del phase["annual_cost"]
                                
                                # Essential portion slider
                                ess_pct = int(phase.get("essential_portion", 1.0) * 100)
                                phase["essential_portion"] = c_ph5.number_input("Ess%", 0, 100, ess_pct, key=f"ph_ess_{i}_{p_idx}_{selected_strat_edit}", label_visibility="collapsed", help="% fixed/essential") / 100.0
                                
                                if c_ph6.button("X", key=f"del_ph_{i}_{p_idx}_{selected_strat_edit}"):
                                    phases_remove.append(p_idx)
                            
                            for p_idx in sorted(phases_remove, reverse=True):
                                child["phases"].pop(p_idx)
                            
                        if st.button("Delete Child", key=f"del_ch_{i}_{selected_strat_edit}"):
                            kids_remove.append(i)
                
                for i in sorted(kids_remove, reverse=True):
                    children_data.pop(i)
                
                col_upd_s, col_del_s = st.columns([3, 1])
                with col_upd_s:
                    if st.button("Update Strategy", key=f"btn_upd_{selected_strat_edit}"):
                        # Save back to dict
                        new_strat = {
                            "base_monthly_spend": new_base_monthly,
                            "base_essential_pct": base_essential_pct,
                            "spending_items": spending_items,
                            "location": loc,
                            "has_mortgage": has_m,
                            "mortgage_payment": m_pmt,
                            "mortgage_years": m_yrs,
                            "housing_projects": housing_projects,
                            # Keep old flags false to avoid confusion if we revert or mix usage
                            "has_future_house": False, 
                            "num_kids": len(children_data),
                            "children": children_data,
                            "child_profiles": child_profiles
                        }
                        st.session_state.spending_strategies[selected_strat_edit] = new_strat
                        persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies) # Auto-save
                        st.success(f"Updated {selected_strat_edit}!")
                
                with col_del_s:
                    if st.button("🗑️ Delete", key=f"btn_del_s_{selected_strat_edit}", type="primary"):
                        del st.session_state.spending_strategies[selected_strat_edit]
                        persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)
                        st.success(f"Deleted {selected_strat_edit}!")
                        st.rerun() 
