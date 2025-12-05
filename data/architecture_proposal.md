This is a fantastic project. Building your own financial dashboard gives you a level of granularity and privacy that off-the-shelf tools like Mint or Quicken (which struggle with complex equity events like ISO AMT) simply cannot match.

Since you are on Ubuntu and comfortable building this yourself, I propose a **Python-centric modular architecture**. This will allow you to run the app locally in your browser, keeping your sensitive financial data strictly on your machine.

### **I. High-Level Architecture**

We will build a "Modular Monolith" using **Streamlit**. Streamlit is perfect for this because it turns Python data scripts into interactive web apps in minutes, meaning you spend time on the *financial logic* (the hard part), not on HTML/CSS.

**The Tech Stack:**

  * **Frontend/UI:** **Streamlit** (Interactive sliders, graphs, and data tables).
  * **Data Processing:** **Pandas** (The industry standard for financial data manipulation).
  * **Market Data:** **yfinance** (To pull live ACHR prices or potential IPO comps).
  * **Storage:** **JSON or SQLite** (Simple, local file-based storage to save your "Scenarios").
  * **OS:** Ubuntu (Native home for these tools).

-----

### **II. Detailed Module Design**

You should organize your code into four distinct logic modules. Do not try to write one giant script.

#### **1. The Income & Equity Module (`equity.py`)**

This is where you model your complex compensation. You need a class structure that can handle the different tax treatments of your grants.

  * **Inputs:**
      * Salary (Base)
      * RSU Grants (Vesting schedule, Grant Price, *Current* Price)
      * ISO Grants (Strike Price, FMV, Vesting)
      * Wife’s ESPP (Contribution %, Discount, Lookback provision)
  * **Key Logic:**
      * **RSU Income:** `(Vested Shares * Current Price)` treated as **Ordinary Income**.
      * **ISO "Spread":** `(FMV - Strike)` at exercise. This is **0 tax** for Regular Tax but **100% taxable** for AMT.
      * **Hypothetical IPO Slider:** A global variable that lets you change the stock price from $5 to $50 to see how your Net Worth changes instantly.

#### **2. The Tax Engine (`tax_engine.py`)**

*This is the most critical component for you.* Do not hard-code tax rates; create a "TaxRegime" class so you can swap "California 2025" for "Alabama 2026".

  * **Features:**
      * **Dual-Calculation:** You must run two parallel calculations for every scenario: **Regular Tax** and **AMT**. You pay whichever is *higher*.
      * **State Logic:**
          * **CA:** High income tax (up to 13.3%+), treats capital gains as ordinary income.
          * **AL:** Lower income tax (\~5%), but you need to check if they follow federal rules for AMT (Alabama generally ties to federal AGI but has different deductions).
      * **The "ISO Trap" Detector:** A visual warning if your ISO exercise creates a massive AMT bill that isn't covered by cash liquidity.

#### **3. The "Move to Birmingham" Simulator (`scenarios.py`)**

This module compares two defined states.

  * **Scenario A:** Stay in CA for 5 years. High cost of living, high tax, high salary growth potential.
  * **Scenario B:** Move to AL in Year 2.
      * *Input:* Cost of Living Adjustment (e.g., Housing -40%).
      * *Input:* Salary Adjustment (will your private co. adjust pay for location?).
      * *Output:* Net Savings Rate comparison.

#### **4. Retirement & Passive Income (`retirement.py`)**

Since you asked about passive income, you need a module that calculates **SWR (Safe Withdrawal Rate)** based on your nest egg.

  * **Monte Carlo Simulation:** Don't just assume 7% growth. Run 1,000 simulations using historical volatility (use `numpy`) to see the probability of ruining your portfolio if you retire early.

-----

### **III. Proposed Dashboard Layout (UI)**

In Streamlit, you can use "Tabs" to keep the interface clean.

**Sidebar:**

  * Global Inputs: `Current Age`, `ACHR Stock Price`, `Private Co. Share Price`, `Inflation Rate`.
  * **Action Button:** `Save Current Scenario`.

