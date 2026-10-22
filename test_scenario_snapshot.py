"""Lightweight regression test for scenario blind-structure snapshot handling."""
import copy
import importlib.util
import types
from pathlib import Path

source = Path(__file__).with_name("poker_tournament_director.py")
spec = importlib.util.spec_from_file_location("mypoker_tournament_test", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

custom_levels = [
    {"name": "Imported 1", "minutes": 17, "sb": 125, "bb": 250, "ante": 25, "kind": "Play"},
    {"name": "Dinner break", "minutes": 12, "sb": 0, "bb": 0, "ante": 0, "kind": "Break"},
    {"name": "Imported 2", "minutes": 22, "sb": 200, "bb": 400, "ante": 50, "kind": "Play"},
]
app_stub = types.SimpleNamespace(
    levels=copy.deepcopy(custom_levels),
    _pre_freeroll_buy_in=None,
    _pre_freeroll_house_fee=None,
    _pre_freeroll_payout_mode=None,
    sound_overrides={},
)
snapshot = module.TournamentDirector._scenario_config_snapshot(app_stub, levels_override=custom_levels)
normalized = module.TournamentDirector._normalize_scenario_config(app_stub, snapshot)
assert normalized is not None
expected_levels = copy.deepcopy(custom_levels)
expected_levels[1]["pause_after"] = False  # Legacy break rows default to No without a per-break choice.
assert normalized["levels"] == expected_levels
print("PASS: custom blind levels, antes, durations, and breaks survive; missing break Pause? defaults to No.")
