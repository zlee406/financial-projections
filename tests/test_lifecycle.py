import unittest
import pandas as pd
from logic.lifecycle import SpendingModel, HousingProject, Child, ChildCostPhase, SpendingItem

class TestSpendingModel(unittest.TestCase):
    def test_should_generate_schedule_with_base_spend(self):
        # Precondition
        model = SpendingModel(current_age=40, death_age=45, base_annual_spend=50000, current_year=2025)
        
        # Under test
        df = model.generate_schedule()
        
        # Postcondition
        self.assertEqual(len(df), 6) # 40, 41, 42, 43, 44, 45
        self.assertTrue((df["Required_Real_Spend"] == 50000).all())

    def test_should_handle_multiple_housing_projects(self):
        # Precondition
        hp1 = HousingProject(name="H1", purchase_year=2026, price=100000, down_payment=20000, interest_rate=0, term_years=10, property_tax_rate=0, maintenance_rate=0)
        hp2 = HousingProject(name="H2", purchase_year=2028, price=200000, down_payment=40000, interest_rate=0, term_years=10, property_tax_rate=0, maintenance_rate=0)
        
        model = SpendingModel(
            current_age=40, 
            death_age=50, 
            base_annual_spend=0, 
            current_year=2025,
            housing_projects=[hp1, hp2]
        )
        
        # Under test
        df = model.generate_schedule()
        
        # Postcondition
        # Note: Mortgage payments are deflated by EXPECTED_FUTURE_INFLATION (2.5%)
        # 2025 (Age 40): 0
        # 2026 (Age 41): Down Payment 1 (20k) + Mortgage 1 Starts (8k/1.025) = ~27.8k
        # 2027 (Age 42): 8k/1.025^2 = ~7.6k
        # 2028 (Age 43): Down Payment 2 (40k) + Mortgage 1 (8k/1.025^3) + Mortgage 2 (16k/1.025^3) = ~62.3k
        
        spends = df.set_index("Age")["Required_Real_Spend"]
        
        self.assertEqual(spends.loc[40], 0)
        self.assertAlmostEqual(spends.loc[41], 27805, delta=100)  # Down payment (20k) + deflated mortgage
        self.assertAlmostEqual(spends.loc[42], 7615, delta=100)   # Deflated mortgage payment
        self.assertAlmostEqual(spends.loc[43], 62286, delta=100)  # Down payment (40k) + deflated mortgages

    def test_should_calculate_child_costs_dynamically(self):
        # Precondition
        # Born 2020. Current Year 2025. Child is 5.
        phase1 = ChildCostPhase(name="Early", start_age=0, end_age=5, monthly_cost=10000/12)
        phase2 = ChildCostPhase(name="School", start_age=6, end_age=17, monthly_cost=5000/12)
        
        child = Child(name="Test", birth_year=2020, phases=[phase1, phase2])
        model = SpendingModel(
            current_age=30,
            death_age=35,
            base_monthly_spend=0,
            current_year=2025,
            children=[child]
        )
        
        # Under test
        df = model.generate_schedule()
        # 2025 (Age 30): Child Age 5 -> Phase 1 (10k)
        # 2026 (Age 31): Child Age 6 -> Phase 2 (5k)
        
        spends = df.set_index("Age")["Required_Real_Spend"]
        self.assertAlmostEqual(spends.loc[30], 10000, places=2)
        self.assertAlmostEqual(spends.loc[31], 5000, places=2)

    def test_should_handle_indefinite_spending_items(self):
        # Precondition
        item1 = SpendingItem(name="Indefinite End", monthly_amount=100, start_year=2026, end_year=None)
        item2 = SpendingItem(name="Start Now", monthly_amount=200, start_year=None, end_year=2026)
        
        model = SpendingModel(
            current_age=40,
            death_age=43,
            base_monthly_spend=0,
            current_year=2025,
            spending_items=[item1, item2]
        )
        
        # Under test
        df = model.generate_schedule()
        spends = df.set_index("Age")["Required_Real_Spend"]
        
        # 2025 (Age 40): Item2 (200*12=2400)
        self.assertEqual(spends.loc[40], 2400)
        
        # 2026 (Age 41): Item1 (100*12=1200) + Item2 (2400) = 3600
        self.assertEqual(spends.loc[41], 3600)
        
        # 2027 (Age 42): Item1 (1200)
        self.assertEqual(spends.loc[42], 1200)

    def test_should_deflate_mortgage_payments_with_inflation(self):
        # Precondition
        # Mortgage: 12k/year nominal.
        # Inflation: 10%.
        # Year 0: 12k real.
        # Year 1: 12k / 1.1 = 10909.09 real.
        
        hp1 = HousingProject(name="H1", purchase_year=2025, price=100000, down_payment=0, interest_rate=0, term_years=10, property_tax_rate=0, maintenance_rate=0)
        # Payment = 10k / year nominal
        
        model = SpendingModel(
            current_age=40,
            death_age=41,
            housing_projects=[hp1],
            current_year=2025
        )
        
        # Under test - now uses EXPECTED_FUTURE_INFLATION constant (2.5%)
        df = model.generate_schedule()
        
        spends = df.set_index("Age")["Required_Real_Spend"]
        
        # 2025 (Age 40): Year 0. Deflator = 1.0. Spend = 10k.
        self.assertAlmostEqual(spends.loc[40], 10000, places=0)
        
        # 2026 (Age 41): Year 1. Deflator = 1.025. Spend = 10k / 1.025 = 9756.1
        self.assertAlmostEqual(spends.loc[41], 9756.1, places=0)

if __name__ == '__main__':
    unittest.main()
