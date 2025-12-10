import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from logic import simulation_bridge
from ui.utils import load_market_data

def render_comparison():
    st.header("Strategy Comparison")
    
    if "comparison_scenarios" not in st.session_state or not st.session_state.comparison_scenarios:
        st.info("No scenarios added yet.")
    else:
        # Load market data for simulation
        df_market = load_market_data()
        
        summary_data = []
        results_map = {}
        
        st.subheader("Scenarios")
        
        for idx, scenario in enumerate(st.session_state.comparison_scenarios):
            name = scenario.get("name", f"Scenario {idx+1}")
            
            with st.expander(f"{name}", expanded=False):
                p_in = scenario["portfolio_inputs"]
                s_in = scenario["spending_inputs"]
                
                c_s1, c_s2 = st.columns(2)
                c_s1.write(f"**Liquid**: ${p_in['liquid_assets']:,.0f} | **401k**: ${p_in['retirement_assets']:,.0f}")
                c_s1.write(f"**Stock**: {p_in['stock_alloc_pct']}% | **Inf**: {p_in.get('inflation_rate',0.03)*100}%")
                
                # Update display for new Spend Model
                base_m = s_in.get("base_monthly_spend", 0)
                if base_m == 0:
                     base_m = s_in.get("base_spend", 0) / 12.0
                
                c_s2.write(f"**Monthly Base**: ${base_m:,.0f}")
                c_s2.write(f"**Location**: {s_in.get('location', 'N/A')}")
                
                if st.button(f"Remove {idx+1}", key=f"del_cmp_{idx}"):
                    st.session_state.comparison_scenarios.pop(idx)
                    st.rerun()

            # Run Sim
            s_res, s_stats, _ = simulation_bridge.run_simulation_wrapper(scenario["spending_inputs"], scenario["portfolio_inputs"], df_market)
            results_map[idx] = (s_res, s_stats)
            
            summary_data.append({
                "Scenario": name,
                "Success Rate": f"{s_stats['success_rate']:.1%}",
                "Median End Wealth": f"${s_stats['median_end_value']:,.0f}",
                "Min Spend": f"${s_stats.get('min_annual_spend',0):,.0f}"
            })
            
        st.divider()
        st.dataframe(pd.DataFrame(summary_data))
        
        st.subheader("Median Wealth Trajectories")
        fig_comp = go.Figure()
        for idx, (s_res, s_stats) in results_map.items():
            if not s_res.balances.empty:
                df_bal = s_res.balances.T
                p50 = df_bal.quantile(0.5, axis=1)
                # Use name if available
                scen_name = st.session_state.comparison_scenarios[idx].get("name", f"Scenario {idx+1}")
                fig_comp.add_trace(go.Scatter(x=p50.index, y=p50, mode='lines', name=scen_name))
        st.plotly_chart(fig_comp, width='stretch')