**Tab 1: The "This Year" View (Tax & Cash Flow)**

  * **Visual:** A Waterfall chart showing: `Gross Pay` -\> `Taxes (Fed/State/AMT)` -\> `Expenses` -\> `Net Savings`.
  * **Interactive:** A slider for "ISO Options to Exercise". As you slide it up, watch a red bar ("AMT Bill") grow on the chart.
  * **Insight:** A metric showing your "Effective Tax Rate" blending CA and Fed taxes.

**Tab 2: The "California vs. Alabama" Comparison**

  * **Visual:** Split screen. Left side is CA, Right side is AL.
  * **Data:** A table comparing "Disposable Income" after housing and taxes in both locations.
  * **Key Consideration:** AL has lower property taxes but different sales tax structures.

**Tab 3: Financial Independence (FIRE)**

  * **Visual:** A line graph projecting your Net Worth vs. your "Financial Independence Number" (e.g., 25x annual expenses).
  * **Inputs:** Passive Income Strategies toggles:
      * *Dividend Yield:* Input expected yield (e.g., 3-4% from SCHD/VYM).
      * *Rental Income:* Input expected Birmingham rental yields (Cap rates are often higher in AL than CA).

-----

### **IV. Getting Started (Code Skeleton)**

Here is the exact structure to create on your Ubuntu machine:

```bash
/finance-app
    ├── app.py              # Main Streamlit entry point
    ├── data/               # Folder for saving scenarios (JSON)
    ├── logic/
    │   ├── equity.py       # RSU/ISO calculations
    │   ├── tax.py          # US/CA/AL tax brackets
    │   └── monte_carlo.py  # Retirement simulations
    └── requirements.txt    # streamlit, pandas, yfinance, plotly
```

**Step 1: Install Dependencies**

```bash
pip install streamlit pandas yfinance plotly numpy
```

**Step 2: Create a simple `app.py`**

```python
import streamlit as st
import pandas as pd
from logic.tax import calculate_taxes

st.set_page_config(page_title="Family Finance Dashboard", layout="wide")

st.title("Family Financial Planning & Tax Tool")

# Sidebar Scenarios
location = st.sidebar.selectbox("Location", ["California", "Alabama"])
private_stock_price = st.sidebar.number_input("Private Co. Stock Price ($)", 10, 100, 25)

# Main Dashboard
col1, col2 = st.columns(2)

with col1:
    st.subheader("Income & Equity")
    salary = st.number_input("Combined Base Salary", value=200000)
    rsu_vest = st.number_input("RSU Value Vesting This Year", value=50000)
    
    # Simple Tax Estimate Call (You would build this logic out)
    tax_bill = calculate_taxes(salary + rsu_vest, location)
    st.metric("Estimated Tax Bill", f"${tax_bill:,}")

with col2:
    st.subheader("ISO Strategy")
    isos_to_exercise = st.slider("ISOs to Exercise", 0, 10000, 0)
    strike_price = 2.00
    spread = (private_stock_price - strike_price) * isos_to_exercise
    
    if spread > 80000: # Rough AMT exemption threshold warning
        st.error(f"Warning: AMT Risk! Spread is ${spread:,}")
    else:
        st.success(f"ISO Spread: ${spread:,}")
```

### **V. Specific Advice for Your Situation**

1.  **The "Alabama Arbitrage":**

      * Your app needs to calculate the "Geographic Arbitrage." If you keep your CA salary (or most of it) but move to AL, your savings rate effectively doubles.
      * *Feature to build:* A "Moving Cost Amortization" calculator. Moving is expensive. Calculate how many months of "Alabama Savings" it takes to break even on the move.

2.  **AMT Credits:**

      * If you trigger AMT in California by exercising ISOs, you generate an **AMT Credit** that you can use in future years to lower your regular tax.
      * *App Logic:* You need a "Tax Carryforward" variable in your data model. If `Year 1 AMT > Regular Tax`, store the difference. In `Year 2`, check if you can use that credit.

3.  **Passive Income Strategy for Birmingham:**

      * Birmingham has a very different real estate market than CA.
      * *Strategy:* Build a "Rental Property" module where you can input a $250k Birmingham house price, 20% down, and $1,800 rent. Compare this Return on Equity (ROE) against just keeping that money in the S\&P 500.
