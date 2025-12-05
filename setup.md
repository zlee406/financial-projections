# Setup Instructions

## 1. Environment Setup

It is recommended to use a conda virtual environment.

```bash
conda create -n finances python=3.11
conda activate finances
```

## 2. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## 3. Run the Application

Launch the Streamlit dashboard:

```bash
streamlit run app.py
```

The application will open in your default web browser (typically at http://localhost:8501).

## 4. Project Structure

- `app.py`: Main application file containing the UI and orchestration logic.
- `logic/`: Contains the core financial logic modules.
  - `tax.py`: Tax calculation engine.
  - `tax_rules.py`: Tax constants and bracket definitions (EDIT THIS for future years).
  - `equity.py`: Classes for handling RSUs and ISOs.
  - `monte_carlo.py`: Simulation logic for retirement planning.
- `data/`: Directory for storing saved scenarios (future feature).

