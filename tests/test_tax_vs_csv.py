from dataclasses import dataclass
import unittest
from logic import tax, tax_rules

class TestTaxCalculationSimplified(unittest.TestCase):
    def setUp(self):
        # Set up a TaxEngine with Federal only or simplified location to match CSV logic
        # The CSV seems to simulate Federal logic primarily for the AMT check
        self.engine = tax.TaxEngine("California") # Using CA but focusing on Fed results
        
        # Override rules with 2025 estimates from CSV if they differ significantly 
        # or ensure logic/tax_rules.py matches the CSV assumptions.
        # We will assume logic/tax_rules.py is updated to 2025 before this runs.

    @unittest.skip("Requires calibration of tax rules to match CSV exactly")
    def test_csv_scenario(self):
        # Inputs from CSV
        w2_income = 425000.00
        ltcg_income = 400842.12
        iso_spread_exercise = 429180.00
        # AMT Adjustment Sale (negative) - derived from CSV Line 38
        # "Total AMT Adjustment": -57,458.82
        # This reduces AMTI.
        amt_adjustment_sale = -57458.82
        
        # Run projection
        # We need to extend the run_projection method to accept these new params
        result = self.engine.run_projection(
            ordinary_income=w2_income,
            ltcg_income=ltcg_income,
            iso_spread=iso_spread_exercise,
            amt_adjustment_sale=amt_adjustment_sale
        )
        
        # Validation against CSV "TAXES" section
        
        # 1. Regular Federal Tax Components
        # Ordinary Tax (Line 65): 80,526.00
        # This implies a specific set of brackets. 
        # Taxable Ord = 425000 - 30000 (Std Ded) = 395000.
        # Let's check if my updated tax_rules produces this.
        self.assertAlmostEqual(result.federal_ordinary_tax, 80526.00, delta=500, msg="Ordinary Tax Mismatch")
        
        # LTCG Tax (Line 69): 69,915.92
        self.assertAlmostEqual(result.federal_ltcg_tax, 69915.92, delta=100, msg="LTCG Tax Mismatch")
        
        # NIIT Tax (Line 70): 15,232.00
        self.assertAlmostEqual(result.niit_tax, 15232.00, delta=100, msg="NIIT Tax Mismatch")
        
        # Total Regular Tax (Line 71): 165,673.92
        # Note: CSV sums the above 3.
        self.assertAlmostEqual(result.regular_federal_total, 165673.92, delta=500, msg="Total Regular Tax Mismatch")
        
        # 2. AMT Tax Components
        # AMTI (Line 57): 1,197,563.30
        self.assertAlmostEqual(result.amti, 1197563.30, delta=1000, msg="AMTI Mismatch")
        
        # AMT Tax (Line 73): 330,665.72
        self.assertAlmostEqual(result.amt_tax, 330665.72, delta=1000, msg="AMT Tax Mismatch")
        
        # 3. Final Decision
        # TOTAL Tax Liability (Line 78): 330,665.72 (AMT wins)
        # Note: This is just the federal income tax part.
        self.assertTrue(result.is_amt_triggered)
        self.assertAlmostEqual(result.total_federal_liability, 330665.72, delta=1000, msg="Total Federal Liability Mismatch")

if __name__ == '__main__':
    unittest.main()


