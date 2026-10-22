"""Focused regression checks for configurable payout templates and user defaults."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "poker_tournament_director.py"
WORKBOOK = HERE / "MyPoker Payout Chart Templates.xlsx"
spec = importlib.util.spec_from_file_location("mypoker_payout_templates_test_v628", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# User-preferred entry thresholds: up to 10 pays 2, 11-20 pays 3, 21-30 pays 4.
assert module.DEFAULT_PAYOUT_RULES[:3] == [
    {"min_entries": 2, "max_entries": 10, "paid_places": 2},
    {"min_entries": 11, "max_entries": 20, "paid_places": 3},
    {"min_entries": 21, "max_entries": 30, "paid_places": 4},
]

# User-approved Texas Standard splits, including the corrected 4-place split.
assert module.DEFAULT_PAYOUT_TEMPLATE_NAME == "Texas Standard (Preferred)"
assert module.DEFAULT_PAYOUT_SPLITS[2] == [60, 40]
assert module.DEFAULT_PAYOUT_SPLITS[3] == [50, 30, 20]
assert module.DEFAULT_PAYOUT_SPLITS[4] == [50, 25, 16, 9]
assert sum(module.DEFAULT_PAYOUT_SPLITS[4]) == 100

# Alternative profile remains available and preserves the older built-in split.
assert module.BUILT_IN_PAYOUT_TEMPLATES["Balanced (Current Defaults)"][2] == [65, 35]
assert module.BUILT_IN_PAYOUT_TEMPLATES["Balanced (Current Defaults)"][4] == [45, 30, 15, 10]
assert len(module.BUILT_IN_PAYOUT_TEMPLATES) == 5
for profile_name, charts in module.BUILT_IN_PAYOUT_TEMPLATES.items():
    assert set(charts) == set(range(2, 16)), profile_name
    for paid_places, percentages in charts.items():
        assert len(percentages) == paid_places, (profile_name, paid_places)
        assert abs(sum(float(v) for v in percentages) - 100) <= 0.02, (profile_name, paid_places, percentages)
        assert all(float(v) > 0 for v in percentages), (profile_name, paid_places)

# Verify the actual Excel sheets can be read through the app's standard-library reader.
workbook_sheets = module.read_xlsx_sheets(str(WORKBOOK))
expected_workbook_sheets = {"Texas Standard", "Balanced Current", "Top Heavy", "Deeper Payout", "Flat Wide"}
assert expected_workbook_sheets.issubset(set(workbook_sheets)), set(workbook_sheets)
for sheet_name, profile_name in [
    ("Texas Standard", "Texas Standard (Preferred)"),
    ("Balanced Current", "Balanced (Current Defaults)"),
    ("Top Heavy", "Top-Heavy"),
    ("Deeper Payout", "Deeper Payout"),
    ("Flat Wide", "Flat / Wide Payout"),
]:
    parsed = module.parse_payout_template_rows(workbook_sheets[sheet_name])
    assert set(parsed) == set(range(2, 16)), (sheet_name, set(parsed))
    for places, split in parsed.items():
        assert abs(sum(split) - 100) <= 0.02, (sheet_name, places, split)
    if sheet_name == "Texas Standard":
        assert parsed[2] == [60, 40]
        assert parsed[3] == [50, 30, 20]
        assert parsed[4] == [50, 25, 16, 9]
    if sheet_name == "Balanced Current":
        assert parsed[2] == [65, 35]
        assert parsed[4] == [45, 30, 15, 10]

# Parser must reject a chart that does not total 100%.
invalid_rows = [
    ["Paid Places", "1st Place %", "2nd Place %", "3rd Place %", "4th Place %"],
    [4, 50, 25, 15, 9],
]
try:
    module.parse_payout_template_rows(invalid_rows)
except ValueError as exc:
    assert "not 100%" in str(exc)
else:
    raise AssertionError("Payout parser must reject charts that do not total 100%.")

print("PASS: payout entry thresholds, preferred splits, five alternative profiles, Excel import, and 100% validation.")
