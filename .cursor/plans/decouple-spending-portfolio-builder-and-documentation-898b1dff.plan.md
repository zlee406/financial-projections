<!-- 898b1dff-2e3f-4970-a67a-eab4a450bce8 685da463-37ae-4b66-bb09-b304e367399c -->
# Project Plan: Compare Tab, Save/Load, and House Modeling

## 1. Data Model & Logic Updates (`logic/lifecycle.py`)

- **Update Child Class**:
- Replace `current_age` with `birth_year`.
- Add `current_year` parameter to `SpendingModel` to calculate ages dynamically.
- **Add FuturePurchase Class**:
- Create `FuturePurchase` dataclass with: `purchase_year` (or age), `price`, `down_payment`, `interest_rate`, `term_years`, `property_tax_rate`, `maintenance_rate`.
- **Update SpendingModel**:
- Incorporate `FuturePurchase` logic into `generate_schedule`:
- **One-time cost**: Down payment in purchase year.
- **Recurring cost**: Mortgage P&I (for term years).
- **Ongoing cost**: Property tax + maintenance (forever/until death).
- We should be able to add multiple of these in different years.

## 2. App State & Save/Load (`app.py`)

- **Session State Standardization**:
- Assign unique `key`s to all Streamlit input widgets to map them to `st.session_state`.
- **Save/Load Logic**:
- Implement `save_scenario()`: Dumps relevant `session_state` keys to a JSON structure.
- Implement `load_scenario()`: Uploads JSON and updates `session_state`.
- Add "Save" (Download Button) and "Load" (File Uploader) in a "Settings" or Sidebar area.

## 3. Compare Tab (`app.py`)

- **New Tab**: "Compare Strategies".
- **Scenario Management**:
- Allow users to "Add Current Strategy" to a comparison list.
- Store comparison scenarios in `st.session_state['comparison_scenarios']`.
- **Concise Module**:
- Render a compact card/expander for each saved scenario.
- **Editable Inputs**: Allow modifying key inputs (Stock %, Spend, Strategy) directly in the comparison card.
- **Visualization**:
- Comparative Table: Success Rate, Median Ending Wealth, etc.
- Comparative Charts: Success Probability curves or Wealth distribution overlays.

## 4. UI Refinements (`app.py`)

- **Stock Slider**: Replace with `st.number_input` (0-100) with validation.
- **Child Input**: Update to "Birth Year" input.
- **House Input**: Add section in "Spending Builder" for `FuturePurchase` details.
- **Net Worth Tracking (Bonus)**: Simple calculation of Home Equity over time to display alongside portfolio value in the single-run view if a house is purchased.

### To-dos

- [ ] Update logic/retirement.py: Implement bucketed portfolio logic (Liquid vs 401k) and IPO windfall.
- [ ] Update logic/lifecycle.py: Ensure SpendingModel is serializable/clean for multiple instances.
- [ ] Update app.py: Implement Portfolio Builder UI & Spending Strategy Manager.
- [ ] Update app.py: Integrate new logic into Analysis Tab & Add Documentation.
- [ ] Update tests/test_retirement.py: Test bucket logic.