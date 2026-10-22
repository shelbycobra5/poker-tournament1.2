"""Regression check: workbook import parser preserves per-break Pause? values."""
import importlib.util
from pathlib import Path
SOURCE = Path(__file__).with_name("poker_tournament_director.py")
spec = importlib.util.spec_from_file_location("mypoker_pause_import_test", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ParserHelpers:
    _column_index = staticmethod(module.TournamentDirector._column_index)
    _cell = staticmethod(module.TournamentDirector._cell)
    _import_integer = staticmethod(module.TournamentDirector._import_integer)

rows = [
    ["Template workbook example"],
    ["Editable schedule"],
    ["Keep headers in row 5"],
    [],
    ["Order", "Name", "Kind", "Minutes", "Small Blind", "Big Blind", "Ante", "Pause?"],
    [1, "Level 1", "Play", 15, 25, 50, 0, "—"],
    [2, "Break 1", "Break", 10, 0, 0, 0, "Yes"],
    [3, "Level 2", "Play", 20, 50, 100, 0, "—"],
    [4, "Break 2", "Break", 5, 0, 0, 0, "No"],
]
parsed = module.TournamentDirector._parse_level_rows(ParserHelpers(), rows)
assert len(parsed) == 4
assert parsed[1]["kind"] == "Break" and parsed[1]["pause_after"] is True
assert parsed[3]["kind"] == "Break" and parsed[3]["pause_after"] is False
assert parsed[0]["minutes"] == 15 and parsed[2]["minutes"] == 20
print("PASS: imported Excel-style rows retain each break's Pause? setting and level durations.")

# Load the delivered workbook using the same XLSX reader used by the app.
workbook_path = Path(__file__).with_name("MyPoker Blind Structure Templates.xlsx")
sheets = module.read_xlsx_sheets(str(workbook_path))
expected = {
    "Small Stack 20 Min": (8, 2),
    "Texas Standard 20 Min": (16, 3),
    "Texas Turbo 15 Min": (14, 2),
    "Texas Hyper 10 Min": (12, 2),
    "Texas Deep Stack 25": (17, 4),
}
for sheet_name, (expected_play, expected_breaks) in expected.items():
    imported_rows = module.TournamentDirector._parse_level_rows(ParserHelpers(), sheets[sheet_name])
    assert sum(row["kind"] != "Break" for row in imported_rows) == expected_play, sheet_name
    assert sum(row["kind"] == "Break" for row in imported_rows) == expected_breaks, sheet_name
print("PASS: all five sheets in the delivered Excel workbook import through the app's XLSX reader.")
