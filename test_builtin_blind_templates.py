"""Regression checks for Texas-style and lower-blind built-in templates."""
import copy
import importlib.util
from pathlib import Path
SOURCE = Path(__file__).with_name("poker_tournament_director.py")
spec = importlib.util.spec_from_file_location("mypoker_builtin_templates_test_v627", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

expected_keys = {"small_stack_20", "texas_standard_20", "texas_turbo_15", "texas_hyper_turbo_10", "texas_deep_stack_25"}
assert set(module.BUILT_IN_BLIND_TEMPLATES) == expected_keys
assert set(module.BUILT_IN_BLIND_TEMPLATE_LABELS.values()) == expected_keys
assert len(module.BUILT_IN_BLIND_TEMPLATE_LABELS) == 5
assert module.BLIND_TEMPLATE_STARTING_STACKS["small_stack_20"] == 10000
assert all(module.BLIND_TEMPLATE_STARTING_STACKS[k] == 25000 for k in expected_keys if k.startswith("texas_"))

for key, rows in module.BUILT_IN_BLIND_TEMPLATES.items():
    assert rows, f"{key} should not be empty"
    play_rows = [row for row in rows if row.get("kind") != "Break"]
    assert play_rows, f"{key} needs play levels"
    for row in rows:
        assert int(row.get("minutes", 0)) >= 1, f"{key} has invalid duration"
        if row.get("kind") == "Break":
            assert int(row.get("sb", 0)) == 0 and int(row.get("bb", 0)) == 0
            expected_pause = key == "texas_turbo_15"
            assert row.get("pause_after") is expected_pause, f"Unexpected pause setting for {key}: {row}"
        else:
            assert int(row.get("sb", 0)) > 0 and int(row.get("bb", 0)) > 0

small = [r for r in module.BUILT_IN_BLIND_TEMPLATES["small_stack_20"] if r.get("kind") != "Break"]
assert [(r["sb"], r["bb"]) for r in small[:2]] == [(25, 50), (50, 100)]
for key in expected_keys - {"small_stack_20"}:
    plays = [r for r in module.BUILT_IN_BLIND_TEMPLATES[key] if r.get("kind") != "Break"]
    assert [(r["sb"], r["bb"]) for r in plays[:2]] == [(100, 200), (200, 400)], key
assert all(r["minutes"] == 20 for r in small)
assert all(r["minutes"] == 20 for r in module.BUILT_IN_BLIND_TEMPLATES["texas_standard_20"] if r.get("kind") != "Break")
assert all(r["minutes"] == 15 for r in module.BUILT_IN_BLIND_TEMPLATES["texas_turbo_15"] if r.get("kind") != "Break")
turbo_rows = module.BUILT_IN_BLIND_TEMPLATES["texas_turbo_15"]
turbo_plays = [r for r in turbo_rows if r.get("kind") != "Break"]
turbo_breaks = [r for r in turbo_rows if r.get("kind") == "Break"]
assert [(r["sb"], r["bb"]) for r in turbo_plays] == [
    (100, 200), (200, 400), (300, 600), (400, 800), (500, 1000), (1000, 2000),
    (2000, 4000), (3000, 6000), (4000, 8000), (5000, 10000), (10000, 20000),
    (20000, 40000), (40000, 80000), (80000, 160000),
]
assert len(turbo_breaks) == 2
assert all(r["pause_after"] is True for r in turbo_breaks)
assert all(r["minutes"] == 10 for r in module.BUILT_IN_BLIND_TEMPLATES["texas_hyper_turbo_10"] if r.get("kind") != "Break")
assert all(r["minutes"] == 25 for r in module.BUILT_IN_BLIND_TEMPLATES["texas_deep_stack_25"] if r.get("kind") != "Break")

working_copy = copy.deepcopy(module.BUILT_IN_BLIND_TEMPLATES["texas_turbo_15"])
working_copy[0]["minutes"] = 99
working_copy.append({"name": "Test row", "minutes": 1, "sb": 1, "bb": 2, "ante": 0, "kind": "Play"})
assert module.BUILT_IN_BLIND_TEMPLATES["texas_turbo_15"][0]["minutes"] == 15
assert len(working_copy) == len(module.BUILT_IN_BLIND_TEMPLATES["texas_turbo_15"]) + 1
print("PASS: five built-in templates include four Texas-style 100/200 starts plus the preserved 25/50 Small Stack option.")
