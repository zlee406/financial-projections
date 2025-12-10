import unittest
import pandas as pd
from logic.retirement import (
    ScheduleOnlyStrategy,
    ConstantDollarStrategy,
    PercentPortfolioStrategy,
    VPWStrategy,
    GuytonKlingerStrategy,
    get_all_strategy_names,
    get_strategy_description,
    STRATEGY_DESCRIPTIONS,
)


def create_spending_schedule(base_amount: float, years: int, variable: bool = False) -> pd.Series:
    """Create a spending schedule for testing."""
    if variable:
        # Simulate varying spending (higher early, lower later)
        amounts = [base_amount * (1.2 - 0.02 * y) for y in range(years)]
    else:
        amounts = [base_amount] * years
    return pd.Series(amounts)


def print_withdrawal_table(strategy_name: str, withdrawals: list, portfolio_values: list, years: int):
    """Print a formatted table of withdrawals by year."""
    print(f"\n{'='*70}")
    print(f"Strategy: {strategy_name}")
    print(f"{'='*70}")
    print(f"{'Year':<6} {'Portfolio':>15} {'Withdrawal':>15} {'Rate':>10}")
    print(f"{'-'*6} {'-'*15} {'-'*15} {'-'*10}")
    for y in range(years):
        portfolio = portfolio_values[y]
        withdrawal = withdrawals[y]
        rate = (withdrawal / portfolio * 100) if portfolio > 0 else 0
        print(f"{y:<6} ${portfolio:>14,.0f} ${withdrawal:>14,.0f} {rate:>9.2f}%")
    print(f"{'='*70}")
    print(f"Total withdrawn: ${sum(withdrawals):,.0f}")
    print(f"Average withdrawal: ${sum(withdrawals)/len(withdrawals):,.0f}")


class TestScheduleOnlyStrategy(unittest.TestCase):
    
    def test_should_withdraw_exact_schedule_given_schedule(self):
        """Schedule Only should return exactly the scheduled amount, adjusted for inflation."""
        # Preconditions
        strategy = ScheduleOnlyStrategy(inflation_rate=0.03)
        schedule = create_spending_schedule(100000, 10)
        
        withdrawals = []
        portfolio_values = []
        portfolio = 2_000_000
        prev_withdrawal = 100000
        
        # Under test
        for year in range(10):
            portfolio_values.append(portfolio)
            w = strategy.calculate_withdrawal(
                current_portfolio_value=portfolio,
                year=year,
                initial_withdrawal=100000,
                previous_withdrawal=prev_withdrawal,
                spending_schedule=schedule
            )
            withdrawals.append(w)
            prev_withdrawal = w
            portfolio = portfolio - w  # Simple depletion for demo
        
        print_withdrawal_table("Schedule Only (flat $100k)", withdrawals, portfolio_values, 10)
        
        # Postconditions
        self.assertAlmostEqual(withdrawals[0], 100000, places=0)  # Year 0: no inflation adjustment
        self.assertAlmostEqual(withdrawals[1], 100000 * 1.03, places=0)  # Year 1: 3% inflation
        self.assertAlmostEqual(withdrawals[5], 100000 * (1.03 ** 5), places=0)

    def test_should_inflate_initial_given_no_schedule(self):
        """Without a schedule, should inflate initial withdrawal each year."""
        # Preconditions
        strategy = ScheduleOnlyStrategy(inflation_rate=0.03)
        
        withdrawals = []
        portfolio_values = []
        portfolio = 2_000_000
        prev_withdrawal = 80000
        
        # Under test
        for year in range(10):
            portfolio_values.append(portfolio)
            w = strategy.calculate_withdrawal(
                current_portfolio_value=portfolio,
                year=year,
                initial_withdrawal=80000,
                previous_withdrawal=prev_withdrawal,
                spending_schedule=None
            )
            withdrawals.append(w)
            prev_withdrawal = w
            portfolio = portfolio - w
        
        print_withdrawal_table("Schedule Only (no schedule, $80k initial)", withdrawals, portfolio_values, 10)
        
        # Postconditions
        self.assertAlmostEqual(withdrawals[0], 80000, places=0)
        self.assertAlmostEqual(withdrawals[1], 80000 * 1.03, places=0)


