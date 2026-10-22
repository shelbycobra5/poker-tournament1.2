"""Small regression test for the header Save behavior without opening a GUI."""
import copy
import importlib.util
from pathlib import Path

SOURCE = Path(__file__).with_name("poker_tournament_director.py")
spec = importlib.util.spec_from_file_location("mypoker_test_module", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class FakeStatus:
    def __init__(self): self.value = ""
    def set(self, value): self.value = value

class FakeTree:
    def selection_set(self, _value): pass
    def focus(self, _value): pass

class FakeApp:
    _save_from_header = module.TournamentDirector._save_from_header
    def __init__(self):
        self.levels = [
            {"name": "Imported 1", "minutes": 17, "sb": 100, "bb": 200, "ante": 25, "kind": "Play"},
            {"name": "Dinner Break", "minutes": 12, "sb": 0, "bb": 0, "ante": 0, "kind": "Break"},
            {"name": "Imported 2", "minutes": 19, "sb": 200, "bb": 400, "ante": 50, "kind": "Play"},
        ]
        self.active_scenario_id = "scenario-1"
        self.scenarios = [{"id": "scenario-1", "name": "Friday Game", "description": "test", "config": {"old": True}}]
        self.scenario_tree = FakeTree()
        self.scenario_status_var = FakeStatus()
        self.applied = False
        self.library_saved = False
        self.session_saved = False
    def _apply_tournament_settings_from_form(self):
        self.applied = True
        return True
    def _scenario_config_snapshot(self, levels_override=None):
        return {"levels": copy.deepcopy(levels_override), "tournament_name": "Edited Tournament"}
    def _normalize_scenario_config(self, raw): return raw
    def _save_scenario_library(self):
        self.library_saved = True
        return True
    def _refresh_scenario_tree(self): pass
    def _scenario_selection_changed(self): pass
    def _save_data(self): self.session_saved = True

app = FakeApp()
original_levels = copy.deepcopy(app.levels)
app._save_from_header()
assert app.applied
assert app.library_saved and app.session_saved
assert app.scenarios[0]["config"]["levels"] == original_levels
assert app.scenarios[0]["config"]["tournament_name"] == "Edited Tournament"
assert app.scenarios[0]["updated_at"]
assert "Friday Game" in app.scenario_status_var.value
print("PASS: header Save updates the active scenario with imported play levels/breaks and saves the session.")
