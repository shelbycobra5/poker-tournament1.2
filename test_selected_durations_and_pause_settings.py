"""Regression checks for selected durations and individual break pause settings."""
import copy
import importlib.util
import types
from pathlib import Path

SOURCE = Path(__file__).with_name("poker_tournament_director.py")
spec = importlib.util.spec_from_file_location("mypoker_v62_test", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Scenario normalization preserves per-break settings and discards obsolete global pause flags.
app_stub = types.SimpleNamespace(sound_overrides={})
levels = [
    {"name": "Level 1", "minutes": 15, "sb": 25, "bb": 50, "ante": 0, "kind": "Play"},
    {"name": "Break 1", "minutes": 10, "sb": 0, "bb": 0, "ante": 0, "kind": "Break", "pause_after": True},
    {"name": "Level 2", "minutes": 20, "sb": 50, "bb": 100, "ante": 0, "kind": "Play"},
    {"name": "Break 2", "minutes": 5, "sb": 0, "bb": 0, "ante": 0, "kind": "Break", "pause_after": False},
]
config = {"tournament_type": "Standard Tournament", "levels": copy.deepcopy(levels),
          "pause_after_blind_level": True, "pause_after_break": True}
normalized = module.TournamentDirector._normalize_scenario_config(app_stub, config)
assert normalized is not None
assert "pause_after_blind_level" not in normalized
assert "pause_after_break" not in normalized
assert normalized["levels"][1]["pause_after"] is True
assert normalized["levels"][3]["pause_after"] is False

# Older scenario-level global break flags must not override individual row settings.
legacy = {"tournament_type": "Standard Tournament", "pause_after_break": True, "pause_after_blind_level": True, "levels": [
    {"name": "Level 1", "minutes": 15, "sb": 25, "bb": 50, "kind": "Play"},
    {"name": "Break 1", "minutes": 10, "sb": 0, "bb": 0, "kind": "Break"},
]}
legacy_normalized = module.TournamentDirector._normalize_scenario_config(app_stub, legacy)
assert legacy_normalized is not None
assert "pause_after_break" not in legacy_normalized
assert "pause_after_blind_level" not in legacy_normalized
assert legacy_normalized["levels"][1]["pause_after"] is False

# Selected-duration application only touches selected rows of the requested kind.
class FakeVar:
    def __init__(self, value): self.value = value
    def get(self): return self.value

class FakeTree:
    def __init__(self, selected): self.selected = selected
    def selection(self): return tuple(self.selected)

class FakeApp:
    fill_selected_durations = module.TournamentDirector.fill_selected_durations
    def __init__(self):
        self.levels = copy.deepcopy(levels)
        self.level_tree = FakeTree(["0", "2", "3"])
        self.play_duration_var = FakeVar("25")
        self.break_duration_var = FakeVar("7")
        self.current_level = 2
        self.remaining_seconds = 1200
        self.running = False
        self.history = []
        self.saved = False
        self.refreshed = False
    def _save_data(self): self.saved = True
    def _refresh_all(self): self.refreshed = True

fake = FakeApp()
old_showinfo = module.messagebox.showinfo
old_showerror = module.messagebox.showerror
try:
    module.messagebox.showinfo = lambda *args, **kwargs: None
    module.messagebox.showerror = lambda *args, **kwargs: None
    fake.fill_selected_durations("Play")
    assert fake.levels[0]["minutes"] == 25
    assert fake.levels[2]["minutes"] == 25
    assert fake.levels[3]["minutes"] == 5  # Wrong-kind selected row is ignored.
    assert fake.remaining_seconds == 1500
    fake.fill_selected_durations("Break")
    assert fake.levels[3]["minutes"] == 7
    assert fake.levels[1]["minutes"] == 10  # Unselected break remains unchanged.
    assert fake.saved and fake.refreshed
finally:
    module.messagebox.showinfo = old_showinfo
    module.messagebox.showerror = old_showerror

print("PASS: global pause flags are ignored, per-break pause settings are preserved, and selected duration updates are scoped correctly.")