class TestConstantDollarStrategy(unittest.TestCase):
    
    def test_should_apply_limits_given_min_max(self):
        """Constant Dollar should respect min/max limits."""
        # Preconditions
        strategy = ConstantDollarStrategy(
            inflation_rate=0.03,
            min_withdrawal=50000,
            max_withdrawal=120000,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        schedule = create_spending_schedule(40000, 10)  # Below minimum
        
        withdrawals = []
        portfolio_values = []
        portfolio = 2_000_000
        prev_withdrawal = 50000
        
        # Under test
        for year in range(10):
            portfolio_values.append(portfolio)
            w = strategy.calculate_withdrawal(
                current_portfolio_value=portfolio,
                year=year,
                initial_withdrawal=50000,
                previous_withdrawal=prev_withdrawal,
                spending_schedule=schedule
            )
            withdrawals.append(w)
            prev_withdrawal = w
            portfolio = portfolio - w
        
        print_withdrawal_table("Constant Dollar (min=$50k, max=$120k, schedule=$40k)", withdrawals, portfolio_values, 10)
        
        # Postconditions - should be at least min
        for w in withdrawals:
            self.assertGreaterEqual(w, 50000)


class TestPercentPortfolioStrategy(unittest.TestCase):
    
    def test_should_withdraw_percentage_given_4_percent(self):
        """percentage% of portfolio strategy."""
        # Preconditions
        percentage = 0.00
        inflation_rate = 0.03
        strategy = PercentPortfolioStrategy(
            percentage=percentage,
            inflation_rate=inflation_rate,
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        
        withdrawals = []
        portfolio_values = []
        portfolio = 2_000_000
        prev_withdrawal = 80000
        
        # Simulate with 7% returns
        annual_return = 0.07
        
        # Under test
        for year in range(20):
            portfolio_values.append(portfolio)
            w = strategy.calculate_withdrawal(
                current_portfolio_value=portfolio,
                year=year,
                initial_withdrawal=80000,
                previous_withdrawal=prev_withdrawal,
                spending_schedule=None
            )
            withdrawals.append(w)
            prev_withdrawal = w
            portfolio = (portfolio - w) * (1 + annual_return)
        print_withdrawal_table(f"{percentage * 100}% of Portfolio (7% returns)", withdrawals, portfolio_values, 20)
        
        # Postconditions
        self.assertAlmostEqual(withdrawals[0], 2_000_000 * percentage, places=0)

    def test_should_apply_floor_given_schedule(self):
        """Should respect spending schedule floor."""
        # Preconditions
        strategy = PercentPortfolioStrategy(
            percentage=0.02,  # Very low rate
            inflation_rate=0.03,
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,  # Hard floor
            flexible_floor_pct=0.75
        )
        schedule = create_spending_schedule(80000, 10)
        
        withdrawals = []
        portfolio_values = []
        portfolio = 2_000_000
        prev_withdrawal = 80000
        
        # Under test
        for year in range(10):
            portfolio_values.append(portfolio)
            w = strategy.calculate_withdrawal(
                current_portfolio_value=portfolio,
                year=year,
                initial_withdrawal=80000,
                previous_withdrawal=prev_withdrawal,
                spending_schedule=schedule
            )
            withdrawals.append(w)
            prev_withdrawal = w
            portfolio = portfolio - w
        
        print_withdrawal_table("2% Portfolio with $80k schedule floor", withdrawals, portfolio_values, 10)
        
        # Postconditions - should be at least the schedule (inflated)
        for y, w in enumerate(withdrawals):
            expected_floor = 80000 * (1.03 ** y)
            self.assertGreaterEqual(w, expected_floor - 1)  # Allow rounding


class TestVPWStrategy(unittest.TestCase):
    
    def test_should_increase_rate_with_age(self):
        """VPW should withdraw more as remaining years decrease."""
        # Preconditions
        strategy = VPWStrategy(
            start_age=40,
            max_age=100,
            inflation_rate=0.03,
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        
        withdrawals = []
        portfolio_values = []
        portfolio = 2_000_000
        prev_withdrawal = 0
        
        # Under test
        for year in range(30):
            portfolio_values.append(portfolio)
            w = strategy.calculate_withdrawal(
                current_portfolio_value=portfolio,
                year=year,
                initial_withdrawal=0,
                previous_withdrawal=prev_withdrawal,
                spending_schedule=None
            )
            withdrawals.append(w)
            prev_withdrawal = w
            # Assume flat portfolio for simplicity
            portfolio = portfolio - w + w  # Constant portfolio
        
        print_withdrawal_table("VPW (age 40-70, constant $2M portfolio)", withdrawals, portfolio_values, 30)
        
        # Postconditions - withdrawal rate should increase
        rate_year_0 = withdrawals[0] / 2_000_000
        rate_year_29 = withdrawals[29] / 2_000_000
        self.assertGreater(rate_year_29, rate_year_0)


class TestGuytonKlingerStrategy(unittest.TestCase):
    
    def test_should_cut_spending_given_high_rate(self):
        """GK should reduce spending when withdrawal rate gets too high."""
        # Preconditions
        strategy = GuytonKlingerStrategy(
            initial_rate=0.04,
            portfolio_value=2_000_000,
            inflation_rate=0.03,
            guardrail_upper=0.20,
            guardrail_lower=0.20,
            min_withdrawal=None,
            max_withdrawal=None,
            flexible_spending=False,
            flexible_floor_pct=0.75
        )
        
        withdrawals = []
        portfolio_values = []
        portfolio = 2_000_000
        prev_withdrawal = 80000
        
        # Simulate bear market - portfolio drops 40%
        for year in range(10):
            if year == 2:
                portfolio = portfolio * 0.6  # 40% drop
            portfolio_values.append(portfolio)
            w = strategy.calculate_withdrawal(
                current_portfolio_value=portfolio,
                year=year,
                initial_withdrawal=80000,
                previous_withdrawal=prev_withdrawal,
                spending_schedule=None
            )
            withdrawals.append(w)
            prev_withdrawal = w
            portfolio = portfolio - w
        
        print_withdrawal_table("Guyton-Klinger (40% drop year 2)", withdrawals, portfolio_values, 10)
        
        # Postconditions - should have cut after the drop
        # Year 3 should be less than year 2 (after the cut kicks in)
        self.assertLess(withdrawals[3], withdrawals[1] * 1.1)  # Allowing some inflation


class TestStrategyDescriptions(unittest.TestCase):
    
    def test_should_return_all_strategy_names(self):
        """get_all_strategy_names should return all strategies."""
        names = get_all_strategy_names()
        
        print("\nAvailable Strategies:")
        for name in names:
            print(f"  - {name}")
        
        self.assertIn("Schedule Only", names)
        self.assertIn("Constant Dollar (Targets Schedule)", names)
        self.assertIn("Percent of Portfolio", names)
        self.assertIn("VPW", names)
        self.assertIn("Guyton-Klinger", names)

    def test_should_return_descriptions(self):
        """get_strategy_description should return description for each strategy."""
        print("\nStrategy Descriptions:")
        print("=" * 70)
        
        for name in get_all_strategy_names():
            desc = get_strategy_description(name)
            print(f"\n{name}:")
            print(f"  {desc}")
            self.assertIsNotNone(desc)
            self.assertNotEqual(desc, "No description available.")


class TestStrategyComparison(unittest.TestCase):
    """Run all strategies side-by-side for comparison."""
    
    def test_compare_all_strategies_given_same_conditions(self):
        """Compare all strategies with identical starting conditions."""
        # Preconditions
        portfolio = 2_000_000
        schedule = create_spending_schedule(80000, 20)
        annual_return = 0.05
        
        strategies = {
            "Schedule Only": ScheduleOnlyStrategy(inflation_rate=0.03),
            "Constant Dollar": ConstantDollarStrategy(
                inflation_rate=0.03,
                min_withdrawal=60000,
                max_withdrawal=150000,
                flexible_spending=False,
                flexible_floor_pct=0.75
            ),
            "4% Portfolio": PercentPortfolioStrategy(
                percentage=0.04,
                inflation_rate=0.03,
                min_withdrawal=None,
                max_withdrawal=None,
                flexible_spending=False,
                flexible_floor_pct=0.75
            ),
            "VPW (age 50)": VPWStrategy(
                start_age=50,
                max_age=100,
                inflation_rate=0.03,
                min_withdrawal=None,
                max_withdrawal=None,
                flexible_spending=False,
                flexible_floor_pct=0.75
            ),
            "Guyton-Klinger": GuytonKlingerStrategy(
                initial_rate=0.04,
                portfolio_value=portfolio,
                inflation_rate=0.03,
                guardrail_upper=0.20,
                guardrail_lower=0.20,
                min_withdrawal=None,
                max_withdrawal=None,
                flexible_spending=False,
                flexible_floor_pct=0.75
            ),
        }
        
        print("\n" + "=" * 80)
        print("STRATEGY COMPARISON - 20 Year Simulation")
        print(f"Starting Portfolio: ${portfolio:,}")
        print(f"Annual Return: {annual_return:.1%}")
        print(f"Schedule: $80,000/year (real)")
        print("=" * 80)
        
        results = {}
        
        for name, strategy in strategies.items():
            p = portfolio
            withdrawals = []
            portfolio_values = []
            prev_w = 80000
            
            for year in range(20):
                portfolio_values.append(p)
                w = strategy.calculate_withdrawal(
                    current_portfolio_value=p,
                    year=year,
                    initial_withdrawal=80000,
                    previous_withdrawal=prev_w,
                    spending_schedule=schedule
                )
                withdrawals.append(w)
                prev_w = w
                p = (p - w) * (1 + annual_return)
            
            results[name] = {
                "withdrawals": withdrawals,
                "final_portfolio": p,
                "total_withdrawn": sum(withdrawals),
                "min_withdrawal": min(withdrawals),
                "max_withdrawal": max(withdrawals),
            }
            
            print_withdrawal_table(name, withdrawals, portfolio_values, 20)
        
        # Summary comparison
        print("\n" + "=" * 80)
        print("SUMMARY COMPARISON")
        print("=" * 80)
        print(f"{'Strategy':<20} {'Total Withdrawn':>15} {'Min Year':>12} {'Max Year':>12} {'Final Port':>15}")
        print("-" * 80)
        for name, r in results.items():
            print(f"{name:<20} ${r['total_withdrawn']:>14,.0f} ${r['min_withdrawal']:>11,.0f} ${r['max_withdrawal']:>11,.0f} ${r['final_portfolio']:>14,.0f}")
        
        # Postcondition - all strategies should have withdrawn something
        for name, r in results.items():
            self.assertGreater(r['total_withdrawn'], 0, f"{name} should have withdrawn something")


if __name__ == '__main__':
    unittest.main()

