import unittest

class TestStrategyLogic(unittest.TestCase):
    def test_should_add_child_profile_to_strategy(self):
        # Precondition
        strategy_data = {
            "base_monthly_spend": 5000.0,
            "child_profiles": {}
        }
        
        new_prof_name = "Test Profile"
        
        # Under test
        # Logic from app.py
        child_profiles = strategy_data.get("child_profiles", {})
        
        if new_prof_name and new_prof_name not in child_profiles:
            child_profiles[new_prof_name] = [
                {"name": "Early Years", "start_age": 0, "end_age": 4, "annual_cost": 15000.0},
                {"name": "School", "start_age": 5, "end_age": 18, "annual_cost": 2000.0}
            ]
            if "child_profiles" not in strategy_data:
                strategy_data["child_profiles"] = child_profiles
        
        # Postcondition
        self.assertIn("Test Profile", strategy_data["child_profiles"])
        self.assertEqual(len(strategy_data["child_profiles"]["Test Profile"]), 2)

    def test_should_add_child_profile_when_key_missing_in_strategy(self):
        # Precondition
        strategy_data = {
            "base_monthly_spend": 5000.0
            # "child_profiles" missing
        }
        
        new_prof_name = "Test Profile"
        
        # Under test
        child_profiles = strategy_data.get("child_profiles", {})
        
        if new_prof_name and new_prof_name not in child_profiles:
            child_profiles[new_prof_name] = [
                {"name": "Early Years", "start_age": 0, "end_age": 4, "annual_cost": 15000.0}
            ]
            if "child_profiles" not in strategy_data:
                strategy_data["child_profiles"] = child_profiles
                
        # Postcondition
        self.assertIn("child_profiles", strategy_data)
        self.assertIn("Test Profile", strategy_data["child_profiles"])

    def test_should_not_overwrite_existing_profile(self):
        # Precondition
        strategy_data = {
            "child_profiles": {
                "Existing": [{"name": "Old", "start_age": 0, "end_age": 1, "annual_cost": 100}]
            }
        }
        
        new_prof_name = "Existing"
        
        # Under test
        child_profiles = strategy_data.get("child_profiles", {})
        
        was_added = False
        if new_prof_name and new_prof_name not in child_profiles:
            child_profiles[new_prof_name] = []
            was_added = True
            
        # Postcondition
        self.assertFalse(was_added)
        self.assertEqual(strategy_data["child_profiles"]["Existing"][0]["annual_cost"], 100)

if __name__ == '__main__':
    unittest.main()

