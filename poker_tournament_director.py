import csv
import json
import os
import re
import time
import zipfile
import math
import wave
import struct
import hashlib
import tempfile
import copy
import uuid
import sys
import subprocess
try:
    import winsound
except ImportError:  # Non-Windows environments use Tk's built-in bell as a fallback.
    winsound = None
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime
from posixpath import normpath, join as posix_join

APP_TITLE = "MyPoker Tournament"
APP_VERSION = "1.1.0"


def resource_path(filename):
    """Locate bundled resources in source runs and PyInstaller builds."""
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(bundle_dir, filename)


# This development package uses its own data folder so local-test settings, scenarios,
# and session archives never overwrite data from the installed v61 application.
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), "MyPokerTournament_Local_Test")
os.makedirs(APP_DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(APP_DATA_DIR, "mypoker_tournament.json")
LEGACY_DATA_FILE = os.path.join(APP_DATA_DIR, "poker_tournament_director.json")
# Migrate only data belonging to this local-test package, never production app data.
if not os.path.exists(DATA_FILE) and os.path.exists(LEGACY_DATA_FILE):
    try:
        import shutil as _shutil
        _shutil.copy2(LEGACY_DATA_FILE, DATA_FILE)
    except OSError:
        DATA_FILE = LEGACY_DATA_FILE
SCENARIOS_FILE = os.path.join(APP_DATA_DIR, "mypoker_tournament_scenarios.json")
TOURNAMENT_ARCHIVE_FILE = os.path.join(APP_DATA_DIR, "mypoker_tournament_sessions.json")

# Default entry thresholds match the user's usual live-game approach. For tournaments
# above 30 entries, progressively expand the paid field; the values remain editable in
# Tournament Settings > Payout Rules.
LEGACY_DEFAULT_PAYOUT_RULES = [
    {"min_entries": 2, "max_entries": 5, "paid_places": 2},
    {"min_entries": 6, "max_entries": 10, "paid_places": 3},
    {"min_entries": 11, "max_entries": 20, "paid_places": 4},
    {"min_entries": 21, "max_entries": 30, "paid_places": 5},
    {"min_entries": 31, "max_entries": 40, "paid_places": 6},
    {"min_entries": 41, "max_entries": 50, "paid_places": 7},
    {"min_entries": 51, "max_entries": 75, "paid_places": 9},
    {"min_entries": 76, "max_entries": 100, "paid_places": 10},
    {"min_entries": 101, "max_entries": 150, "paid_places": 12},
    {"min_entries": 151, "max_entries": 200, "paid_places": 15},
]
DEFAULT_PAYOUT_RULES = [
    {"min_entries": 2, "max_entries": 10, "paid_places": 2},
    {"min_entries": 11, "max_entries": 20, "paid_places": 3},
    {"min_entries": 21, "max_entries": 30, "paid_places": 4},
    {"min_entries": 31, "max_entries": 40, "paid_places": 5},
    {"min_entries": 41, "max_entries": 50, "paid_places": 6},
    {"min_entries": 51, "max_entries": 75, "paid_places": 8},
    {"min_entries": 76, "max_entries": 100, "paid_places": 10},
    {"min_entries": 101, "max_entries": 150, "paid_places": 12},
    {"min_entries": 151, "max_entries": 200, "paid_places": 15},
]

# Preserve the previous default chart as an optional profile, while making the user's
# preferred splits the default for 2, 3, and 4 paid places.
LEGACY_DEFAULT_PAYOUT_SPLITS = {
    2: [65, 35],
    3: [50, 30, 20],
    4: [45, 30, 15, 10],
    5: [40, 25, 15, 12, 8],
    6: [35, 23, 15, 11, 9, 7],
    7: [32, 22, 15, 11, 8, 7, 5],
    8: [30, 21, 15, 11, 8, 6, 5, 4],
    9: [28, 20, 15, 11, 8, 6, 5, 4, 3],
    10: [27, 19, 14, 10, 8, 6, 5, 4, 4, 3],
    12: [24, 17, 13, 10, 8, 6, 5, 4, 4, 3, 3, 3],
    15: [22, 15, 11, 9, 7, 6, 5, 4, 4, 3, 3, 3, 3, 3, 2],
}
DEFAULT_PAYOUT_SPLITS = {
    2: [60, 40],
    3: [50, 30, 20],
    4: [50, 25, 16, 9],
    5: [40, 25, 15, 12, 8],
    6: [35, 23, 15, 11, 9, 7],
    7: [32, 22, 15, 11, 8, 7, 5],
    8: [30, 21, 15, 11, 8, 6, 5, 4],
    9: [28, 20, 15, 11, 8, 6, 5, 4, 3],
    10: [27, 19, 14, 10, 8, 6, 5, 4, 4, 3],
    12: [24, 17, 13, 10, 8, 6, 5, 4, 4, 3, 3, 3],
    15: [22, 15, 11, 9, 7, 6, 5, 4, 4, 3, 3, 3, 3, 3, 2],
}

DEFAULT_PAYOUT_TEMPLATE_NAME = "Texas Standard (Preferred)"
BUILT_IN_PAYOUT_TEMPLATE_LABELS = (
    "Texas Standard (Preferred)",
    "Balanced (Current Defaults)",
    "Top-Heavy",
    "Deeper Payout",
    "Flat / Wide Payout",
)


def _normalize_percentage_values(values):
    """Round a positive weight list into a percentage split that totals 100%."""
    total = sum(float(value) for value in values)
    if not values or total <= 0:
        return []
    result = [round(float(value) * 100.0 / total, 2) for value in values]
    result[-1] = round(result[-1] + 100.0 - sum(result), 2)
    return result


def _build_builtin_payout_templates():
    """Build five complete traditional percentage profiles by paid-place count."""
    profiles = {label: {} for label in BUILT_IN_PAYOUT_TEMPLATE_LABELS}
    for places in range(2, 16):
        preferred = DEFAULT_PAYOUT_SPLITS.get(places)
        if preferred is None:
            preferred = _normalize_percentage_values([places - index for index in range(places)])
        legacy = LEGACY_DEFAULT_PAYOUT_SPLITS.get(places)
        if legacy is None:
            legacy = list(preferred)
        profiles["Texas Standard (Preferred)"][places] = list(preferred)
        profiles["Balanced (Current Defaults)"][places] = list(legacy)
        profiles["Top-Heavy"][places] = _normalize_percentage_values(
            [(places - index) ** 1.7 for index in range(places)]
        )
        profiles["Deeper Payout"][places] = _normalize_percentage_values(
            [(places - index) ** 0.9 for index in range(places)]
        )
        profiles["Flat / Wide Payout"][places] = _normalize_percentage_values(
            [(places - index) ** 0.55 for index in range(places)]
        )
    return profiles


def _payout_rules_signature(rules):
    """Normalize rules for safe migration checks against exact historical defaults."""
    try:
        return tuple(sorted(
            (int(row["min_entries"]), int(row["max_entries"]), int(row["paid_places"]))
            for row in rules
        ))
    except (TypeError, ValueError, KeyError):
        return None


def _payout_splits_signature(splits):
    """Normalize payout splits for safe migration checks."""
    try:
        return tuple(sorted(
            (int(key), tuple(round(float(value), 4) for value in values))
            for key, values in splits.items()
        ))
    except (TypeError, ValueError, AttributeError):
        return None


BUILT_IN_PAYOUT_TEMPLATES = _build_builtin_payout_templates()

DEFAULT_LEVELS = [
    {"name": "Level 1", "minutes": 20, "sb": 25, "bb": 50, "ante": 0, "kind": "Play"},
    {"name": "Level 2", "minutes": 20, "sb": 50, "bb": 100, "ante": 0, "kind": "Play"},
    {"name": "Level 3", "minutes": 20, "sb": 75, "bb": 150, "ante": 0, "kind": "Play"},
    {"name": "Level 4", "minutes": 20, "sb": 100, "bb": 200, "ante": 0, "kind": "Play"},
    {"name": "Break 1", "minutes": 10, "sb": 0, "bb": 0, "ante": 0, "kind": "Break", "pause_after": False},
    {"name": "Level 5", "minutes": 20, "sb": 150, "bb": 300, "ante": 0, "kind": "Play"},
    {"name": "Level 6", "minutes": 20, "sb": 200, "bb": 400, "ante": 0, "kind": "Play"},
    {"name": "Level 7", "minutes": 20, "sb": 300, "bb": 600, "ante": 0, "kind": "Play"},
    {"name": "Level 8", "minutes": 20, "sb": 400, "bb": 800, "ante": 0, "kind": "Play"},
    {"name": "Break 2", "minutes": 10, "sb": 0, "bb": 0, "ante": 0, "kind": "Break", "pause_after": False},
]


def _make_blind_template(play_blinds, play_minutes, break_after_levels, break_minutes, pause_breaks=False):
    """Create a fresh, editable blind-template structure from blind amounts."""
    rows = []
    break_after_levels = set(break_after_levels)
    break_number = 0
    for level_number, (small_blind, big_blind) in enumerate(play_blinds, start=1):
        rows.append({
            "name": f"Level {level_number}", "minutes": play_minutes,
            "sb": small_blind, "bb": big_blind, "ante": 0, "kind": "Play",
        })
        if level_number in break_after_levels:
            break_number += 1
            rows.append({
                "name": f"Break {break_number}", "minutes": break_minutes,
                "sb": 0, "bb": 0, "ante": 0, "kind": "Break", "pause_after": bool(pause_breaks),
            })
    return rows


# Built-in starter structures available in the New Scenario Wizard. Each selection
# is deep-copied into the scenario so edits never alter the built-in template.
# Texas-style templates open at 100/200, then 200/400. The Small Stack option
# intentionally retains the original lower-blind structure for groups that prefer it.
BUILT_IN_BLIND_TEMPLATES = {
    "small_stack_20": [dict(row) for row in DEFAULT_LEVELS],
    "texas_standard_20": _make_blind_template(
        [(100, 200), (200, 400), (300, 600), (400, 800), (600, 1200), (800, 1600),
         (1000, 2000), (1500, 3000), (2000, 4000), (3000, 6000), (4000, 8000),
         (6000, 12000), (8000, 16000), (10000, 20000), (15000, 30000), (20000, 40000)],
        20, (4, 8, 12), 10,
    ),
    "texas_turbo_15": _make_blind_template(
        [(100, 200), (200, 400), (300, 600), (400, 800), (500, 1000), (1000, 2000),
         (2000, 4000), (3000, 6000), (4000, 8000), (5000, 10000), (10000, 20000),
         (20000, 40000), (40000, 80000), (80000, 160000)],
        15, (5, 10), 10, pause_breaks=True,
    ),
    "texas_hyper_turbo_10": _make_blind_template(
        [(100, 200), (200, 400), (300, 600), (600, 1200), (1000, 2000), (1500, 3000),
         (2500, 5000), (4000, 8000), (6000, 12000), (10000, 20000), (15000, 30000),
         (25000, 50000)],
        10, (5, 10), 5,
    ),
    "texas_deep_stack_25": _make_blind_template(
        [(100, 200), (200, 400), (300, 600), (400, 800), (500, 1000), (600, 1200),
         (800, 1600), (1000, 2000), (1500, 3000), (2000, 4000), (3000, 6000),
         (4000, 8000), (6000, 12000), (8000, 16000), (10000, 20000), (15000, 30000),
         (20000, 40000)],
        25, (4, 8, 12, 15), 10,
    ),
}

BUILT_IN_BLIND_TEMPLATE_LABELS = {
    "Small Stack 20-Minute Template (25/50 Start)": "small_stack_20",
    "Texas Standard 20-Minute Template (100/200 Start)": "texas_standard_20",
    "Texas Turbo 15-Minute Template (100/200 Start)": "texas_turbo_15",
    "Texas Hyper-Turbo 10-Minute Template (100/200 Start)": "texas_hyper_turbo_10",
    "Texas Deep Stack 25-Minute Template (100/200 Start)": "texas_deep_stack_25",
}

# Suggested chip-stack defaults shown in the New Scenario Wizard when a built-in
# blind template is selected. Users can freely change the Starting Chip Stack field.
BLIND_TEMPLATE_STARTING_STACKS = {
    "small_stack_20": 10000,
    "texas_standard_20": 25000,
    "texas_turbo_15": 25000,
    "texas_hyper_turbo_10": 25000,
    "texas_deep_stack_25": 25000,
}

def money(value):
    return f"${value:,.2f}"


def money_whole(value):
    """Format tournament payout amounts as whole dollars (round half up)."""
    return f"${int(math.floor(float(value) + 0.5)):,.0f}"


def format_percent(value):
    """Format payout shares without unnecessary trailing decimal zeros."""
    return f"{float(value):g}%"


def format_payout_rule(value):
    """Show a percentage share or a fixed-dollar payout rule in a consistent way."""
    if isinstance(value, str):
        return value
    return format_percent(value)


def calculate_mixed_payout_awards(pool, configuration, rounding_increment=1):
    """Calculate a mixed fixed-dollar/percentage payout structure.

    Percentages apply to the pool remaining after fixed awards are deducted.
    If the structure is invalid or violates the minimum-award safety rule, return
    (None, reason) so the caller can fall back to its traditional percentage split.
    """
    try:
        pool = int(pool)
        increment = max(1, int(rounding_increment))
        if pool <= 0:
            return None, "The distributable prize pool is zero."
        if not isinstance(configuration, (list, tuple)) or len(configuration) < 2:
            return None, "The mixed payout structure is incomplete."

        normalized = []
        percentage_total = 0.0
        fixed_total = 0
        percentage_indexes = []
        for index, row in enumerate(configuration):
            if not isinstance(row, dict):
                return None, "A mixed payout row is invalid."
            method = str(row.get("method", "Percentage"))
            value = float(row.get("value", 0))
            if not math.isfinite(value) or value <= 0:
                return None, f"Position {index + 1} must have a positive payout value."
            if method == "Percentage":
                if value > 100:
                    return None, f"Position {index + 1} has a percentage greater than 100%."
                normalized.append((method, value))
                percentage_total += value
                percentage_indexes.append(index)
            elif method == "Fixed amount ($)":
                fixed_value = int(round(value))
                if abs(value - fixed_value) > 0.0001:
                    return None, f"The fixed payout for position {index + 1} must be a whole dollar amount."
                normalized.append((method, fixed_value))
                fixed_total += fixed_value
            else:
                return None, f"Position {index + 1} has an unknown payout method."

        if not percentage_indexes:
            return None, "At least one position must use a percentage of the remaining pool."
        if abs(percentage_total - 100.0) > 0.01:
            return None, f"Percentage awards total {percentage_total:.2f}%, not 100%."
        if fixed_total >= pool:
            return None, "The fixed-dollar awards leave no money for the percentage-based positions."

        remaining_pool = pool - fixed_total
        amounts = [0] * len(normalized)
        for index, (method, value) in enumerate(normalized):
            if method == "Fixed amount ($)":
                amounts[index] = int(value)
            else:
                raw_amount = remaining_pool * float(value) / 100.0
                amounts[index] = int(math.floor(raw_amount / increment + 0.5)) * increment

        # Reconcile rounding against the first percentage-based position, not a fixed award.
        residual = remaining_pool - sum(amounts[i] for i in percentage_indexes)
        amounts[percentage_indexes[0]] += residual
        if any(amount <= 0 for amount in amounts):
            return None, "Rounding would create a zero or negative award."
        if sum(amounts) != pool:
            return None, "The mixed awards could not be reconciled to the prize pool."

        # If a lower position has a fixed award, every higher position must pay at least
        # that amount. Test after rounding and residual reconciliation.
        for lower_index, (method, value) in enumerate(normalized):
            if method != "Fixed amount ($)":
                continue
            fixed_award = int(value)
            for higher_index in range(lower_index):
                if amounts[higher_index] < fixed_award:
                    return None, (
                        f"Position {higher_index + 1} would pay {money_whole(amounts[higher_index])}, "
                        f"less than the fixed {money_whole(fixed_award)} award at position {lower_index + 1}."
                    )

        rows = []
        for index, (method, value) in enumerate(normalized):
            rule_label = value if method == "Percentage" else f"Fixed {money_whole(value)}"
            rows.append((index + 1, rule_label, amounts[index]))
        return rows, ""
    except (TypeError, ValueError, OverflowError) as exc:
        return None, f"The mixed payout structure could not be calculated: {exc}"


def normalize_header(value):
    """Normalize an imported spreadsheet header for flexible column matching."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def parse_payout_template_rows(rows):
    """Parse one worksheet of paid-place percentage charts into {place_count: split}.

    Expected columns are Paid Places, 1st Place %, 2nd Place %, etc. Title and
    instruction rows before the header are permitted. Every imported chart row
    must have a positive percentage for each paid place and total 100 percent.
    """
    if not rows:
        raise ValueError("The payout template worksheet is empty.")

    header_row_index = None
    places_column = None
    percent_columns = {}
    for row_index, row in enumerate(rows):
        headers = [normalize_header(value) for value in row]
        found_places = next((idx for idx, value in enumerate(headers)
                             if value in ("paidplaces", "numberofpaidplaces", "paidplacecount", "placecount")), None)
        found_percent = {}
        for idx, value in enumerate(headers):
            match = re.match(r"^(\d+)", value)
            if match and ("place" in value or value.endswith("pct") or value.endswith("percent")):
                found_percent[int(match.group(1))] = idx
        if found_places is not None and len(found_percent) >= 2:
            header_row_index = row_index
            places_column = found_places
            percent_columns = found_percent
            break

    if header_row_index is None or places_column is None:
        raise ValueError("Could not find payout-template headers. Include 'Paid Places' and columns such as '1st Place %', '2nd Place %', etc.")

    output = {}
    for row_number, row in enumerate(rows[header_row_index + 1:], start=header_row_index + 2):
        try:
            raw_places = row[places_column] if places_column < len(row) else ""
            if raw_places is None or str(raw_places).strip() == "":
                continue
            places_float = float(str(raw_places).strip())
            places = int(places_float)
            if places_float != places or not 2 <= places <= 100:
                raise ValueError(f"Row {row_number}: Paid Places must be a whole number from 2 to 100.")
            values = []
            for finish in range(1, places + 1):
                col = percent_columns.get(finish)
                if col is None or col >= len(row) or row[col] is None or str(row[col]).strip() == "":
                    raise ValueError(f"Row {row_number}: missing the percentage for {finish}{'st' if finish == 1 else 'nd' if finish == 2 else 'rd' if finish == 3 else 'th'} place.")
                raw_value = str(row[col]).strip().replace("%", "")
                value = float(raw_value)
                if not math.isfinite(value) or value <= 0 or value > 100:
                    raise ValueError(f"Row {row_number}: each active payout percentage must be greater than 0 and no more than 100.")
                values.append(value)
            total = sum(values)
            if abs(total - 100.0) > 0.01:
                raise ValueError(f"Row {row_number}: percentages for {places} paid places total {total:.2f}%, not 100%.")
            if places in output:
                raise ValueError(f"Row {row_number}: duplicate chart for {places} paid places.")
            output[places] = [round(value, 2) for value in values]
        except ValueError:
            raise
        except (TypeError, OverflowError) as exc:
            raise ValueError(f"Row {row_number}: invalid payout-template value ({exc}).") from exc

    if not output:
        raise ValueError("No payout charts were found below the header row.")
    return dict(sorted(output.items()))


def read_xlsx_sheets(path):
    """Read basic values from an .xlsx workbook using only Python's standard library."""
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    ns = {"m": main_ns, "r": rel_ns, "pr": package_rel_ns}
    with zipfile.ZipFile(path, "r") as workbook_zip:
        names = set(workbook_zip.namelist())
        if "xl/workbook.xml" not in names:
            raise ValueError("This file does not appear to be a valid .xlsx workbook.")

        shared_strings = []
        if "xl/sharedStrings.xml" in names:
            shared_root = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("m:si", ns):
                shared_strings.append("".join(t.text or "" for t in item.iter(f"{{{main_ns}}}t")))

        rel_root = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
        relationship_targets = {
            rel.attrib.get("Id"): rel.attrib.get("Target", "")
            for rel in rel_root.findall("pr:Relationship", ns)
        }
        workbook_root = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        sheets = {}
        sheet_nodes = workbook_root.findall("m:sheets/m:sheet", ns)

        def cell_column_index(reference):
            letters = "".join(ch for ch in (reference or "") if ch.isalpha()).upper()
            value = 0
            for char in letters:
                value = value * 26 + ord(char) - ord("A") + 1
            return max(0, value - 1)

        for sheet_node in sheet_nodes:
            sheet_name = sheet_node.attrib.get("name", f"Sheet{len(sheets) + 1}")
            relationship_id = sheet_node.attrib.get(f"{{{rel_ns}}}id")
            target = relationship_targets.get(relationship_id, "")
            if target.startswith("/"):
                worksheet_path = target.lstrip("/")
            else:
                worksheet_path = normpath(posix_join("xl", target))
            worksheet_path = worksheet_path.replace("\\", "/")
            if worksheet_path not in names:
                raise ValueError(f"Could not locate worksheet '{sheet_name}' in the workbook.")

            worksheet_root = ET.fromstring(workbook_zip.read(worksheet_path))
            sheet_data = worksheet_root.find("m:sheetData", ns)
            output_rows = []
            if sheet_data is not None:
                for row_node in sheet_data.findall("m:row", ns):
                    cells = {}
                    max_col = -1
                    for cell in row_node.findall("m:c", ns):
                        col = cell_column_index(cell.attrib.get("r", ""))
                        max_col = max(max_col, col)
                        cell_type = cell.attrib.get("t", "")
                        value_node = cell.find("m:v", ns)
                        if cell_type == "inlineStr":
                            value = "".join(t.text or "" for t in cell.iter(f"{{{main_ns}}}t"))
                        elif value_node is None or value_node.text is None:
                            value = ""
                        elif cell_type == "s":
                            try:
                                value = shared_strings[int(value_node.text)]
                            except (ValueError, IndexError):
                                value = value_node.text
                        elif cell_type == "b":
                            value = "TRUE" if value_node.text == "1" else "FALSE"
                        else:
                            value = value_node.text
                        cells[col] = value
                    if max_col >= 0:
                        output_rows.append([cells.get(i, "") for i in range(max_col + 1)])
                    else:
                        output_rows.append([])
            # Do not offer entirely empty worksheets as import candidates.
            while output_rows and not any(str(v).strip() for v in output_rows[-1]):
                output_rows.pop()
            if output_rows:
                sheets[sheet_name] = output_rows
        if not sheets:
            raise ValueError("No populated worksheets were found in this workbook.")
        return sheets

class TournamentDirector(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        # Apply application branding to the Windows taskbar/title-bar icon when available.
        try:
            self.iconbitmap(default=resource_path(os.path.join("assets", "MyPokerTournament.ico")))
        except Exception:
            pass
        try:
            self.app_icon_photo = tk.PhotoImage(file=resource_path(os.path.join("assets", "MyPokerTournament_Icon.png")))
            self.iconphoto(True, self.app_icon_photo)
        except Exception:
            self.app_icon_photo = None
        # Main-window size is applied from saved screen-relative percentages after settings load.
        self.geometry("1180x780")
        self.minsize(900, 560)
        self.configure(bg="#101820")
        self.levels = [dict(x) for x in DEFAULT_LEVELS]
        self.current_level = 0
        self.remaining_seconds = 20 * 60
        self.running = False
        self.deadline = None
        self.after_id = None
        self.players = []
        self.next_player_id = 1
        self.tournament_name = "Texas Hold'em Tournament"
        # Tournament Type is a selectable template; charity and payout mode remain independently configurable.
        self.tournament_type = "Standard Tournament"
        self._pre_freeroll_buy_in = None
        self._pre_freeroll_house_fee = None
        self._pre_freeroll_payout_mode = None
        # House fee is supported only by Home Game. Keep its value separately so
        # switching templates does not lose the Home Game configuration.
        self.home_game_house_fee = 0.0
        self._last_selected_tournament_type = self.tournament_type
        # Main page opens centered at a saved percentage of the current monitor.
        # The separate full-screen tournament display is not affected by these values.
        self.main_window_width_percent = 90
        self.main_window_height_percent = 85
        # Classic preserves the established full-screen display; Modern is an optional enhanced layout.
        self.fullscreen_theme = "Classic"
        # TV control readability settings; apply on the next full-screen display launch.
        self.fullscreen_control_font_size = 10
        self.fullscreen_control_button_scale = 100
        self.buy_in = 30.0
        self.reentry_fee = 20.0
        self.ante_enabled = False  # Ante UI/function is temporarily hidden in this release.
        self.rebuy_enabled = True
        self.add_on_enabled = True
        self.add_on_fee = 0.0
        self.add_on_chips = 0
        self.house_fee = 0.0
        self.charity_mode = False
        self.charity_method = "Fixed per entry"
        self.charity_value = 0.0
        self.limit_charity_paid_places = False
        self.charity_max_paid_places = 5
        self.tracking_mode = "Entry count only"  # Named-player interface is temporarily hidden.
        self.anonymous_original_entries = 0
        self.anonymous_reentries = 0
        self.anonymous_addons = 0
        self.anonymous_active_players = 0
        self.starting_stack = 10000
        self.start_time = None
        self.history = []
        self.scenarios = []
        self.active_scenario_id = ""
        self.active_scenario_name = ""
        self.payout_rules = [dict(x) for x in DEFAULT_PAYOUT_RULES]
        self.payout_splits = {int(k): list(v) for k, v in DEFAULT_PAYOUT_SPLITS.items()}
        self.payout_template_name = DEFAULT_PAYOUT_TEMPLATE_NAME
        # Entry-based paid-place behavior remains automatic by default.
        self.payout_position_mode = "Automatic by entry rules"
        self.target_paid_places = 6
        self.max_paid_places = 6
        # Optional per-place mixed rules keyed by the number of paid places, e.g. "6".
        self.mixed_payouts = {}
        self._mixed_payout_fallback_reason = ""
        self._mixed_payout_missing_config = False
        self._mixed_payout_missing_places = 0
        # Entry-based percentages remain the default; freeroll prizes are independent of entries.
        self.payout_mode = "Traditional Percentages"
        self.freeroll_paid_places = 1
        self.freeroll_payouts = [0, 0, 0]  # fixed whole-dollar awards for 1st, 2nd, and 3rd
        self.payout_rounding_increment = 5
        self.sound_enabled = True
        self.default_sound = "Chime"
        self.sound_volume = 70
        self.custom_sound_path = ""
        self.sound_warning_seconds = 60
        self.sound_overrides = {
            "clock_started": "Off",
            "low_time": "One Minute",
            "level_ends": "Use default",
            "break_ends": "Use default",
            "level_changed": "Off",
            "blind_level_starts": "Long Gong",
        }
        self._low_time_warned_level = None
        self._blind_start_sound_played = False
        self._load_data()
        self._load_scenario_library()
        self._apply_main_window_geometry(self.main_window_width_percent, self.main_window_height_percent)
        self._build_ui()
        self._refresh_all()
        self._tick()

    def _load_data(self):
        saved_tracking_mode = "Entry count only"
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.levels = data.get("levels", self.levels)
                self.current_level = max(0, min(int(data.get("current_level", 0)), len(self.levels)-1))
                self.remaining_seconds = max(0, int(data.get("remaining_seconds", self.levels[self.current_level]["minutes"]*60)))
                self.players = data.get("players", [])
                self.next_player_id = int(data.get("next_player_id", 1))
                self.tournament_name = data.get("tournament_name", self.tournament_name)
                self.active_scenario_id = str(data.get("active_scenario_id", "") or "")
                self.active_scenario_name = str(data.get("active_scenario_name", "") or "")
                self.main_window_width_percent = max(70, min(100, int(data.get("main_window_width_percent", self.main_window_width_percent))))
                self.main_window_height_percent = max(70, min(100, int(data.get("main_window_height_percent", self.main_window_height_percent))))
                saved_display_theme = str(data.get("fullscreen_theme", self.fullscreen_theme) or "Classic")
                self.fullscreen_theme = saved_display_theme if saved_display_theme in ("Classic", "Modern") else "Classic"
                try:
                    self.fullscreen_control_font_size = max(8, min(15, int(data.get("fullscreen_control_font_size", self.fullscreen_control_font_size))))
                except (TypeError, ValueError):
                    self.fullscreen_control_font_size = 10
                try:
                    self.fullscreen_control_button_scale = max(75, min(150, int(data.get("fullscreen_control_button_scale", self.fullscreen_control_button_scale))))
                except (TypeError, ValueError):
                    self.fullscreen_control_button_scale = 100
                self.buy_in = float(data.get("buy_in", self.buy_in))
                self.reentry_fee = float(data.get("reentry_fee", self.reentry_fee))
                # Legacy ante setting is intentionally not exposed in this release.
                self.ante_enabled = False
                self.rebuy_enabled = bool(data.get("rebuy_enabled", self.rebuy_enabled))
                self.add_on_enabled = bool(data.get("add_on_enabled", self.add_on_enabled))
                self.add_on_fee = float(data.get("add_on_fee", self.add_on_fee))
                self.add_on_chips = max(0, int(data.get("add_on_chips", self.add_on_chips)))
                self.house_fee = float(data.get("house_fee", self.house_fee))
                self.charity_mode = bool(data.get("charity_mode", self.charity_mode))
                self.charity_method = data.get("charity_method", self.charity_method)
                self.charity_value = float(data.get("charity_value", self.charity_value))
                self.limit_charity_paid_places = bool(data.get("limit_charity_paid_places", self.limit_charity_paid_places))
                self.charity_max_paid_places = max(1, min(100, int(data.get("charity_max_paid_places", self.charity_max_paid_places))))
                default_saved_mode = "Named players" if self.players else "Entry count only"
                saved_tracking_mode = str(data.get("tracking_mode", default_saved_mode))
                self.tracking_mode = saved_tracking_mode
                self.anonymous_original_entries = max(0, int(data.get("anonymous_original_entries", 0)))
                self.anonymous_reentries = max(0, int(data.get("anonymous_reentries", 0)))
                self.anonymous_addons = max(0, int(data.get("anonymous_addons", 0)))
                # Older saves default active players to original entries.
                self.anonymous_active_players = max(0, int(data.get("anonymous_active_players", data.get("anonymous_original_entries", 0))))
                self.starting_stack = int(data.get("starting_stack", self.starting_stack))
                self.start_time = data.get("start_time")
                self.history = data.get("history", [])
                loaded_rules = data.get("payout_rules", self.payout_rules)
                # Update old built-in thresholds, but preserve user-customized rule tables.
                if _payout_rules_signature(loaded_rules) == _payout_rules_signature(LEGACY_DEFAULT_PAYOUT_RULES):
                    self.payout_rules = [dict(row) for row in DEFAULT_PAYOUT_RULES]
                else:
                    self.payout_rules = loaded_rules
                stored_splits = data.get("payout_splits", self.payout_splits)
                stored_template_name = data.get("payout_template_name")
                loaded_split_signature = _payout_splits_signature(stored_splits)
                legacy_split_signature = _payout_splits_signature(LEGACY_DEFAULT_PAYOUT_SPLITS)
                self.payout_splits = {int(k): list(v) for k, v in stored_splits.items()}
                if not stored_template_name and loaded_split_signature == legacy_split_signature:
                    # v62.7 and earlier did not store a profile name; migrate their untouched
                    # built-in chart to the user's preferred chart while retaining custom edits.
                    self.payout_splits = {int(k): list(v) for k, v in DEFAULT_PAYOUT_SPLITS.items()}
                    self.payout_template_name = DEFAULT_PAYOUT_TEMPLATE_NAME
                elif stored_template_name:
                    self.payout_template_name = str(stored_template_name)
                else:
                    default_map = {int(k): list(v) for k, v in DEFAULT_PAYOUT_SPLITS.items()}
                    self.payout_template_name = DEFAULT_PAYOUT_TEMPLATE_NAME if self.payout_splits == default_map else "Custom / edited"
                allowed_position_modes = ("Automatic by entry rules", "Target fixed number", "Automatic with maximum cap")
                saved_position_mode = str(data.get("payout_position_mode", self.payout_position_mode))
                self.payout_position_mode = saved_position_mode if saved_position_mode in allowed_position_modes else "Automatic by entry rules"
                self.target_paid_places = max(1, min(100, int(data.get("target_paid_places", self.target_paid_places))))
                self.max_paid_places = max(1, min(100, int(data.get("max_paid_places", self.max_paid_places))))
                self.mixed_payouts = {}
                raw_mixed_payouts = data.get("mixed_payouts", {})
                if isinstance(raw_mixed_payouts, dict):
                    for place_key, rows in raw_mixed_payouts.items():
                        try:
                            places = int(place_key)
                            if not 2 <= places <= 100 or not isinstance(rows, list) or len(rows) != places:
                                continue
                            clean_rows = []
                            pct_total = 0.0
                            pct_count = 0
                            valid_rows = True
                            for row in rows:
                                if not isinstance(row, dict):
                                    valid_rows = False
                                    break
                                method = str(row.get("method", "Percentage"))
                                value = float(row.get("value", 0))
                                if not math.isfinite(value) or value <= 0:
                                    valid_rows = False
                                    break
                                if method == "Percentage":
                                    if value > 100:
                                        valid_rows = False
                                        break
                                    pct_total += value
                                    pct_count += 1
                                    clean_rows.append({"method": method, "value": round(value, 4)})
                                elif method == "Fixed amount ($)":
                                    if abs(value - round(value)) > 0.0001:
                                        valid_rows = False
                                        break
                                    clean_rows.append({"method": method, "value": int(round(value))})
                                else:
                                    valid_rows = False
                                    break
                            if valid_rows and pct_count and abs(pct_total - 100.0) <= 0.01:
                                self.mixed_payouts[str(places)] = clean_rows
                        except (TypeError, ValueError, OverflowError):
                            continue
                saved_payout_mode = str(data.get("payout_mode", "Entry-based"))
                if saved_payout_mode in ("Freeroll fixed payouts", "Freeroll Fixed Prizes"):
                    self.payout_mode = "Freeroll Fixed Prizes"
                elif saved_payout_mode in ("Mixed Fixed + Percentage", "Traditional Percentages"):
                    self.payout_mode = saved_payout_mode
                elif saved_payout_mode == "Entry-based":
                    # Preserve the previous behavior when a mixed structure was already active
                    # for the currently selected paid-place count.
                    try:
                        loaded_places = self._paid_places_for_entries(self._counts()[1])
                        has_current_mixed = bool(self.mixed_payouts.get(str(loaded_places), self.mixed_payouts.get(loaded_places)))
                    except Exception:
                        has_current_mixed = False
                    self.payout_mode = "Mixed Fixed + Percentage" if has_current_mixed else "Traditional Percentages"
                else:
                    self.payout_mode = "Traditional Percentages"

                # Migrate old settings without applying a new template to their fees or other values.
                allowed_tournament_types = ("Standard Tournament", "Charity Tournament", "Home Game", "Freeroll")
                saved_tournament_type = str(data.get("tournament_type", ""))
                if saved_tournament_type in allowed_tournament_types:
                    self.tournament_type = saved_tournament_type
                else:
                    # Older releases had no separate type field. Infer Charity when Benefit Pot
                    # is already enabled; otherwise default to Standard without altering existing fees.
                    if self.charity_mode:
                        self.tournament_type = "Charity Tournament"
                    elif self.payout_mode == "Freeroll Fixed Prizes" and self.buy_in == 0:
                        self.tournament_type = "Freeroll"
                    else:
                        self.tournament_type = "Standard Tournament"
                self._last_selected_tournament_type = self.tournament_type
                try:
                    cached_buy = data.get("pre_freeroll_buy_in", None)
                    self._pre_freeroll_buy_in = None if cached_buy is None else max(0.0, float(cached_buy))
                except (TypeError, ValueError):
                    self._pre_freeroll_buy_in = None
                try:
                    cached_house = data.get("pre_freeroll_house_fee", None)
                    self._pre_freeroll_house_fee = None if cached_house is None else max(0.0, float(cached_house))
                except (TypeError, ValueError):
                    self._pre_freeroll_house_fee = None
                saved_home_game_house_fee = data.get("home_game_house_fee", None)
                try:
                    if saved_home_game_house_fee is not None:
                        self.home_game_house_fee = max(0.0, float(saved_home_game_house_fee))
                    elif self.tournament_type == "Home Game":
                        # Migration: older saves stored the current Home Game fee directly.
                        self.home_game_house_fee = max(0.0, float(self.house_fee))
                    elif self.tournament_type == "Freeroll" and self._pre_freeroll_house_fee is not None:
                        # Preserve a Home Game fee when an older save was temporarily in Freeroll.
                        self.home_game_house_fee = max(0.0, float(self._pre_freeroll_house_fee))
                    else:
                        self.home_game_house_fee = 0.0
                except (TypeError, ValueError, OverflowError):
                    self.home_game_house_fee = 0.0
                # House fees do not apply to Standard, Charity, or Freeroll tournaments.
                self.house_fee = self.home_game_house_fee if self.tournament_type == "Home Game" else 0.0
                saved_pre_freeroll_mode = str(data.get("pre_freeroll_payout_mode", ""))
                self._pre_freeroll_payout_mode = (
                    saved_pre_freeroll_mode if saved_pre_freeroll_mode in
                    ("Traditional Percentages", "Mixed Fixed + Percentage", "Freeroll Fixed Prizes") else None
                )
                self.freeroll_paid_places = max(1, min(3, int(data.get("freeroll_paid_places", self.freeroll_paid_places))))
                saved_fixed_payouts = data.get("freeroll_payouts", self.freeroll_payouts)
                if isinstance(saved_fixed_payouts, (list, tuple)) and len(saved_fixed_payouts) >= 3:
                    self.freeroll_payouts = [max(0, int(float(v))) for v in saved_fixed_payouts[:3]]
                self.payout_rounding_increment = int(data.get("payout_rounding_increment", self.payout_rounding_increment))
                if self.payout_rounding_increment not in (1, 5, 10, 20, 25, 50, 100):
                    self.payout_rounding_increment = 5
                self.sound_enabled = bool(data.get("sound_enabled", self.sound_enabled))
                self.default_sound = str(data.get("default_sound", self.default_sound))
                if self.default_sound not in ("Off", "Chime", "Bell", "Alert", "Double Chime", "Gong", "Long Gong", "One Minute", "Custom WAV"):
                    self.default_sound = "Chime"
                self.sound_volume = max(0, min(100, int(data.get("sound_volume", self.sound_volume))))
                self.custom_sound_path = str(data.get("custom_sound_path", self.custom_sound_path) or "")
                self.sound_warning_seconds = max(0, min(3600, int(data.get("sound_warning_seconds", self.sound_warning_seconds))))
                saved_overrides = data.get("sound_overrides", {})
                allowed_overrides = ("Use default", "Off", "Chime", "Bell", "Alert", "Double Chime", "Gong", "Long Gong", "One Minute", "Custom WAV")
                for event_key, default_value in self.sound_overrides.items():
                    candidate = str(saved_overrides.get(event_key, default_value))
                    # Migrate the prior default low-time warning to the uploaded 60-second tone.
                    if event_key == "low_time" and candidate == "Use default":
                        candidate = "One Minute"
                    # Upgrade the old synthetic gong choice to the uploaded Long Gong sound
                    # for blind starts; other event-specific gong choices remain unchanged.
                    if event_key == "blind_level_starts" and candidate == "Gong":
                        candidate = "Long Gong"
                    self.sound_overrides[event_key] = candidate if candidate in allowed_overrides else default_value
        except Exception:
            # A damaged save file should not prevent the program from opening.
            pass
        # Named-player tracking is temporarily hidden from the UI. If a prior save
        # was using that mode, preserve the roster data but migrate live totals to the
        # visible count-only model so the controls remain usable. This conversion is
        # one-time because the saved tracking mode is changed to Entry count only.
        if saved_tracking_mode == "Named players" and self.players:
            try:
                self.anonymous_original_entries = len(self.players)
                self.anonymous_reentries = sum(max(0, int(player.get("entries", 1)) - 1) for player in self.players)
                self.anonymous_active_players = sum(1 for player in self.players if player.get("status", "Active") == "Active")
            except (TypeError, ValueError):
                pass
        self.tracking_mode = "Entry count only"
        self.ante_enabled = False
        if not self.levels:
            self.levels = [dict(x) for x in DEFAULT_LEVELS]
        # Each break owns its own pause flag. Legacy global pause settings are ignored.
        for row in self.levels:
            if row.get("kind") == "Break":
                row["pause_after"] = bool(row.get("pause_after", False))
        self.current_level = max(0, min(self.current_level, len(self.levels)-1))
        self._normalize_anonymous_counts()

    def _normalize_anonymous_counts(self):
        """Keep anonymous counts nonnegative and active players no greater than paid entries."""
        self.anonymous_original_entries = max(0, int(self.anonymous_original_entries))
        self.anonymous_reentries = max(0, int(self.anonymous_reentries))
        self.anonymous_active_players = max(0, int(self.anonymous_active_players))
        included_rebuys = self.anonymous_reentries if self.rebuy_enabled else 0
        total_entries = self.anonymous_original_entries + included_rebuys
        self.anonymous_active_players = min(self.anonymous_active_players, total_entries)

    def _save_data(self):
        self._normalize_anonymous_counts()
        if self.running and self.deadline is not None:
            self.remaining_seconds = max(0, int(self.deadline - time.monotonic()))
        data = {
            "levels": self.levels, "current_level": self.current_level,
            "remaining_seconds": self.remaining_seconds, "players": self.players,
            "next_player_id": self.next_player_id, "tournament_name": self.tournament_name,
            "active_scenario_id": self.active_scenario_id, "active_scenario_name": self.active_scenario_name,
            "tournament_type": self.tournament_type,
            "pre_freeroll_buy_in": self._pre_freeroll_buy_in,
            "pre_freeroll_house_fee": self._pre_freeroll_house_fee,
            "pre_freeroll_payout_mode": self._pre_freeroll_payout_mode,
            "main_window_width_percent": self.main_window_width_percent,
            "main_window_height_percent": self.main_window_height_percent,
            "fullscreen_theme": self.fullscreen_theme,
            "fullscreen_control_font_size": self.fullscreen_control_font_size,
            "fullscreen_control_button_scale": self.fullscreen_control_button_scale,
            "buy_in": self.buy_in, "reentry_fee": self.reentry_fee,
            "ante_enabled": self.ante_enabled, "rebuy_enabled": self.rebuy_enabled,
            "add_on_enabled": self.add_on_enabled,
            "add_on_fee": self.add_on_fee,
            "add_on_chips": self.add_on_chips,
            "house_fee": self.house_fee,
            "home_game_house_fee": self.home_game_house_fee,
            "charity_mode": self.charity_mode, "charity_method": self.charity_method, "charity_value": self.charity_value,
            "limit_charity_paid_places": self.limit_charity_paid_places,
            "charity_max_paid_places": self.charity_max_paid_places,
            "tracking_mode": self.tracking_mode, "anonymous_original_entries": self.anonymous_original_entries,
            "anonymous_reentries": self.anonymous_reentries, "anonymous_addons": self.anonymous_addons,
            "anonymous_active_players": self.anonymous_active_players,
            "starting_stack": self.starting_stack, "start_time": self.start_time, "history": self.history,
            "payout_rules": self.payout_rules, "payout_splits": self.payout_splits,
            "payout_template_name": self.payout_template_name,
            "payout_position_mode": self.payout_position_mode,
            "target_paid_places": self.target_paid_places,
            "max_paid_places": self.max_paid_places,
            "mixed_payouts": self.mixed_payouts,
            "payout_mode": self.payout_mode,
            "freeroll_paid_places": self.freeroll_paid_places,
            "freeroll_payouts": self.freeroll_payouts,
            "payout_rounding_increment": self.payout_rounding_increment,
            "sound_enabled": self.sound_enabled,
            "default_sound": self.default_sound,
            "sound_volume": self.sound_volume,
            "custom_sound_path": self.custom_sound_path,
            "sound_warning_seconds": self.sound_warning_seconds,
            "sound_overrides": self.sound_overrides
        }
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            messagebox.showwarning("Save warning", f"Could not save tournament data:\n{e}")

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(12, 7))
        style.configure("TButton", font=("Segoe UI", 10), padding=6)
        style.configure("TLabel", font=("Segoe UI", 10))

        header = tk.Frame(self, bg="#101820")
        header.pack(fill="x", padx=18, pady=(14, 8))
        self.name_var = tk.StringVar(value=self.tournament_name)
        tk.Label(header, textvariable=self.name_var, bg="#101820", fg="white",
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        # Keep Help permanently visible in the black main-window header, immediately
        # to the left of Save. The separate full-screen TV display intentionally omits
        # application navigation and Help controls.
        header_actions = tk.Frame(header, bg="#101820")
        header_actions.pack(side="right")
        ttk.Button(header_actions, text="Help / User Guide", command=self._open_help_tab).grid(
            row=0, column=0, padx=(0, 8), sticky="e")
        ttk.Button(header_actions, text="Save", command=self._save_from_header).grid(
            row=0, column=1, sticky="e")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.clock_tab = ttk.Frame(self.notebook, padding=12)
        self.scenarios_tab = ttk.Frame(self.notebook, padding=12)
        self.settings_tab = ttk.Frame(self.notebook, padding=0)
        self.display_sound_tab = ttk.Frame(self.notebook, padding=12)
        self.levels_tab = ttk.Frame(self.notebook, padding=12)
        self.players_tab = ttk.Frame(self.notebook, padding=12)
        self.reports_tab = ttk.Frame(self.notebook, padding=12)
        self.payouts_tab = ttk.Frame(self.notebook, padding=12)
        # Help is opened in its own window from the permanent header button.
        # The player/entry controls are temporarily hidden from main navigation,
        # but the backing frame remains available for existing internal refresh logic.
        self.help_tab = None
        self.help_window = None
        self.notebook.add(self.clock_tab, text="Tournament Clock")
        self.notebook.add(self.scenarios_tab, text="Scenarios")
        self.notebook.add(self.settings_tab, text="Tournament Settings")
        self.notebook.add(self.display_sound_tab, text="Display & Sound")
        self.notebook.add(self.levels_tab, text="Blind Structure")
        # Statistics & Reports is intentionally hidden for customer release v1.2.0.
        # Keep its frame and implementation for possible future reactivation.
        self.notebook.add(self.payouts_tab, text="Payout Calculator")
        self._build_clock_tab()
        self._build_scenarios_tab()
        self._build_settings_tab()
        self._build_display_sound_tab()
        self._build_levels_tab()
        self._build_players_tab()
        self._build_reports_tab()
        self._build_payouts_tab()
        # F1 opens contextual help in a separate window; Help remains in the header.
        self.bind_all("<F1>", self._help_for_current_tab)

    # ------------------------------------------------------------------
    # Offline Help
    # ------------------------------------------------------------------
    def _help_topic_content(self):
        """Built-in offline help topics, maintained alongside the application."""
        return {
            "Quick Start": (
                "Start a new tournament\n\n"
                "1. Open Tournament Settings and choose Standard Tournament, Charity Tournament, Home Game, or Freeroll.\n"
                "2. Review Entries & Fees, Charity / Benefit Pot, and Payout Rules.\n"
                "3. Open Blind Structure. Confirm the levels and breaks, or import a structure.\n"
                "4. Click Save in the upper-right corner.\n"
                "5. Use the quick tournament count controls on the Tournament Clock page when needed; the separate Players & Entries navigation tab is not shown in this release.\n"
                "6. Select Tournament Clock and start or resume the clock.\n"
                "7. Use Open Full Screen / Tournament Display for the TV.\n\n"
                "Tip: create and test scenarios before game night. Launching a scenario starts a new tournament at Level 1, paused."
            ),
            "Main tabs": (
                "What each tab is for\n\n"
                "Tournament Clock — current level, remaining time, slider, and ±30-second adjustments.\n"
                "Help / User Guide — opens the built-in offline help window and provides access to the full user manual.\n"
                "Scenarios — create and manage reusable tournament setups.\n"
                "Tournament Settings — tournament type, entry fees, rebuy/add-on rules, Benefit Pot, and payout settings. Blind levels always advance automatically; each break controls its own pause behavior.\n"
                "Display & Sound — main-window sizing and sound configuration.\n"
                "Blind Structure — add, edit, reorder, import, and bulk-adjust levels and breaks.\n"
                "Player/entry counts are managed from the quick tournament count controls on the Tournament Clock page; a separate Players & Entries navigation tab is not shown.\n"
                "Statistics & Reports is not shown in this release; its underlying code is retained.\n"
                "Payout Calculator — view the current estimated payout results.\n\n"
                "Use Help / User Guide in the black header immediately to the left of Save. F1 opens contextual help for the current tab. Click Save in the upper-right corner after changing settings."
            ),
            "Scenario Manager": (
                "Save tournament setups for reuse\n\n"
                "The Scenarios tab stores reusable settings separately from the live tournament. Use New Scenario Wizard to create a setup. Save Current Setup as Scenario captures the current settings.\n\n"
                "Select a scenario to Edit, Duplicate, Rename, Delete, or Launch New Tournament. Double-clicking a scenario also launches it.\n\n"
                "Scenario definitions include the tournament type, fees, rebuys and add-ons, Benefit Pot, payout rules, blind structure, and relevant sound preferences. Charity and Freeroll can be combined.\n\n"
                "Launching starts at Level 1 in a paused state with fresh count totals. If the current tournament has data, it is archived first. If the archive cannot be written, the launch is blocked. The scenario library remains separate."
            ),
            "New Scenario Wizard": (
                "Create a reusable scenario\n\n"
                "Step 1 — Scenario Basics: enter a scenario name, display title, type, optional description, and starting blind structure.\n"
                "Step 2 — Entries & Rules: set starting stack, buy-in, re-entry and add-on fees/chips, and enable optional features.\n"
                "Step 3 — Charity & Payouts: configure Benefit Pot, payout mode, paid-place rule, rounding, traditional splits, mixed payout structures, or fixed freeroll awards.\n"
                "Step 4 — Blind Structure & Review: use the current structure, a built-in Standard, Turbo, Hyper-Turbo, or Deep Stack template, an imported structure, or another scenario's structure. Add, edit, remove, reorder levels/breaks, or bulk-set durations.\n\n"
                "You can go back through wizard steps before saving. Give scenarios distinct names so you can identify the right setup quickly."
            ),
            "Tournament Settings": (
                "Choose a tournament template, then review dependent settings\n\n"
                "General: name, tournament type, and starting stack.\n"
                "Entries & Fees: buy-in, re-entry fee, house fee for Home Game only, add-on fee/chips, and on/off switches for rebuys/add-ons.\n"
                "Charity / Benefit Pot: enable the Benefit Pot, select fixed-per-entry or percentage-of-entry calculation, and optionally enforce a charity paid-place cap.\n"
                "Payout Rules: choose Traditional Percentages, Mixed Fixed + Percentage, or Freeroll Fixed Prizes; choose rounding and paid-position behavior; edit relevant payout structures.\n"
                "Blind levels always advance automatically. Each break has its own Pause? setting on the Blind Structure tab.\n\n"
                "Some fields are intentionally disabled when they do not apply. For example, House Fee is available only for Home Game. Rebuys and add-ons can be disabled independently. Click Save after making settings changes."
            ),
            "Entries and player counts": (
                "Count-based controls\n\n"
                "Add Player + / Bust Player − change active players only. Active players cannot exceed total paid entries. Busting a player does not delete an entry. Add Player can restore an active player if a bust was recorded by mistake.\n\n"
                "Add Entry + / Remove Entry − change initial-entry totals.\n"
                "Re-buy + / Re-buy − change the rebuy count and paid-entry total, but do not change active players.\n"
                "Add-on + / Add-on − change add-on counts, not players or paid-entry thresholds. Add-on buttons are hidden when add-ons are disabled. Rebuy controls are hidden when rebuys are disabled.\n\n"
                "If you reduce a count to zero, the decrement action is guarded. Use Reset Tournament to Zero only when intentionally clearing the current counts and tournament activity."
            ),
            "Blind Structure and breaks": (
                "Manage the schedule\n\n"
                "The Blind Structure tab contains ordered play levels and breaks. Each play level has a name, duration, small blind, and big blind. Play levels always advance automatically at expiration. Each break has its own clickable Pause? cell that controls whether the clock pauses when that break ends. Shift-click selects a range of rows and Ctrl-click selects individual rows. Ante controls are hidden in this release.\n\n"
                "Use Add Level, Add Break, Edit Selected, Delete Selected, and the move/reorder controls as available. Apply to All Play Levels and Apply to All Breaks set a shared duration for the relevant type.\n\n"
                "Import Blind Structure supports CSV, TSV, TXT, and XLSX files. For spreadsheet files with multiple populated worksheets, choose the worksheet to import. Import can replace the existing structure or append rows. Replacing a structure resets the clock to Level 1. Review imported values before starting."
            ),
            "Clock controls": (
                "Operate the tournament clock\n\n"
                "The main Tournament Clock tab and full-screen display show the current level and remaining time. Use Resume Clock to start/continue, Pause Clock to stop the countdown, and Reset Level to return the current level to its full scheduled duration.\n\n"
                "The time slider ranges from 0 to the configured duration of the current level or break. The −30 sec and +30 sec buttons adjust within those same boundaries. They do not change the scheduled duration.\n\n"
                "Play levels always transition automatically when they reach zero. Breaks also transition automatically unless that specific break row has its Pause? cell checked. When a break is configured to pause, the clock advances to the next scheduled row and waits paused. No confirmation dialog is required at a normal transition."
            ),
            "Full-screen display": (
                "TV display and controls\n\n"
                "Open the full-screen display from the Tournament Clock tab. It shows the tournament title, current level and timer, current blinds, next level, time until the next break (or break end), the Status/Statistics/Prizes dashboard, and the time-remaining pie chart.\n\n"
                "The pie represents the remaining fraction of the current level or break. It is green during normal time, yellow below 60 seconds, and red at 20 seconds or less. The digital timer remains the exact timer.\n\n"
                "Display & Sound includes a full-screen theme selector. Classic preserves the familiar layout. Modern uses a dark, cyan-accented style with a bottom-docked Hide/Show tab and smooth vertical slide animation. The Modern tab remains visible when controls are hidden and follows the timer pie's green/yellow/red color. Green controls add/increase/start; red controls remove/decrease/end; neutral controls handle other actions. Theme changes apply the next time you open the full-screen display. When large control fonts or button sizes leave less vertical room, Modern automatically reduces dashboard card, pie, and text sizing so the Status, Statistics, and 10-place payout details stay visible; Classic keeps its existing natural resizing. Press Escape to close the full-screen window."
            ),
            "Payout modes": (
                "Three payout modes are supported\n\n"
                "Traditional Percentages: distribute the prize pool by the saved percentage split for the calculated number of paid places. Edit the split under Tournament Settings → Payout Rules. The split must total 100%.\n\n"
                "Mixed Fixed + Percentage: configure a structure for a specific number of paid places. Fixed awards are deducted first; percentage positions share the remaining pool. The percentage rows must total 100%. If the structure violates a safety check, the calculator falls back to the traditional percentage split for that calculation and reports why.\n\n"
                "Freeroll Fixed Prizes: enter fixed amounts for one, two, or three places. These awards do not expand or shrink with entry count.\n\n"
                "The Payout Calculator tab is the results view. Select the payout method and edit its configuration in Tournament Settings → Payout Rules. Whole-dollar awards are displayed."
            ),
            "Paid-position rules": (
                "Choose how many positions are paid\n\n"
                "Automatic by entry rules: use the entry thresholds and configured number of paid places. Rebuys count as additional paid entries.\n\n"
                "Target fixed number: target the chosen number of paid places, limited by the actual entry count.\n\n"
                "Automatic with maximum cap: use the entry thresholds but never exceed the selected maximum.\n\n"
                "When enabled, the charity-specific maximum is an additional cap. It can reduce the number of paid places below the general rule. Freeroll fixed prizes use the configured fixed prize positions rather than entry thresholds."
            ),
            "Mixed payouts and safety fallback": (
                "Configure fixed awards and percentage awards\n\n"
                "For each paid-place count, configure a row per position. A row can be Percentage or Fixed amount ($). Fixed amounts are deducted from the distributable prize pool first. Percentage rows share the remainder and must total 100%.\n\n"
                "After applying the selected rounding increment and reconciling the total, the calculator checks that all awards are positive and that any higher position pays at least as much as a fixed award assigned to a lower position.\n\n"
                "If checks fail—for example, the fixed awards consume too much of the pool, rounding produces a non-positive award, percentages are invalid, or an earlier place would pay less than a later fixed award—the mixed structure is not used for that calculation. The traditional percentage split is used and the calculator displays a fallback reason. The saved mixed structure remains available to edit."
            ),
            "Freeroll fixed prizes": (
                "Use a host-funded fixed award structure\n\n"
                "Choose Freeroll Fixed Prizes under Tournament Settings → Payout Rules, then click Configure Freeroll Prizes. Select 1, 2, or 3 paid places and enter the fixed dollar amount for each active position. Disabled fields are not part of the selected place count.\n\n"
                "The displayed awards are independent of entry count. The host-funded fixed awards define the displayed prize total. Paid re-entries and add-ons can still be enabled as configured; their fees are included/excluded from the pool according to the selected settings and current payout mode. Charity/Benefit Pot can be enabled independently."
            ),
            "Charity and Benefit Pot": (
                "Configure the charity allocation\n\n"
                "Enable Charity / Benefit Pot under Tournament Settings → Charity / Benefit Pot. Select Fixed per entry or Percentage of each entry, then enter the amount or percent. If enabled, the calculated Benefit Pot is shown above Total Player Pot on the dashboard.\n\n"
                "The general paid-position rule and optional charity maximum cap work together; the charity cap can only reduce the number of paid places. Charity can be combined with Freeroll Fixed Prizes or the entry-funded payout modes.\n\n"
                "House Fee is available only for Home Game. It is disabled and excluded from calculations for other tournament types."
            ),
            "Display and sound": (
                "Main window sizing and sound alerts\n\n"
                "Display & Sound contains Configure Window Size, Configure Full-Screen Controls, and Open Sound Settings. Main-window width and height can be set independently from 70% to 100% of the monitor's reported dimensions. The window is centered; the full-screen tournament display has its own layout.\n\n"
                "Configure Full-Screen Controls opens the full-screen display with a settings popup over it. Adjust control font size (8–15 pt) and button size (75–150%) and the actual controls update live behind the popup. Save & Finish keeps the selected sizes; press Esc afterward to return to the main application. Cancel Preview restores the prior settings.\n\n"
                "Sound Settings lets you enable/disable sounds, select a default sound, choose the volume, set the low-time warning threshold (0 disables the warning), and override the sound for specific events. Use Test before saving.\n\n"
                "The supplied Long Gong WAV is configured for blind-level starts. One Minute WAV is configured for the low-time warning. Custom WAV files must be uncompressed PCM WAV. Verify actual playback on the tournament PC."
            ),
            "Reports and exports": (
                "Review and export tournament information\n\n"
                "Statistics & Reports is hidden from the main navigation in v1.2.0; its underlying reporting code is retained for possible future use. Blind Structure can be exported to CSV. The Payout Calculator remains available for payout results.\n\n"
                "The Payout Calculator is the main payout results view. It shows paid places, payout method/share, and estimated award amounts. Recalculate after changing entries, rebuys, add-ons, charity settings, or payout configuration."
            ),
            "Save, data, and backups": (
                "Where settings and tournament records are stored\n\n"
                "Current tournament/settings: mypoker_tournament.json in the current user's home folder.\n"
                "Saved scenario library: mypoker_tournament_scenarios.json in the current user's home folder.\n"
                "Archived sessions: mypoker_tournament_sessions.json in the current user's home folder.\n\n"
                "Close the app before copying these files for backup. Keep all three together when preserving a complete setup. Do not edit them while the application is open. An archived session is a JSON record; this release does not include a dedicated archive browser or restore screen.\n\n"
                "Installed release: MyPoker Tournament 1.1.0. After setup completes, launch the app from the Start Menu or optional desktop shortcut. The installed application includes its own runtime; Python does not need to be installed separately. The installer also places User Manual.pdf, the editable Word manual, release notes, and bundled sound files in the installation folder."
            ),
            "Installation and updates": (
                "Install and update MyPoker Tournament\n\n"
                "Run MyPokerTournament-Setup-1.1.0.exe and follow the Windows installer. You can choose to create a desktop shortcut; a Start Menu shortcut is created automatically. The installed app runs without a separate Python installation.\n\n"
                "The installer places the app, icon, offline Help, manuals, and bundled sounds under your Windows user profile. Your tournament data is stored separately in your user home folder, so uninstalling or reinstalling the application should not remove the tournament, scenarios, or archived sessions. Back up the three JSON data files before a major update.\n\n"
                "Version: 1.1.0. Installer builds are currently unsigned, so Windows may show a SmartScreen or antivirus warning. Only run the installer obtained from a trusted build of this project.\n\n"
                "After installation, launch MyPoker Tournament from the Start Menu or desktop shortcut. The Help / User Guide button in the black header opens these offline topics and the PDF manual."
            ),
            "Troubleshooting": (
                "Common issues\n\n"
                "The app will not start: launch it from the Start Menu or desktop shortcut. If it fails, restart Windows if prompted and try reinstalling from MyPokerTournament-Setup-1.1.0.exe. Keep your data files backed up before reinstalling.\n\n"
                "A sound does not play: open Display & Sound → Open Sound Settings, confirm sound is enabled and volume is above zero, use Test, check Windows audio output/mixer levels, and reinstall if the bundled sounds appear to be missing.\n\n"
                "A payout mode appears unavailable: open Tournament Settings → Payout Rules. Buttons are disabled when they do not apply to the current payout mode. In Mixed mode, configure a structure for the current number of paid places.\n\n"
                "The main window is cut off: lower the width/height percentages under Display & Sound → Configure Window Size. The setting affects the main window, not the full-screen TV display.\n\n"
                "Scenario launch is blocked: the app protects a live session by requiring a successful archive write. Check that the home-folder archive file is not read-only or malformed and that there is disk space. Back up existing files before attempting repairs."
            ),
        }

    def _build_help_tab(self, parent=None):
        tab = parent if parent is not None else self.help_tab
        ttk.Label(tab, text="MyPoker Tournament Help", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text="Offline instructions for the current release. Search topics below, press F1 for help related to the current tab, or open the complete PDF user manual.",
            wraplength=1050, justify="left"
        ).pack(anchor="w", pady=(3, 10))

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Quick Start", command=lambda: self._select_help_topic("Quick Start")).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Open User Manual (PDF)", command=self._open_user_manual).pack(side="left", padx=6)
        ttk.Label(toolbar, text="Tip: press F1 on any main tab for relevant help.", foreground="#52606d").pack(side="right")

        search_row = ttk.Frame(tab)
        search_row.pack(fill="x", pady=(0, 8))
        ttk.Label(search_row, text="Search help topics:").pack(side="left", padx=(0, 8))
        self.help_search_var = tk.StringVar()
        search = ttk.Entry(search_row, textvariable=self.help_search_var, width=40)
        search.pack(side="left", fill="x", expand=True)
        ttk.Button(search_row, text="Clear", command=lambda: self.help_search_var.set("")).pack(side="left", padx=(8, 0))

        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True)
        topic_frame = ttk.LabelFrame(body, text="Help Topics", padding=6)
        topic_frame.pack(side="left", fill="y", padx=(0, 10))
        self.help_topic_listbox = tk.Listbox(topic_frame, width=31, exportselection=False,
                                             font=("Segoe UI", 10), activestyle="dotbox")
        topic_scroll = ttk.Scrollbar(topic_frame, orient="vertical", command=self.help_topic_listbox.yview)
        self.help_topic_listbox.configure(yscrollcommand=topic_scroll.set)
        self.help_topic_listbox.pack(side="left", fill="y", expand=True)
        topic_scroll.pack(side="right", fill="y")
        self.help_topic_contents = self._help_topic_content()
        self.help_topic_names = list(self.help_topic_contents)
        self.help_topic_listbox.bind("<<ListboxSelect>>", self._show_selected_help_topic)

        article_frame = ttk.LabelFrame(body, text="Instructions", padding=8)
        article_frame.pack(side="left", fill="both", expand=True)
        self.help_article_heading = ttk.Label(article_frame, text="Quick Start", font=("Segoe UI", 12, "bold"))
        self.help_article_heading.pack(anchor="w", pady=(0, 6))
        article_body = ttk.Frame(article_frame)
        article_body.pack(fill="both", expand=True)
        self.help_article = tk.Text(article_body, wrap="word", font=("Segoe UI", 10),
                                    relief="flat", borderwidth=0, padx=8, pady=8)
        article_scroll = ttk.Scrollbar(article_body, orient="vertical", command=self.help_article.yview)
        self.help_article.configure(yscrollcommand=article_scroll.set)
        self.help_article.pack(side="left", fill="both", expand=True)
        article_scroll.pack(side="right", fill="y")
        self.help_article.configure(state="disabled", background="#ffffff", foreground="#202830", insertbackground="#202830", selectbackground="#c7e3f5", selectforeground="#202830")

        self.help_search_var.trace_add("write", lambda *_: self._filter_help_topics())
        self._filter_help_topics()
        self._select_help_topic("Quick Start")

    def _filter_help_topics(self):
        if not hasattr(self, "help_topic_listbox"):
            return
        query = self.help_search_var.get().strip().casefold()
        self.help_topic_listbox.delete(0, tk.END)
        matches = []
        for title, body in self.help_topic_contents.items():
            if not query or query in title.casefold() or query in body.casefold():
                matches.append(title)
                self.help_topic_listbox.insert(tk.END, title)
        if matches:
            self.help_topic_listbox.selection_set(0)
            self.help_topic_listbox.activate(0)
            self._render_help_topic(matches[0])
        else:
            self.help_article_heading.configure(text="No matching topic")
            self.help_article.configure(state="normal")
            self.help_article.delete("1.0", tk.END)
            self.help_article.insert("1.0", "No help topics match your search. Try another word.")
            self.help_article.configure(state="disabled")

    def _render_help_topic(self, topic):
        if topic not in self.help_topic_contents:
            return
        self.help_article_heading.configure(text=topic)
        self.help_article.configure(state="normal")
        self.help_article.delete("1.0", tk.END)
        self.help_article.insert("1.0", self.help_topic_contents[topic])
        self.help_article.configure(state="disabled")
        self.help_article.yview_moveto(0)

    def _show_selected_help_topic(self, _event=None):
        selection = self.help_topic_listbox.curselection()
        if selection:
            topic = self.help_topic_listbox.get(selection[0])
            self._render_help_topic(topic)

    def _open_help_tab(self, topic="Quick Start"):
        """Open built-in offline Help in a dedicated window, not a main navigation tab."""
        try:
            if self.help_window is not None and self.help_window.winfo_exists():
                self.help_window.deiconify()
                self.help_window.lift()
                self.help_window.focus_force()
                self._select_help_topic(topic)
                return
        except tk.TclError:
            pass
        win = tk.Toplevel(self)
        win.title("MyPoker Tournament — Help / User Guide")
        win.geometry("1050x700")
        win.minsize(800, 560)
        win.transient(self)
        self.help_window = win
        outer = ttk.Frame(win, padding=12)
        outer.pack(fill="both", expand=True)
        self._build_help_tab(parent=outer)
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_help_window(win))
        self._select_help_topic(topic)

    def _close_help_window(self, win):
        try:
            win.destroy()
        finally:
            if self.help_window is win:
                self.help_window = None

    def _select_help_topic(self, topic):
        self.help_search_var.set("")
        try:
            index = self.help_topic_names.index(topic)
        except ValueError:
            index = 0
        self.help_topic_listbox.selection_clear(0, tk.END)
        self.help_topic_listbox.selection_set(index)
        self.help_topic_listbox.activate(index)
        self.help_topic_listbox.see(index)
        self._render_help_topic(self.help_topic_names[index])

    def _open_user_manual(self):
        """Open the installed PDF manual, falling back to the bundled resource."""
        manual_path = resource_path("User Manual.pdf")
        # In a frozen Windows installation, prefer the persistent copy beside the EXE.
        # The PyInstaller one-file resource directory is temporary and is removed on exit.
        if getattr(sys, "frozen", False):
            installed_copy = os.path.join(os.path.dirname(sys.executable), "User Manual.pdf")
            if os.path.isfile(installed_copy):
                manual_path = installed_copy
        if not os.path.isfile(manual_path):
            messagebox.showerror(
                "User Manual Not Found",
                "User Manual.pdf was not found in the application resources. Re-run the MyPoker Tournament installer to repair the installation.",
                parent=self,
            )
            return
        try:
            if os.name == "nt":
                os.startfile(manual_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", manual_path])
            else:
                subprocess.Popen(["xdg-open", manual_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            messagebox.showerror("Unable to Open User Manual", f"Could not open the PDF manual:\n{exc}", parent=self)

    def _help_for_current_tab(self, _event=None):
        if not hasattr(self, "notebook"):
            return None
        try:
            tab_text = self.notebook.tab(self.notebook.select(), "text")
        except tk.TclError:
            tab_text = "Help"
        mapping = {
            "Tournament Clock": "Clock controls",
            "Scenarios": "Scenario Manager",
            "Tournament Settings": "Tournament Settings",
            "Display & Sound": "Display and sound",
            "Blind Structure": "Blind Structure and breaks",
            "Statistics & Reports": "Reports and exports",
            "Payout Calculator": "Payout modes",
        }
        topic = mapping.get(tab_text, "Quick Start")
        self._open_help_tab(topic)
        return "break"

    # ------------------------------------------------------------------
    # Scenario Manager
    # ------------------------------------------------------------------
    def _scenario_config_snapshot(self, levels_override=None):
        """Capture reusable tournament configuration without live tournament data.

        ``levels_override`` lets save/wizard flows retain the exact blind structure
        that was on screen before settings validation refreshes the UI. Imported
        blind schedules are data, not a preset, so never regenerate them here.
        """
        keys = (
            "levels", "tournament_name", "tournament_type", "pre_freeroll_buy_in",
            "pre_freeroll_house_fee", "pre_freeroll_payout_mode", "home_game_house_fee",
            "buy_in", "reentry_fee", "ante_enabled", "rebuy_enabled",
            "add_on_enabled", "add_on_fee", "add_on_chips", "house_fee", "charity_mode",
            "charity_method", "charity_value", "limit_charity_paid_places", "charity_max_paid_places",
            "tracking_mode", "starting_stack", "payout_rules", "payout_splits", "payout_template_name",
            "payout_position_mode", "target_paid_places", "max_paid_places", "mixed_payouts",
            "payout_mode", "freeroll_paid_places", "freeroll_payouts", "payout_rounding_increment",
            "sound_enabled", "default_sound", "sound_volume", "custom_sound_path",
            "sound_warning_seconds", "sound_overrides",
        )
        snapshot = {key: copy.deepcopy(getattr(self, key)) for key in keys
                    if hasattr(self, key)}
        # Explicitly pin the active blind structure. In particular, do not let a
        # settings-form refresh or wizard initialization replace imported levels
        # with DEFAULT_LEVELS before the scenario snapshot is created.
        source_levels = levels_override if levels_override is not None else getattr(self, "levels", None)
        if isinstance(source_levels, list) and source_levels:
            snapshot["levels"] = copy.deepcopy(source_levels)
        snapshot["pre_freeroll_buy_in"] = copy.deepcopy(self._pre_freeroll_buy_in)
        snapshot["pre_freeroll_house_fee"] = copy.deepcopy(self._pre_freeroll_house_fee)
        snapshot["pre_freeroll_payout_mode"] = copy.deepcopy(self._pre_freeroll_payout_mode)
        snapshot["tracking_mode"] = "Entry count only"
        snapshot["ante_enabled"] = False
        # JSON round-trip makes the snapshot independent from live mutable lists/dictionaries.
        return json.loads(json.dumps(snapshot))

    def _load_scenario_library(self):
        """Load reusable scenario definitions from a separate file, not the session save."""
        self.scenarios = []
        try:
            if not os.path.exists(SCENARIOS_FILE):
                return
            with open(SCENARIOS_FILE, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if not isinstance(raw, list):
                return
            seen = set()
            for item in raw:
                if not isinstance(item, dict) or not isinstance(item.get("config"), dict):
                    continue
                name = str(item.get("name", "")).strip()
                sid = str(item.get("id", "")).strip() or uuid.uuid4().hex
                if not name or sid in seen:
                    continue
                cfg = self._normalize_scenario_config(item["config"])
                if cfg is None:
                    continue
                seen.add(sid)
                self.scenarios.append({
                    "id": sid,
                    "name": name,
                    "description": str(item.get("description", "") or ""),
                    "created_at": str(item.get("created_at", "") or ""),
                    "updated_at": str(item.get("updated_at", "") or ""),
                    "config": cfg,
                })
        except Exception:
            # A damaged scenario library must never prevent the tournament clock from opening.
            self.scenarios = []

    def _normalize_scenario_config(self, raw):
        """Validate and normalize a scenario configuration loaded from JSON."""
        if not isinstance(raw, dict):
            return None
        cfg = copy.deepcopy(raw)
        allowed_types = ("Standard Tournament", "Charity Tournament", "Home Game", "Freeroll")
        allowed_modes = ("Traditional Percentages", "Mixed Fixed + Percentage", "Freeroll Fixed Prizes")
        allowed_position_modes = ("Automatic by entry rules", "Target fixed number", "Automatic with maximum cap")
        try:
            cfg["tournament_type"] = str(cfg.get("tournament_type", "Standard Tournament"))
            if cfg["tournament_type"] not in allowed_types:
                return None
            cfg["tournament_name"] = str(cfg.get("tournament_name", "MyPoker Tournament") or "MyPoker Tournament")
            cfg["levels"] = cfg.get("levels", [dict(x) for x in DEFAULT_LEVELS])
            if not isinstance(cfg["levels"], list) or not cfg["levels"]:
                return None
            clean_levels = []
            for level in cfg["levels"]:
                if not isinstance(level, dict):
                    return None
                kind = "Break" if level.get("kind") == "Break" else "Play"
                minutes = int(level.get("minutes", 20))
                if minutes < 1 or minutes > 240:
                    return None
                row = {
                    "name": str(level.get("name", "Break" if kind == "Break" else "Level")),
                    "minutes": minutes,
                    "sb": 0 if kind == "Break" else int(level.get("sb", 0)),
                    "bb": 0 if kind == "Break" else int(level.get("bb", 0)),
                    "ante": 0 if kind == "Break" else int(level.get("ante", 0)),
                    "kind": kind,
                }
                if kind == "Break":
                    # Every break has an independent pause setting; missing legacy flags default off.
                    row["pause_after"] = bool(level.get("pause_after", False))
                if min(row["sb"], row["bb"], row["ante"]) < 0 or (kind == "Play" and row["bb"] <= 0):
                    return None
                clean_levels.append(row)
            if not any(row["kind"] == "Play" for row in clean_levels):
                return None
            cfg["levels"] = clean_levels
            cfg["buy_in"] = max(0.0, float(cfg.get("buy_in", 30)))
            cfg["reentry_fee"] = max(0.0, float(cfg.get("reentry_fee", 20)))
            cfg["home_game_house_fee"] = max(0.0, float(cfg.get("home_game_house_fee", cfg.get("house_fee", 0))))
            cfg["house_fee"] = cfg["home_game_house_fee"] if cfg["tournament_type"] == "Home Game" else 0.0
            cfg["add_on_fee"] = max(0.0, float(cfg.get("add_on_fee", 0)))
            cfg["add_on_chips"] = max(0, int(cfg.get("add_on_chips", 0)))
            cfg["starting_stack"] = max(1, int(cfg.get("starting_stack", 10000)))
            cfg["ante_enabled"] = False
            cfg["rebuy_enabled"] = bool(cfg.get("rebuy_enabled", True))
            cfg["add_on_enabled"] = bool(cfg.get("add_on_enabled", True))
            # Obsolete global pause flags from older versions are intentionally ignored.
            cfg.pop("pause_after_break", None)
            cfg.pop("pause_after_blind_level", None)
            cfg["charity_mode"] = bool(cfg.get("charity_mode", False))
            cfg["charity_method"] = str(cfg.get("charity_method", "Fixed per entry"))
            if cfg["charity_method"] not in ("Fixed per entry", "Percentage of each entry"):
                cfg["charity_method"] = "Fixed per entry"
            cfg["charity_value"] = max(0.0, float(cfg.get("charity_value", 0)))
            cfg["limit_charity_paid_places"] = bool(cfg.get("limit_charity_paid_places", False))
            cfg["charity_max_paid_places"] = max(1, min(100, int(cfg.get("charity_max_paid_places", 5))))
            cfg["tracking_mode"] = "Entry count only"
            cfg["payout_mode"] = cfg.get("payout_mode", "Traditional Percentages")
            if cfg["payout_mode"] not in allowed_modes:
                cfg["payout_mode"] = "Traditional Percentages"
            cfg["payout_position_mode"] = cfg.get("payout_position_mode", "Automatic by entry rules")
            if cfg["payout_position_mode"] not in allowed_position_modes:
                cfg["payout_position_mode"] = "Automatic by entry rules"
            cfg["target_paid_places"] = max(1, min(100, int(cfg.get("target_paid_places", 6))))
            cfg["max_paid_places"] = max(1, min(100, int(cfg.get("max_paid_places", 6))))
            cfg["payout_rounding_increment"] = int(cfg.get("payout_rounding_increment", 5))
            if cfg["payout_rounding_increment"] not in (1, 5, 10, 20, 25, 50, 100):
                cfg["payout_rounding_increment"] = 5
            loaded_rules = cfg.get("payout_rules", [dict(x) for x in DEFAULT_PAYOUT_RULES])
            if _payout_rules_signature(loaded_rules) == _payout_rules_signature(LEGACY_DEFAULT_PAYOUT_RULES):
                cfg["payout_rules"] = [dict(row) for row in DEFAULT_PAYOUT_RULES]
            else:
                cfg["payout_rules"] = loaded_rules
            raw_splits = cfg.get("payout_splits", DEFAULT_PAYOUT_SPLITS)
            if not cfg.get("payout_template_name") and _payout_splits_signature(raw_splits) == _payout_splits_signature(LEGACY_DEFAULT_PAYOUT_SPLITS):
                raw_splits = DEFAULT_PAYOUT_SPLITS
                cfg["payout_template_name"] = DEFAULT_PAYOUT_TEMPLATE_NAME
            cfg["payout_splits"] = {str(k): list(v) for k, v in raw_splits.items()}
            if cfg.get("payout_template_name"):
                cfg["payout_template_name"] = str(cfg["payout_template_name"])
            else:
                default_map = {str(k): list(v) for k, v in DEFAULT_PAYOUT_SPLITS.items()}
                cfg["payout_template_name"] = DEFAULT_PAYOUT_TEMPLATE_NAME if cfg["payout_splits"] == default_map else "Custom / edited"
            cfg["mixed_payouts"] = {str(k): copy.deepcopy(v) for k, v in cfg.get("mixed_payouts", {}).items()}
            cfg["freeroll_paid_places"] = max(1, min(3, int(cfg.get("freeroll_paid_places", 1))))
            raw_awards = cfg.get("freeroll_payouts", [0, 0, 0])
            cfg["freeroll_payouts"] = [max(0, int(float(v))) for v in list(raw_awards)[:3]]
            while len(cfg["freeroll_payouts"]) < 3:
                cfg["freeroll_payouts"].append(0)
            cfg["pre_freeroll_buy_in"] = cfg.get("pre_freeroll_buy_in")
            cfg["pre_freeroll_house_fee"] = cfg.get("pre_freeroll_house_fee")
            cfg["pre_freeroll_payout_mode"] = cfg.get("pre_freeroll_payout_mode")
            cfg["sound_enabled"] = bool(cfg.get("sound_enabled", True))
            cfg["default_sound"] = str(cfg.get("default_sound", "Chime"))
            cfg["sound_volume"] = max(0, min(100, int(cfg.get("sound_volume", 70))))
            cfg["custom_sound_path"] = str(cfg.get("custom_sound_path", "") or "")
            cfg["sound_warning_seconds"] = max(0, min(3600, int(cfg.get("sound_warning_seconds", 60))))
            cfg["sound_overrides"] = cfg.get("sound_overrides", dict(self.sound_overrides))
            if not isinstance(cfg["sound_overrides"], dict):
                cfg["sound_overrides"] = dict(self.sound_overrides)
            return cfg
        except (TypeError, ValueError, OverflowError):
            return None

    def _save_scenario_library(self):
        """Atomically save scenario definitions in their own file."""
        try:
            directory = os.path.dirname(SCENARIOS_FILE) or "."
            os.makedirs(directory, exist_ok=True)
            tmp_path = SCENARIOS_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(self.scenarios, handle, indent=2)
            os.replace(tmp_path, SCENARIOS_FILE)
            return True
        except Exception as exc:
            messagebox.showerror("Scenario Save Error", f"Could not save the scenario library:\n{exc}", parent=self)
            return False

    def _build_scenarios_tab(self):
        tab = self.scenarios_tab
        ttk.Label(tab, text="Scenario Manager", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text="Save complete tournament setups so you can launch them later without re-entering fees, payout rules, sounds, or blind schedules. Scenario definitions are stored separately from the current tournament session.",
            wraplength=1100, justify="left"
        ).pack(anchor="w", pady=(4, 10))

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="New Scenario Wizard…", command=self._scenario_new_wizard).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Save Current Setup as Scenario…", command=self._scenario_save_current).pack(side="left", padx=6)
        self.scenario_launch_button = ttk.Button(toolbar, text="Launch New Tournament", command=self._scenario_launch_selected)
        self.scenario_launch_button.pack(side="left", padx=6)
        self.scenario_edit_button = ttk.Button(toolbar, text="Edit Selected…", command=self._scenario_edit_selected)
        self.scenario_edit_button.pack(side="left", padx=6)
        self.scenario_duplicate_button = ttk.Button(toolbar, text="Duplicate", command=self._scenario_duplicate_selected)
        self.scenario_duplicate_button.pack(side="left", padx=6)
        self.scenario_rename_button = ttk.Button(toolbar, text="Rename", command=self._scenario_rename_selected)
        self.scenario_rename_button.pack(side="left", padx=6)
        self.scenario_delete_button = ttk.Button(toolbar, text="Delete", command=self._scenario_delete_selected)
        self.scenario_delete_button.pack(side="left", padx=6)

        columns = ("name", "type", "payout", "levels", "rebuys", "addons", "updated")
        self.scenario_tree = ttk.Treeview(tab, columns=columns, show="headings", height=12, selectmode="browse")
        for column, heading, width in (
            ("name", "Scenario", 230), ("type", "Tournament Type", 190), ("payout", "Payout Mode", 210),
            ("levels", "Levels / Breaks", 110), ("rebuys", "Rebuys", 80), ("addons", "Add-ons", 80),
            ("updated", "Last Updated", 150),
        ):
            self.scenario_tree.heading(column, text=heading)
            self.scenario_tree.column(column, width=width, anchor="w" if column in ("name", "type", "payout") else "center")
        self.scenario_tree.pack(fill="both", expand=True)
        self.scenario_tree.bind("<<TreeviewSelect>>", self._scenario_selection_changed)
        self.scenario_tree.bind("<Double-1>", lambda _event: self._scenario_launch_selected())

        self.scenario_status_var = tk.StringVar(value="No scenario selected.")
        ttk.Label(tab, textvariable=self.scenario_status_var, wraplength=1100, justify="left",
                  foreground="#52606d").pack(anchor="w", pady=(8, 2))
        ttk.Label(
            tab,
            text="Launch starts a fresh tournament at Level 1 paused. If the current tournament has data, it is archived first in a separate file; your scenario library is kept separate from tournament sessions.",
            wraplength=1100, justify="left", foreground="#52606d"
        ).pack(anchor="w", pady=(4, 0))
        self._refresh_scenario_tree()

    def _refresh_scenario_tree(self):
        if not hasattr(self, "scenario_tree"):
            return
        previous = self.scenario_tree.selection()
        selected_id = previous[0] if previous else getattr(self, "active_scenario_id", "")
        for item in self.scenario_tree.get_children():
            self.scenario_tree.delete(item)
        for scenario in sorted(self.scenarios, key=lambda item: item.get("name", "").casefold()):
            cfg = scenario.get("config", {})
            levels = cfg.get("levels", [])
            play_count = sum(1 for row in levels if row.get("kind") != "Break")
            break_count = sum(1 for row in levels if row.get("kind") == "Break")
            payout_mode = str(cfg.get("payout_mode", "Traditional Percentages"))
            updated = str(scenario.get("updated_at", ""))
            if len(updated) > 16:
                updated = updated[:16].replace("T", " ")
            self.scenario_tree.insert("", "end", iid=scenario["id"], values=(
                scenario.get("name", ""), cfg.get("tournament_type", ""), payout_mode,
                f"{play_count} / {break_count}", "On" if cfg.get("rebuy_enabled", True) else "Off",
                "On" if cfg.get("add_on_enabled", True) else "Off", updated or "—"
            ))
        if selected_id and self.scenario_tree.exists(selected_id):
            self.scenario_tree.selection_set(selected_id)
            self.scenario_tree.focus(selected_id)
        self._scenario_selection_changed()

    def _selected_scenario(self):
        if not hasattr(self, "scenario_tree"):
            return None
        selected = self.scenario_tree.selection()
        if not selected:
            return None
        sid = selected[0]
        return next((item for item in self.scenarios if item.get("id") == sid), None)

    def _scenario_selection_changed(self, _event=None):
        scenario = self._selected_scenario()
        state = "normal" if scenario else "disabled"
        for attr in ("scenario_launch_button", "scenario_edit_button", "scenario_duplicate_button",
                     "scenario_rename_button", "scenario_delete_button"):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.configure(state=state)
        if not scenario:
            if hasattr(self, "scenario_status_var"):
                self.scenario_status_var.set(
                    f"{len(self.scenarios)} saved scenario(s). Create one with New Scenario Wizard or save your current setup."
                    if self.scenarios else "No saved scenarios yet. Use New Scenario Wizard or Save Current Setup as Scenario to build your library."
                )
            return
        cfg = scenario["config"]
        levels = cfg.get("levels", [])
        breaks = sum(1 for row in levels if row.get("kind") == "Break")
        plays = len(levels) - breaks
        charity = "Benefit Pot on" if cfg.get("charity_mode") else "Benefit Pot off"
        self.scenario_status_var.set(
            f"{scenario['name']} — {scenario.get('description', '')}\n"
            f"{cfg.get('tournament_type')} · {cfg.get('payout_mode')} · {plays} play levels / {breaks} breaks · "
            f"Rebuys {'enabled' if cfg.get('rebuy_enabled') else 'disabled'} · "
            f"Add-ons {'enabled' if cfg.get('add_on_enabled') else 'disabled'} · {charity}."
        )

    def _scenario_current_has_data(self):
        try:
            return bool(
                self.players or self.anonymous_original_entries or self.anonymous_reentries or self.anonymous_addons
                or self.start_time is not None or self.current_level != 0 or self.history
                or self.remaining_seconds != int(self.levels[0].get("minutes", 20)) * 60
            )
        except Exception:
            return bool(self.players or self.start_time is not None)

    def _archive_current_tournament(self, was_running_before=False):
        """Append the current tournament session to a separate archive before scenario launch.

        The scenario library and current-session save remain separate. An archive write is
        atomic; if the archive can't be saved, the new scenario is not launched.
        """
        try:
            directory = os.path.dirname(TOURNAMENT_ARCHIVE_FILE) or "."
            os.makedirs(directory, exist_ok=True)
            archived_sessions = []
            if os.path.exists(TOURNAMENT_ARCHIVE_FILE):
                with open(TOURNAMENT_ARCHIVE_FILE, "r", encoding="utf-8") as handle:
                    archived_sessions = json.load(handle)
                if not isinstance(archived_sessions, list):
                    raise ValueError("The tournament archive file is not a valid session list. It was not overwritten.")

            active, entries, reentries = self._counts()
            payout_entries, payout_pool, paid_places, payout_rows = self._calculate_payouts()
            record = {
                "archive_id": uuid.uuid4().hex,
                "archived_at": datetime.now().isoformat(timespec="seconds"),
                "tournament_name": self.tournament_name,
                "scenario_id": self.active_scenario_id,
                "scenario_name": self.active_scenario_name,
                "tournament_started_at": self.start_time,
                "clock_was_running_at_archive": bool(was_running_before),
                "current_level_index": int(self.current_level),
                "current_level_number": int(self.current_level) + 1,
                "current_level": copy.deepcopy(self._current_level()),
                "remaining_seconds": int(self._current_seconds() if self.running else self.remaining_seconds),
                "levels": copy.deepcopy(self.levels),
                "players": copy.deepcopy(self.players),
                "next_player_id": int(self.next_player_id),
                "tracking_mode": self.tracking_mode,
                "anonymous_original_entries": int(self.anonymous_original_entries),
                "anonymous_active_players": int(self.anonymous_active_players),
                "anonymous_reentries": int(self.anonymous_reentries),
                "anonymous_addons": int(self.anonymous_addons),
                "active_players": int(active),
                "total_entries": int(entries),
                "rebuys": int(reentries),
                "history": copy.deepcopy(self.history),
                "configuration": self._scenario_config_snapshot(),
                "financials": copy.deepcopy(self._entry_financials()),
                "payout_summary": {
                    "entries": int(payout_entries),
                    "prize_pool": int(payout_pool),
                    "paid_places": int(paid_places),
                    "awards": [
                        {"place": int(row[0]), "share_percent": float(row[1]), "amount": int(row[2])}
                        for row in payout_rows
                    ],
                    "mixed_payout_fallback_reason": str(getattr(self, "_mixed_payout_fallback_reason", "") or ""),
                },
            }
            archived_sessions.append(record)
            tmp_path = TOURNAMENT_ARCHIVE_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(archived_sessions, handle, indent=2)
            os.replace(tmp_path, TOURNAMENT_ARCHIVE_FILE)
            return True
        except Exception as exc:
            messagebox.showerror(
                "Tournament Archive Error",
                "The current tournament could not be archived, so the new scenario was not launched. "
                "Your current tournament data has not been cleared.\n\n"
                f"Archive file: {TOURNAMENT_ARCHIVE_FILE}\n\nDetails: {exc}",
                parent=self,
            )
            return False

    def _scenario_apply_type_template(self, cfg, selected):
        """Apply scenario-wizard type defaults while keeping charity independently selectable with freeroll."""
        previous = str(cfg.get("tournament_type", "Standard Tournament"))
        if previous == "Home Game" and selected != "Home Game":
            try:
                cfg["home_game_house_fee"] = max(0.0, float(cfg.get("house_fee", cfg.get("home_game_house_fee", 0))))
            except (TypeError, ValueError):
                pass
        leaving_freeroll = previous == "Freeroll" and selected != "Freeroll"
        if selected == "Freeroll" and previous != "Freeroll":
            cfg["pre_freeroll_buy_in"] = cfg.get("buy_in", 30.0)
            cfg["pre_freeroll_house_fee"] = cfg.get("house_fee", 0.0)
            cfg["pre_freeroll_payout_mode"] = cfg.get("payout_mode", "Traditional Percentages")
            cfg["buy_in"] = 0.0
            cfg["house_fee"] = 0.0
            cfg["payout_mode"] = "Freeroll Fixed Prizes"
        elif leaving_freeroll:
            cfg["buy_in"] = cfg.get("pre_freeroll_buy_in") if cfg.get("pre_freeroll_buy_in") is not None else 30.0
            cfg["home_game_house_fee"] = cfg.get("pre_freeroll_house_fee") if cfg.get("pre_freeroll_house_fee") is not None else cfg.get("home_game_house_fee", 0.0)
            cfg["house_fee"] = cfg["home_game_house_fee"] if selected == "Home Game" else 0.0
            restored_mode = cfg.get("pre_freeroll_payout_mode") or "Traditional Percentages"
            cfg["payout_mode"] = restored_mode if restored_mode in (
                "Traditional Percentages", "Mixed Fixed + Percentage", "Freeroll Fixed Prizes"
            ) else "Traditional Percentages"
            cfg["pre_freeroll_buy_in"] = None
            cfg["pre_freeroll_house_fee"] = None
            cfg["pre_freeroll_payout_mode"] = None
        cfg["tournament_type"] = selected
        if selected == "Charity Tournament":
            cfg["charity_mode"] = True
        elif selected in ("Standard Tournament", "Home Game"):
            cfg["charity_mode"] = False
            if not leaving_freeroll:
                cfg["payout_mode"] = "Traditional Percentages"
        if selected == "Home Game":
            cfg["house_fee"] = max(0.0, float(cfg.get("home_game_house_fee", cfg.get("house_fee", 0))))
        else:
            cfg["house_fee"] = 0.0
        return cfg

    def _scenario_save_current(self):
        # Capture before applying/refreshing settings: imported custom levels must
        # survive the refresh and be the exact levels written into the scenario.
        current_levels = copy.deepcopy(getattr(self, "levels", []))
        if not self._apply_tournament_settings_from_form():
            return
        name = simpledialog.askstring("Save Current Setup as Scenario", "Scenario name:", parent=self)
        if not name or not name.strip():
            return
        if any(item["name"].casefold() == name.strip().casefold() for item in self.scenarios):
            messagebox.showerror("Duplicate scenario name", "A scenario with this name already exists. Choose a different name or duplicate/rename the existing scenario.", parent=self)
            return
        description = simpledialog.askstring("Scenario Description", "Optional description:", parent=self) or ""
        now = datetime.now().isoformat(timespec="seconds")
        cfg = self._scenario_config_snapshot(levels_override=current_levels)
        # Normalize once before persisting so the library stores the same validated
        # level rows that Launch New Tournament will later restore.
        cfg = self._normalize_scenario_config(cfg)
        if cfg is None:
            messagebox.showerror("Scenario Save Error", "The current settings or blind structure are invalid. Please review the Blind Structure tab and try again.", parent=self)
            return
        scenario = {"id": uuid.uuid4().hex, "name": name.strip(), "description": description.strip(),
                    "created_at": now, "updated_at": now, "config": cfg}
        old_scenarios = copy.deepcopy(self.scenarios)
        self.scenarios.append(scenario)
        if self._save_scenario_library():
            self._refresh_scenario_tree()
            self.scenario_tree.selection_set(scenario["id"])
            self.scenario_tree.focus(scenario["id"])
            self._scenario_selection_changed()
        else:
            self.scenarios = old_scenarios
            self._refresh_scenario_tree()

    def _scenario_duplicate_selected(self):
        source = self._selected_scenario()
        if not source:
            return
        name = simpledialog.askstring("Duplicate Scenario", "Name for the copy:", initialvalue=f"{source['name']} Copy", parent=self)
        if not name or not name.strip():
            return
        if any(item["name"].casefold() == name.strip().casefold() for item in self.scenarios):
            messagebox.showerror("Duplicate scenario name", "A scenario with this name already exists.", parent=self)
            return
        now = datetime.now().isoformat(timespec="seconds")
        duplicate = {"id": uuid.uuid4().hex, "name": name.strip(), "description": source.get("description", ""),
                     "created_at": now, "updated_at": now, "config": copy.deepcopy(source["config"])}
        old_scenarios = copy.deepcopy(self.scenarios)
        self.scenarios.append(duplicate)
        if self._save_scenario_library():
            self._refresh_scenario_tree()
            self.scenario_tree.selection_set(duplicate["id"])
            self._scenario_selection_changed()
        else:
            self.scenarios = old_scenarios
            self._refresh_scenario_tree()

    def _scenario_rename_selected(self):
        scenario = self._selected_scenario()
        if not scenario:
            return
        name = simpledialog.askstring("Rename Scenario", "Scenario name:", initialvalue=scenario["name"], parent=self)
        if not name or not name.strip():
            return
        if any(item["id"] != scenario["id"] and item["name"].casefold() == name.strip().casefold() for item in self.scenarios):
            messagebox.showerror("Duplicate scenario name", "A scenario with this name already exists.", parent=self)
            return
        old_scenarios = copy.deepcopy(self.scenarios)
        scenario["name"] = name.strip()
        scenario["updated_at"] = datetime.now().isoformat(timespec="seconds")
        if self._save_scenario_library():
            self._refresh_scenario_tree()
            self.scenario_tree.selection_set(scenario["id"])
            self._scenario_selection_changed()
        else:
            self.scenarios = old_scenarios
            self._refresh_scenario_tree()

    def _scenario_delete_selected(self):
        scenario = self._selected_scenario()
        if not scenario:
            return
        if not messagebox.askyesno("Delete Scenario", f"Delete saved scenario '{scenario['name']}'?\n\nThis does not delete any saved tournament results.", icon="warning", parent=self):
            return
        old_scenarios = copy.deepcopy(self.scenarios)
        self.scenarios = [item for item in self.scenarios if item["id"] != scenario["id"]]
        if self._save_scenario_library():
            self._refresh_scenario_tree()
        else:
            self.scenarios = old_scenarios
            self._refresh_scenario_tree()

    def _scenario_new_wizard(self):
        self._scenario_wizard(existing=None)

    def _scenario_edit_selected(self):
        scenario = self._selected_scenario()
        if scenario:
            self._scenario_wizard(existing=scenario)

    def _scenario_launch_selected(self):
        scenario = self._selected_scenario()
        if not scenario:
            return
        cfg = self._normalize_scenario_config(scenario.get("config", {}))
        if cfg is None:
            messagebox.showerror("Invalid Scenario", "This scenario's configuration is invalid. Edit it or create a replacement scenario.", parent=self)
            return
        had_current_session = bool(self.running or self._scenario_current_has_data())
        if had_current_session:
            confirmed = messagebox.askyesno(
                "Launch New Tournament",
                f"Launch '{scenario['name']}' as a new tournament?\n\n"
                "The current tournament will be archived separately, including player records, entries, history, "
                "financials, and a payout snapshot. The live session will then be reset to Level 1 and paused. "
                "Your saved scenarios will remain available.\n\nContinue?",
                icon="warning", parent=self
            )
            if not confirmed:
                return
        was_running_before = bool(self.running)
        self.pause_clock()
        if had_current_session and not self._archive_current_tournament(was_running_before=was_running_before):
            if hasattr(self, "scenario_status_var"):
                self.scenario_status_var.set("Launch cancelled because the current tournament could not be safely archived.")
            return
        # Replace only reusable configuration; session data is archived before being reset.
        config_attrs = (
            "levels", "tournament_name", "tournament_type", "pre_freeroll_buy_in", "pre_freeroll_house_fee",
            "pre_freeroll_payout_mode", "home_game_house_fee", "buy_in", "reentry_fee", "ante_enabled",
            "rebuy_enabled", "add_on_enabled", "add_on_fee", "add_on_chips", "house_fee",
            "charity_mode", "charity_method", "charity_value", "limit_charity_paid_places", "charity_max_paid_places",
            "tracking_mode", "starting_stack", "payout_rules", "payout_splits", "payout_template_name", "payout_position_mode",
            "target_paid_places", "max_paid_places", "mixed_payouts", "payout_mode", "freeroll_paid_places",
            "freeroll_payouts", "payout_rounding_increment", "sound_enabled", "default_sound", "sound_volume",
            "custom_sound_path", "sound_warning_seconds", "sound_overrides",
        )
        for key in config_attrs:
            if key in cfg:
                attr_name = {
                    "pre_freeroll_buy_in": "_pre_freeroll_buy_in",
                    "pre_freeroll_house_fee": "_pre_freeroll_house_fee",
                    "pre_freeroll_payout_mode": "_pre_freeroll_payout_mode",
                }.get(key, key)
                setattr(self, attr_name, copy.deepcopy(cfg[key]))
        self.payout_splits = {int(k): list(v) for k, v in self.payout_splits.items()}
        self.mixed_payouts = {str(k): copy.deepcopy(v) for k, v in self.mixed_payouts.items()}
        self.running = False
        self.deadline = None
        self.current_level = 0
        self.remaining_seconds = int(self.levels[0].get("minutes", 20)) * 60
        self._low_time_warned_level = None
        self._blind_start_sound_played = False
        self.players = []
        self.next_player_id = 1
        self.anonymous_original_entries = 0
        self.anonymous_active_players = 0
        self.anonymous_reentries = 0
        self.anonymous_addons = 0
        self.start_time = None
        self.history = []
        self.active_scenario_id = scenario["id"]
        self.active_scenario_name = scenario["name"]
        self._last_selected_tournament_type = self.tournament_type
        # Synchronize the form variables and dependent control states without running template side-effects.
        if hasattr(self, "settings_vars"):
            values = {
                "name": self.tournament_name,
                "tournament_type": self.tournament_type,
                "buy_in": self.buy_in,
                "reentry_fee": self.reentry_fee,
                "ante_enabled": self.ante_enabled,
                "rebuy_enabled": self.rebuy_enabled,
                "add_on_enabled": self.add_on_enabled,
                "add_on_fee": self.add_on_fee,
                "add_on_chips": self.add_on_chips,
                "house_fee": self.house_fee,
                "charity_mode": "Yes" if self.charity_mode else "No",
                "charity_method": self.charity_method,
                "charity_value": self.charity_value,
                "limit_charity_paid_places": self.limit_charity_paid_places,
                "charity_max_paid_places": self.charity_max_paid_places,
                "tracking_mode": self.tracking_mode,
                "payout_mode": self.payout_mode,
                "payout_rounding_increment": self.payout_rounding_increment,
                "stack": self.starting_stack,
            }
            for key, value in values.items():
                if key in self.settings_vars:
                    self.settings_vars[key].set(value)
            if hasattr(self, "payout_mode_var"):
                self.payout_mode_var.set(self.payout_mode)
            if hasattr(self, "payout_template_var"):
                self.payout_template_var.set(self.payout_template_name)
            if hasattr(self, "name_var"):
                self.name_var.set(self.tournament_name)
            if hasattr(self, "tournament_type_help_var"):
                self.tournament_type_help_var.set(self._tournament_type_help_text(self.tournament_type))
            self._refresh_settings_dependencies()
        self._refresh_all()
        self._refresh_scenario_tree()
        if hasattr(self, "scenario_status_var"):
            self.scenario_status_var.set(f"Loaded '{scenario['name']}'. New tournament is at Level 1 and paused.")
        self.notebook.select(self.clock_tab)
        self._save_data()

    def _scenario_wizard(self, existing=None):
        """Four-step wizard to create/edit a reusable tournament setup."""
        # Keep a copy of the actual active/imported structure before validation
        # triggers a UI refresh. The wizard's "Current blind structure" choice
        # must use this snapshot, not a regenerated/default structure.
        current_levels_snapshot = copy.deepcopy(getattr(self, "levels", []))
        if not self._apply_tournament_settings_from_form():
            return
        editing = existing is not None
        if editing:
            base = self._normalize_scenario_config(existing.get("config", {}))
            if base is None:
                messagebox.showerror("Invalid Scenario", "Could not edit this scenario because its saved configuration is invalid.", parent=self)
                return
            scenario_name = existing.get("name", "")
            scenario_description = existing.get("description", "")
            original_id = existing["id"]
            created_at = existing.get("created_at") or datetime.now().isoformat(timespec="seconds")
        else:
            base = self._scenario_config_snapshot(levels_override=current_levels_snapshot)
            scenario_name = ""
            scenario_description = ""
            original_id = None
            created_at = datetime.now().isoformat(timespec="seconds")

        dlg = tk.Toplevel(self)
        dlg.title("Edit Scenario" if editing else "New Scenario Wizard")
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("900x700")
        dlg.minsize(780, 620)

        heading_var = tk.StringVar(value="Step 1 of 4 — Scenario Basics")
        ttk.Label(dlg, textvariable=heading_var, font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        ttk.Label(dlg, text="A scenario saves reusable rules and the blind structure, not player names or the current clock position.",
                  foreground="#52606d", wraplength=850).pack(anchor="w", padx=16, pady=(0, 8))
        holder = ttk.Frame(dlg)
        holder.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        footer = ttk.Frame(dlg)
        footer.pack(fill="x", padx=14, pady=(0, 14))

        pages = [ttk.Frame(holder, padding=10) for _ in range(4)]
        page_index = {"value": 0}
        draft = copy.deepcopy(base)
        name_var = tk.StringVar(value=scenario_name)
        display_name_var = tk.StringVar(value=base.get("tournament_name", self.tournament_name))
        description_var = tk.StringVar(value=scenario_description)
        type_var = tk.StringVar(value=base.get("tournament_type", self.tournament_type))
        type_before = {"value": type_var.get()}
        source_options = ["Current blind structure", *BUILT_IN_BLIND_TEMPLATE_LABELS.keys(), "Import blind template file…"]
        source_lookup = {
            "Current blind structure": ("current", None),
            "Import blind template file…": ("import", None),
            "Imported blind template": ("imported", None),
        }
        # Keep the built-in options explicit and readable instead of presenting one
        # generic starter structure. Existing saved scenarios retain their own levels.
        for template_label, template_key in BUILT_IN_BLIND_TEMPLATE_LABELS.items():
            source_lookup[template_label] = ("template", template_key)
        previous_source = {"value": "Current blind structure"}
        if editing:
            source_options.insert(0, "Keep scenario's blind structure")
            source_lookup["Keep scenario's blind structure"] = ("keep", None)
            source_var = tk.StringVar(value="Keep scenario's blind structure")
        else:
            source_var = tk.StringVar(value="Current blind structure")
        previous_source["value"] = source_var.get()
        for scenario in self.scenarios:
            if editing and scenario.get("id") == existing.get("id"):
                continue
            label = f"Copy from scenario: {scenario['name']}"
            source_options.append(label)
            source_lookup[label] = ("scenario", scenario["id"])

        vars_ = {
            "tracking_mode": tk.StringVar(value="Entry count only"),
            "starting_stack": tk.StringVar(value=str(base.get("starting_stack", self.starting_stack))),
            "buy_in": tk.StringVar(value=str(base.get("buy_in", self.buy_in))),
            "reentry_fee": tk.StringVar(value=str(base.get("reentry_fee", self.reentry_fee))),
            "house_fee": tk.StringVar(value=str(base.get("house_fee", self.house_fee))),
            "home_game_house_fee": tk.StringVar(value=str(base.get("home_game_house_fee", base.get("house_fee", self.house_fee)))),
            "add_on_fee": tk.StringVar(value=str(base.get("add_on_fee", self.add_on_fee))),
            "add_on_chips": tk.StringVar(value=str(base.get("add_on_chips", self.add_on_chips))),
            "rebuy_enabled": tk.BooleanVar(value=base.get("rebuy_enabled", self.rebuy_enabled)),
            "add_on_enabled": tk.BooleanVar(value=base.get("add_on_enabled", self.add_on_enabled)),
            "ante_enabled": tk.BooleanVar(value=False),
            "charity_mode": tk.BooleanVar(value=base.get("charity_mode", self.charity_mode)),
            "charity_method": tk.StringVar(value=base.get("charity_method", self.charity_method)),
            "charity_value": tk.StringVar(value=str(base.get("charity_value", self.charity_value))),
            "limit_charity_paid_places": tk.BooleanVar(value=base.get("limit_charity_paid_places", self.limit_charity_paid_places)),
            "charity_max_paid_places": tk.StringVar(value=str(base.get("charity_max_paid_places", self.charity_max_paid_places))),
            "payout_mode": tk.StringVar(value=base.get("payout_mode", self.payout_mode)),
            "payout_position_mode": tk.StringVar(value=base.get("payout_position_mode", self.payout_position_mode)),
            "target_paid_places": tk.StringVar(value=str(base.get("target_paid_places", self.target_paid_places))),
            "max_paid_places": tk.StringVar(value=str(base.get("max_paid_places", self.max_paid_places))),
            "payout_rounding_increment": tk.StringVar(value=str(base.get("payout_rounding_increment", self.payout_rounding_increment))),
            "freeroll_paid_places": tk.StringVar(value=str(base.get("freeroll_paid_places", self.freeroll_paid_places))),
            "freeroll_1": tk.StringVar(value=str((base.get("freeroll_payouts", self.freeroll_payouts) + [0, 0, 0])[:3][0])),
            "freeroll_2": tk.StringVar(value=str((base.get("freeroll_payouts", self.freeroll_payouts) + [0, 0, 0])[:3][1])),
            "freeroll_3": tk.StringVar(value=str((base.get("freeroll_payouts", self.freeroll_payouts) + [0, 0, 0])[:3][2])),
        }
        traditional_places_values = sorted(set(range(2, 16)) | {int(k) for k in base.get("payout_splits", {}) if str(k).isdigit()})
        tradition_initial = int(base.get("target_paid_places", 6))
        if tradition_initial not in traditional_places_values:
            tradition_initial = 6
        trad_places_var = tk.StringVar(value=str(tradition_initial))
        payout_template_var = tk.StringVar(value=str(base.get("payout_template_name", DEFAULT_PAYOUT_TEMPLATE_NAME)))
        payout_template_choices = list(BUILT_IN_PAYOUT_TEMPLATE_LABELS)
        if payout_template_var.get() not in payout_template_choices:
            payout_template_choices.append(payout_template_var.get())
        split_map = base.get("payout_splits", {})
        initial_split = split_map.get(str(tradition_initial), split_map.get(tradition_initial, DEFAULT_PAYOUT_SPLITS.get(tradition_initial, self._generated_payout_split(tradition_initial))))
        trad_split_var = tk.StringVar(value=", ".join(str(v) for v in initial_split))
        mixed_places_var = tk.StringVar(value=str(max(2, min(100, int(base.get("target_paid_places", 6))))))

        level_source_combo = None
        level_tree = None
        level_summary_var = tk.StringVar(value="")
        play_duration_var = tk.StringVar(value=str(next((int(x.get("minutes", 20)) for x in draft["levels"] if x.get("kind") != "Break"), 20)))
        break_duration_var = tk.StringVar(value=str(next((int(x.get("minutes", 10)) for x in draft["levels"] if x.get("kind") == "Break"), 10)))

        def try_float(variable, current=0.0):
            try:
                value = float(variable.get())
                return value if math.isfinite(value) else current
            except (TypeError, ValueError):
                return current

        def sync_vars_from_draft():
            type_var.set(draft.get("tournament_type", "Standard Tournament"))
            display_name_var.set(draft.get("tournament_name", "MyPoker Tournament"))
            payout_template_var.set(draft.get("payout_template_name", DEFAULT_PAYOUT_TEMPLATE_NAME))
            for key in ("tracking_mode", "starting_stack", "buy_in", "reentry_fee", "house_fee", "home_game_house_fee",
                        "add_on_fee", "add_on_chips", "rebuy_enabled", "add_on_enabled", "ante_enabled",
                        "charity_mode", "charity_method", "charity_value", "limit_charity_paid_places", "charity_max_paid_places",
                        "payout_mode", "payout_position_mode", "target_paid_places", "max_paid_places", "payout_rounding_increment",
                        "freeroll_paid_places"):
                if key in vars_:
                    value = draft.get(key, vars_[key].get())
                    vars_[key].set(value)
            awards = list(draft.get("freeroll_payouts", [0, 0, 0]))
            while len(awards) < 3:
                awards.append(0)
            for idx, key in enumerate(("freeroll_1", "freeroll_2", "freeroll_3")):
                vars_[key].set(str(awards[idx]))
            try:
                places = int(trad_places_var.get())
            except ValueError:
                places = 6
            splits = draft.get("payout_splits", {})
            split = splits.get(str(places), splits.get(places, DEFAULT_PAYOUT_SPLITS.get(places, self._generated_payout_split(places))))
            trad_split_var.set(", ".join(str(v) for v in split))

        def write_controls_to_draft(strict=True, validate_all=True):
            """Copy form values into a private config dictionary; optionally validate user input."""
            cfg = draft
            try:
                cfg["tournament_name"] = display_name_var.get().strip() or name_var.get().strip() or "MyPoker Tournament"
                cfg["tournament_type"] = type_var.get().strip()
                if cfg["tournament_type"] not in ("Standard Tournament", "Charity Tournament", "Home Game", "Freeroll"):
                    raise ValueError("Choose a valid tournament type.")
                cfg["tracking_mode"] = "Entry count only"
                cfg["starting_stack"] = int(vars_["starting_stack"].get())
                cfg["buy_in"] = float(vars_["buy_in"].get())
                cfg["reentry_fee"] = float(vars_["reentry_fee"].get())
                cfg["home_game_house_fee"] = float(vars_["home_game_house_fee"].get())
                typed_house = float(vars_["house_fee"].get())
                cfg["house_fee"] = typed_house if cfg["tournament_type"] == "Home Game" else 0.0
                cfg["add_on_fee"] = float(vars_["add_on_fee"].get())
                cfg["add_on_chips"] = int(vars_["add_on_chips"].get())
                cfg["rebuy_enabled"] = bool(vars_["rebuy_enabled"].get())
                cfg["add_on_enabled"] = bool(vars_["add_on_enabled"].get())
                cfg["ante_enabled"] = False
                cfg["charity_mode"] = bool(vars_["charity_mode"].get())
                cfg["charity_method"] = vars_["charity_method"].get()
                cfg["charity_value"] = float(vars_["charity_value"].get())
                cfg["limit_charity_paid_places"] = bool(vars_["limit_charity_paid_places"].get())
                cfg["charity_max_paid_places"] = int(vars_["charity_max_paid_places"].get())
                cfg["payout_mode"] = vars_["payout_mode"].get()
                cfg["payout_template_name"] = payout_template_var.get().strip() or DEFAULT_PAYOUT_TEMPLATE_NAME
                cfg["payout_position_mode"] = vars_["payout_position_mode"].get()
                cfg["target_paid_places"] = int(vars_["target_paid_places"].get())
                cfg["max_paid_places"] = int(vars_["max_paid_places"].get())
                cfg["payout_rounding_increment"] = int(vars_["payout_rounding_increment"].get())
                cfg["freeroll_paid_places"] = int(vars_["freeroll_paid_places"].get())
                awards = []
                for key in ("freeroll_1", "freeroll_2", "freeroll_3"):
                    value = float(vars_[key].get().strip() or 0)
                    if not math.isfinite(value) or value < 0 or not value.is_integer():
                        raise ValueError("Freeroll awards must be nonnegative whole-dollar amounts.")
                    awards.append(int(value))
                cfg["freeroll_payouts"] = awards
                # Save the currently displayed traditional split under its selected place count.
                places = int(trad_places_var.get())
                raw_split = [v.strip() for v in trad_split_var.get().replace(";", ",").split(",") if v.strip()]
                split = [float(v) for v in raw_split]
                if len(split) != places or any((not math.isfinite(v) or v <= 0 or v > 100) for v in split):
                    raise ValueError(f"Enter exactly {places} positive percentages for that payout split.")
                if abs(sum(split) - 100.0) > 0.01:
                    raise ValueError("The selected traditional payout percentages must total 100%.")
                cfg.setdefault("payout_splits", {})[str(places)] = split
                if strict and validate_all:
                    if min(cfg["buy_in"], cfg["reentry_fee"], cfg["home_game_house_fee"], cfg["add_on_fee"], cfg["charity_value"]) < 0:
                        raise ValueError("Fees and contribution amounts cannot be negative.")
                    if cfg["add_on_chips"] < 0 or cfg["starting_stack"] < 1:
                        raise ValueError("Add-on chips cannot be negative and starting stack must be positive.")
                    if cfg["tournament_type"] == "Freeroll":
                        cfg["buy_in"] = 0.0
                        cfg["house_fee"] = 0.0
                    if cfg["tournament_type"] != "Home Game":
                        cfg["house_fee"] = 0.0
                    if cfg["house_fee"] > cfg["buy_in"] and cfg["tournament_type"] == "Home Game":
                        raise ValueError("House fee cannot exceed the original buy-in.")
                    if cfg["charity_method"] == "Percentage of each entry" and cfg["charity_value"] > 100:
                        raise ValueError("Benefit Pot percentage must be between 0 and 100.")
                    if cfg["charity_method"] == "Fixed per entry" and cfg["charity_mode"]:
                        paid_fees = []
                        if cfg["buy_in"] > 0:
                            paid_fees.append(cfg["buy_in"])
                        if cfg["rebuy_enabled"] and cfg["reentry_fee"] > 0:
                            paid_fees.append(cfg["reentry_fee"])
                        if paid_fees and cfg["charity_value"] > min(paid_fees):
                            raise ValueError("Fixed Benefit Pot contribution cannot exceed the smallest paid entry fee.")
                    if cfg["payout_mode"] not in ("Traditional Percentages", "Mixed Fixed + Percentage", "Freeroll Fixed Prizes"):
                        raise ValueError("Choose a valid payout mode.")
                    if cfg["payout_position_mode"] not in ("Automatic by entry rules", "Target fixed number", "Automatic with maximum cap"):
                        raise ValueError("Choose a valid paid-position rule.")
                    if not 1 <= cfg["target_paid_places"] <= 100 or not 1 <= cfg["max_paid_places"] <= 100:
                        raise ValueError("Paid-place target and cap must be between 1 and 100.")
                    if cfg["payout_rounding_increment"] not in (1, 5, 10, 20, 25, 50, 100):
                        raise ValueError("Choose a supported payout rounding increment.")
                    if not 1 <= cfg["freeroll_paid_places"] <= 3:
                        raise ValueError("Freeroll must pay 1, 2, or 3 places.")
                    if any(awards[i] <= 0 for i in range(cfg["freeroll_paid_places"])) and cfg["payout_mode"] == "Freeroll Fixed Prizes":
                        raise ValueError("Enter a positive fixed-dollar award for every paid freeroll position.")
                    if cfg["payout_mode"] == "Mixed Fixed + Percentage" and not cfg.get("mixed_payouts"):
                        raise ValueError("Configure at least one mixed payout structure before saving this scenario.")
                    if not str(name_var.get()).strip():
                        raise ValueError("Enter a scenario name.")
                    if not cfg.get("levels") or not any(lvl.get("kind") != "Break" for lvl in cfg["levels"]):
                        raise ValueError("The blind structure must contain at least one play level.")
                    for lvl in cfg["levels"]:
                        if int(lvl.get("minutes", 0)) < 1 or int(lvl.get("minutes", 0)) > 240:
                            raise ValueError(f"'{lvl.get('name', 'Level')}' duration must be between 1 and 240 minutes.")
                        if lvl.get("kind") != "Break" and (int(lvl.get("bb", 0)) <= 0 or min(int(lvl.get("sb", 0)), int(lvl.get("bb", 0))) < 0):
                            raise ValueError(f"'{lvl.get('name', 'Level')}' has an invalid blind value.")
                return True
            except Exception as exc:
                if strict:
                    messagebox.showerror("Check Scenario Settings", str(exc), parent=dlg)
                return False

        dependency_callbacks = {}
        def set_entry_dependencies(*_):
            # This closure is rebound to wizard_widgets_set_entry_dependencies after all wizard
            # controls have been created. At build time, only refresh payout mode-specific groups.
            refresh_func = dependency_callbacks.get("refresh")
            if refresh_func:
                refresh_func()

        # Step 1: scenario identity and type.
        page = pages[0]
        ttk.Label(page, text="Name this reusable tournament setup, then choose a starting type.",
                  wraplength=820, justify="left").pack(anchor="w", pady=(0, 12))
        page1_grid = ttk.Frame(page)
        page1_grid.pack(fill="x", anchor="n")
        for row, (label, var, width) in enumerate((
            ("Scenario name", name_var, 44), ("Tournament display title", display_name_var, 44), ("Description (optional)", description_var, 60)
        )):
            ttk.Label(page1_grid, text=label).grid(row=row, column=0, sticky="w", padx=(2, 14), pady=7)
            ttk.Entry(page1_grid, textvariable=var, width=width).grid(row=row, column=1, sticky="w", padx=2, pady=7)
        ttk.Label(page1_grid, text="Tournament type template").grid(row=3, column=0, sticky="w", padx=(2, 14), pady=7)
        type_combo = ttk.Combobox(page1_grid, textvariable=type_var,
                                  values=["Standard Tournament", "Charity Tournament", "Home Game", "Freeroll"],
                                  state="readonly", width=41)
        type_combo.grid(row=3, column=1, sticky="w", padx=2, pady=7)
        ttk.Label(page, text="Charity and Freeroll can overlap. Choose a type to apply its starting defaults, then configure the individual options on the next steps.",
                  foreground="#52606d", wraplength=820, justify="left").pack(anchor="w", pady=(12, 0))
        ttk.Label(page, text="Starting blind structure").pack(anchor="w", pady=(18, 3))
        source_combo = ttk.Combobox(page, textvariable=source_var, values=source_options, state="readonly", width=54)
        source_combo.pack(anchor="w")
        ttk.Label(page, text="Choose the current structure, one of four built-in templates, or import your own. You can edit every level and break before saving.",
                  foreground="#52606d", wraplength=820).pack(anchor="w", pady=(4, 0))

        # Step 2: fees and clock behavior.
        page = pages[1]
        ttk.Label(page, text="Configure how entries, rebuys, add-ons, and the clock should work.",
                  wraplength=820, justify="left").pack(anchor="w", pady=(0, 10))
        page2_grid = ttk.Frame(page)
        page2_grid.pack(fill="x", anchor="n")
        wizard_widgets = {}
        wizard_field_labels = {}
        field_specs = [
            ("Starting chip stack", "starting_stack", "entry", None),
            ("Original buy-in ($)", "buy_in", "entry", None),
            ("Rebuy / re-entry fee ($)", "reentry_fee", "entry", None),
            ("Home Game house fee per original entry ($)", "home_game_house_fee", "entry", None),
            ("Add-on fee ($)", "add_on_fee", "entry", None),
            ("Add-on chips per add-on", "add_on_chips", "entry", None),
        ]
        for row, (label, key, kind, options) in enumerate(field_specs):
            label_widget = ttk.Label(page2_grid, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=(2, 14), pady=5)
            wizard_field_labels[key] = label_widget
            if kind == "combo":
                widget = ttk.Combobox(page2_grid, textvariable=vars_[key], values=options, state="readonly", width=33)
            else:
                widget = ttk.Entry(page2_grid, textvariable=vars_[key], width=36)
            widget.grid(row=row, column=1, sticky="w", padx=2, pady=5)
            wizard_widgets[key] = widget
        checks = ttk.Frame(page)
        checks.pack(fill="x", anchor="n", pady=(12, 0))
        for key, label in (
            ("rebuy_enabled", "Enable rebuys / paid re-entries"),
            ("add_on_enabled", "Enable add-ons"),
        ):
            ttk.Checkbutton(checks, text=label, variable=vars_[key], command=set_entry_dependencies).pack(anchor="w", pady=3)
        wizard_widgets.update({
            "charity_method": None, "charity_value": None, "charity_max_paid_places": None,
        })

        # Step 3: charity and payout settings.
        page = pages[2]
        ttk.Label(page, text="Charity is optional and independent from payout method. Payout rules and splits are saved in the scenario.",
                  wraplength=820, justify="left").pack(anchor="w", pady=(0, 8))
        page3_canvas_wrap = ttk.Frame(page)
        page3_canvas_wrap.pack(fill="both", expand=True)
        page3_canvas = tk.Canvas(page3_canvas_wrap, highlightthickness=0, borderwidth=0)
        page3_scroll = ttk.Scrollbar(page3_canvas_wrap, orient="vertical", command=page3_canvas.yview)
        page3_inner = ttk.Frame(page3_canvas)
        page3_inner.bind("<Configure>", lambda _e: page3_canvas.configure(scrollregion=page3_canvas.bbox("all")))
        page3_window = page3_canvas.create_window((0, 0), window=page3_inner, anchor="nw")
        page3_canvas.configure(yscrollcommand=page3_scroll.set)
        page3_canvas.bind("<Configure>", lambda e: page3_canvas.itemconfigure(page3_window, width=e.width))
        page3_canvas.pack(side="left", fill="both", expand=True)
        page3_scroll.pack(side="right", fill="y")

        charity_box = ttk.LabelFrame(page3_inner, text="Charity / Benefit Pot", padding=8)
        charity_box.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(charity_box, text="Enable Benefit Pot", variable=vars_["charity_mode"], command=set_entry_dependencies).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
        charity_widgets = {}
        charity_field_labels = {}
        for row, (label, key, combo_vals) in enumerate((
            ("Contribution calculation", "charity_method", ["Fixed per entry", "Percentage of each entry"]),
            ("Amount ($) or percentage (%)", "charity_value", None),
            ("Maximum paid places", "charity_max_paid_places", None),
        ), start=1):
            label_widget = ttk.Label(charity_box, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=(2, 12), pady=4)
            charity_field_labels[key] = label_widget
            if combo_vals:
                widget = ttk.Combobox(charity_box, textvariable=vars_[key], values=combo_vals, state="readonly", width=34)
            else:
                widget = ttk.Entry(charity_box, textvariable=vars_[key], width=37)
            widget.grid(row=row, column=1, sticky="w", padx=2, pady=4)
            charity_widgets[key] = widget
        charity_cap_check = ttk.Checkbutton(
            charity_box, text="Enforce charity maximum paid places",
            variable=vars_["limit_charity_paid_places"], command=set_entry_dependencies
        )
        charity_cap_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=(5, 2))
        wizard_widgets.update(charity_widgets)

        payout_box = ttk.LabelFrame(page3_inner, text="Payout Rules", padding=8)
        payout_box.pack(fill="x", pady=(0, 8))
        payout_widgets = {}
        row = 0
        for label, key, options in (
            ("Payout mode", "payout_mode", ["Traditional Percentages", "Mixed Fixed + Percentage", "Freeroll Fixed Prizes"]),
            ("Paid-position rule", "payout_position_mode", ["Automatic by entry rules", "Target fixed number", "Automatic with maximum cap"]),
            ("Target paid places", "target_paid_places", None),
            ("Maximum paid places", "max_paid_places", None),
            ("Payout rounding increment ($)", "payout_rounding_increment", ["1", "5", "10", "20", "25", "50", "100"]),
        ):
            ttk.Label(payout_box, text=label).grid(row=row, column=0, sticky="w", padx=(2, 12), pady=4)
            if options:
                widget = ttk.Combobox(payout_box, textvariable=vars_[key], values=options, state="readonly", width=34)
            else:
                widget = ttk.Entry(payout_box, textvariable=vars_[key], width=37)
            widget.grid(row=row, column=1, sticky="w", padx=2, pady=4)
            payout_widgets[key] = widget
            row += 1

        detail_holder = ttk.Frame(payout_box)
        detail_holder.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 2))
        traditional_frame = ttk.LabelFrame(detail_holder, text="Traditional Percentage Split", padding=6)
        ttk.Label(traditional_frame, text="Payout chart profile").grid(row=0, column=0, sticky="w", padx=2, pady=3)
        payout_template_combo = ttk.Combobox(
            traditional_frame, textvariable=payout_template_var, values=payout_template_choices,
            state="readonly", width=28
        )
        payout_template_combo.grid(row=0, column=1, sticky="w", padx=3, pady=3)
        payout_template_controls = ttk.Frame(traditional_frame)
        payout_template_controls.grid(row=0, column=2, sticky="w", padx=3, pady=3)
        ttk.Button(payout_template_controls, text="Apply Profile", command=lambda: apply_scenario_payout_template()).pack(side="left", padx=(0, 4))
        ttk.Button(payout_template_controls, text="Import Excel…", command=lambda: import_scenario_payout_template()).pack(side="left")
        ttk.Label(traditional_frame, text="Place count").grid(row=1, column=0, sticky="w", padx=2, pady=3)
        trad_places_combo = ttk.Combobox(traditional_frame, textvariable=trad_places_var,
                                          values=[str(v) for v in traditional_places_values], state="readonly", width=8)
        trad_places_combo.grid(row=1, column=1, sticky="w", padx=3, pady=3)
        ttk.Label(traditional_frame, text="Percentages (comma separated; total 100%)").grid(row=2, column=0, sticky="w", padx=2, pady=3)
        ttk.Entry(traditional_frame, textvariable=trad_split_var, width=58).grid(row=2, column=1, sticky="w", padx=3, pady=3)

        mixed_frame = ttk.LabelFrame(detail_holder, text="Mixed Fixed + Percentage", padding=6)
        ttk.Label(mixed_frame, text="Configure a per-place-count mixed structure. Existing saved mixed structures are copied into the scenario.",
                  wraplength=720, justify="left").pack(anchor="w", pady=(0, 5))
        ttk.Label(mixed_frame, text="Paid places to configure").pack(side="left")
        ttk.Combobox(mixed_frame, textvariable=mixed_places_var, values=[str(v) for v in range(2, 101)], state="readonly", width=8).pack(side="left", padx=6)
        mixed_status_var = tk.StringVar(value="")
        ttk.Button(mixed_frame, text="Configure Mixed Structure…", command=lambda: open_scenario_mixed_editor()).pack(side="left", padx=6)
        ttk.Label(mixed_frame, textvariable=mixed_status_var, foreground="#52606d").pack(anchor="w", pady=(6, 0))

        freeroll_frame = ttk.LabelFrame(detail_holder, text="Freeroll Fixed Prizes", padding=6)
        ttk.Label(freeroll_frame, text="Number of paid places").grid(row=0, column=0, sticky="w", padx=2, pady=3)
        freeroll_places_combo = ttk.Combobox(freeroll_frame, textvariable=vars_["freeroll_paid_places"], values=["1", "2", "3"], state="readonly", width=8)
        freeroll_places_combo.grid(row=0, column=1, sticky="w", padx=3, pady=3)
        freeroll_entries = []
        for idx, (label, key) in enumerate((("1st place ($)", "freeroll_1"), ("2nd place ($)", "freeroll_2"), ("3rd place ($)", "freeroll_3")), start=1):
            ttk.Label(freeroll_frame, text=label).grid(row=idx, column=0, sticky="w", padx=2, pady=3)
            ent = ttk.Entry(freeroll_frame, textvariable=vars_[key], width=14)
            ent.grid(row=idx, column=1, sticky="w", padx=3, pady=3)
            freeroll_entries.append(ent)

        def update_freeroll_fields(*_):
            try:
                places = int(vars_["freeroll_paid_places"].get())
            except ValueError:
                places = 1
            for idx, entry in enumerate(freeroll_entries, start=1):
                entry.configure(state="normal" if idx <= places else "disabled")

        freeroll_places_combo.bind("<<ComboboxSelected>>", update_freeroll_fields)

        def payout_details_refresh(*_):
            for frame in (traditional_frame, mixed_frame, freeroll_frame):
                frame.pack_forget()
            mode = vars_["payout_mode"].get()
            if mode == "Traditional Percentages":
                traditional_frame.pack(fill="x", expand=True)
            elif mode == "Mixed Fixed + Percentage":
                mixed_frame.pack(fill="x", expand=True)
            else:
                freeroll_frame.pack(fill="x", expand=True)
            try:
                places = int(vars_["freeroll_paid_places"].get())
            except ValueError:
                places = 1
            for idx, entry in enumerate(freeroll_entries, start=1):
                entry.configure(state="normal" if mode == "Freeroll Fixed Prizes" and idx <= places else "disabled")
            mixed_places = mixed_places_var.get()
            has_mixed = mixed_places in draft.get("mixed_payouts", {}) or mixed_places.isdigit() and int(mixed_places) in draft.get("mixed_payouts", {})
            mixed_status_var.set(("Configured structures: " + ", ".join(sorted(str(k) for k in draft.get("mixed_payouts", {}).keys()))) if has_mixed else "Configure the place count before launching in Mixed mode.")
            position_mode = vars_["payout_position_mode"].get()
            payout_widgets["target_paid_places"].configure(state="normal" if position_mode == "Target fixed number" else "disabled")
            payout_widgets["max_paid_places"].configure(state="normal" if position_mode == "Automatic with maximum cap" else "disabled")

        dependency_callbacks["refresh"] = payout_details_refresh
        vars_["payout_mode"].trace_add("write", payout_details_refresh)
        vars_["payout_position_mode"].trace_add("write", payout_details_refresh)
        vars_["freeroll_paid_places"].trace_add("write", payout_details_refresh)
        trad_places_combo.bind("<<ComboboxSelected>>", lambda _e: load_traditional_split())

        def load_traditional_split():
            try:
                places = int(trad_places_var.get())
            except ValueError:
                places = 6
            splits = draft.get("payout_splits", {})
            values = splits.get(str(places), splits.get(places, DEFAULT_PAYOUT_SPLITS.get(places, self._generated_payout_split(places))))
            trad_split_var.set(", ".join(str(v) for v in values))

        def apply_scenario_payout_template():
            label = payout_template_var.get().strip()
            template = BUILT_IN_PAYOUT_TEMPLATES.get(label)
            if template is None:
                if label == draft.get("payout_template_name") and draft.get("payout_splits"):
                    messagebox.showinfo("Payout Profile", "This scenario's currently loaded chart configuration is already active. Import a worksheet to replace it with a different custom profile.", parent=dlg)
                    return
                messagebox.showwarning("Payout Profile", "Choose a built-in profile or import a custom Excel worksheet.", parent=dlg)
                return
            draft["payout_splits"] = {str(k): list(v) for k, v in template.items()}
            draft["payout_template_name"] = label
            available = sorted(set(range(2, 16)) | {int(k) for k in draft["payout_splits"] if str(k).isdigit()})
            trad_places_combo.configure(values=[str(value) for value in available])
            if int(trad_places_var.get()) not in available:
                trad_places_var.set(str(available[-1]))
            load_traditional_split()
            messagebox.showinfo("Payout Profile Applied", f"Applied '{label}' with percentage charts for {len(template)} paid-place counts. Entry thresholds still determine how many places are paid.", parent=dlg)

        def import_scenario_payout_template():
            path, rows = self._read_import_rows("Import Payout Chart Template")
            if not path:
                return
            try:
                imported = parse_payout_template_rows(rows)
            except Exception as exc:
                messagebox.showerror("Invalid Payout Template", str(exc), parent=dlg)
                return
            draft["payout_splits"] = {str(k): list(v) for k, v in imported.items()}
            label = f"Imported: {os.path.basename(path)}"
            draft["payout_template_name"] = label
            if label not in payout_template_choices:
                payout_template_choices.append(label)
                payout_template_combo.configure(values=payout_template_choices)
            payout_template_var.set(label)
            available = sorted(set(range(2, 16)) | set(imported.keys()))
            trad_places_combo.configure(values=[str(value) for value in available])
            if int(trad_places_var.get()) not in available:
                trad_places_var.set(str(next(iter(imported))))
            load_traditional_split()
            messagebox.showinfo("Payout Template Imported", f"Imported {len(imported)} payout chart(s) from {os.path.basename(path)}. Each included chart was validated to total 100%.", parent=dlg)

        def open_scenario_mixed_editor():
            try:
                places = int(mixed_places_var.get())
            except ValueError:
                places = 6
            new_mixed = self._scenario_mixed_payouts_dialog(dlg, draft.get("mixed_payouts", {}),
                                                              draft.get("payout_splits", {}), places)
            if new_mixed is not None:
                draft["mixed_payouts"] = new_mixed
                payout_details_refresh()

        wizard_widgets.update(charity_widgets)

        # Step 4: blind schedule and break editor.
        page = pages[3]
        ttk.Label(page, text="Each scenario gets its own blind schedule. Select a source, adjust durations in bulk, or edit individual levels.",
                  wraplength=820, justify="left").pack(anchor="w", pady=(0, 8))
        source_line = ttk.Frame(page)
        source_line.pack(fill="x", pady=(0, 7))
        ttk.Label(source_line, text="Blind source:").pack(side="left")
        source_combo_page4 = ttk.Combobox(source_line, textvariable=source_var, values=source_options, state="readonly", width=45)
        source_combo_page4.pack(side="left", padx=8)
        ttk.Button(source_line, text="Import Blind Template…", command=lambda: import_scenario_blind_template()).pack(side="left", padx=(4, 0))
        bulk_line = ttk.LabelFrame(page, text="Set Durations", padding=6)
        bulk_line.pack(fill="x", pady=(0, 7))
        wizard_play_line = ttk.Frame(bulk_line)
        wizard_play_line.pack(fill="x", pady=(0, 3))
        ttk.Label(wizard_play_line, text="Play levels (min)").pack(side="left", padx=(0, 3))
        ttk.Entry(wizard_play_line, textvariable=play_duration_var, width=6).pack(side="left", padx=(0, 5))
        ttk.Button(wizard_play_line, text="Apply to All Play Levels", command=lambda: apply_scenario_durations("Play", selected_only=False)).pack(side="left", padx=(0, 4))
        ttk.Button(wizard_play_line, text="Apply to Selected Play Levels", command=lambda: apply_scenario_durations("Play", selected_only=True)).pack(side="left")
        wizard_break_line = ttk.Frame(bulk_line)
        wizard_break_line.pack(fill="x")
        ttk.Label(wizard_break_line, text="Breaks (min)").pack(side="left", padx=(0, 3))
        ttk.Entry(wizard_break_line, textvariable=break_duration_var, width=6).pack(side="left", padx=(0, 5))
        ttk.Button(wizard_break_line, text="Apply to All Breaks", command=lambda: apply_scenario_durations("Break", selected_only=False)).pack(side="left", padx=(0, 4))
        ttk.Button(wizard_break_line, text="Apply to Selected Breaks", command=lambda: apply_scenario_durations("Break", selected_only=True)).pack(side="left")
        level_toolbar = ttk.Frame(page)
        level_toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(level_toolbar, text="Add Play Level", command=lambda: add_scenario_level("Play")).pack(side="left", padx=(0, 4))
        ttk.Button(level_toolbar, text="Add Break", command=lambda: add_scenario_level("Break")).pack(side="left", padx=4)
        ttk.Button(level_toolbar, text="Edit Selected", command=lambda: edit_scenario_level()).pack(side="left", padx=4)
        ttk.Button(level_toolbar, text="Remove Selected", command=lambda: remove_scenario_level()).pack(side="left", padx=4)
        ttk.Button(level_toolbar, text="Move Up", command=lambda: move_scenario_level(-1)).pack(side="left", padx=4)
        ttk.Button(level_toolbar, text="Move Down", command=lambda: move_scenario_level(1)).pack(side="left", padx=4)
        lcols = ("num", "name", "kind", "minutes", "sb", "bb", "pause")
        level_tree = ttk.Treeview(page, columns=lcols, show="headings", height=10, selectmode="extended")
        for col, heading, width in (("num", "#", 40), ("name", "Level / Break", 195), ("kind", "Type", 70),
                                    ("minutes", "Minutes", 70), ("sb", "Small Blind", 85), ("bb", "Big Blind", 85),
                                    ("pause", "Pause?", 65)):
            level_tree.heading(col, text=heading)
            level_tree.column(col, width=width, anchor="center" if col != "name" else "w")
        level_tree.pack(fill="both", expand=True)
        ttk.Label(page, text="Shift-click selects a range; Ctrl-click selects individual rows. Click a break's Pause? cell to toggle pausing when that break ends.",
                  foreground="#52606d", wraplength=800).pack(anchor="w", pady=(6, 0))

        def refresh_scenario_levels():
            try:
                previous_selection = [int(iid) for iid in level_tree.selection()]
            except (TypeError, ValueError, tk.TclError):
                previous_selection = []
            for item in level_tree.get_children():
                level_tree.delete(item)
            for idx, level in enumerate(draft.get("levels", [])):
                is_break = level.get("kind") == "Break"
                pause_cell = ("☑" if bool(level.get("pause_after", False)) else "☐") if is_break else "—"
                level_tree.insert("", "end", iid=str(idx), values=(idx + 1, level.get("name", ""), level.get("kind", "Play"),
                    level.get("minutes", 20), "—" if is_break else f"{int(level.get('sb',0)):,}",
                    "—" if is_break else f"{int(level.get('bb',0)):,}", pause_cell))
            play_count = sum(1 for item in draft.get("levels", []) if item.get("kind") != "Break")
            break_count = len(draft.get("levels", [])) - play_count
            valid_selection = [str(i) for i in previous_selection if 0 <= i < len(draft.get("levels", []))]
            if valid_selection:
                level_tree.selection_set(*valid_selection)
            level_summary_var.set(f"{len(draft.get('levels', []))} total rows: {play_count} play levels and {break_count} breaks. Display and sound preferences are saved with this scenario; monitor/window size remains global.")

        def on_scenario_pause_cell_click(event):
            if level_tree.identify_region(event.x, event.y) != "cell" or level_tree.identify_column(event.x) != "#7":
                return None
            iid = level_tree.identify_row(event.y)
            if not iid:
                return None
            index = int(iid)
            if not 0 <= index < len(draft.get("levels", [])) or draft["levels"][index].get("kind") != "Break":
                return "break"
            row = draft["levels"][index]
            current_pause = bool(row.get("pause_after", False))
            row["pause_after"] = not current_pause
            refresh_scenario_levels()
            level_tree.selection_set(str(index))
            return "break"

        level_tree.bind("<Button-1>", on_scenario_pause_cell_click, add="+")

        def import_scenario_blind_template():
            path, rows = self._read_import_rows("Import Blind Template for Scenario")
            if not path:
                source_var.set(previous_source["value"])
                return
            try:
                imported = self._parse_level_rows(rows)
                if not imported or not any(item.get("kind") != "Break" for item in imported):
                    raise ValueError("The template must contain at least one play level.")
            except Exception as exc:
                messagebox.showerror("Invalid Blind Template", str(exc), parent=dlg)
                source_var.set(previous_source["value"])
                return
            draft["levels"] = copy.deepcopy(imported)
            imported_label = "Imported blind template"
            if imported_label not in source_options:
                source_options.append(imported_label)
            source_lookup[imported_label] = ("imported", None)
            for combo in (source_combo, source_combo_page4):
                combo.configure(values=source_options)
            source_var.set(imported_label)
            previous_source["value"] = imported_label
            refresh_scenario_levels()
            messagebox.showinfo(
                "Blind Template Imported",
                f"Imported {len(imported)} level/break row(s) from {os.path.basename(path)}.\n\n"
                "Review the structure below, then finish saving the scenario.",
                parent=dlg,
            )

        def source_changed(_event=None):
            choice = source_var.get()
            kind, sid = source_lookup.get(choice, ("keep", None))
            if kind == "import":
                import_scenario_blind_template()
                return
            if kind == "current":
                draft["levels"] = copy.deepcopy(current_levels_snapshot)
            elif kind == "template":
                template_rows = BUILT_IN_BLIND_TEMPLATES.get(sid, DEFAULT_LEVELS)
                draft["levels"] = copy.deepcopy(template_rows)
                recommended_stack = BLIND_TEMPLATE_STARTING_STACKS.get(sid)
                if recommended_stack:
                    vars_["starting_stack"].set(str(recommended_stack))
                    draft["starting_stack"] = int(recommended_stack)
            elif kind == "scenario":
                found = next((item for item in self.scenarios if item.get("id") == sid), None)
                if found:
                    draft["levels"] = copy.deepcopy(found["config"].get("levels", DEFAULT_LEVELS))
            elif kind in ("keep", "imported"):
                pass
            previous_source["value"] = choice
            refresh_scenario_levels()
        source_combo.bind("<<ComboboxSelected>>", source_changed)
        source_combo_page4.bind("<<ComboboxSelected>>", source_changed)

        def selected_scenario_level_index():
            selected = level_tree.selection()
            return int(selected[0]) if selected else None

        def add_scenario_level(kind):
            vals = self._scenario_level_dialog(dlg, kind=kind, default_name=f"{kind} {sum(1 for row in draft['levels'] if row.get('kind') == kind) + 1}")
            if vals:
                draft["levels"].append(vals)
                refresh_scenario_levels()
                level_tree.selection_set(str(len(draft["levels"]) - 1))

        def edit_scenario_level():
            index = selected_scenario_level_index()
            if index is None:
                return
            vals = self._scenario_level_dialog(dlg, initial=draft["levels"][index], kind=draft["levels"][index].get("kind", "Play"))
            if vals:
                draft["levels"][index] = vals
                refresh_scenario_levels()
                level_tree.selection_set(str(index))

        def remove_scenario_level():
            index = selected_scenario_level_index()
            if index is None:
                return
            if len(draft["levels"]) <= 1:
                messagebox.showwarning("Cannot remove level", "At least one scheduled row must remain.", parent=dlg)
                return
            del draft["levels"][index]
            refresh_scenario_levels()
            if draft["levels"]:
                level_tree.selection_set(str(min(index, len(draft["levels"]) - 1)))

        def move_scenario_level(direction):
            index = selected_scenario_level_index()
            if index is None:
                return
            target = index + direction
            if not 0 <= target < len(draft["levels"]):
                return
            draft["levels"][index], draft["levels"][target] = draft["levels"][target], draft["levels"][index]
            refresh_scenario_levels()
            level_tree.selection_set(str(target))

        def apply_scenario_durations(kind, selected_only=False):
            variable = play_duration_var if kind == "Play" else break_duration_var
            try:
                minutes = int(variable.get())
                if not 1 <= minutes <= 240:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid duration", "Duration must be between 1 and 240 minutes.", parent=dlg)
                return
            selected_indexes = {int(iid) for iid in level_tree.selection() if iid.isdigit()} if selected_only else set(range(len(draft["levels"])))
            changed = 0
            for index, level in enumerate(draft["levels"]):
                if index not in selected_indexes:
                    continue
                is_break = level.get("kind") == "Break"
                if (kind == "Break" and is_break) or (kind == "Play" and not is_break):
                    level["minutes"] = minutes
                    changed += 1
            if selected_only and changed == 0:
                messagebox.showinfo("Select matching rows", f"Select one or more {kind.lower()} rows first.", parent=dlg)
            elif changed:
                refresh_scenario_levels()

        def on_type_changed(_event=None):
            selected = type_var.get()
            if selected == type_before["value"]:
                return
            old_type = type_before["value"]
            # Capture every pending wizard choice before applying the template. The type combobox
            # already contains the new value, so restore the prior type in the draft before using
            # the template transition logic. This also preserves the display title when the type changes.
            write_controls_to_draft(strict=False, validate_all=False)
            draft["tournament_type"] = old_type
            # Preserve all pending wizard edits before applying the type template.
            for key, var_key in (("buy_in", "buy_in"), ("reentry_fee", "reentry_fee"), ("home_game_house_fee", "home_game_house_fee"),
                                 ("house_fee", "house_fee"), ("add_on_fee", "add_on_fee"), ("add_on_chips", "add_on_chips"),
                                 ("charity_value", "charity_value"), ("payout_mode", "payout_mode")):
                if key in ("add_on_chips",):
                    try: draft[key] = max(0, int(vars_[var_key].get()))
                    except ValueError: pass
                elif key in ("buy_in", "reentry_fee", "home_game_house_fee", "house_fee", "add_on_fee", "charity_value"):
                    try: draft[key] = max(0, float(vars_[var_key].get()))
                    except ValueError: pass
                else:
                    draft[key] = vars_[var_key].get()
            old = type_before["value"]
            self._scenario_apply_type_template(draft, selected)
            sync_vars_from_draft()
            type_before["value"] = selected
            set_entry_dependencies()

        type_combo.bind("<<ComboboxSelected>>", on_type_changed)
        refresh_scenario_levels()

        def validate_entry_step():
            try:
                values = [float(vars_[key].get()) for key in ("buy_in", "reentry_fee", "home_game_house_fee", "add_on_fee")]
                chips = int(vars_["add_on_chips"].get())
                stack = int(vars_["starting_stack"].get())
                if any((not math.isfinite(v) or v < 0) for v in values) or chips < 0 or stack < 1:
                    raise ValueError("Fees and add-on chips must be nonnegative, and starting stack must be positive.")
                buy, reentry, home_fee, addon = values
                if type_var.get() == "Freeroll":
                    buy = 0.0
                    vars_["buy_in"].set("0")
                if type_var.get() == "Home Game" and home_fee > buy:
                    raise ValueError("The Home Game house fee cannot exceed the original buy-in.")
                draft["buy_in"] = buy
                draft["reentry_fee"] = reentry
                draft["home_game_house_fee"] = home_fee
                draft["house_fee"] = home_fee if type_var.get() == "Home Game" else 0.0
                draft["add_on_fee"] = addon
                draft["add_on_chips"] = chips
                draft["starting_stack"] = stack
                return True
            except Exception as exc:
                messagebox.showerror("Check Entry Settings", str(exc), parent=dlg)
                return False

        def next_step():
            idx = page_index["value"]
            if idx == 0:
                if not name_var.get().strip():
                    messagebox.showerror("Scenario Name Required", "Enter a name for this scenario.", parent=dlg)
                    return
                if any(item["id"] != original_id and item["name"].casefold() == name_var.get().strip().casefold() for item in self.scenarios):
                    messagebox.showerror("Duplicate Scenario Name", "A scenario with this name already exists.", parent=dlg)
                    return
            if idx == 1:
                if not write_controls_to_draft(strict=True, validate_all=False):
                    messagebox.showerror("Check Entry Settings", "Review the entered values before continuing.", parent=dlg)
                    return
                if not validate_entry_step():
                    return
                # Update the visible tournament title and start step 3 with the selected type's settings.
                if type_var.get() == "Freeroll":
                    vars_["buy_in"].set("0")
                    vars_["house_fee"].set("0")
                set_entry_dependencies()
            if idx == 2:
                if not write_controls_to_draft(strict=True):
                    return
                if vars_["payout_mode"].get() == "Mixed Fixed + Percentage" and not draft.get("mixed_payouts"):
                    messagebox.showerror("Mixed Payout Structure Required", "Configure at least one mixed payout structure before saving this scenario.", parent=dlg)
                    return
            if idx >= 3:
                return
            pages[idx].pack_forget()
            page_index["value"] = idx + 1
            pages[idx + 1].pack(fill="both", expand=True)
            headings = ["Step 1 of 4 — Scenario Basics", "Step 2 of 4 — Entries & Rules",
                        "Step 3 of 4 — Charity & Payouts", "Step 4 of 4 — Blind Structure & Review"]
            heading_var.set(headings[idx + 1])
            back_button.configure(state="normal")
            next_button.configure(state="normal" if idx + 1 < 3 else "disabled")
            finish_button.configure(state="normal" if idx + 1 == 3 else "disabled")
            if idx + 1 == 3:
                refresh_scenario_levels()

        def previous_step():
            idx = page_index["value"]
            if idx <= 0:
                return
            if idx == 2:
                write_controls_to_draft(strict=False)
            pages[idx].pack_forget()
            page_index["value"] = idx - 1
            pages[idx - 1].pack(fill="both", expand=True)
            headings = ["Step 1 of 4 — Scenario Basics", "Step 2 of 4 — Entries & Rules",
                        "Step 3 of 4 — Charity & Payouts", "Step 4 of 4 — Blind Structure & Review"]
            heading_var.set(headings[idx - 1])
            back_button.configure(state="normal" if idx - 1 > 0 else "disabled")
            next_button.configure(state="normal")
            finish_button.configure(state="disabled")

        def finish_wizard():
            if not write_controls_to_draft(strict=True):
                return
            cfg = self._normalize_scenario_config(draft)
            if cfg is None:
                messagebox.showerror("Invalid Scenario", "The scenario settings or blind structure are invalid. Review the settings and try again.", parent=dlg)
                return
            scenario_name_final = name_var.get().strip()
            if not scenario_name_final:
                messagebox.showerror("Scenario Name Required", "Enter a scenario name.", parent=dlg)
                return
            now = datetime.now().isoformat(timespec="seconds")
            record = {
                "id": original_id or uuid.uuid4().hex,
                "name": scenario_name_final,
                "description": description_var.get().strip(),
                "created_at": created_at,
                "updated_at": now,
                "config": cfg,
            }
            old_scenarios = copy.deepcopy(self.scenarios)
            if editing:
                self.scenarios = [record if item["id"] == original_id else item for item in self.scenarios]
            else:
                self.scenarios.append(record)
            if not self._save_scenario_library():
                self.scenarios = old_scenarios
                return
            dlg.destroy()
            self._refresh_scenario_tree()
            self.scenario_tree.selection_set(record["id"])
            self.scenario_tree.focus(record["id"])
            self._scenario_selection_changed()
            messagebox.showinfo("Scenario Saved", f"'{record['name']}' has been saved to the Scenario Manager. Select it and click Launch New Tournament when you're ready.", parent=self)

        back_button = ttk.Button(footer, text="‹ Back", command=previous_step, state="disabled")
        back_button.pack(side="left")
        ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side="right", padx=(8, 0))
        finish_button = ttk.Button(footer, text="Save Scenario", command=finish_wizard, state="disabled")
        finish_button.pack(side="right", padx=(8, 0))
        next_button = ttk.Button(footer, text="Next ›", command=next_step)
        next_button.pack(side="right", padx=(8, 0))
        pages[0].pack(fill="both", expand=True)

        def wizard_widgets_set_entry_dependencies(*_args):
            """Show only controls that apply to the choices made in the wizard."""
            field_rules = {
                "buy_in": type_var.get() != "Freeroll",
                "reentry_fee": bool(vars_["rebuy_enabled"].get()),
                "home_game_house_fee": type_var.get() == "Home Game",
                "add_on_fee": bool(vars_["add_on_enabled"].get()),
                "add_on_chips": bool(vars_["add_on_enabled"].get()),
            }
            for key, visible in field_rules.items():
                widget = wizard_widgets.get(key)
                label = wizard_field_labels.get(key)
                for control in (label, widget):
                    if control is None:
                        continue
                    if visible and not control.winfo_manager():
                        control.grid()
                    elif not visible and control.winfo_manager():
                        control.grid_remove()
                if widget is not None:
                    widget.configure(state="normal" if visible else "disabled")

            charity_on = bool(vars_["charity_mode"].get())
            charity_cap_on = bool(vars_["limit_charity_paid_places"].get())
            for key in ("charity_method", "charity_value", "charity_max_paid_places"):
                visible = charity_on and (key != "charity_max_paid_places" or charity_cap_on)
                widget = wizard_widgets.get(key)
                label = charity_field_labels.get(key)
                for control in (label, widget):
                    if control is None:
                        continue
                    if visible and not control.winfo_manager():
                        control.grid()
                    elif not visible and control.winfo_manager():
                        control.grid_remove()
                if widget is not None:
                    widget.configure(state="normal" if visible else "disabled")
            if charity_on and not charity_cap_check.winfo_manager():
                charity_cap_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=(5, 2))
            elif not charity_on and charity_cap_check.winfo_manager():
                charity_cap_check.grid_remove()
            if "payout_details_refresh" in locals():
                payout_details_refresh()

        # Rebind callbacks after all page-specific widgets and closures exist.
        for key in ("rebuy_enabled", "add_on_enabled"):
            vars_[key].trace_add("write", wizard_widgets_set_entry_dependencies)
        for key in ("charity_mode", "limit_charity_paid_places"):
            vars_[key].trace_add("write", wizard_widgets_set_entry_dependencies)
        type_combo.bind("<<ComboboxSelected>>", lambda event: (on_type_changed(event), wizard_widgets_set_entry_dependencies()), add="+")
        vars_["payout_mode"].trace_add("write", lambda *_: payout_details_refresh())
        vars_["payout_position_mode"].trace_add("write", lambda *_: payout_details_refresh())
        set_entry_dependencies = wizard_widgets_set_entry_dependencies
        dependency_callbacks["refresh"] = wizard_widgets_set_entry_dependencies
        wizard_widgets_set_entry_dependencies()
        update_freeroll_fields()
        payout_details_refresh()
        self.wait_window(dlg)

    def _scenario_mixed_payouts_dialog(self, parent, existing_mixed, payout_splits, initial_places=6):
        """Edit mixed payout rows for one or more place counts without altering the active tournament."""
        result = None
        working = {str(k): copy.deepcopy(v) for k, v in (existing_mixed or {}).items()}
        dlg = tk.Toplevel(parent)
        dlg.title("Scenario Mixed Payout Structures")
        dlg.transient(parent)
        dlg.grab_set()
        dlg.geometry("620x650")
        dlg.minsize(560, 500)
        ttk.Label(dlg, text="Configure fixed-dollar and percentage awards for a paid-place count.",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 5))
        ttk.Label(dlg, text="Fixed amounts are deducted first. Percentage rows must total 100%. The normal safety check runs when payouts are calculated.",
                  wraplength=580, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        selector = ttk.Frame(dlg)
        selector.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Label(selector, text="Paid places:").pack(side="left")
        places_var = tk.StringVar(value=str(max(2, min(100, int(initial_places)))))
        ttk.Combobox(selector, textvariable=places_var, values=[str(n) for n in range(2, 101)], state="readonly", width=8).pack(side="left", padx=8)
        canvas_wrap = ttk.Frame(dlg)
        canvas_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        canvas = tk.Canvas(canvas_wrap, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_wrap, orient="vertical", command=canvas.yview)
        rows_frame = ttk.Frame(canvas)
        rows_frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        row_vars = []
        current_count = {"value": None}
        footer_info = tk.StringVar(value="")
        ttk.Label(dlg, textvariable=footer_info, foreground="#52606d").pack(anchor="w", padx=14, pady=(0, 6))

        def default_rows(places):
            saved = working.get(str(places))
            if not isinstance(saved, list):
                saved = working.get(places)
            if isinstance(saved, list) and len(saved) == places:
                return [dict(row) for row in saved]
            split = payout_splits.get(str(places), payout_splits.get(places, DEFAULT_PAYOUT_SPLITS.get(places)))
            if not split:
                split = self._generated_payout_split(places)
            return [{"method": "Percentage", "value": value} for value in split]

        def save_rows_in_memory():
            try:
                places = int(current_count["value"])
                if not row_vars or len(row_vars) != places:
                    return True
                rows = []
                pct_total = 0.0
                pct_count = 0
                for idx, row in enumerate(row_vars, start=1):
                    method = row["method"].get()
                    value = float(row["value"].get())
                    if not math.isfinite(value) or value <= 0:
                        raise ValueError(f"Position {idx} must have a positive payout value.")
                    if method == "Percentage":
                        if value > 100:
                            raise ValueError(f"Position {idx} cannot exceed 100%.")
                        pct_total += value
                        pct_count += 1
                        rows.append({"method": method, "value": value})
                    else:
                        if not value.is_integer():
                            raise ValueError(f"Position {idx} fixed award must be a whole dollar amount.")
                        rows.append({"method": "Fixed amount ($)", "value": int(value)})
                if pct_count == 0:
                    raise ValueError("At least one position must use a percentage.")
                if abs(pct_total - 100.0) > 0.01:
                    raise ValueError(f"Percentage rows total {pct_total:.2f}%; they must total 100%.")
                working[str(places)] = rows
                footer_info.set(f"{places}-place mixed payout structure saved in this wizard. Percentage rows total {pct_total:.2f}%.")
                return True
            except (TypeError, ValueError) as exc:
                messagebox.showerror("Invalid Mixed Payout", str(exc), parent=dlg)
                return False

        def build_rows(_event=None):
            if current_count["value"] is not None and not save_rows_in_memory():
                return
            for child in rows_frame.winfo_children():
                child.destroy()
            row_vars.clear()
            places = int(places_var.get())
            current_count["value"] = places
            ttk.Label(rows_frame, text="Position", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=4, pady=5, sticky="w")
            ttk.Label(rows_frame, text="Method", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, padx=4, pady=5, sticky="w")
            ttk.Label(rows_frame, text="Value", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=4, pady=5, sticky="w")
            for idx, row in enumerate(default_rows(places), start=1):
                ttk.Label(rows_frame, text=f"{idx}{'st' if idx == 1 else 'nd' if idx == 2 else 'rd' if idx == 3 else 'th'} place").grid(row=idx, column=0, sticky="w", padx=4, pady=3)
                method_var = tk.StringVar(value=row.get("method", "Percentage"))
                value_var = tk.StringVar(value=str(row.get("value", 0)))
                ttk.Combobox(rows_frame, textvariable=method_var, values=["Percentage", "Fixed amount ($)"], state="readonly", width=23).grid(row=idx, column=1, padx=4, pady=3)
                ttk.Entry(rows_frame, textvariable=value_var, width=16).grid(row=idx, column=2, padx=4, pady=3)
                row_vars.append({"method": method_var, "value": value_var})
            footer_info.set(f"Configure {places} paid positions. Fixed amounts are deducted first; percentage rows apply to the remaining pool.")

        def save_and_close():
            if not save_rows_in_memory():
                return
            nonlocal result
            result = working
            dlg.destroy()

        places_combo = selector.winfo_children()[1]
        places_combo.bind("<<ComboboxSelected>>", build_rows)
        footer = ttk.Frame(dlg)
        footer.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Button(footer, text="Save Mixed Structures", command=save_and_close).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side="right")
        build_rows()
        self.wait_window(dlg)
        return result

    def _scenario_level_dialog(self, parent, initial=None, kind="Play", default_name=None):
        vals = dict(initial or {})
        resolved_kind = vals.get("kind", kind)
        dlg = tk.Toplevel(parent)
        dlg.title("Edit Scenario Level" if initial else "Add Scenario Level")
        dlg.transient(parent)
        dlg.grab_set()
        dlg.resizable(False, False)
        vars_ = {
            "name": tk.StringVar(value=str(vals.get("name", default_name or ("Break" if kind == "Break" else "Level")))),
            "minutes": tk.StringVar(value=str(vals.get("minutes", 20 if kind == "Play" else 10))),
            "kind": tk.StringVar(value=resolved_kind),
            "sb": tk.StringVar(value=str(vals.get("sb", 0 if resolved_kind == "Break" else 100))),
            "bb": tk.StringVar(value=str(vals.get("bb", 0 if resolved_kind == "Break" else 200))),
            "ante": tk.StringVar(value=str(vals.get("ante", 0))),
        }
        fields = [("Level / break name", "name"), ("Duration (minutes)", "minutes"), ("Type", "kind"),
                  ("Small blind", "sb"), ("Big blind", "bb")]
        widgets = {}
        for row, (label, key) in enumerate(fields):
            ttk.Label(dlg, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=5)
            if key == "kind":
                widget = ttk.Combobox(dlg, textvariable=vars_[key], values=["Play", "Break"], state="readonly", width=22)
            else:
                widget = ttk.Entry(dlg, textvariable=vars_[key], width=25)
            widget.grid(row=row, column=1, sticky="w", padx=12, pady=5)
            widgets[key] = widget

        def update_kind(*_):
            # Ante controls are intentionally hidden in this release. Only
            # update the visible blind fields, while retaining the hidden ante
            # value in the saved structure for possible future reintroduction.
            is_play = vars_["kind"].get() == "Play"
            for key in ("sb", "bb"):
                widgets[key].configure(state="normal" if is_play else "disabled")
            if not is_play:
                vars_["sb"].set("0")
                vars_["bb"].set("0")
                vars_["ante"].set("0")
            elif initial is None:
                vars_["sb"].set("100")
                vars_["bb"].set("200")
        vars_["kind"].trace_add("write", update_kind)
        update_kind()
        result = {}
        def save():
            try:
                name = vars_["name"].get().strip() or default_name or ("Break" if vars_["kind"].get() == "Break" else "Level")
                minutes = int(vars_["minutes"].get())
                current_kind = vars_["kind"].get()
                if not 1 <= minutes <= 240:
                    raise ValueError("Duration must be between 1 and 240 minutes.")
                if current_kind not in ("Play", "Break"):
                    raise ValueError("Choose Play or Break.")
                if current_kind == "Break":
                    sb = bb = ante = 0
                else:
                    sb, bb, ante = int(vars_["sb"].get()), int(vars_["bb"].get()), int(vars_["ante"].get())
                    if min(sb, bb) < 0 or bb <= 0:
                        raise ValueError("Blind values cannot be negative, and big blind must be positive.")
                result.update({"name": name, "minutes": minutes, "sb": sb, "bb": bb, "ante": ante, "kind": current_kind})
                if current_kind == "Break":
                    result["pause_after"] = bool(vals.get("pause_after", False))
                dlg.destroy()
            except Exception as exc:
                messagebox.showerror("Invalid Level", str(exc), parent=dlg)
        buttons = ttk.Frame(dlg)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)
        self.wait_window(dlg)
        return result or None

    def _build_clock_tab(self):
        tab = self.clock_tab
        top = ttk.Frame(tab)
        top.pack(fill="x")
        self.level_label = tk.Label(top, text="", font=("Segoe UI", 18, "bold"), fg="#18212b")
        self.level_label.pack(side="left")
        self.status_label = tk.Label(top, text="PAUSED", font=("Segoe UI", 10, "bold"), fg="#a33")
        self.status_label.pack(side="right")

        clock_panel = tk.Frame(tab, bg="#101820", padx=24, pady=12)
        clock_panel.pack(fill="x", pady=(8, 6))
        self.timer_label = tk.Label(clock_panel, text="20:00", bg="#101820", fg="#ffffff",
                                    font=("Consolas", 58, "bold"))
        self.timer_label.pack()
        self.blinds_label = tk.Label(clock_panel, text="25 / 50", bg="#101820", fg="#65d6a6",
                                     font=("Segoe UI", 24, "bold"))
        self.blinds_label.pack(pady=(0, 2))
        self.next_label = ttk.Label(tab, text="", font=("Segoe UI", 11), foreground="#263746")
        self.next_label.pack(pady=(0, 6))

        controls = ttk.Frame(tab)
        controls.pack(fill="x", pady=3)
        self._make_action_button(controls, "▶ Start / Resume", self.start_clock, force="positive").pack(side="left", padx=3)
        self._make_action_button(controls, "Ⅱ Pause", self.pause_clock, force="negative").pack(side="left", padx=3)
        self._make_action_button(controls, "↻ Reset Level", self.reset_level, force="neutral").pack(side="left", padx=3)
        ttk.Button(controls, text="Full Screen Display", command=self._open_display).pack(side="right", padx=3)

        # Main-page manual timer control mirrors the full-screen display. It is
        # bounded to the current level/break duration, with silent clamping at 0
        # and the configured maximum.
        time_adjust = ttk.LabelFrame(tab, text="Adjust Current Level Time", padding=(8, 3))
        time_adjust.pack(fill="x", pady=(2, 4))
        time_adjust_row = ttk.Frame(time_adjust)
        time_adjust_row.pack(fill="x", padx=2, pady=1)
        self._make_action_button(
            time_adjust_row, "−30 sec", lambda: self._adjust_main_level_time(-30), force="negative"
        ).pack(side="left", padx=(2, 7))
        initial_duration = max(1, self._current_level_duration_seconds())
        self.main_time_slider_var = tk.DoubleVar(value=min(self._current_seconds(), initial_duration))
        self.main_time_slider_state = {"dragging": False, "syncing": False, "level": self.current_level}
        self.main_time_slider_scale = ttk.Scale(
            time_adjust_row, from_=0, to=initial_duration, orient="horizontal",
            variable=self.main_time_slider_var, command=self._on_main_time_slider_changed
        )
        self.main_time_slider_scale.pack(side="left", fill="x", expand=True, padx=6)
        self.main_time_adjust_value = ttk.Label(
            time_adjust_row, text=self._format_clock_duration(self._current_seconds()),
            font=("Consolas", 11, "bold"), width=9, anchor="center"
        )
        self.main_time_adjust_value.pack(side="left", padx=5)
        self._make_action_button(
            time_adjust_row, "+30 sec", lambda: self._adjust_main_level_time(30), force="positive"
        ).pack(side="left", padx=(7, 2))
        self.main_time_slider_scale.bind("<ButtonPress-1>", self._main_time_slider_pressed, add="+")
        self.main_time_slider_scale.bind("<ButtonRelease-1>", self._main_time_slider_released, add="+")
        self.main_time_slider_scale.bind("<KeyRelease>", self._main_time_slider_released, add="+")

        quick = ttk.LabelFrame(tab, text="Quick Tournament Controls", padding=4)
        quick.pack(fill="x", pady=(4, 0))
        self.quick_controls_frame = quick
        self.quick_groups_main = {
            "Entries": self._build_action_group(quick, "Entries", [
                ("Add Entry +", self.quick_add_entry_action),
                ("Remove Entry −", self.quick_remove_entry_action),
            ]),
            "Players": self._build_action_group(quick, "Players", [
                ("Add Player +", self.quick_add_player_action),
                ("Bust Player −", self.quick_bust_player_action),
            ]),
            "Re-buys": self._build_action_group(quick, "Re-buys", [
                ("Re-buy +", self.quick_add_rebuy_action),
                ("Re-buy −", self.quick_remove_rebuy_action),
            ]),
            "Add-ons": self._build_action_group(quick, "Add-ons", [
                ("Add-on +", self.add_anonymous_addon),
                ("Add-on −", self.remove_anonymous_addon),
            ]),
            "Level": self._build_action_group(quick, "Level", [
                ("Next Level", self.next_level, "positive"),
                ("Previous Level", self.previous_level, "negative"),
            ]),
        }
        self._layout_quick_groups(quick, self.quick_groups_main)

        dashboard = ttk.Frame(tab)
        dashboard.pack(fill="both", expand=True, pady=(7, 0))
        self.dashboard_vars = {
            "status": tk.StringVar(value="Active Players: 0\nTotal Entries: 0\nRe-buys: 0\nAdd-ons: 0"),
            "statistics": tk.StringVar(value="Avg. stack: 0\nTotal chips: 0\nTotal prize: $0"),
            "prizes": tk.StringVar(value="Payouts appear when entries are recorded."),
            "benefit_pot": tk.StringVar(value=""),
            "player_pot": tk.StringVar(value="$0"),
        }
        # Keep the main-page dashboard focused on Status, Statistics and Prizes.
        # The live time-remaining pie belongs on the full-screen player-facing display.
        for column, weight in enumerate((4, 4, 6)):
            dashboard.columnconfigure(column, weight=weight, uniform="dashboard")
        dashboard.rowconfigure(0, weight=1)
        for column, (heading, key) in enumerate([
            ("Status", "status"), ("Statistics", "statistics"), ("Prizes", "prizes")
        ]):
            panel = ttk.LabelFrame(dashboard, text=heading, padding=(10, 5))
            panel.grid(row=0, column=column, sticky="nsew", padx=3)
            if key == "prizes":
                prizes_body = ttk.Frame(panel)
                prizes_body.pack(fill="both", expand=True, anchor="nw")
                prizes_body.columnconfigure(0, weight=3)
                prizes_body.columnconfigure(1, weight=1)
                self.main_prizes_body = prizes_body
                self.main_prizes_text_label = ttk.Label(
                    prizes_body, textvariable=self.dashboard_vars["prizes"], justify="left",
                    font=("Segoe UI", 11, "bold"), anchor="nw", wraplength=240
                )
                self.main_prizes_text_label.grid(row=0, column=0, sticky="new", padx=(0, 8))
                pot_box = ttk.Frame(prizes_body, padding=(8, 2, 0, 2))
                pot_box.grid(row=0, column=1, sticky="nsew")
                self.main_pot_box = pot_box
                self.main_benefit_header = ttk.Label(
                    pot_box, text="BENEFIT POT", justify="center",
                    font=("Segoe UI", 9, "bold"), anchor="center", wraplength=100
                )
                self.main_benefit_value = ttk.Label(
                    pot_box, textvariable=self.dashboard_vars["benefit_pot"], justify="center",
                    font=("Segoe UI", 14, "bold"), anchor="center"
                )
                self.main_player_pot_header = ttk.Label(
                    pot_box, text="TOTAL PLAYER POT", justify="center",
                    font=("Segoe UI", 9, "bold"), anchor="center", wraplength=100
                )
                self.main_player_pot_header.pack(fill="x", pady=(4, 5))
                ttk.Label(pot_box, textvariable=self.dashboard_vars["player_pot"], justify="center",
                          font=("Segoe UI", 17, "bold"), anchor="center").pack(fill="x")
            else:
                ttk.Label(panel, textvariable=self.dashboard_vars[key], justify="left",
                          font=("Segoe UI", 11, "bold"), anchor="nw", wraplength=330).pack(
                              fill="both", expand=True, anchor="nw"
                          )

    def _make_action_button(self, parent, label, command, force=None, dark=False):
        if force == "positive" or (force is None and "+" in label):
            bg, active_bg = "#18864b", "#126738"
        elif force == "negative" or (force is None and ("−" in label or "Remove" in label or "Bust" in label)):
            bg, active_bg = "#c0392b", "#922b21"
        else:
            bg, active_bg = ("#34495e", "#263746") if dark else ("#59636e", "#414a52")
        return tk.Button(parent, text=label, command=command, bg=bg, activebackground=active_bg,
                         fg="white", activeforeground="white", disabledforeground="#eeeeee",
                         font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                         padx=7, pady=4, cursor="hand2")

    def _build_action_group(self, parent, title, actions, dark=False):
        if dark:
            group = tk.Frame(parent, bg="#1d2b36", highlightbackground="#475866", highlightthickness=1, padx=6, pady=5)
            tk.Label(group, text=title, bg="#1d2b36", fg="#ffffff",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
        else:
            group = ttk.LabelFrame(parent, text=title, padding=(5, 4))
        for action in actions:
            if len(action) == 3:
                label, command, force = action
            else:
                label, command = action
                force = None
            self._make_action_button(group, label, command, force=force, dark=dark).pack(fill="x", padx=2, pady=2)
        return group

    def _layout_quick_groups(self, container, groups, include_rebuys=None, include_addons=None):
        """Lay out quick-action groups, omitting disabled rebuy/add-on controls."""
        if include_rebuys is None:
            include_rebuys = self.rebuy_enabled
        if include_addons is None:
            include_addons = self.add_on_enabled
        for col in range(5):
            container.grid_columnconfigure(col, weight=0, uniform="")
        visible = [(title, widget) for title, widget in groups.items()
                   if not (title == "Re-buys" and not include_rebuys)
                   and not (title == "Add-ons" and not include_addons)]
        for widget in groups.values():
            if widget.winfo_manager() == "grid":
                widget.grid_remove()
        for col, (_title, widget) in enumerate(visible):
            container.grid_columnconfigure(col, weight=1, uniform="actiongroups")
            widget.grid(row=0, column=col, sticky="nsew", padx=2, pady=2)

    def _dashboard_texts(self):
        active, entries, rebuys = self._counts()
        financials = self._entry_financials()
        # Show these as separate facts: a rebuy raises total entries, not active players.
        # Avoid the old "Players: active / entries" format, which looked like player count increased.
        status_lines = [f"Active Players: {active}", f"Total Entries: {entries}"]
        if self.rebuy_enabled:
            status_lines.append(f"Re-buys: {rebuys}")
        if self.add_on_enabled:
            status_lines.append(f"Add-ons: {financials['addons']}")
        status_text = "\n".join(status_lines)
        total_chips = max(0, entries * int(self.starting_stack) + financials["addons"] * int(self.add_on_chips))
        average_stack = round(total_chips / active) if active > 0 else 0
        stats_text = (
            f"Avg. stack: {average_stack:,}\n"
            f"Total chips: {total_chips:,}\n"
            f"Total prize: {money_whole(self._pool())}\n"
            f"Elapsed levels: {self.current_level}"
        )
        _, payout_pool, paid_places, payout_rows = self._calculate_payouts()
        if payout_rows:
            ordinal = lambda place: f"{place}st" if place == 1 else f"{place}nd" if place == 2 else f"{place}rd" if place == 3 else f"{place}th"
            # Show every configured payout; the display panel grows vertically as needed.
            visible = [f"{ordinal(place)}: {money_whole(amount)}" for place, _pct, amount in payout_rows]
            if self._mixed_payout_fallback_reason:
                visible.insert(0, "SAFE FALLBACK: standard percentages used")
            prizes_text = "\n".join(visible)
        else:
            prizes_text = "Payouts appear when the prize pool and entry count are sufficient."
        benefit_amount = float(financials.get("charity", 0.0) or 0.0)
        benefit_text = money_whole(benefit_amount) if benefit_amount > 0 else ""
        return {"status": status_text, "statistics": stats_text, "prizes": prizes_text,
                "benefit_pot": benefit_text, "player_pot": money_whole(payout_pool)}

    def _build_levels_tab(self):
        tab = self.levels_tab
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Import Blind Structure…", command=self.import_levels).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Add Level", command=self.add_level).pack(side="left", padx=(0, 5))
        ttk.Button(toolbar, text="Add Break", command=self.add_break).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Edit Selected", command=self.edit_level).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Delete Selected", command=self.delete_level).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Move Up", command=lambda: self.move_level(-1)).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Move Down", command=lambda: self.move_level(1)).pack(side="left", padx=5)

        first_play_minutes = next((int(x.get("minutes", 20)) for x in self.levels if x.get("kind") != "Break"), 20)
        first_break_minutes = next((int(x.get("minutes", 10)) for x in self.levels if x.get("kind") == "Break"), 10)
        self.play_duration_var = tk.StringVar(value=str(first_play_minutes))
        self.break_duration_var = tk.StringVar(value=str(first_break_minutes))
        bulk = ttk.LabelFrame(tab, text="Set Durations", padding=7)
        bulk.pack(fill="x", pady=(0, 8))
        play_line = ttk.Frame(bulk)
        play_line.pack(fill="x", pady=(0, 4))
        ttk.Label(play_line, text="Play levels (minutes):").pack(side="left", padx=(2, 4))
        ttk.Entry(play_line, textvariable=self.play_duration_var, width=6).pack(side="left", padx=3)
        ttk.Button(play_line, text="Apply to All Play Levels", command=self.fill_play_durations).pack(side="left", padx=(2, 8))
        ttk.Button(play_line, text="Apply to Selected Play Levels", command=lambda: self.fill_selected_durations("Play")).pack(side="left", padx=3)
        break_line = ttk.Frame(bulk)
        break_line.pack(fill="x")
        ttk.Label(break_line, text="Breaks (minutes):").pack(side="left", padx=(2, 4))
        ttk.Entry(break_line, textvariable=self.break_duration_var, width=6).pack(side="left", padx=3)
        ttk.Button(break_line, text="Apply to All Breaks", command=self.fill_break_durations).pack(side="left", padx=(2, 8))
        ttk.Button(break_line, text="Apply to Selected Breaks", command=lambda: self.fill_selected_durations("Break")).pack(side="left", padx=3)
        ttk.Label(bulk, text="Shift-click selects a range; Ctrl-click adds or removes individual rows. Click a break's Pause cell to toggle it.",
                  foreground="#52606d").pack(anchor="w", pady=(5, 0))

        cols = ("num", "name", "kind", "minutes", "sb", "bb", "pause")
        self.level_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="extended")
        headings = {"num":"#", "name":"Level / Break", "kind":"Type", "minutes":"Duration (min)",
                    "sb":"Small Blind", "bb":"Big Blind", "pause":"Pause?"}
        widths = {"num":45, "name":205, "kind":85, "minutes":105, "sb":105, "bb":105, "pause":85}
        for c in cols:
            self.level_tree.heading(c, text=headings[c])
            self.level_tree.column(c, width=widths[c], anchor="center")
        self.level_tree.pack(fill="both", expand=True)
        self.level_tree.bind("<Double-1>", lambda e: self.edit_level())
        self.level_tree.bind("<Button-1>", self._on_level_tree_click, add="+")

    def _on_level_tree_click(self, event):
        """Treat the Pause? cell as an individually clickable checkbox for break rows."""
        if not hasattr(self, "level_tree") or self.level_tree.identify_region(event.x, event.y) != "cell":
            return None
        if self.level_tree.identify_column(event.x) != "#7":
            return None
        iid = self.level_tree.identify_row(event.y)
        if not iid:
            return None
        try:
            index = int(iid)
        except (TypeError, ValueError):
            return "break"
        if not 0 <= index < len(self.levels) or self.levels[index].get("kind") != "Break":
            return "break"
        old_levels = copy.deepcopy(self.levels)
        current_pause = bool(self.levels[index].get("pause_after", False))
        self.levels[index]["pause_after"] = not current_pause
        active_id = getattr(self, "active_scenario_id", "")
        scenario = next((item for item in self.scenarios if item.get("id") == active_id), None) if active_id else None
        if scenario:
            old_scenario_levels = copy.deepcopy(scenario.get("config", {}).get("levels", []))
            scenario.setdefault("config", {})["levels"] = copy.deepcopy(self.levels)
            scenario["updated_at"] = datetime.now().isoformat(timespec="seconds")
            if not self._save_scenario_library():
                self.levels = old_levels
                scenario["config"]["levels"] = old_scenario_levels
                return "break"
        self._save_data()
        self._refresh_all()
        try:
            self.level_tree.selection_set(str(index))
        except tk.TclError:
            pass
        return "break"

    def _build_players_tab(self):
        """Show count-based player/entry controls; named-player UI is deferred to a later release."""
        tab = self.players_tab
        ttk.Label(tab, text="Players & Entries", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text="Use count-based controls for active players, initial entries, rebuys, and add-ons. Each count is tracked independently.",
            foreground="#52606d", wraplength=900, justify="left"
        ).pack(anchor="w", pady=(3, 12))

        counter = ttk.LabelFrame(tab, text="Tournament Counts", padding=12)
        counter.pack(fill="x", pady=(0, 10))

        player_controls = ttk.Frame(counter)
        player_controls.pack(fill="x", pady=(0, 8))
        ttk.Label(player_controls, text="Active players:").pack(side="left", padx=(3, 10))
        self._make_action_button(player_controls, "Add Player +", self.quick_add_player_action, force="positive").pack(side="left", padx=4)
        self._make_action_button(player_controls, "Bust Player −", self.quick_bust_player_action, force="negative").pack(side="left", padx=4)

        entry_controls = ttk.Frame(counter)
        entry_controls.pack(fill="x", pady=(0, 8))
        ttk.Label(entry_controls, text="Initial entries:").pack(side="left", padx=(3, 10))
        self._make_action_button(entry_controls, "Add Entry +", self.quick_add_entry_action, force="positive").pack(side="left", padx=4)
        self._make_action_button(entry_controls, "Remove Entry −", self.quick_remove_entry_action, force="negative").pack(side="left", padx=4)

        rebuy_controls = ttk.Frame(counter)
        self.rebuy_controls_page = rebuy_controls
        rebuy_controls.pack(fill="x", pady=(0, 8))
        ttk.Label(rebuy_controls, text="Rebuys:").pack(side="left", padx=(3, 10))
        self._make_action_button(rebuy_controls, "Re-buy +", self.quick_add_rebuy_action, force="positive").pack(side="left", padx=4)
        self._make_action_button(rebuy_controls, "Re-buy −", self.quick_remove_rebuy_action, force="negative").pack(side="left", padx=4)

        addon_controls = ttk.Frame(counter)
        self.addon_controls_page = addon_controls
        addon_controls.pack(fill="x", pady=(0, 8))
        ttk.Label(addon_controls, text="Add-ons:").pack(side="left", padx=(3, 10))
        self._make_action_button(addon_controls, "Add-on +", self.add_anonymous_addon, force="positive").pack(side="left", padx=4)
        self._make_action_button(addon_controls, "Add-on −", self.remove_anonymous_addon, force="negative").pack(side="left", padx=4)

        self.anonymous_count_label = ttk.Label(counter, text="", font=("Segoe UI", 11, "bold"))
        self.anonymous_count_label.pack(anchor="w", pady=(8, 0))

    def _build_reports_tab(self):
        tab = self.reports_tab
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="Refresh Statistics", command=self._refresh_reports).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Export Summary Report (TXT)", command=self.export_report).pack(side="left", padx=6)
        ttk.Button(top, text="Export Blind Structure (CSV)", command=self.export_levels_csv).pack(side="left", padx=6)
        self.report_text = tk.Text(tab, wrap="word", font=("Consolas", 10), height=25, bg="#f7f9fb")
        self.report_text.pack(fill="both", expand=True)
        self.report_text.configure(state="disabled")


    def _build_payouts_tab(self):
        """Display the calculated payout results; configuration lives in Tournament Settings."""
        tab = self.payouts_tab
        self.payout_mode_info = ttk.Label(
            tab, text="", foreground="#52606d", wraplength=1000, justify="left"
        )
        self.payout_mode_info.pack(anchor="w", fill="x", pady=(0, 8))

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Recalculate Payouts", command=self._refresh_payouts).pack(side="left")
        ttk.Label(
            toolbar,
            text="Payout method, paid-place rules, thresholds, and payout editors are managed under Tournament Settings → Payout Rules.",
            foreground="#52606d"
        ).pack(side="left", padx=(12, 0))

        self.payout_summary = ttk.Label(tab, text="", font=("Segoe UI", 11, "bold"))
        self.payout_summary.pack(anchor="w", pady=(0, 5))
        payout_cols = ("place", "percent", "amount")
        self.payout_tree = ttk.Treeview(tab, columns=payout_cols, show="headings", height=15)
        for c, heading, width in [
            ("place", "Finish Position", 200),
            ("percent", "Payout Method / Share", 260),
            ("amount", "Estimated Payout", 220),
        ]:
            self.payout_tree.heading(c, text=heading)
            self.payout_tree.column(c, width=width, anchor="center")
        self.payout_tree.pack(fill="both", expand=True)
        ttk.Label(
            tab,
            text="This tab shows the calculated awards for the current tournament and payout mode. Configure payout mode, paid-position rules, percentage splits, mixed awards, and freeroll prizes under Tournament Settings.",
            foreground="#52606d", wraplength=1000, justify="left"
        ).pack(anchor="w", pady=(8, 0))

    def _on_payout_mode_selected(self, _event=None):
        """Handle the payout-method selection from Tournament Settings."""
        requested = self.payout_mode_var.get()
        allowed_modes = (
            "Traditional Percentages",
            "Mixed Fixed + Percentage",
            "Freeroll Fixed Prizes",
        )
        if requested not in allowed_modes:
            self.payout_mode_var.set(self.payout_mode)
            return
        if requested == "Freeroll Fixed Prizes":
            # Require every selected position to have a valid positive fixed award.
            places = max(1, min(3, int(self.freeroll_paid_places)))
            amounts = self.freeroll_payouts[:places]
            if len(amounts) != places or any(int(amount) <= 0 for amount in amounts):
                self.payout_mode_var.set(self.payout_mode)
                self._configure_freeroll_payouts(enable_mode_on_save=True)
                return
        self.payout_mode = requested
        self._save_data()
        self._refresh_settings_dependencies()
        self._refresh_all()

    def _update_payout_mode_controls(self, mode=None):
        """Enable only payout configuration controls relevant to the selected mode."""
        if not hasattr(self, "configure_freeroll_button"):
            return
        mode = mode or self.payout_mode
        is_traditional = mode == "Traditional Percentages"
        is_mixed = mode == "Mixed Fixed + Percentage"
        is_freeroll = mode == "Freeroll Fixed Prizes"
        uses_entry_positions = not is_freeroll
        entry_thresholds_used = uses_entry_positions and self.payout_position_mode != "Target fixed number"

        self.configure_freeroll_button.configure(state="normal" if is_freeroll else "disabled")
        self.paid_position_rules_button.configure(state="normal" if uses_entry_positions else "disabled")
        for button in (self.add_payout_rule_button, self.edit_payout_rule_button, self.delete_payout_rule_button):
            button.configure(state="normal" if entry_thresholds_used else "disabled")

        # The traditional percentage table remains useful as the safety fallback
        # for a mixed structure, but it is irrelevant in a host-funded freeroll.
        self.edit_payout_splits_button.configure(
            text="Edit Traditional Fallback…" if is_mixed else "Edit Payout Percentages…",
            state="normal" if (is_traditional or is_mixed) else "disabled",
        )
        self.edit_mixed_payouts_button.configure(state="normal" if is_mixed else "disabled")

        if hasattr(self, "payout_threshold_heading"):
            if is_freeroll:
                heading = "Entry thresholds (not used for Freeroll Fixed Prizes)"
            elif self.payout_position_mode == "Target fixed number":
                heading = "Automatic entry thresholds (not used while Target fixed number is selected)"
            else:
                heading = "Automatic entry thresholds (each rebuy/re-entry counts as a new entry)"
            self.payout_threshold_heading.configure(text=heading)
        if hasattr(self, "payout_rule_tree"):
            if entry_thresholds_used:
                self.payout_rule_tree.state(["!disabled"])
            else:
                self.payout_rule_tree.state(["disabled"])

    def _on_payout_rule_tree_double_click(self, _event=None):
        """Prevent opening threshold editors while the threshold table is inactive."""
        if self.payout_mode == "Freeroll Fixed Prizes" or self.payout_position_mode == "Target fixed number":
            return "break"
        self.edit_payout_rule()
        return "break"

    def _effective_freeroll_places(self):
        places = max(1, min(3, int(self.freeroll_paid_places)))
        if self.charity_mode and self.limit_charity_paid_places:
            places = min(places, max(1, int(self.charity_max_paid_places)))
        return places

    def _effective_freeroll_amounts(self):
        places = self._effective_freeroll_places()
        try:
            amounts = [int(float(value)) for value in self.freeroll_payouts[:places]]
        except (ValueError, TypeError):
            return []
        if len(amounts) != places or any(value <= 0 for value in amounts):
            return []
        return amounts

    def _configure_freeroll_payouts(self, enable_mode_on_save=True):
        """Configure fixed host-funded awards for a freeroll, independent of entry counts."""
        dlg = tk.Toplevel(self)
        dlg.title("Freeroll / Fixed Payouts")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        ttk.Label(
            dlg,
            text="Set fixed whole-dollar awards for a host-funded freeroll. These amounts do not change when player or entry counts change.",
            wraplength=430, justify="left"
        ).grid(row=0, column=0, columnspan=3, padx=14, pady=(14, 10), sticky="w")

        places_var = tk.StringVar(value=str(self.freeroll_paid_places))
        ttk.Label(dlg, text="Number of paid places:").grid(row=1, column=0, padx=14, pady=6, sticky="w")
        places_combo = ttk.Combobox(dlg, textvariable=places_var, values=["1", "2", "3"], state="readonly", width=8)
        places_combo.grid(row=1, column=1, padx=8, pady=6, sticky="w")

        payout_vars = [tk.StringVar(value=str(int(v))) for v in self.freeroll_payouts[:3]]
        # Keep explicit references to only the three payout amount fields.
        # ttk.Combobox is also an Entry subclass, so discovering fields by
        # isinstance(..., ttk.Entry) accidentally included the paid-place selector
        # and shifted every enable/disable operation by one position.
        payout_entries = []
        for index, (label, variable) in enumerate(zip(("1st place ($)", "2nd place ($)", "3rd place ($)"), payout_vars), start=2):
            ttk.Label(dlg, text=label).grid(row=index, column=0, padx=14, pady=6, sticky="w")
            entry = ttk.Entry(dlg, textvariable=variable, width=14)
            entry.grid(row=index, column=1, padx=8, pady=6, sticky="w")
            payout_entries.append(entry)

        # Keep fields beyond the selected paid-place count visible but disabled, preserving their saved amounts.
        total_var = tk.StringVar(value="Fixed payout total: $0")
        ttk.Label(dlg, textvariable=total_var, font=("Segoe UI", 10, "bold")).grid(
            row=5, column=0, columnspan=3, padx=14, pady=(8, 4), sticky="w")
        note = ttk.Label(dlg, text="Amounts must be positive whole dollars for every paid position. Payout rounding settings do not alter these fixed awards.",
                         foreground="#52606d", wraplength=430, justify="left")
        note.grid(row=6, column=0, columnspan=3, padx=14, pady=(0, 8), sticky="w")

        def refresh_fields(*_):
            try:
                places = int(places_var.get())
            except ValueError:
                places = 1
            total = 0
            valid = True
            for idx, (variable, entry) in enumerate(zip(payout_vars, payout_entries), start=1):
                entry.configure(state="normal" if idx <= places else "disabled")
                try:
                    raw = variable.get().strip()
                    amount = float(raw)
                    if not math.isfinite(amount) or amount < 0 or not amount.is_integer():
                        valid = False
                    if idx <= places:
                        total += int(amount) if amount >= 0 and amount.is_integer() else 0
                except (ValueError, TypeError):
                    valid = False
            total_var.set(f"Fixed payout total: {money_whole(total)}" + ("" if valid else "  (check amounts)"))

        places_combo.bind("<<ComboboxSelected>>", refresh_fields)
        for variable in payout_vars:
            variable.trace_add("write", refresh_fields)
        refresh_fields()

        def save_fixed_payouts():
            try:
                places = int(places_var.get())
                amounts = []
                for index, variable in enumerate(payout_vars, start=1):
                    raw = variable.get().strip()
                    if not raw and index > places:
                        amounts.append(0)
                        continue
                    amount = float(raw)
                    if not math.isfinite(amount) or amount < 0 or not amount.is_integer():
                        raise ValueError("Enter nonnegative whole-dollar amounts without cents.")
                    amount = int(amount)
                    if index <= places and amount <= 0:
                        raise ValueError(f"The {index}{'st' if index == 1 else 'nd' if index == 2 else 'rd'}-place payout must be greater than $0.")
                    amounts.append(amount)
                self.freeroll_paid_places = places
                self.freeroll_payouts = amounts
                if enable_mode_on_save:
                    self.payout_mode = "Freeroll Fixed Prizes"
                    if hasattr(self, "payout_mode_var"):
                        self.payout_mode_var.set(self.payout_mode)
                self._save_data()
                self._refresh_all()
                dlg.destroy()
            except Exception as exc:
                messagebox.showerror("Invalid fixed payouts", str(exc), parent=dlg)

        footer = ttk.Frame(dlg)
        footer.grid(row=7, column=0, columnspan=3, padx=14, pady=(4, 14), sticky="e")
        ttk.Button(footer, text="Save Fixed Payouts", command=save_fixed_payouts).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side="right")
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

    def _selected_payout_rule_index(self):
        selected = self.payout_rule_tree.selection()
        return int(selected[0]) if selected else None

    def _payout_rule_dialog(self, initial=None):
        initial = initial or {"min_entries": 1, "max_entries": 10, "paid_places": 3}
        dlg = tk.Toplevel(self)
        dlg.title("Payout Entry Rule")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        vars_ = {k: tk.StringVar(value=str(initial[k])) for k in ("min_entries","max_entries","paid_places")}
        for r, (label, key) in enumerate([("Minimum total entries","min_entries"),("Maximum total entries","max_entries"),("Number of paid places","paid_places")]):
            ttk.Label(dlg, text=label).grid(row=r, column=0, sticky="w", padx=12, pady=6)
            ttk.Entry(dlg, textvariable=vars_[key], width=18).grid(row=r, column=1, padx=12, pady=6)
        result = {}
        def save():
            try:
                lo, hi, places = (int(vars_[k].get()) for k in ("min_entries","max_entries","paid_places"))
                if lo < 1 or hi < lo or places < 1 or places > hi:
                    raise ValueError("Use positive entries, max >= min, and paid places no greater than the maximum entries.")
                result.update({"min_entries":lo,"max_entries":hi,"paid_places":places})
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Invalid rule", str(e), parent=dlg)
        buttons = ttk.Frame(dlg)
        buttons.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)
        self.wait_window(dlg)
        return result or None

    def configure_paid_position_rules(self):
        """Choose automatic, fixed-target, or automatically capped paid-place behavior."""
        dlg = tk.Toplevel(self)
        dlg.title("Paid Position Rules")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        dlg.geometry("570x350")

        ttk.Label(dlg, text="Choose how many payout positions should be paid.",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(16, 5))
        ttk.Label(
            dlg,
            text="The charity-event cap remains a separate additional restriction. If there are fewer than two total entries, the entry-based payout list stays empty.",
            wraplength=530, justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 12))

        form = ttk.Frame(dlg)
        form.pack(fill="x", padx=16)
        mode_var = tk.StringVar(value=self.payout_position_mode)
        target_var = tk.StringVar(value=str(self.target_paid_places))
        cap_var = tk.StringVar(value=str(self.max_paid_places))

        ttk.Label(form, text="Paid-position mode:").grid(row=0, column=0, sticky="w", pady=7, padx=(0, 12))
        mode_combo = ttk.Combobox(
            form, textvariable=mode_var,
            values=["Automatic by entry rules", "Target fixed number", "Automatic with maximum cap"],
            state="readonly", width=34
        )
        mode_combo.grid(row=0, column=1, sticky="w", pady=7)

        ttk.Label(form, text="Target number of paid places:").grid(row=1, column=0, sticky="w", pady=7, padx=(0, 12))
        target_entry = ttk.Entry(form, textvariable=target_var, width=12)
        target_entry.grid(row=1, column=1, sticky="w", pady=7)

        ttk.Label(form, text="Maximum paid places:").grid(row=2, column=0, sticky="w", pady=7, padx=(0, 12))
        cap_entry = ttk.Entry(form, textvariable=cap_var, width=12)
        cap_entry.grid(row=2, column=1, sticky="w", pady=7)

        help_var = tk.StringVar(value="")
        ttk.Label(dlg, textvariable=help_var, wraplength=530, justify="left", foreground="#52606d").pack(
            anchor="w", padx=16, pady=(8, 12))

        def update_state(_event=None):
            mode = mode_var.get()
            target_entry.configure(state="normal" if mode == "Target fixed number" else "disabled")
            cap_entry.configure(state="normal" if mode == "Automatic with maximum cap" else "disabled")
            if mode == "Automatic by entry rules":
                help_var.set("The entry-threshold table determines paid places automatically, with no general maximum cap.")
            elif mode == "Target fixed number":
                help_var.set("Target this number of paid positions whenever enough entries exist. If there are fewer entries than the target, pay no more places than there are entries.")
            else:
                help_var.set("Use the existing entry-threshold table, but never exceed the selected maximum number of paid places.")

        mode_combo.bind("<<ComboboxSelected>>", update_state)
        update_state()
        footer = ttk.Frame(dlg)
        footer.pack(fill="x", padx=16, pady=(0, 14))

        def save_rules():
            try:
                mode = mode_var.get()
                if mode not in ("Automatic by entry rules", "Target fixed number", "Automatic with maximum cap"):
                    raise ValueError("Choose a valid paid-position mode.")
                target = int(target_var.get())
                cap = int(cap_var.get())
                if not 1 <= target <= 100:
                    raise ValueError("The target number of paid places must be between 1 and 100.")
                if not 1 <= cap <= 100:
                    raise ValueError("The maximum number of paid places must be between 1 and 100.")
                self.payout_position_mode = mode
                self.target_paid_places = target
                self.max_paid_places = cap
                self._save_data()
                self._refresh_all()
                dlg.destroy()
            except (ValueError, tk.TclError) as exc:
                messagebox.showerror("Invalid paid-position rules", str(exc), parent=dlg)

        ttk.Button(footer, text="Save Rules", command=save_rules).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side="right")

    def edit_mixed_payouts(self):
        """Configure a percentage/fixed-dollar combination for a paid-place count."""
        if self.payout_mode != "Mixed Fixed + Percentage":
            messagebox.showinfo(
                "Mixed payout mode is not selected",
                "Select 'Mixed Fixed + Percentage' in the Payout mode dropdown before configuring mixed payouts.",
                parent=self,
            )
            return

        place_choices = sorted(set(range(2, 101)))
        current_places = self._paid_places_for_entries(self._counts()[1])
        initial_places = current_places if current_places in place_choices else 6

        dlg = tk.Toplevel(self)
        dlg.title("Edit Mixed Payouts")
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("620x690")
        dlg.minsize(550, 480)

        ttk.Label(dlg, text="Mix percentage awards with fixed-dollar awards",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        ttk.Label(
            dlg,
            text="Fixed awards are deducted first. Percentage rows divide the remaining pool and must add up to 100%. Every position above a fixed award must pay at least that fixed amount; otherwise the calculator will use the traditional percentage split for safety.",
            wraplength=580, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 10))

        selector = ttk.Frame(dlg)
        selector.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Label(selector, text="Number of paid places:").pack(side="left")
        selected_places = tk.StringVar(value=str(initial_places))
        place_combo = ttk.Combobox(selector, textvariable=selected_places,
                                   values=[str(n) for n in place_choices], state="readonly", width=8)
        place_combo.pack(side="left", padx=(8, 14))
        ttk.Label(selector, text="Save each place-count structure before switching counts.",
                  foreground="#52606d").pack(side="left")

        canvas_wrap = ttk.Frame(dlg)
        canvas_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        canvas = tk.Canvas(canvas_wrap, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_wrap, orient="vertical", command=canvas.yview)
        rows_frame = ttk.Frame(canvas)
        rows_frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(canvas_window, width=e.width))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row_controls = []
        loaded_place_count = {"value": None}
        total_var = tk.StringVar(value="Percentages: 100%  |  Fixed awards: $0")
        status_var = tk.StringVar(value="")

        def update_totals(*_args):
            try:
                percentage_total = sum(float(row["value"].get()) for row in row_controls
                                       if row["method"].get() == "Percentage")
                fixed_total = sum(int(float(row["value"].get())) for row in row_controls
                                  if row["method"].get() == "Fixed amount ($)" and row["value"].get().strip())
                total_var.set(f"Percentages: {percentage_total:.2f}%  |  Fixed awards: {money_whole(fixed_total)}")
                status_var.set("" if abs(percentage_total - 100) <= 0.01 else "Percentage rows must total 100%.")
            except (ValueError, tk.TclError):
                total_var.set("Percentages: —  |  Fixed awards: —")
                status_var.set("Check the entered values.")

        def load_rows(_event=None):
            for child in rows_frame.winfo_children():
                child.destroy()
            row_controls.clear()
            places = int(selected_places.get())
            saved = self.mixed_payouts.get(str(places), self.mixed_payouts.get(places))
            if isinstance(saved, list) and len(saved) == places:
                configuration = [dict(row) for row in saved]
            else:
                split = self._split_for_places(places)
                configuration = [{"method": "Percentage", "value": split[i]} for i in range(places)]

            for col, (heading, width) in enumerate((("Position", 110), ("Payout method", 190), ("Amount / percent", 160))):
                ttk.Label(rows_frame, text=heading, font=("Segoe UI", 9, "bold")).grid(
                    row=0, column=col, sticky="w", padx=(2, 8), pady=(3, 8))
                rows_frame.grid_columnconfigure(col, weight=1 if col == 1 else 0)

            for index, config in enumerate(configuration, start=1):
                ttk.Label(rows_frame, text=f"{index}{'st' if index == 1 else 'nd' if index == 2 else 'rd' if index == 3 else 'th'} place").grid(
                    row=index, column=0, sticky="w", padx=(2, 8), pady=3)
                method = str(config.get("method", "Percentage"))
                if method not in ("Percentage", "Fixed amount ($)"):
                    method = "Percentage"
                method_var = tk.StringVar(value=method)
                value_var = tk.StringVar(value=str(config.get("value", 0)))
                method_combo = ttk.Combobox(rows_frame, textvariable=method_var,
                                            values=["Percentage", "Fixed amount ($)"], state="readonly", width=18)
                method_combo.grid(row=index, column=1, sticky="w", padx=(0, 8), pady=3)
                value_entry = ttk.Entry(rows_frame, textvariable=value_var, width=16)
                value_entry.grid(row=index, column=2, sticky="w", pady=3)
                row_controls.append({"method": method_var, "value": value_var})
                method_var.trace_add("write", update_totals)
                value_var.trace_add("write", update_totals)
            loaded_place_count["value"] = places
            canvas.yview_moveto(0)
            update_totals()

        place_combo.bind("<<ComboboxSelected>>", load_rows)
        load_rows()
        ttk.Label(dlg, textvariable=total_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(0, 2))
        ttk.Label(dlg, textvariable=status_var, foreground="#b45309").pack(anchor="w", padx=14, pady=(0, 6))
        footer = ttk.Frame(dlg)
        footer.pack(fill="x", padx=14, pady=(0, 14))

        def save_mixed():
            try:
                places = int(selected_places.get())
                if len(row_controls) != places:
                    raise ValueError("There must be one payout rule for each paid position.")
                configuration = []
                percentage_total = 0.0
                percentage_count = 0
                for index, row in enumerate(row_controls, start=1):
                    method = row["method"].get()
                    raw_value = row["value"].get().strip()
                    if not raw_value:
                        raise ValueError(f"Enter a value for position {index}.")
                    value = float(raw_value)
                    if not math.isfinite(value) or value <= 0:
                        raise ValueError(f"Position {index} must have a positive value.")
                    if method == "Percentage":
                        if value > 100:
                            raise ValueError(f"The percentage for position {index} cannot exceed 100%.")
                        value = round(value, 4)
                        percentage_total += value
                        percentage_count += 1
                    elif method == "Fixed amount ($)":
                        rounded = int(round(value))
                        if abs(value - rounded) > 0.0001:
                            raise ValueError(f"The fixed amount for position {index} must be a whole-dollar value.")
                        value = rounded
                    else:
                        raise ValueError(f"Choose a payout method for position {index}.")
                    configuration.append({"method": method, "value": value})
                if not percentage_count:
                    raise ValueError("At least one position must use a percentage of the remaining pool. Use Freeroll fixed payouts for an all-fixed structure.")
                if abs(percentage_total - 100.0) > 0.01:
                    raise ValueError(f"The percentage rows must total 100%. The current total is {percentage_total:.2f}%.")
                self.mixed_payouts[str(places)] = configuration
                self._save_data()
                self._refresh_all()
                dlg.destroy()
            except Exception as exc:
                messagebox.showerror("Invalid mixed payouts", str(exc), parent=dlg)

        def clear_mixed_structure():
            places = int(selected_places.get())
            key = str(places)
            if key not in self.mixed_payouts and places not in self.mixed_payouts:
                messagebox.showinfo(
                    "No mixed structure",
                    f"No mixed payout structure is saved for {places} paid places.",
                    parent=dlg,
                )
                return
            if messagebox.askyesno(
                "Use traditional percentages",
                f"Remove the mixed structure for {places} paid places and use the traditional percentage split instead?",
                parent=dlg,
            ):
                self.mixed_payouts.pop(key, None)
                self.mixed_payouts.pop(places, None)
                self.payout_mode = "Traditional Percentages"
                if hasattr(self, "payout_mode_var"):
                    self.payout_mode_var.set(self.payout_mode)
                self._save_data()
                self._refresh_all()
                load_rows()

        ttk.Button(footer, text="Use Traditional Percentage Split", command=clear_mixed_structure).pack(side="left")
        ttk.Button(footer, text="Save This Structure", command=save_mixed).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side="right")

    def add_payout_rule(self):
        result = self._payout_rule_dialog()
        if result:
            self.payout_rules.append(result)
            self.payout_rules.sort(key=lambda r: int(r["min_entries"]))
            self._save_data()
            self._refresh_payouts()

    def edit_payout_rule(self):
        idx = self._selected_payout_rule_index()
        if idx is None:
            messagebox.showinfo("Select a rule", "Select a payout threshold to edit.")
            return
        result = self._payout_rule_dialog(dict(self.payout_rules[idx]))
        if result:
            self.payout_rules[idx] = result
            self.payout_rules.sort(key=lambda r: int(r["min_entries"]))
            self._save_data()
            self._refresh_payouts()

    def delete_payout_rule(self):
        idx = self._selected_payout_rule_index()
        if idx is None:
            return
        if messagebox.askyesno("Delete rule", "Delete the selected payout threshold?"):
            del self.payout_rules[idx]
            self._save_data()
            self._refresh_payouts()

    @staticmethod
    def _generated_payout_split(places):
        """Create a descending default split that adds up to exactly 100%."""
        places = max(1, int(places))
        weights = [max(1, places - i) for i in range(places)]
        total = sum(weights)
        split = [round(w * 100 / total, 2) for w in weights]
        if split:
            split[-1] = round(split[-1] + 100.0 - sum(split), 2)
        return split

    def _apply_current_payout_template(self):
        """Apply a built-in traditional percentage profile to the current tournament."""
        label = self.payout_template_var.get().strip() if hasattr(self, "payout_template_var") else self.payout_template_name
        template = BUILT_IN_PAYOUT_TEMPLATES.get(label)
        if template is None:
            messagebox.showinfo(
                "Payout Profile",
                "The selected imported profile is already reflected in the saved charts. To replace it, import another Excel worksheet.",
                parent=self,
            )
            return
        self.payout_splits = {int(k): list(v) for k, v in template.items()}
        self.payout_template_name = label
        self._save_data()
        self._refresh_all()
        messagebox.showinfo(
            "Payout Profile Applied",
            f"Applied '{label}' with charts for 2 through 15 paid places. Entry thresholds still determine how many places are paid.",
            parent=self,
        )

    def _import_current_payout_template(self):
        """Import all traditional percentage charts from one workbook worksheet."""
        path, rows = self._read_import_rows("Import Payout Chart Template")
        if not path:
            return
        try:
            imported = parse_payout_template_rows(rows)
        except Exception as exc:
            messagebox.showerror("Invalid Payout Template", str(exc), parent=self)
            return
        self.payout_splits = {int(k): list(v) for k, v in imported.items()}
        self.payout_template_name = f"Imported: {os.path.basename(path)}"
        if hasattr(self, "payout_template_combo"):
            values = list(BUILT_IN_PAYOUT_TEMPLATE_LABELS)
            if self.payout_template_name not in values:
                values.append(self.payout_template_name)
            self.payout_template_combo.configure(values=values)
        if hasattr(self, "payout_template_var"):
            self.payout_template_var.set(self.payout_template_name)
        self._save_data()
        self._refresh_all()
        messagebox.showinfo(
            "Payout Template Imported",
            f"Imported {len(imported)} percentage chart(s) from {os.path.basename(path)}. Each imported chart was validated to total 100%.",
            parent=self,
        )

    def edit_payout_splits(self):
        """Edit the percentage split for one paid-place count at a time."""
        # Include common presets plus any paid-place counts used by custom threshold rules.
        place_choices = set(range(1, 16))
        place_choices.update(int(k) for k in self.payout_splits if int(k) >= 1)
        for rule in self.payout_rules:
            try:
                count = int(rule.get("paid_places", 0))
                if 1 <= count <= 100:
                    place_choices.add(count)
            except (TypeError, ValueError):
                continue
        choices = sorted(place_choices)
        current_places = self._paid_places_for_entries(self._counts()[1])
        initial_places = current_places if current_places in place_choices else (5 if 5 in place_choices else choices[0])

        dlg = tk.Toplevel(self)
        dlg.title("Edit Payout Percentages")
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("430x610")
        dlg.minsize(390, 430)

        ttk.Label(dlg, text="Configure the share of the player pot paid to each place.",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        ttk.Label(dlg, text="Edit one paid-place structure at a time. Save this split before editing another; percentages must total 100%.",
                  wraplength=390).pack(anchor="w", padx=14, pady=(0, 10))

        selector = ttk.Frame(dlg)
        selector.pack(fill="x", padx=14, pady=(0, 10))
        ttk.Label(selector, text="Number of paid places:").pack(side="left")
        selected_places = tk.StringVar(value=str(initial_places))
        place_combo = ttk.Combobox(selector, textvariable=selected_places,
                                   values=[str(n) for n in choices], state="readonly", width=8)
        place_combo.pack(side="left", padx=(8, 0))

        canvas_wrap = ttk.Frame(dlg)
        canvas_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        canvas = tk.Canvas(canvas_wrap, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_wrap, orient="vertical", command=canvas.yview)
        rows_frame = ttk.Frame(canvas)
        rows_frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(canvas_window, width=e.width))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        percent_vars = []
        loaded_place_count = {"value": None}

        def load_rows(_event=None):
            for child in rows_frame.winfo_children():
                child.destroy()
            percent_vars.clear()
            places = int(selected_places.get())
            split = list(self.payout_splits.get(places, self._generated_payout_split(places)))
            if len(split) != places or abs(sum(float(v) for v in split) - 100.0) > 0.05:
                split = self._generated_payout_split(places)
            ttk.Label(rows_frame, text="Finish position", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=0, sticky="w", padx=(2, 12), pady=(3, 8))
            ttk.Label(rows_frame, text="Percent", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=1, sticky="w", pady=(3, 8))
            for index, value in enumerate(split, start=1):
                ttk.Label(rows_frame, text=f"{index}{'st' if index == 1 else 'nd' if index == 2 else 'rd' if index == 3 else 'th'} place").grid(
                    row=index, column=0, sticky="w", padx=(2, 12), pady=3)
                var = tk.StringVar(value=f"{float(value):g}")
                ttk.Entry(rows_frame, textvariable=var, width=12).grid(row=index, column=1, sticky="w", pady=3)
                percent_vars.append(var)
            loaded_place_count["value"] = places
            canvas.yview_moveto(0)

        place_combo.bind("<<ComboboxSelected>>", load_rows)
        load_rows()

        total_var = tk.StringVar(value="Total: 100%")
        def update_total(*_):
            try:
                values = [float(v.get()) for v in percent_vars]
                total_var.set(f"Total: {sum(values):.2f}%")
            except (ValueError, tk.TclError):
                total_var.set("Total: —")
        for var in list(percent_vars):
            var.trace_add("write", update_total)
        # Rows are rebuilt on structure changes, so bind updates for newly built entries as well.
        original_load_rows = load_rows
        def reload_rows(event=None):
            original_load_rows(event)
            for var in list(percent_vars):
                var.trace_add("write", update_total)
            update_total()
        place_combo.unbind("<<ComboboxSelected>>")
        place_combo.bind("<<ComboboxSelected>>", reload_rows)

        total_label = ttk.Label(dlg, textvariable=total_var, font=("Segoe UI", 10, "bold"))
        total_label.pack(anchor="w", padx=14, pady=(0, 6))
        footer = ttk.Frame(dlg)
        footer.pack(fill="x", padx=14, pady=(0, 14))

        def save_split():
            try:
                places = int(selected_places.get())
                values = [float(var.get().strip()) for var in percent_vars]
                if len(values) != places:
                    raise ValueError("The split does not have one percentage for each paid place.")
                if any(not math.isfinite(v) or v <= 0 or v > 100 for v in values):
                    raise ValueError("Each paid place must have a percentage greater than 0 and no greater than 100.")
                total = sum(values)
                if abs(total - 100.0) > 0.01:
                    raise ValueError(f"The percentages must total 100%. Your current total is {total:.2f}%.")
                values = [round(v, 2) for v in values]
                values[-1] = round(values[-1] + 100.0 - sum(values), 2)
                self.payout_splits[places] = values
                self.payout_template_name = "Custom / edited"
                if hasattr(self, "payout_template_var"):
                    self.payout_template_var.set(self.payout_template_name)
                    if hasattr(self, "payout_template_combo"):
                        options = list(BUILT_IN_PAYOUT_TEMPLATE_LABELS) + [self.payout_template_name]
                        self.payout_template_combo.configure(values=options)
                self._save_data()
                self._refresh_all()
                dlg.destroy()
            except Exception as exc:
                messagebox.showerror("Invalid payout percentages", str(exc), parent=dlg)

        ttk.Button(footer, text="Save This Split", command=save_split).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side="right")
        update_total()

    def _paid_places_for_entries(self, entries):
        """Resolve paid places from automatic rules, a fixed target, and independent caps."""
        entries = max(0, int(entries))
        if entries < 2:
            places = 0
        elif self.payout_position_mode == "Target fixed number":
            # A fixed target overrides entry thresholds; only physical entry count limits it.
            places = min(entries, max(1, int(self.target_paid_places)))
        else:
            matches = [r for r in self.payout_rules if int(r["min_entries"]) <= entries <= int(r["max_entries"])]
            if matches:
                places = int(matches[0]["paid_places"])
            elif self.payout_rules:
                # Above the final threshold, use its configured paid-place value.
                places = int(max(self.payout_rules, key=lambda r: int(r["max_entries"]))["paid_places"])
            else:
                places = max(2, round(entries * 0.15))
            places = min(entries, max(0, places))
            if self.payout_position_mode == "Automatic with maximum cap":
                places = min(places, max(1, int(self.max_paid_places)))

        # The charity cap remains an independent additional restriction.
        if self.charity_mode and self.limit_charity_paid_places:
            places = min(places, max(1, int(self.charity_max_paid_places)))
        return min(entries, max(0, places))

    def _split_for_places(self, places):
        if places in self.payout_splits:
            split = list(self.payout_splits[places])
        elif str(places) in self.payout_splits:
            split = list(self.payout_splits[str(places)])
        else:
            split = self._generated_payout_split(places)
        if len(split) != places or abs(sum(float(v) for v in split) - 100.0) > 0.05:
            split = self._generated_payout_split(places)
        return split

    def _traditional_payout_rows(self, pool, places):
        """Build the existing all-percentage payout structure for safe fallback."""
        splits = self._split_for_places(places)
        increment = max(1, int(self.payout_rounding_increment))
        amounts = [int(math.floor(((pool * pct / 100) / increment) + 0.5)) * increment for pct in splits]
        # Reconcile the residual in first place so total awards equal the rounded pool.
        amounts[0] = int(amounts[0] + pool - sum(amounts))
        return list(zip(range(1, places + 1), splits, amounts))

    def _calculate_payouts(self):
        entries = self._counts()[1]
        self._mixed_payout_fallback_reason = ""
        self._mixed_payout_missing_config = False
        self._mixed_payout_missing_places = 0

        # Freeroll awards are host-funded and independent of entries and entry thresholds.
        if self.payout_mode == "Freeroll Fixed Prizes":
            places = self._effective_freeroll_places()
            raw_amounts = self.freeroll_payouts[:places]
            try:
                amounts = [int(float(value)) for value in raw_amounts]
            except (ValueError, TypeError):
                amounts = []
            if len(amounts) != places or any(amount <= 0 for amount in amounts):
                return entries, 0, 0, []
            pool = sum(amounts)
            shares = [(amount / pool) * 100.0 for amount in amounts] if pool > 0 else []
            return entries, pool, places, list(zip(range(1, places + 1), shares, amounts))

        pool = int(math.floor(self._entry_financials()["prize_pool"] + 0.5))
        places = self._paid_places_for_entries(entries)
        if places <= 0:
            return entries, pool, places, []

        mixed_config = None
        if self.payout_mode == "Mixed Fixed + Percentage":
            mixed_config = self.mixed_payouts.get(str(places), self.mixed_payouts.get(places))
            if not mixed_config:
                self._mixed_payout_missing_config = True
                self._mixed_payout_missing_places = places

        if pool <= 0:
            return entries, pool, places, []

        if self.payout_mode == "Mixed Fixed + Percentage":
            if not mixed_config:
                return entries, pool, places, self._traditional_payout_rows(pool, places)
            mixed_rows, reason = calculate_mixed_payout_awards(
                pool, mixed_config, self.payout_rounding_increment
            )
            if mixed_rows is not None:
                return entries, pool, places, mixed_rows
            self._mixed_payout_fallback_reason = reason or "The mixed payout did not pass safety checks."

        # Traditional mode always uses the percentage split, even if a saved mixed structure exists.
        return entries, pool, places, self._traditional_payout_rows(pool, places)

    def _refresh_payouts(self):
        if not hasattr(self, "payout_tree"):
            return
        for item in self.payout_rule_tree.get_children():
            self.payout_rule_tree.delete(item)
        for i, rule in enumerate(sorted(self.payout_rules, key=lambda r: int(r["min_entries"]))):
            self.payout_rule_tree.insert("", "end", iid=str(i), values=(rule["min_entries"], rule["max_entries"], rule["paid_places"]))

        entries, pool, places, payouts = self._calculate_payouts()
        position_mode = self.payout_position_mode
        if position_mode == "Target fixed number":
            position_help = f"Payout positions: target {self.target_paid_places} places"
        elif position_mode == "Automatic with maximum cap":
            position_help = f"Payout positions: automatic by entries, capped at {self.max_paid_places} places"
        else:
            position_help = "Payout positions: automatic by entry rules"
        if self.charity_mode and self.limit_charity_paid_places:
            position_help += f"; charity cap {self.charity_max_paid_places}"

        summary = ""
        if self.payout_mode == "Freeroll Fixed Prizes":
            summary = f"Entries: {entries}   |   Host-funded fixed prize pool: {money_whole(pool)}   |   Paid positions: {places}"
            mode_help = "FREEROLL FIXED PRIZES ACTIVE — each award is a fixed dollar amount and does not change with player or entry counts."
        elif self.payout_mode == "Mixed Fixed + Percentage":
            summary = f"Entries: {entries}   |   Estimated prize pool: {money_whole(pool)}   |   Paid positions: {places}"
            if self._mixed_payout_fallback_reason:
                summary += "   |   SAFE FALLBACK"
                mode_help = (
                    "SAFE FALLBACK ACTIVE — " + self._mixed_payout_fallback_reason +
                    " The traditional percentage split is being used for this calculation."
                )
            elif self._mixed_payout_missing_config:
                mode_help = (
                    f"MIXED FIXED + PERCENTAGE SELECTED — no mixed payout structure is saved for {self._mixed_payout_missing_places} paid places. "
                    "Traditional percentages are displayed until you click Edit Mixed Payouts… and save a structure for this place count."
                )
            else:
                mode_help = (
                    f"MIXED FIXED + PERCENTAGE ACTIVE — {position_help}. Fixed-dollar awards are deducted first; "
                    "percentage positions divide the remaining pool. If a safety rule fails, traditional percentages are used instead."
                )
        else:
            summary = f"Entries: {entries}   |   Estimated prize pool: {money_whole(pool)}   |   Paid positions: {places}"
            mode_help = (
                f"TRADITIONAL PERCENTAGES ACTIVE — {position_help}. "
                "The saved percentage split is applied to the entry-funded prize pool."
            )

        self.payout_summary.configure(text=summary)
        if hasattr(self, "payout_mode_info"):
            if self._mixed_payout_fallback_reason:
                foreground = "#b45309"
            elif self._mixed_payout_missing_config:
                foreground = "#b45309"
            else:
                foreground = "#52606d"
            self.payout_mode_info.configure(text=mode_help, foreground=foreground)
        if hasattr(self, "payout_mode_var") and self.payout_mode_var.get() != self.payout_mode:
            self.payout_mode_var.set(self.payout_mode)
        self._update_payout_mode_controls()
        for item in self.payout_tree.get_children():
            self.payout_tree.delete(item)
        for place, payout_rule, amount in payouts:
            self.payout_tree.insert(
                "", "end",
                values=(f"{place}{'st' if place==1 else 'nd' if place==2 else 'rd' if place==3 else 'th'} place",
                        format_payout_rule(payout_rule), money_whole(amount))
            )

    def _format_clock_duration(self, seconds):
        """Format timer values as MM:SS, using HH:MM:SS only when needed."""
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"

    def _sync_main_time_adjustment(self, seconds=None):
        """Keep the main-page slider tied to the current level and its duration."""
        scale = getattr(self, "main_time_slider_scale", None)
        if scale is None:
            return
        try:
            if not scale.winfo_exists():
                return
        except tk.TclError:
            return
        state = getattr(self, "main_time_slider_state", {})
        if state.get("level") != self.current_level:
            state["dragging"] = False
            state["level"] = self.current_level
        current = self._current_seconds() if seconds is None else max(0, int(seconds))
        duration = max(1, self._current_level_duration_seconds())
        bounded = max(0, min(duration, current))
        if state.get("dragging"):
            label = getattr(self, "main_time_adjust_value", None)
            if label is not None:
                label.configure(text=self._format_clock_duration(bounded))
            return
        state["syncing"] = True
        try:
            scale.configure(from_=0, to=duration)
            self.main_time_slider_var.set(bounded)
            self.main_time_adjust_value.configure(text=self._format_clock_duration(bounded))
        finally:
            state["syncing"] = False

    def _on_main_time_slider_changed(self, value):
        state = getattr(self, "main_time_slider_state", {})
        if state.get("syncing"):
            return
        state["dragging"] = True
        duration = max(1, self._current_level_duration_seconds())
        try:
            seconds = int(round(float(value)))
        except (TypeError, ValueError):
            return
        seconds = max(0, min(duration, seconds))
        self.set_remaining_seconds(seconds, save=False, record_history=False, refresh=False)
        self.timer_label.configure(text=self._format_clock_duration(seconds))
        self.main_time_adjust_value.configure(text=self._format_clock_duration(seconds))

    def _main_time_slider_pressed(self, _event=None):
        if hasattr(self, "main_time_slider_state"):
            self.main_time_slider_state["dragging"] = True

    def _main_time_slider_released(self, _event=None):
        # Let Tk finish applying the final slider value before saving it.
        try:
            self.after_idle(self._finish_main_time_slider)
        except tk.TclError:
            pass

    def _finish_main_time_slider(self):
        scale = getattr(self, "main_time_slider_scale", None)
        state = getattr(self, "main_time_slider_state", None)
        if scale is None or state is None:
            return
        duration = max(1, self._current_level_duration_seconds())
        try:
            seconds = int(round(float(scale.get())))
        except (TypeError, ValueError, tk.TclError):
            seconds = self._current_seconds()
        seconds = max(0, min(duration, seconds))
        state["dragging"] = False
        state["level"] = self.current_level
        self.set_remaining_seconds(seconds, save=True, record_history=True, refresh=True)

    def _adjust_main_level_time(self, delta_seconds):
        """Adjust remaining time in 30-second increments, clamped to this level."""
        duration = max(1, self._current_level_duration_seconds())
        current = max(0, min(duration, self._current_seconds()))
        seconds = max(0, min(duration, current + int(delta_seconds)))
        if seconds == current:
            self._sync_main_time_adjustment(seconds)
            return
        self.set_remaining_seconds(seconds, save=True, record_history=True, refresh=True)

    def _current_level(self):
        return self.levels[self.current_level]

    def _current_seconds(self):
        if self.running and self.deadline is not None:
            return max(0, int(self.deadline - time.monotonic()))
        return max(0, int(self.remaining_seconds))

    def _current_level_duration_seconds(self):
        """Return the configured duration of the current play level or break."""
        try:
            minutes = int(float(self._current_level().get("minutes", 20)))
        except (TypeError, ValueError):
            minutes = 20
        return max(0, minutes * 60)

    def set_remaining_seconds(self, seconds, save=True, record_history=True, refresh=True):
        """Set the current level's remaining time, preserving running/paused state."""
        try:
            seconds = int(round(float(seconds)))
        except (TypeError, ValueError):
            return self._current_seconds()
        seconds = max(0, min(24 * 60 * 60, seconds))
        self.remaining_seconds = seconds
        if self.running:
            self.deadline = time.monotonic() + seconds
        else:
            self.deadline = None
        if seconds > self.sound_warning_seconds:
            self._low_time_warned_level = None
        if record_history:
            self.history.append({
                "event": "timer_adjusted",
                "time": datetime.now().isoformat(timespec="seconds"),
                "level": self.current_level + 1,
                "remaining_seconds": seconds,
            })
        if save:
            self._save_data()
        if refresh:
            self._refresh_clock()
        return seconds

    def adjust_remaining_seconds(self, delta_seconds):
        """Add/subtract time in seconds without changing whether the clock is running."""
        return self.set_remaining_seconds(self._current_seconds() + int(delta_seconds))

    def start_clock(self):
        if self.running:
            return
        if self.remaining_seconds <= 0:
            self.remaining_seconds = self._current_level()["minutes"] * 60
        self.running = True
        self.deadline = time.monotonic() + self.remaining_seconds
        if self.start_time is None:
            self.start_time = datetime.now().isoformat(timespec="seconds")
        self.history.append({"event":"clock_started_or_resumed", "time":datetime.now().isoformat(timespec="seconds"),
                             "level":self.current_level+1})
        # The platform audio API can interrupt an asynchronous sound when another
        # sound is requested immediately afterward. Give the blind-start gong
        # priority over the optional generic clock-start sound so the gong remains
        # audible even when both events are configured.
        play_blind_start = (
            self._current_level().get("kind") != "Break"
            and not self._blind_start_sound_played
        )
        if play_blind_start:
            self._blind_start_sound_played = True
        self._play_event_sound("clock_started")
        if play_blind_start:
            self._play_event_sound("blind_level_starts")
        self._save_data()
        self._refresh_clock()

    def pause_clock(self):
        if self.running:
            self.remaining_seconds = self._current_seconds()
            self.running = False
            self.deadline = None
            self.history.append({"event":"clock_paused", "time":datetime.now().isoformat(timespec="seconds"),
                                 "level":self.current_level+1})
            self._save_data()
        self._refresh_clock()

    def reset_level(self):
        self.running = False
        self.deadline = None
        self._low_time_warned_level = None
        self._blind_start_sound_played = False
        self.remaining_seconds = int(self._current_level()["minutes"]) * 60
        self.history.append({"event":"level_reset", "time":datetime.now().isoformat(timespec="seconds"),
                             "level":self.current_level+1})
        self._save_data()
        self._refresh_all()

    def next_level(self, automatic=False):
        self.running = False
        self.deadline = None
        if self.current_level < len(self.levels)-1:
            self.current_level += 1
            self._low_time_warned_level = None
            self._blind_start_sound_played = False
            self.remaining_seconds = int(self._current_level()["minutes"]) * 60
            self.history.append({"event":"level_advanced", "time":datetime.now().isoformat(timespec="seconds"),
                                 "level":self.current_level+1, "automatic":automatic})
            if not automatic:
                self._play_event_sound("level_changed")
            self._save_data()
            self._refresh_all()
        else:
            self.remaining_seconds = 0
            self._refresh_all()
            if not automatic:
                messagebox.showinfo("Tournament", "You are already at the final level.")

    def previous_level(self):
        self.running = False
        self.deadline = None
        if self.current_level > 0:
            self.current_level -= 1
            self._low_time_warned_level = None
            self._blind_start_sound_played = False
            self.remaining_seconds = int(self._current_level()["minutes"]) * 60
            self.history.append({"event":"level_moved_back", "time":datetime.now().isoformat(timespec="seconds"),
                                 "level":self.current_level+1})
            self._play_event_sound("level_changed")
            self._save_data()
            self._refresh_all()

    def _tick(self):
        if self.running:
            secs = self._current_seconds()
            self.remaining_seconds = secs
            if 0 < secs <= self.sound_warning_seconds and self._low_time_warned_level != self.current_level:
                self._low_time_warned_level = self.current_level
                self._play_event_sound("low_time")
            if secs <= 0:
                expired_level = dict(self._current_level())
                self.running = False
                self.deadline = None
                self.remaining_seconds = 0
                self.history.append({"event":"level_timer_expired", "time":datetime.now().isoformat(timespec="seconds"),
                                     "level":self.current_level+1})

                # A break that pauses at its end uses the configured Break Ends sound.
                # A break that flows directly into the next blind level stays quiet here;
                # start_clock() then uses the existing Blind Level Starts sound preference.
                # A final break with no following row does not trigger either transition sound.
                expired_is_break = expired_level.get("kind") == "Break"
                has_next_level = self.current_level < len(self.levels) - 1
                should_pause_after_break = (
                    expired_is_break
                    and has_next_level
                    and bool(expired_level.get("pause_after", False))
                )
                if expired_is_break:
                    if should_pause_after_break:
                        self._play_event_sound("break_ends")
                else:
                    self._play_event_sound("level_ends")

                # No modal dialogs on expiration. Normally the schedule flows continuously.
                # If configured, a break ends by advancing to the next scheduled row and
                # leaving that row paused so the host may resume it when ready.
                if has_next_level:
                    # Regular blind levels always advance automatically. Only an
                    # individually checked break row can leave the next level paused.
                    self.next_level(automatic=True)
                    if should_pause_after_break:
                        self.running = False
                        self.deadline = None
                        self.history.append({
                            "event": "paused_after_break",
                            "time": datetime.now().isoformat(timespec="seconds"),
                            "level": self.current_level + 1,
                        })
                        self._save_data()
                        self._refresh_all()
                    else:
                        self.start_clock()
                else:
                    self._save_data()
                    self._refresh_all()
            self._refresh_clock()
        self.after_id = self.after(250, self._tick)

    def _apply_live_screen_settings(self):
        """Show only live-tournament features enabled in Tournament Settings."""
        if hasattr(self, "quick_controls_frame") and hasattr(self, "quick_groups_main"):
            self._layout_quick_groups(self.quick_controls_frame, self.quick_groups_main,
                                      include_rebuys=self.rebuy_enabled, include_addons=self.add_on_enabled)
        if hasattr(self, "rebuy_controls_page"):
            if self.rebuy_enabled:
                if not self.rebuy_controls_page.winfo_manager():
                    pack_options = {"fill": "x", "pady": (0, 4)}
                    if hasattr(self, "addon_controls_page") and self.addon_controls_page.winfo_manager():
                        pack_options["before"] = self.addon_controls_page
                    self.rebuy_controls_page.pack(**pack_options)
            elif self.rebuy_controls_page.winfo_manager():
                self.rebuy_controls_page.pack_forget()
        if hasattr(self, "record_reentry_button"):
            if self.rebuy_enabled:
                if not self.record_reentry_button.winfo_manager():
                    self.record_reentry_button.pack(side="left", padx=5, before=self.record_reentry_anchor)
            elif self.record_reentry_button.winfo_manager():
                self.record_reentry_button.pack_forget()
        if hasattr(self, "addon_controls_page"):
            if self.add_on_enabled:
                if not self.addon_controls_page.winfo_manager():
                    self.addon_controls_page.pack(fill="x")
            elif self.addon_controls_page.winfo_manager():
                self.addon_controls_page.pack_forget()

    def _adjust_main_prizes_wrap(self, event=None):
        """Keep payout text and pot headings readable as the main window is resized."""
        body = getattr(self, "main_prizes_body", None)
        label = getattr(self, "main_prizes_text_label", None)
        pot_box = getattr(self, "main_pot_box", None)
        if body is None or label is None or pot_box is None:
            return
        body_width = max(1, body.winfo_width())
        pot_width = max(1, pot_box.winfo_width())
        payout_width = max(80, min(600, body_width - pot_width - 22))
        label.configure(wraplength=payout_width)
        pot_heading_width = max(60, min(180, pot_width - 12))
        self.main_player_pot_header.configure(wraplength=pot_heading_width)
        self.main_benefit_header.configure(wraplength=pot_heading_width)

    def _time_pie_color(self, seconds):
        """Return the remaining-slice color with low-time warnings."""
        seconds = max(0, int(seconds))
        if seconds <= 20:
            return "#e03131"  # red: final twenty seconds
        if seconds < 60:
            return "#f0c419"  # yellow: under one minute
        return "#22a56b"      # green: normal time remaining

    def _draw_time_pie(self, canvas):
        """Draw current-level remaining time on the supplied canvas."""
        if canvas is None or not canvas.winfo_exists():
            return
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        if width < 40 or height < 40:
            return

        seconds = max(0, int(self._current_seconds()))
        duration = max(1, int(self._current_level_duration_seconds()))
        ratio = max(0.0, min(1.0, seconds / duration))
        # The remaining portion starts grey. The elapsed-time wedge is green
        # normally, yellow below one minute remaining, and red for the final
        # ten seconds.
        slice_color = self._time_pie_color(seconds)
        elapsed_ratio = 1.0 - ratio
        remaining_color = "#3b4652"
        canvas.configure(cursor="arrow")
        canvas.delete("all")

        diameter = max(28, min(width, height) - 20)
        left = (width - diameter) / 2
        top = (height - diameter) / 2
        right = left + diameter
        bottom = top + diameter
        canvas.create_oval(
            left, top, right, bottom,
            fill=remaining_color, outline=remaining_color, width=1
        )
        if elapsed_ratio >= 0.999:
            canvas.create_oval(
                left, top, right, bottom,
                fill=slice_color, outline=slice_color, width=1
            )
        elif elapsed_ratio > 0:
            canvas.create_arc(
                left, top, right, bottom, start=90, extent=-359.99 * elapsed_ratio,
                style=tk.PIESLICE, fill=slice_color, outline=slice_color, width=1
            )
        canvas.create_oval(left, top, right, bottom, outline="#75818b", width=2)

        percentage_text = f"{int(math.floor(ratio * 100 + 0.5))}%"
        text_color = "#17232c" if slice_color == "#f0c419" else "#ffffff"
        canvas.create_text(
            (left + right) / 2, (top + bottom) / 2,
            text=percentage_text, fill=text_color,
            font=("Segoe UI", max(12, int(diameter * 0.15)), "bold")
        )
        self.fullscreen_time_pie_current_color = slice_color
        self.fullscreen_time_pie_ratio = ratio
        self.fullscreen_time_pie_percentage_text = percentage_text

    def _refresh_clock(self):
        level = self._current_level()
        secs = self._current_seconds()
        self.timer_label.configure(text=self._format_clock_duration(secs))
        self._sync_main_time_adjustment(secs)
        is_break = level.get("kind") == "Break"
        self.level_label.configure(text=f"{level['name']}  •  {'BREAK' if is_break else 'LEVEL '+str(self.current_level+1)}")
        self.status_label.configure(text="RUNNING" if self.running else "PAUSED",
                                    fg="#167a4a" if self.running else "#a33")
        self.blinds_label.configure(text="BREAK" if is_break else f"{int(level['sb']):,} / {int(level['bb']):,}")
        if self.current_level < len(self.levels)-1:
            nxt = self.levels[self.current_level+1]
            label = f"Next: {nxt['name']} — {nxt['minutes']} min"
            if nxt.get("kind") == "Break":
                label += " (Break)"
            else:
                label += f" · Blinds {int(nxt['sb']):,} / {int(nxt['bb']):,}"
            self.next_label.configure(text=label)
        else:
            self.next_label.configure(text="Final scheduled level")
        self._refresh_quick_stats()

    def _refresh_all(self):
        self._refresh_clock()
        self._apply_live_screen_settings()
        self._refresh_levels()
        self._refresh_players()
        self._refresh_reports()
        if hasattr(self, "anonymous_count_label"):
            active_count, entry_count, rebuy_count = self._counts()
            counter_parts = [f"Active players: {active_count}"]
            if self.rebuy_enabled:
                counter_parts.append(f"Rebuys: {rebuy_count}")
            if self.add_on_enabled:
                counter_parts.append(f"Add-ons: {self.anonymous_addons}")
            counter_parts.append(f"Entries: {entry_count}")
            self.anonymous_count_label.configure(text="  |  ".join(counter_parts))
        self._refresh_payouts()

    def _refresh_levels(self):
        if not hasattr(self, "level_tree"):
            return
        try:
            previous_selection = [int(iid) for iid in self.level_tree.selection()]
        except (TypeError, ValueError, tk.TclError):
            previous_selection = []
        for item in self.level_tree.get_children():
            self.level_tree.delete(item)
        for i, level in enumerate(self.levels):
            is_break = level.get("kind") == "Break"
            pause_cell = ("☑" if bool(level.get("pause_after", False)) else "☐") if is_break else "—"
            self.level_tree.insert("", "end", iid=str(i), values=(
                i+1, level["name"], level.get("kind","Play"), level["minutes"],
                "—" if is_break else f"{int(level['sb']):,}",
                "—" if is_break else f"{int(level['bb']):,}", pause_cell
            ))
        if self.levels:
            valid = [str(i) for i in previous_selection if 0 <= i < len(self.levels)]
            self.level_tree.selection_set(*(valid if valid else [str(self.current_level)]))

    def _refresh_players(self):
        if not hasattr(self, "player_tree"):
            return
        for item in self.player_tree.get_children():
            self.player_tree.delete(item)
        for p in self.players:
            self.player_tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"], p["name"], p.get("entries",1), p.get("status","Active"),
                p.get("finish_place",""), p.get("notes","")
            ))

    def _counts(self):
        if self.tracking_mode == "Entry count only":
            active = self.anonymous_active_players
            reentries = self.anonymous_reentries if self.rebuy_enabled else 0
            entries = self.anonymous_original_entries + reentries
        else:
            active = sum(1 for p in self.players if p.get("status","Active") == "Active")
            if self.rebuy_enabled:
                reentries = sum(max(0, int(p.get("entries",1))-1) for p in self.players)
                entries = len(self.players) + reentries
            else:
                reentries = 0
                entries = len(self.players)
        return active, entries, reentries

    def _entry_financials(self):
        # The selected tracking mode is the active source for entry and financial counts.
        if self.tracking_mode == "Entry count only":
            original_entries = self.anonymous_original_entries
            reentries = self.anonymous_reentries if self.rebuy_enabled else 0
            addons = self.anonymous_addons if self.add_on_enabled else 0
            total_entries = original_entries + reentries
        else:
            original_entries = len(self.players)
            reentries = (sum(max(0, int(p.get("entries",1))-1) for p in self.players)
                         if self.rebuy_enabled else 0)
            addons = self.anonymous_addons if self.add_on_enabled else 0
            total_entries = original_entries + reentries
        collected = (original_entries * self.buy_in
                     + reentries * self.reentry_fee
                     + addons * self.add_on_fee)
        # House fee is a Home Game-only rule, even if an older save contains a value.
        effective_house_fee = self.house_fee if self.tournament_type == "Home Game" else 0.0
        house = original_entries * effective_house_fee
        charity = 0.0
        if self.charity_mode:
            if self.charity_method == "Percentage of each entry":
                charity = collected * self.charity_value / 100.0
            else:
                # A fixed Benefit Pot amount applies only to entries that actually collect a fee.
                # This allows charity freerolls: free original entries contribute $0, while paid
                # re-entries can still contribute the configured fixed amount.
                paid_original_entries = original_entries if self.buy_in > 0 else 0
                paid_reentries = reentries if self.reentry_fee > 0 else 0
                charity = (paid_original_entries + paid_reentries) * self.charity_value
        prize_pool = max(0.0, collected - house - charity)
        return {"original_entries": original_entries, "reentries": reentries, "addons": addons,
                "total_entries": total_entries, "collected": collected,
                "house": house, "charity": charity, "prize_pool": prize_pool}

    def _pool(self):
        if self.payout_mode == "Freeroll Fixed Prizes":
            amounts = self._effective_freeroll_amounts()
            return sum(amounts) if amounts else 0
        return self._entry_financials()["prize_pool"]

    def _refresh_quick_stats(self):
        if not hasattr(self, "dashboard_vars"):
            return
        dashboard_values = self._dashboard_texts()
        for key, value in dashboard_values.items():
            if key in self.dashboard_vars:
                self.dashboard_vars[key].set(value)
        benefit_is_present = bool(dashboard_values.get("benefit_pot", ""))
        if hasattr(self, "main_benefit_header"):
            if benefit_is_present:
                if not self.main_benefit_header.winfo_manager():
                    self.main_benefit_header.pack(before=self.main_player_pot_header, fill="x", pady=(5, 2))
                    self.main_benefit_value.pack(before=self.main_player_pot_header, fill="x", pady=(0, 6))
            else:
                if self.main_benefit_header.winfo_manager():
                    self.main_benefit_header.pack_forget()
                if self.main_benefit_value.winfo_manager():
                    self.main_benefit_value.pack_forget()

    def _refresh_reports(self):
        if not hasattr(self, "report_text"):
            return
        active, entries, reentries = self._counts()
        eliminated = (max(0, self.anonymous_original_entries - self.anonymous_active_players)
                      if self.tracking_mode == "Entry count only"
                      else sum(1 for p in self.players if p.get("status") == "Eliminated"))
        financials = self._entry_financials()
        total_collected = financials["collected"]
        pool = self._pool()
        current = self._current_level()
        lines = [
            f"{self.tournament_name}",
            "=" * max(10, len(self.tournament_name)),
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Clock status: {'RUNNING' if self.running else 'PAUSED'}",
            f"Current level: {self.current_level+1} of {len(self.levels)} — {current['name']}",
            f"Current timer: {self._current_seconds()//60:02d}:{self._current_seconds()%60:02d}",
            ("Current blinds: Break" if current.get("kind") == "Break" else
             (f"Current blinds: {int(current['sb']):,} / {int(current['bb']):,} (ante {int(current.get('ante',0)):,})"
              if self.ante_enabled else f"Current blinds: {int(current['sb']):,} / {int(current['bb']):,}")),
            "",
            "TOURNAMENT STATISTICS",
            "-" * 24,
            f"Initial entries recorded: {self.anonymous_original_entries if self.tracking_mode == 'Entry count only' else len(self.players)}",
            f"Players remaining: {active}",
            f"Total paid entries (including rebuys): {entries}",
            f"Players eliminated: {eliminated}",
            f"Total entries (including re-entries): {entries}",
            f"Re-entries recorded: {reentries}",
            f"Buy-in: {money(self.buy_in)}",
            f"Re-buy fee ({'enabled' if self.rebuy_enabled else 'disabled'}): {money(self.reentry_fee)}",
            f"Add-on fee: {money(self.add_on_fee)}",
            f"Add-ons recorded: {financials['addons']}",
            f"Add-on collections: {money(financials['addons'] * self.add_on_fee)}",
            f"House fee per original entry (Home Game only): {money(self.house_fee if self.tournament_type == 'Home Game' else 0.0)}",
            f"Tournament type: {self.tournament_type}",
            f"Charity event enabled: {'Yes' if self.charity_mode else 'No'}",
            f"Charity holdback method: {self.charity_method}",
            "Charity holdback applies to every entry (original and re-entry): Yes" if self.charity_mode else "Charity holdback applies to every entry (original and re-entry): No",
            f"Charity holdback value: {self.charity_value:g}{'%' if self.charity_method == 'Percentage of each entry' else ' dollars per entry'}",
            f"Gross money collected: {money(total_collected)}",
            f"House allocation: {money(financials['house'])}",
            f"Charity allocation: {money(financials['charity'])}",
            f"Charity paid-place cap: {'Enabled (max ' + str(self.charity_max_paid_places) + ')' if self.charity_mode and self.limit_charity_paid_places else 'Disabled'}",
            f"Payout mode: {self.payout_mode}",
            f"Estimated prize pool / payout total: {money(pool)}",
            *([f"Entry-funded net pool after fees/benefit: {money(financials['prize_pool'])}"]
              if self.payout_mode == "Freeroll Fixed Prizes" else []),
            "",
            "BLIND STRUCTURE",
            "-" * 24,
        ]
        for i, lev in enumerate(self.levels):
            prefix = "→ " if i == self.current_level else "  "
            if lev.get("kind") == "Break":
                detail = f"{lev['name']}: {lev['minutes']} min — BREAK"
            else:
                detail = f"{lev['name']}: {lev['minutes']} min — {int(lev['sb']):,}/{int(lev['bb']):,}"
            lines.append(prefix + detail)
        entries_for_payout, pool_for_payout, paid_places, payout_rows = self._calculate_payouts()
        lines.extend(["", "PAYOUT ESTIMATE", "-" * 24,
                      f"Payout mode: {self.payout_mode}",
                      (f"Entries used for payout threshold: {entries_for_payout}"
                       if self.payout_mode != "Freeroll Fixed Prizes" else
                       f"Entries recorded (informational only; payouts are fixed): {entries_for_payout}"),
                      f"Paid positions: {paid_places}",
                      f"Paid-position mode: {self.payout_position_mode}",
                      f"Estimated prize pool / payout total: {money_whole(pool_for_payout)}"])
        if self._mixed_payout_fallback_reason:
            lines.append("SAFE FALLBACK: traditional percentage split used — " + self._mixed_payout_fallback_reason)
        elif self._mixed_payout_missing_config:
            lines.append(f"MIXED PAYOUTS NOT CONFIGURED for {self._mixed_payout_missing_places} paid places; traditional split shown until configured.")
        for place, payout_rule, amount in payout_rows:
            lines.append(f"{place}. {format_payout_rule(payout_rule)} — {money_whole(amount)}")
        lines.extend(["", "PLAYER AND ENTRY COUNTS", "-" * 24])
        lines.append(f"Tracking mode: {self.tracking_mode}")
        if self.tracking_mode == "Entry count only":
            lines.append(f"Anonymous original players registered: {self.anonymous_original_entries}")
            lines.append(f"Anonymous active players: {self.anonymous_active_players}")
            lines.append(f"Anonymous re-entries / rebuys: {self.anonymous_reentries}")
            lines.append(f"Anonymous add-ons counted: {financials['addons']}")
            if not self.add_on_enabled and self.anonymous_addons:
                lines.append(f"Saved add-on count (currently disabled): {self.anonymous_addons}")
            lines.append("Player, rebuy, and add-on counts are tracked independently.")
        elif self.players:
            for p in self.players:
                lines.append(f"#{p['id']} {p['name']} | entries: {p.get('entries',1)} | {p.get('status','Active')} | finish: {p.get('finish_place','')}")
        else:
            lines.append("No players registered yet.")
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", "\n".join(lines))
        self.report_text.configure(state="disabled")

    def _selected_level_index(self):
        selected = self.level_tree.selection()
        return int(selected[0]) if selected else None

    def _level_dialog(self, initial=None, kind="Play"):
        dlg = tk.Toplevel(self)
        dlg.title("Edit Level" if initial else "Add Level")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        vals = initial or {"name":"", "minutes":20, "sb":100, "bb":200, "ante":0, "kind":kind}
        vars_ = {key: tk.StringVar(value=str(vals.get(key, default))) for key, default in
                 [("name",""),("minutes",20),("sb",0 if kind=="Break" else 100),
                  ("bb",0 if kind=="Break" else 200),("ante",0),("kind",kind)]}
        fields = [("Name", "name"), ("Duration (minutes)", "minutes")]
        if kind != "Break" and vals.get("kind") != "Break":
            fields += [("Small blind", "sb"), ("Big blind", "bb")]
        for r, (label, key) in enumerate(fields):
            ttk.Label(dlg, text=label).grid(row=r, column=0, sticky="w", padx=12, pady=6)
            ttk.Entry(dlg, textvariable=vars_[key], width=22).grid(row=r, column=1, padx=12, pady=6)
        result = {}
        def save():
            try:
                name = vars_["name"].get().strip() or ("Break" if kind=="Break" else f"Level {len(self.levels)+1}")
                minutes = int(vars_["minutes"].get())
                if minutes < 1 or minutes > 240:
                    raise ValueError("Duration must be between 1 and 240 minutes.")
                k = "Break" if kind=="Break" or vals.get("kind")=="Break" else "Play"
                sb = 0 if k=="Break" else int(vars_["sb"].get())
                bb = 0 if k=="Break" else int(vars_["bb"].get())
                ante = 0 if k=="Break" else int(vars_["ante"].get())
                if min(sb,bb) < 0:
                    raise ValueError("Blind values cannot be negative.")
                if k=="Play" and bb <= 0:
                    raise ValueError("Big blind must be greater than zero.")
                result.update({"name":name,"minutes":minutes,"sb":sb,"bb":bb,"ante":ante,"kind":k})
                if k == "Break":
                    result["pause_after"] = bool(vals.get("pause_after", False))
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Invalid level", str(e), parent=dlg)
        buttons = ttk.Frame(dlg)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=12)
        ttk.Button(buttons, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)
        self.wait_window(dlg)
        return result or None

    def _fill_durations(self, kind, value_text):
        try:
            minutes = int(value_text)
            if minutes < 1 or minutes > 240:
                raise ValueError("Duration must be between 1 and 240 minutes.")
        except Exception as e:
            messagebox.showerror("Invalid duration", str(e), parent=self)
            return
        updated = 0
        for level in self.levels:
            is_break = level.get("kind") == "Break"
            if (kind == "Break" and is_break) or (kind == "Play" and not is_break):
                level["minutes"] = minutes
                updated += 1
        if not updated:
            messagebox.showinfo("No matching rows", f"There are no {kind.lower()} rows to update.", parent=self)
            return
        if self.current_level < len(self.levels) and self.levels[self.current_level].get("kind") == kind and not self.running:
            self.remaining_seconds = minutes * 60
        self.history.append({
            "event": "bulk_duration_updated", "kind": kind, "minutes": minutes,
            "rows_updated": updated, "time": datetime.now().isoformat(timespec="seconds")
        })
        self._save_data()
        self._refresh_all()
        messagebox.showinfo("Durations updated", f"Set {updated} {kind.lower()} row(s) to {minutes} minutes.", parent=self)

    def fill_play_durations(self):
        self._fill_durations("Play", self.play_duration_var.get())

    def fill_break_durations(self):
        self._fill_durations("Break", self.break_duration_var.get())

    def fill_selected_durations(self, kind):
        """Apply one duration only to selected rows of the requested type."""
        variable = self.play_duration_var if kind == "Play" else self.break_duration_var
        try:
            minutes = int(variable.get())
            if not 1 <= minutes <= 240:
                raise ValueError("Duration must be between 1 and 240 minutes.")
        except Exception as exc:
            messagebox.showerror("Invalid duration", str(exc), parent=self)
            return
        selected = sorted({int(iid) for iid in self.level_tree.selection() if iid.isdigit()})
        applicable = [i for i in selected if 0 <= i < len(self.levels)
                      and ((kind == "Break") == (self.levels[i].get("kind") == "Break"))]
        if not applicable:
            messagebox.showinfo("Select matching rows", f"Select one or more {kind.lower()} rows first.", parent=self)
            return
        for index in applicable:
            self.levels[index]["minutes"] = minutes
        if self.current_level in applicable and not self.running:
            self.remaining_seconds = minutes * 60
        self.history.append({
            "event": "selected_duration_updated", "kind": kind, "minutes": minutes,
            "row_indexes": [i + 1 for i in applicable], "time": datetime.now().isoformat(timespec="seconds")
        })
        self._save_data()
        self._refresh_all()
        messagebox.showinfo("Durations updated", f"Set {len(applicable)} selected {kind.lower()} row(s) to {minutes} minutes.", parent=self)

    def add_level(self):
        result = self._level_dialog()
        if result:
            self.levels.append(result)
            self._save_data()
            self._refresh_all()

    def _choose_import_sheet(self, sheets, title):
        """Show a worksheet picker when an Excel file contains multiple populated sheets."""
        if len(sheets) == 1:
            name = next(iter(sheets))
            return name, sheets[name]

        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        ttk.Label(dlg, text="Select the worksheet to import:").pack(anchor="w", padx=12, pady=(12, 6))
        listbox = tk.Listbox(dlg, height=min(12, len(sheets)), width=42, exportselection=False)
        listbox.pack(fill="both", expand=True, padx=12, pady=4)
        names = list(sheets)
        for name in names:
            listbox.insert("end", name)
        listbox.selection_set(0)
        result = {}

        def accept(event=None):
            selected = listbox.curselection()
            if selected:
                name = names[selected[0]]
                result["sheet"] = (name, sheets[name])
                dlg.destroy()

        buttons = ttk.Frame(dlg)
        buttons.pack(pady=(4, 12))
        ttk.Button(buttons, text="Import Selected Sheet", command=accept).pack(side="left", padx=5)
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)
        listbox.bind("<Double-1>", accept)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        self.wait_window(dlg)
        return result.get("sheet")

    def _read_import_rows(self, title):
        """Read a CSV/TSV/text file or an .xlsx worksheet into a list of cell rows."""
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[
                ("Excel workbook", "*.xlsx"),
                ("CSV or text file", "*.csv *.tsv *.txt"),
                ("All supported files", "*.xlsx *.csv *.tsv *.txt"),
                ("All files", "*.*"),
            ],
            parent=self,
        )
        if not path:
            return None, None
        extension = os.path.splitext(path)[1].lower()
        try:
            if extension == ".xlsx":
                sheets = read_xlsx_sheets(path)
                chosen = self._choose_import_sheet(sheets, title)
                if chosen is None:
                    return None, None
                _sheet_name, rows = chosen
                return path, rows
            if extension not in (".csv", ".tsv", ".txt"):
                raise ValueError("Please choose an .xlsx workbook, .csv, .tsv, or .txt file. Older .xls files must first be saved as .xlsx or .csv.")
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                sample = f.read(8192)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                except csv.Error:
                    dialect = csv.excel_tab if extension == ".tsv" else csv.excel
                rows = [list(row) for row in csv.reader(f, dialect)]
            return path, rows
        except Exception as e:
            messagebox.showerror("Import failed", f"Could not read the selected file:\n{e}", parent=self)
            return None, None

    @staticmethod
    def _column_index(headers, aliases):
        alias_set = {normalize_header(x) for x in aliases}
        for index, header in enumerate(headers):
            if normalize_header(header) in alias_set:
                return index
        return None

    @staticmethod
    def _cell(row, index, default=""):
        if index is None or index >= len(row):
            return default
        value = row[index]
        return str(value).strip() if value is not None else default

    @staticmethod
    def _import_integer(value, label, default=None):
        text = str(value or "").strip().replace(",", "").replace("$", "")
        if not text:
            if default is not None:
                return default
            raise ValueError(f"{label} is required.")
        try:
            numeric = float(text)
        except ValueError:
            raise ValueError(f"{label} must be a whole number; found '{value}'.")
        if numeric < 0 or numeric != int(numeric):
            raise ValueError(f"{label} must be a nonnegative whole number; found '{value}'.")
        return int(numeric)

    def _parse_player_rows(self, rows):
        rows = [list(row) for row in rows if any(str(cell or "").strip() for cell in row)]
        if not rows:
            raise ValueError("The selected file does not contain any player rows.")

        name_aliases = {"name", "player", "playername", "fullname", "fullplayername", "participant", "participantname"}
        first_aliases = {"firstname", "givenname", "playerfirstname"}
        last_aliases = {"lastname", "surname", "familyname", "playerlastname"}
        entry_aliases = {"entries", "entry", "entrycount", "totalentries", "numentries", "numberofentries", "totalbuyins", "buyins"}
        rebuy_aliases = {"rebuys", "rebuy", "rebuycount", "reentry", "reentries", "reentrycount", "reentriescount"}
        status_aliases = {"status", "playerstatus", "state"}
        finish_aliases = {"finishplace", "finishposition", "place", "position", "rank"}
        notes_aliases = {"notes", "note", "comments", "comment"}
        registered_aliases = {"registered", "registrationdate", "registeredat", "timestamp"}
        header_tokens = name_aliases | first_aliases | last_aliases | entry_aliases | rebuy_aliases | status_aliases | finish_aliases | notes_aliases | registered_aliases | {"id", "playerid"}
        def is_player_header(row):
            row_headers = [normalize_header(v) for v in row]
            has_name = any(h in name_aliases | first_aliases | last_aliases for h in row_headers)
            has_supporting_field = any(h in (entry_aliases | rebuy_aliases | status_aliases | finish_aliases |
                                              notes_aliases | registered_aliases | {"id", "playerid"})
                                       for h in row_headers)
            has_name_heading = any(h in {"name", "player", "playername", "fullname"} for h in row_headers)
            return has_name and (has_supporting_field or len(rows) == 1 or row is rows[0] or has_name_heading)

        header_row_index = next((idx for idx, row in enumerate(rows[:10]) if is_player_header(row)), None)
        has_header = header_row_index is not None

        if has_header:
            headers = rows[header_row_index]
            name_idx = self._column_index(headers, name_aliases)
            first_idx = self._column_index(headers, first_aliases)
            last_idx = self._column_index(headers, last_aliases)
            if name_idx is None and first_idx is None and last_idx is None:
                raise ValueError("Could not find a player-name column. Use a 'Name' or 'Player' column, or separate 'First Name' and 'Last Name' columns.")
            entries_idx = self._column_index(headers, entry_aliases)
            rebuys_idx = self._column_index(headers, rebuy_aliases)
            status_idx = self._column_index(headers, status_aliases)
            finish_idx = self._column_index(headers, finish_aliases)
            notes_idx = self._column_index(headers, notes_aliases)
            registered_idx = self._column_index(headers, registered_aliases)
            data_rows = rows[header_row_index + 1:]
        else:
            # A plain text/CSV list with one name per row is also a supported format.
            if any(len(row) > 1 and any(str(x or "").strip() for x in row[1:]) for row in rows):
                raise ValueError("This player file has multiple columns but no recognized header row. Add a 'Name' or 'Player' header, or use the program's exported player CSV.")
            name_idx, first_idx, last_idx = 0, None, None
            entries_idx = rebuys_idx = status_idx = finish_idx = notes_idx = registered_idx = None
            data_rows = rows

        parsed = []
        now = datetime.now().isoformat(timespec="seconds")
        for row_number, row in enumerate(data_rows, start=(header_row_index + 2) if has_header else 1):
            if name_idx is not None:
                name = self._cell(row, name_idx)
            else:
                name = ""
            if not name:
                first = self._cell(row, first_idx)
                last = self._cell(row, last_idx)
                name = " ".join(part for part in (first, last) if part)
            if not name:
                continue

            if entries_idx is not None and self._cell(row, entries_idx):
                entries = self._import_integer(self._cell(row, entries_idx), f"Entries on row {row_number}")
                if entries < 1:
                    raise ValueError(f"Entries on row {row_number} must be at least 1.")
            elif rebuys_idx is not None and self._cell(row, rebuys_idx):
                entries = 1 + self._import_integer(self._cell(row, rebuys_idx), f"Rebuys on row {row_number}")
            else:
                entries = 1

            status_raw = normalize_header(self._cell(row, status_idx))
            if status_raw in {"eliminated", "busted", "out", "finished", "inactive", "knockedout", "knockedoutofevent"}:
                status = "Eliminated"
            else:
                status = "Active"
            parsed.append({
                "name": name,
                "entries": entries,
                "status": status,
                "finish_place": self._cell(row, finish_idx),
                "notes": self._cell(row, notes_idx),
                "registered": self._cell(row, registered_idx) or now,
            })
        if not parsed:
            raise ValueError("No player names were found in the selected file.")
        return parsed

    def import_players(self):
        path, rows = self._read_import_rows("Import Player List")
        if not path:
            return
        try:
            imported = self._parse_player_rows(rows)
        except Exception as e:
            messagebox.showerror("Invalid player list", str(e), parent=self)
            return

        replace = messagebox.askyesnocancel(
            "Import Player List",
            f"Found {len(imported)} player(s).\n\n"
            "Yes = replace the existing player list\n"
            "No = append these players to the existing list\n"
            "Cancel = do not import",
            parent=self,
        )
        if replace is None:
            return

        switch_to_named = False
        if self.tracking_mode == "Entry count only":
            switch_to_named = messagebox.askyesno(
                "Use imported names for tournament counts?",
                "The tournament is currently in Entry count only mode. The imported names will be stored in the roster, but they will not affect active-player, entry, or payout totals unless you switch to Named players mode.\n\nSwitch to Named players mode now?",
                parent=self,
            )

        if replace:
            self.players = []
            next_id = 1
        else:
            existing_ids = [int(p.get("id", 0)) for p in self.players]
            next_id = max(int(self.next_player_id), max(existing_ids, default=0) + 1)
        for imported_player in imported:
            player = dict(imported_player)
            player["id"] = next_id
            self.players.append(player)
            next_id += 1
        self.next_player_id = next_id
        if switch_to_named:
            self.tracking_mode = "Named players"
        self.history.append({
            "event": "player_list_imported", "file": os.path.basename(path),
            "count": len(imported), "replaced_existing": bool(replace),
            "time": datetime.now().isoformat(timespec="seconds"),
        })
        self._save_data()
        self._refresh_all()
        messagebox.showinfo(
            "Player Import Complete",
            f"Imported {len(imported)} player(s) from {os.path.basename(path)}.\n\n"
            f"Player list now contains {len(self.players)} record(s).",
            parent=self,
        )

    def _parse_level_rows(self, rows):
        rows = [list(row) for row in rows if any(str(cell or "").strip() for cell in row)]
        if len(rows) < 2:
            raise ValueError("The blind-structure file must include a header row and at least one data row.")
        name_aliases = {"name", "level", "levelname", "levelbreak", "round", "roundname", "blindlevel", "stage"}
        order_aliases = {"order", "sequence", "seq", "number", "levelnumber", "roundnumber", "levelorder"}
        kind_aliases = {"kind", "type", "leveltype", "roundtype", "stagetype", "periodtype"}
        minutes_aliases = {"minutes", "minute", "duration", "durationminutes", "durationmin", "levelduration", "leveltime", "time", "timeinminutes", "lengthminutes"}
        sb_aliases = {"sb", "smallblind", "smallblindamount", "small"}
        bb_aliases = {"bb", "bigblind", "bigblindamount", "big"}
        blinds_aliases = {"blinds", "blindlevels", "blind"}
        ante_aliases = {"ante", "anteamount", "levelante"}
        break_aliases = {"break", "isbreak", "breaklevel"}
        pause_aliases = {"pause", "pauseafter", "pauseafterbreak", "pauseatend", "pauseattheend", "pauseafterthisbreak"}

        header_row_index = None
        for candidate_index, candidate in enumerate(rows[:10]):
            duration_col = self._column_index(candidate, minutes_aliases)
            has_separate_blinds = (self._column_index(candidate, sb_aliases) is not None and
                                   self._column_index(candidate, bb_aliases) is not None)
            has_combined_blinds = self._column_index(candidate, blinds_aliases) is not None
            if duration_col is not None and (has_separate_blinds or has_combined_blinds):
                header_row_index = candidate_index
                break
        if header_row_index is None:
            raise ValueError("Could not identify the header row. Include a duration column and either SB/BB columns or a combined Blinds column.")
        headers = rows[header_row_index]
        data_rows = rows[header_row_index + 1:]

        name_idx = self._column_index(headers, name_aliases)
        order_idx = self._column_index(headers, order_aliases)
        kind_idx = self._column_index(headers, kind_aliases)
        minutes_idx = self._column_index(headers, minutes_aliases)
        sb_idx = self._column_index(headers, sb_aliases)
        bb_idx = self._column_index(headers, bb_aliases)
        blinds_idx = self._column_index(headers, blinds_aliases)
        ante_idx = self._column_index(headers, ante_aliases)
        break_idx = self._column_index(headers, break_aliases)
        pause_idx = self._column_index(headers, pause_aliases)

        if minutes_idx is None:
            raise ValueError("Could not find a duration column. Use a header such as 'minutes' or 'duration'.")
        if (sb_idx is None or bb_idx is None) and blinds_idx is None:
            raise ValueError("Could not find small- and big-blind columns. Use 'sb' and 'bb', 'Small Blind' and 'Big Blind', or a combined 'Blinds' column such as 100/200.")
        if name_idx is None and order_idx is None:
            # Level rows can still be imported if their first column is the level name/number.
            name_idx = 0

        def read_duration(raw, row_number):
            text = str(raw or "").strip().lower()
            text = re.sub(r"\s*(minutes?|mins?)\s*$", "", text)
            if ":" in text:
                parts = text.split(":")
                if len(parts) == 2 and all(part.isdigit() for part in parts):
                    hours, minutes = int(parts[0]), int(parts[1])
                    if minutes >= 60:
                        raise ValueError(f"Duration on row {row_number} has invalid minutes in '{raw}'.")
                    value = hours * 60 + minutes
                else:
                    raise ValueError(f"Duration on row {row_number} must be minutes or HH:MM; found '{raw}'.")
            else:
                value = self._import_integer(text, f"Duration on row {row_number}")
            if not 1 <= value <= 240:
                raise ValueError(f"Duration on row {row_number} must be from 1 to 240 minutes; found '{raw}'.")
            return value

        parsed = []
        play_count = break_count = 0
        for row_number, row in enumerate(data_rows, start=header_row_index + 2):
            if not any(str(cell or "").strip() for cell in row):
                continue
            duration_raw = self._cell(row, minutes_idx)
            if not duration_raw:
                raise ValueError(f"Duration is blank on row {row_number}.")
            minutes = read_duration(duration_raw, row_number)
            raw_name = self._cell(row, name_idx)
            raw_kind = normalize_header(self._cell(row, kind_idx))
            break_flag = normalize_header(self._cell(row, break_idx)) in {"yes", "true", "1", "y", "break"}
            kind_is_break = break_flag or raw_kind in {"break", "breaktime", "pause", "intermission"} or normalize_header(raw_name).startswith("break")

            if kind_is_break:
                kind = "Break"
                break_count += 1
                sb = bb = ante = 0
                name = raw_name or f"Break {break_count}"
                if not normalize_header(name).startswith("break"):
                    name = f"Break {name}"
            else:
                kind = "Play"
                play_count += 1
                if sb_idx is not None and bb_idx is not None:
                    sb = self._import_integer(self._cell(row, sb_idx), f"Small blind on row {row_number}", default=0)
                    bb = self._import_integer(self._cell(row, bb_idx), f"Big blind on row {row_number}", default=0)
                else:
                    blind_text = self._cell(row, blinds_idx)
                    match = re.fullmatch(r"\s*([\d,$]+(?:\.0+)?)\s*(?:/|-|–|—)\s*([\d,$]+(?:\.0+)?)\s*", blind_text)
                    if not match:
                        raise ValueError(f"Blinds on row {row_number} should look like '50/100'; found '{blind_text}'.")
                    sb = self._import_integer(match.group(1), f"Small blind on row {row_number}")
                    bb = self._import_integer(match.group(2), f"Big blind on row {row_number}")
                ante = self._import_integer(self._cell(row, ante_idx), f"Ante on row {row_number}", default=0)
                name = raw_name or f"Level {play_count}"
                if name.isdigit():
                    name = f"Level {name}"
            pause_after = False
            if kind == "Break" and pause_idx is not None:
                pause_raw = normalize_header(self._cell(row, pause_idx))
                if pause_raw in {"yes", "true", "1", "y", "pause", "checked", "x"}:
                    pause_after = True
                elif pause_raw not in {"", "no", "false", "0", "n", "unchecked", "dontpause", "never"}:
                    raise ValueError(
                        f"Pause? on row {row_number} must be Yes or No; found '{self._cell(row, pause_idx)}'."
                    )
            order_raw = self._cell(row, order_idx)
            try:
                order_value = self._import_integer(order_raw, "Order") if order_raw else len(parsed) + 1
            except ValueError:
                order_value = len(parsed) + 1
            parsed_row = {
                "name": name, "minutes": minutes, "sb": sb, "bb": bb,
                "ante": ante, "kind": kind,
            }
            if kind == "Break":
                parsed_row["pause_after"] = pause_after
            parsed.append((order_value, len(parsed), parsed_row))

        if not parsed:
            raise ValueError("No blind-structure rows were found.")
        if play_count == 0:
            raise ValueError("The imported structure must contain at least one play level, not only breaks.")
        if order_idx is not None:
            parsed.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in parsed]

    def import_levels(self):
        path, rows = self._read_import_rows("Import Blind Structure")
        if not path:
            return
        try:
            imported = self._parse_level_rows(rows)
        except Exception as e:
            messagebox.showerror("Invalid blind structure", str(e), parent=self)
            return

        replace = messagebox.askyesnocancel(
            "Import Blind Structure",
            f"Found {len(imported)} level/break row(s).\n\n"
            "Yes = replace the existing blind structure and return to Level 1\n"
            "No = append these rows after the existing structure\n"
            "Cancel = do not import",
            parent=self,
        )
        if replace is None:
            return
        if replace:
            self.running = False
            self.deadline = None
            self.levels = imported
            self.current_level = 0
            self._blind_start_sound_played = False
            self.remaining_seconds = int(self.levels[0]["minutes"]) * 60
        else:
            self.levels.extend(imported)
        self.history.append({
            "event": "blind_structure_imported", "file": os.path.basename(path),
            "count": len(imported), "replaced_existing": bool(replace),
            "time": datetime.now().isoformat(timespec="seconds"),
        })
        self._save_data()
        self._refresh_all()
        messagebox.showinfo(
            "Blind Structure Import Complete",
            f"Imported {len(imported)} row(s) from {os.path.basename(path)}.\n\n"
            f"Blind structure now contains {len(self.levels)} row(s).",
            parent=self,
        )

    def add_break(self):
        result = self._level_dialog(kind="Break")
        if result:
            self.levels.append(result)
            self._save_data()
            self._refresh_all()

    def edit_level(self):
        selected = self.level_tree.selection()
        if len(selected) > 1:
            messagebox.showinfo("Select one level", "Edit Selected works on one row at a time. Keep multi-row selection for duration updates.", parent=self)
            return
        idx = self._selected_level_index()
        if idx is None:
            messagebox.showinfo("Select a level", "Select a level to edit.")
            return
        result = self._level_dialog(dict(self.levels[idx]), self.levels[idx].get("kind","Play"))
        if result:
            self.levels[idx] = result
            if idx == self.current_level and not self.running:
                self.remaining_seconds = result["minutes"]*60
            self._save_data()
            self._refresh_all()

    def delete_level(self):
        selected = sorted({int(iid) for iid in self.level_tree.selection() if iid.isdigit()})
        if not selected:
            return
        remaining = [row for index, row in enumerate(self.levels) if index not in set(selected)]
        if not remaining:
            messagebox.showwarning("Cannot delete", "At least one scheduled row must remain.", parent=self)
            return
        if not any(row.get("kind") != "Break" for row in remaining):
            messagebox.showwarning("Cannot delete", "At least one play level must remain.", parent=self)
            return
        names = [self.levels[i].get("name", f"Row {i + 1}") for i in selected]
        confirm_text = "Delete the selected row?" if len(selected) == 1 else f"Delete these {len(selected)} selected rows?"
        confirm_text += "\n\n" + "\n".join(names[:8])
        if len(names) > 8:
            confirm_text += f"\n…and {len(names) - 8} more"
        if not messagebox.askyesno("Delete selected rows", confirm_text, parent=self):
            return
        old_current = self.current_level
        self.levels = remaining
        deleted_before = sum(1 for index in selected if index < old_current)
        if old_current in selected:
            self.current_level = min(min(selected) - deleted_before, len(self.levels) - 1)
        else:
            self.current_level = max(0, old_current - deleted_before)
        self.current_level = max(0, min(self.current_level, len(self.levels) - 1))
        self._blind_start_sound_played = False
        self.remaining_seconds = min(self.remaining_seconds, int(self._current_level()["minutes"]) * 60)
        self._save_data()
        self._refresh_all()

    def move_level(self, direction):
        if len(self.level_tree.selection()) > 1:
            messagebox.showinfo("Select one level", "Move Up/Down moves one row at a time. Select one row, or use multi-select for duration changes.", parent=self)
            return
        idx = self._selected_level_index()
        if idx is None:
            return
        new = idx + direction
        if not 0 <= new < len(self.levels):
            return
        self.levels[idx], self.levels[new] = self.levels[new], self.levels[idx]
        self._blind_start_sound_played = False
        if self.current_level == idx:
            self.current_level = new
        elif self.current_level == new:
            self.current_level = idx
        self._save_data()
        self._refresh_all()
        self.level_tree.selection_set(str(new))

    def _event_sound_choice(self, event_key):
        """Resolve an event override to its concrete preset."""
        override = self.sound_overrides.get(event_key, "Use default")
        return self.default_sound if override == "Use default" else override

    def _play_event_sound(self, event_key):
        """Play the configured sound for a tournament event, if sounds are enabled."""
        if not self.sound_enabled:
            return
        choice = self._event_sound_choice(event_key)
        if choice == "Off":
            return
        self._play_sound_choice(choice, custom_path=self.custom_sound_path,
                                volume=self.sound_volume, show_error=False)

    def _fallback_sound(self):
        """Use Tk's standard bell when the Windows sound API is unavailable."""
        try:
            self.after(0, self.bell)
        except Exception:
            pass

    def _preset_wav_path(self, preset, volume):
        """Create a small PCM WAV tone for a preset, with amplitude set by volume."""
        volume = max(0, min(100, int(volume)))
        if volume == 0 or preset == "Off":
            return None
        patterns = {
            "Chime": [(784, 0.13), (1046, 0.22)],
            "Bell": [(660, 0.28)],
            "Alert": [(880, 0.10), (0, 0.06), (880, 0.10), (0, 0.06), (659, 0.23)],
            "Double Chime": [(988, 0.12), (0, 0.07), (1318, 0.23)],
        }
        if preset not in patterns and preset != "Gong":
            return None
        out_dir = os.path.join(tempfile.gettempdir(), "PokerTournamentDirectorSounds")
        os.makedirs(out_dir, exist_ok=True)
        safe_name = preset.lower().replace(" ", "_")
        out_path = os.path.join(out_dir, f"{safe_name}_{volume}.wav")
        if os.path.isfile(out_path) and os.path.getsize(out_path) > 44:
            return out_path
        sample_rate = 22050
        amplitude = int(30000 * volume / 100)
        samples = bytearray()
        if preset == "Gong":
            # A gong-like metallic strike: slightly inharmonic partials, beating,
            # quick attack and a long, soft decay (about 2.7 seconds).
            duration = 2.7
            total = int(sample_rate * duration)
            partials = [
                (104.0, 1.00, 2.15, 0.00),
                (157.0, 0.62, 1.70, 0.25),
                (213.0, 0.48, 1.48, 0.70),
                (276.0, 0.36, 1.18, 1.20),
                (338.0, 0.30, 0.95, 0.40),
                (405.0, 0.23, 0.78, 1.70),
                (487.0, 0.18, 0.62, 2.10),
                (572.0, 0.14, 0.50, 0.90),
                (681.0, 0.10, 0.39, 2.70),
                (817.0, 0.07, 0.29, 1.30),
            ]
            weight_sum = sum(partial[1] for partial in partials)
            for idx in range(total):
                t = idx / sample_rate
                attack = min(1.0, t / 0.012)
                # Subtle slow swell creates the shimmering metallic resonance.
                tonal = 0.0
                for frequency, weight, decay, phase in partials:
                    wobble = 1.0 + 0.04 * math.sin(2 * math.pi * (0.32 + frequency / 5000.0) * t + phase)
                    tonal += weight * math.exp(-t / decay) * wobble * math.sin(2 * math.pi * frequency * t + phase)
                value = int(amplitude * 0.84 * attack * tonal / weight_sum)
                samples.extend(struct.pack("<h", max(-32767, min(32767, value))))
        else:
            for frequency, seconds in patterns[preset]:
                count = int(sample_rate * seconds)
                if frequency <= 0:
                    samples.extend(b"\x00\x00" * count)
                    continue
                fade_in = max(1, int(sample_rate * 0.008))
                fade_out = max(1, int(sample_rate * 0.018))
                for idx in range(count):
                    envelope = min(1.0, idx / fade_in, (count - idx - 1) / fade_out)
                    envelope = max(0.0, envelope)
                    value = int(amplitude * envelope * math.sin(2 * math.pi * frequency * idx / sample_rate))
                    samples.extend(struct.pack("<h", value))
        with wave.open(out_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(bytes(samples))
        return out_path

    def _scaled_custom_wav_path(self, source_path, volume):
        """Return a cached volume-adjusted PCM WAV copy.

        Check the cache before reading and scaling the audio samples. This avoids
        repeating CPU-intensive sample processing every time a sound is played.
        Supports 8-, 16-, 24-, and 32-bit PCM WAV files.
        """
        volume = max(0, min(100, int(volume)))
        if volume <= 0:
            return None
        if volume == 100:
            return source_path

        # Identify the source and requested volume before doing any audio processing.
        # The file size and modification timestamp invalidate the cache when the
        # original WAV is replaced or edited.
        stat = os.stat(source_path)
        identity = (
            f"{os.path.abspath(source_path)}|{stat.st_size}|"
            f"{stat.st_mtime_ns}|{volume}"
        ).encode("utf-8", "replace")
        digest = hashlib.sha1(identity).hexdigest()[:16]
        out_dir = os.path.join(tempfile.gettempdir(), "PokerTournamentDirectorSounds")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"custom_{digest}.wav")

        # Critical performance fix: return immediately if the adjusted sound exists.
        if os.path.isfile(out_path) and os.path.getsize(out_path) > 44:
            return out_path

        with wave.open(source_path, "rb") as source:
            params = source.getparams()
            if params.comptype != "NONE" or params.sampwidth not in (1, 2, 3, 4):
                raise ValueError(
                    "The selected WAV must use uncompressed PCM audio "
                    "(8-, 16-, 24-, or 32-bit)."
                )
            frames = bytearray(source.readframes(params.nframes))

        gain = volume / 100.0
        width = params.sampwidth
        if width == 1:
            for offset in range(len(frames)):
                centered = frames[offset] - 128
                frames[offset] = max(0, min(255, int(round(128 + centered * gain))))
        else:
            limit = (1 << (width * 8 - 1)) - 1
            lower = -(1 << (width * 8 - 1))
            for offset in range(0, len(frames) - width + 1, width):
                sample = int.from_bytes(frames[offset:offset + width], "little", signed=True)
                sample = max(lower, min(limit, int(round(sample * gain))))
                frames[offset:offset + width] = sample.to_bytes(width, "little", signed=True)

        with wave.open(out_path, "wb") as output:
            output.setparams(params)
            output.writeframes(bytes(frames))
        return out_path

    def _prepare_bundled_sound_cache(self):
        """Pre-create volume-adjusted bundled alerts before timer operation begins."""
        if not self.sound_enabled or self.sound_volume <= 0 or self.sound_volume >= 100:
            return
        for path in (self._bundled_long_gong_path(), self._bundled_one_minute_path()):
            try:
                if os.path.isfile(path):
                    self._scaled_custom_wav_path(path, self.sound_volume)
            except Exception:
                # Sound failures must not prevent the tournament app from opening.
                pass

    def _bundled_long_gong_path(self):
        """Return the bundled user-supplied long gong WAV alongside the application."""
        return resource_path("Long Gong.wav")

    def _bundled_one_minute_path(self):
        """Return the bundled one-minute warning WAV alongside the application."""
        return resource_path("One Minute.wav")

    def _play_sound_choice(self, choice, custom_path=None, volume=None, show_error=False):
        """Play one preset/custom WAV asynchronously. The volume slider applies to PCM files."""
        if volume is None:
            volume = self.sound_volume
        volume = max(0, min(100, int(volume)))
        if choice == "Off" or volume == 0:
            return
        try:
            if choice in ("Custom WAV", "Long Gong", "One Minute"):
                if choice == "Custom WAV":
                    source_path = custom_path
                elif choice == "Long Gong":
                    source_path = self._bundled_long_gong_path()
                else:
                    source_path = self._bundled_one_minute_path()
                if not source_path or not os.path.isfile(source_path):
                    if show_error:
                        if choice in ("Long Gong", "One Minute"):
                            expected = "Long Gong.wav" if choice == "Long Gong" else "One Minute.wav"
                            messagebox.showerror("Bundled sound missing", f"{expected} is missing from the application resources. Re-run the installer to repair the installation.", parent=self)
                        else:
                            messagebox.showwarning("Custom sound", "Choose an existing WAV file first.", parent=self)
                    return
                path = self._scaled_custom_wav_path(source_path, volume)
            else:
                path = self._preset_wav_path(choice, volume)
            if not path:
                return
            if winsound is not None:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                self._fallback_sound()
        except Exception as exc:
            if show_error:
                messagebox.showerror("Sound test failed", f"The sound could not be played:\n{exc}", parent=self)
            else:
                self._fallback_sound()

    def _sound_settings_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Sound Settings")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        dlg.geometry("740x610")

        enabled_var = tk.BooleanVar(value=self.sound_enabled)
        default_var = tk.StringVar(value=self.default_sound)
        custom_path_var = tk.StringVar(value=self.custom_sound_path)
        volume_var = tk.IntVar(value=self.sound_volume)
        warning_var = tk.StringVar(value=str(self.sound_warning_seconds))
        preset_choices = ["Off", "Chime", "Bell", "Alert", "Double Chime", "Gong", "Long Gong", "One Minute", "Custom WAV"]
        override_choices = ["Use default", "Off", "Chime", "Bell", "Alert", "Double Chime", "Gong", "Long Gong", "One Minute", "Custom WAV"]
        event_definitions = [
            ("Clock starts / resumes", "clock_started"),
            ("Low-time warning", "low_time"),
            ("Play level ends", "level_ends"),
            ("Break ends", "break_ends"),
            ("Manual level change", "level_changed"),
            ("Blind level starts", "blind_level_starts"),
        ]
        override_vars = {key: tk.StringVar(value=self.sound_overrides.get(key, "Use default"))
                         for _label, key in event_definitions}

        content = ttk.Frame(dlg, padding=14)
        content.pack(fill="both", expand=True)
        ttk.Checkbutton(content, text="Enable tournament sound effects", variable=enabled_var).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(content, text="Default sound").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(content, textvariable=default_var, values=preset_choices, state="readonly", width=20).grid(
            row=1, column=1, sticky="w", padx=(10, 8), pady=4)
        ttk.Button(content, text="Test Default", command=lambda: self._play_sound_choice(
            default_var.get(), custom_path=custom_path_var.get().strip(), volume=volume_var.get(), show_error=True
        )).grid(row=1, column=2, sticky="w", pady=4)

        ttk.Label(content, text="Custom WAV file").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(content, textvariable=custom_path_var, width=58).grid(row=2, column=1, sticky="ew", padx=(10, 8), pady=4)
        def browse_custom_sound():
            chosen = filedialog.askopenfilename(
                parent=dlg, title="Choose a sound file", filetypes=[("WAV sound files", "*.wav"), ("All files", "*.*")])
            if chosen:
                custom_path_var.set(chosen)
        ttk.Button(content, text="Browse…", command=browse_custom_sound).grid(row=2, column=2, sticky="w", pady=4)

        ttk.Label(content, text="Volume").grid(row=3, column=0, sticky="w", pady=4)
        volume_frame = ttk.Frame(content)
        volume_frame.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(10, 8), pady=4)
        volume_value_label = ttk.Label(volume_frame, text=f"{volume_var.get()}%", width=5)
        volume_value_label.pack(side="right")
        ttk.Scale(volume_frame, from_=0, to=100, variable=volume_var,
                  command=lambda value: volume_value_label.configure(text=f"{int(float(value))}%")).pack(
                      side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Label(content, text="Low-time warning (seconds; 0 disables)").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(content, textvariable=warning_var, width=10).grid(row=4, column=1, sticky="w", padx=(10, 8), pady=4)
        ttk.Separator(content).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 8))
        ttk.Label(content, text="Sound for each event (choose Use default to use the default sound)",
                  font=("Segoe UI", 10, "bold")).grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 4))
        for row, (label, event_key) in enumerate(event_definitions, start=7):
            ttk.Label(content, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Combobox(content, textvariable=override_vars[event_key], values=override_choices,
                         state="readonly", width=20).grid(row=row, column=1, sticky="w", padx=(10, 8), pady=4)
            ttk.Button(content, text="Test", command=lambda key=event_key: self._play_sound_choice(
                (default_var.get() if override_vars[key].get() == "Use default" else override_vars[key].get()),
                custom_path=custom_path_var.get().strip(), volume=volume_var.get(), show_error=True
            )).grid(row=row, column=2, sticky="w", pady=4)
        ttk.Label(content, text="Long Gong is your supplied 12.47-second recording. One Minute is your supplied 6.82-second low-time warning. Custom WAV files must be uncompressed PCM WAV. Volume adjusts presets and PCM WAV files.",
                  foreground="#555555", wraplength=680).grid(row=13, column=0, columnspan=3, sticky="w", pady=(8, 4))

        def save_sound_settings():
            try:
                volume = int(float(volume_var.get()))
                warning_seconds = int(warning_var.get().strip())
                if not 0 <= volume <= 100:
                    raise ValueError("Volume must be between 0 and 100 percent.")
                if not 0 <= warning_seconds <= 3600:
                    raise ValueError("Low-time warning must be between 0 and 3600 seconds.")
                custom_path = custom_path_var.get().strip()
                needs_custom = default_var.get() == "Custom WAV" or any(
                    variable.get() == "Custom WAV" for variable in override_vars.values())
                if needs_custom:
                    if not custom_path or not os.path.isfile(custom_path):
                        raise ValueError("Choose an existing WAV file for any setting that uses Custom WAV.")
                    try:
                        with wave.open(custom_path, "rb") as chosen_wav:
                            if chosen_wav.getcomptype() != "NONE" or chosen_wav.getsampwidth() not in (1, 2, 3, 4):
                                raise ValueError("Use an uncompressed PCM WAV file (8-, 16-, 24-, or 32-bit).")
                    except (wave.Error, EOFError) as wav_error:
                        raise ValueError(f"The selected file is not a supported WAV file: {wav_error}")
                self.sound_enabled = bool(enabled_var.get())
                self.default_sound = default_var.get()
                self.sound_volume = volume
                self.custom_sound_path = custom_path
                self.sound_warning_seconds = warning_seconds
                self.sound_overrides = {key: variable.get() for key, variable in override_vars.items()}
                self._save_data()
                dlg.destroy()
            except Exception as exc:
                messagebox.showerror("Invalid sound settings", str(exc), parent=dlg)

        button_row = ttk.Frame(content)
        button_row.grid(row=14, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(button_row, text="Save Sound Settings", command=save_sound_settings).pack(side="right", padx=(8, 0))
        ttk.Button(button_row, text="Cancel", command=dlg.destroy).pack(side="right")
        content.columnconfigure(1, weight=1)

    def _apply_main_window_geometry(self, width_percent=None, height_percent=None):
        """Center the main window at a percentage of the current monitor size.

        This affects only the normal application window; the TV/full-screen display
        continues to use its own full-screen layout.
        """
        try:
            width_percent = int(self.main_window_width_percent if width_percent is None else width_percent)
            height_percent = int(self.main_window_height_percent if height_percent is None else height_percent)
        except (TypeError, ValueError):
            width_percent, height_percent = 90, 85
        width_percent = max(70, min(100, width_percent))
        height_percent = max(70, min(100, height_percent))

        screen_width = max(1, int(self.winfo_screenwidth()))
        screen_height = max(1, int(self.winfo_screenheight()))
        # Leave a few pixels beyond the requested percentage for native window borders
        # and title bar; percentages remain relative to the monitor's reported size.
        width = min(max(600, int(screen_width * width_percent / 100)), max(600, screen_width - 32))
        height = min(max(460, int(screen_height * height_percent / 100)), max(460, screen_height - 40))
        # Never set a minimum size larger than the geometry we just calculated.
        self.minsize(min(900, width), min(560, height))
        try:
            if self.state() == "zoomed":
                self.state("normal")
        except tk.TclError:
            pass
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.update_idletasks()
        if hasattr(self, "window_size_summary_var"):
            self.window_size_summary_var.set(self._window_size_summary_text())

    def _window_size_dialog(self):
        """Let users tune the main application window for their current monitor."""
        dlg = tk.Toplevel(self)
        dlg.title("Main Window Size")
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(padx=16, pady=14)

        original_width = self.main_window_width_percent
        original_height = self.main_window_height_percent
        original_geometry = self.geometry()
        original_state = self.state()
        original_min_size = self.minsize()
        width_var = tk.IntVar(value=original_width)
        height_var = tk.IntVar(value=original_height)
        screen_width = int(self.winfo_screenwidth())
        screen_height = int(self.winfo_screenheight())

        ttk.Label(dlg, text="Adjust the main window for this monitor",
                  font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Label(dlg, text=f"Detected monitor: {screen_width} × {screen_height} pixels").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Label(dlg, text="Window width").grid(row=2, column=0, sticky="w", padx=(0, 14), pady=7)
        width_spin = ttk.Spinbox(dlg, from_=70, to=100, increment=1, width=8, textvariable=width_var)
        width_spin.grid(row=2, column=1, sticky="w", pady=7)
        ttk.Label(dlg, text="% of screen width").grid(row=2, column=2, sticky="w", padx=(8, 0), pady=7)

        ttk.Label(dlg, text="Window height").grid(row=3, column=0, sticky="w", padx=(0, 14), pady=7)
        height_spin = ttk.Spinbox(dlg, from_=70, to=100, increment=1, width=8, textvariable=height_var)
        height_spin.grid(row=3, column=1, sticky="w", pady=7)
        ttk.Label(dlg, text="% of screen height").grid(row=3, column=2, sticky="w", padx=(8, 0), pady=7)

        ttk.Label(
            dlg,
            text="The window will be centered. Use a lower percentage if your TV or monitor\n"
                 "cuts off the edges. 100% requests the largest available window size. This setting does not change the Full Screen Display.",
            justify="left", wraplength=470
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(9, 14))

        def values_from_fields():
            try:
                width_pct = int(width_var.get())
                height_pct = int(height_var.get())
            except (ValueError, tk.TclError):
                raise ValueError("Enter whole-number percentages for width and height.")
            if not 70 <= width_pct <= 100:
                raise ValueError("Window width must be between 70% and 100%.")
            if not 70 <= height_pct <= 100:
                raise ValueError("Window height must be between 70% and 100%.")
            return width_pct, height_pct

        def preview():
            try:
                width_pct, height_pct = values_from_fields()
                self._apply_main_window_geometry(width_pct, height_pct)
            except Exception as exc:
                messagebox.showerror("Invalid window size", str(exc), parent=dlg)

        def save_and_close():
            try:
                width_pct, height_pct = values_from_fields()
                self.main_window_width_percent = width_pct
                self.main_window_height_percent = height_pct
                self._apply_main_window_geometry(width_pct, height_pct)
                self._save_data()
                dlg.destroy()
            except Exception as exc:
                messagebox.showerror("Invalid window size", str(exc), parent=dlg)

        def cancel():
            # Cancel restores the exact window geometry/state from before opening the dialog.
            try:
                if self.state() == "zoomed":
                    self.state("normal")
                self.minsize(*original_min_size)
                self.geometry(original_geometry)
                if original_state == "zoomed":
                    self.state("zoomed")
            except tk.TclError:
                pass
            if dlg.winfo_exists():
                dlg.destroy()

        buttons = ttk.Frame(dlg)
        buttons.grid(row=5, column=0, columnspan=3, sticky="e")
        ttk.Button(buttons, text="Preview", command=preview).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", command=save_and_close).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=cancel).pack(side="left")
        dlg.protocol("WM_DELETE_WINDOW", cancel)
        dlg.bind("<Escape>", lambda _event: cancel())
        dlg.update_idletasks()
        x = max(0, (screen_width - dlg.winfo_reqwidth()) // 2)
        y = max(0, (screen_height - dlg.winfo_reqheight()) // 2)
        dlg.geometry(f"+{x}+{y}")

    def _save_from_header(self):
        """Save the current session and, when applicable, update its active scenario.

        The header Save button is used while working in a launched scenario as well
        as during an ordinary live session. Preserve the current blind structure
        before validating the settings form, then write that configuration back to
        the active scenario so imported levels are not silently replaced by defaults.
        """
        # Capture levels first: applying the settings form can refresh dependent UI.
        levels_snapshot = copy.deepcopy(getattr(self, "levels", []))
        if not self._apply_tournament_settings_from_form():
            return

        active_id = str(getattr(self, "active_scenario_id", "") or "")
        active_scenario = next(
            (item for item in getattr(self, "scenarios", []) if str(item.get("id", "")) == active_id),
            None,
        ) if active_id else None

        if active_scenario is not None:
            old_scenarios = copy.deepcopy(self.scenarios)
            cfg = self._normalize_scenario_config(
                self._scenario_config_snapshot(levels_override=levels_snapshot)
            )
            if cfg is None:
                messagebox.showerror(
                    "Scenario Save Error",
                    "The current scenario settings or blind structure are invalid. The saved scenario was not changed.",
                    parent=self,
                )
                return
            active_scenario["config"] = cfg
            active_scenario["updated_at"] = datetime.now().isoformat(timespec="seconds")
            if not self._save_scenario_library():
                self.scenarios = old_scenarios
                self._refresh_scenario_tree()
                return
            self._refresh_scenario_tree()
            try:
                self.scenario_tree.selection_set(active_id)
                self.scenario_tree.focus(active_id)
                self._scenario_selection_changed()
            except Exception:
                pass
            if hasattr(self, "scenario_status_var"):
                self.scenario_status_var.set(
                    f"Saved current settings and blind structure to '{active_scenario['name']}'."
                )

        # Always save the live tournament/session separately from the reusable scenario.
        self._save_data()

    def _add_scrollable_content(self, parent):
        """Create a tab content area that remains usable on smaller monitors."""
        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(canvas, padding=12)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        return content

    def _build_settings_tab(self):
        """Build Tournament Settings with focused sub-tabs for each settings category."""
        content = self._add_scrollable_content(self.settings_tab)
        ttk.Label(content, text="Tournament Settings", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            content,
            text="Keep the rules that define this tournament here. Use the sub-tabs to find only the settings relevant to each category, then click Save in the upper-right corner.",
            wraplength=1000, justify="left"
        ).pack(anchor="w", pady=(3, 10))

        vars_ = {
            "name": tk.StringVar(value=self.tournament_name),
            "tournament_type": tk.StringVar(value=self.tournament_type),
            "buy_in": tk.StringVar(value=str(self.buy_in)),
            "reentry_fee": tk.StringVar(value=str(self.reentry_fee)),
            "ante_enabled": tk.BooleanVar(value=False),
            "rebuy_enabled": tk.BooleanVar(value=self.rebuy_enabled),
            "add_on_enabled": tk.BooleanVar(value=self.add_on_enabled),
            "add_on_fee": tk.StringVar(value=str(self.add_on_fee)),
            "add_on_chips": tk.StringVar(value=str(self.add_on_chips)),
            "house_fee": tk.StringVar(value=str(self.house_fee)),
            "charity_mode": tk.StringVar(value="Yes" if self.charity_mode else "No"),
            "charity_method": tk.StringVar(value=self.charity_method),
            "charity_value": tk.StringVar(value=str(self.charity_value)),
            "limit_charity_paid_places": tk.BooleanVar(value=self.limit_charity_paid_places),
            "charity_max_paid_places": tk.StringVar(value=str(self.charity_max_paid_places)),
            "tracking_mode": tk.StringVar(value="Entry count only"),
            "payout_mode": tk.StringVar(value=self.payout_mode),
            "payout_rounding_increment": tk.StringVar(value=str(self.payout_rounding_increment)),
            "stack": tk.StringVar(value=str(self.starting_stack)),
        }
        self.settings_vars = vars_
        self.payout_mode_var = vars_["payout_mode"]

        sections = ttk.Notebook(content, height=570)
        sections.pack(fill="both", expand=True)
        self.settings_sections = sections
        basics_tab = ttk.Frame(sections, padding=14)
        fees_tab = ttk.Frame(sections, padding=14)
        charity_tab = ttk.Frame(sections, padding=14)
        payout_rules_tab = ttk.Frame(sections, padding=14)
        self.payout_rules_tab = payout_rules_tab
        management_tab = ttk.Frame(sections, padding=14)
        sections.add(basics_tab, text="General")
        sections.add(fees_tab, text="Entries & Fees")
        sections.add(charity_tab, text="Tournament Type")
        sections.add(payout_rules_tab, text="Payout Rules")
        sections.add(management_tab, text="Tournament Management")
        # Keep references so type-specific tabs can be hidden/shown dynamically.
        self.settings_general_tab = basics_tab
        self.tournament_type_tab = charity_tab

        self.settings_field_widgets = {}
        self.settings_field_labels = {}
        self.settings_field_base_states = {}
        self.settings_check_widgets = {}

        def add_field_grid(parent, fields, variable_map, *, combo_specs=None):
            """Add a compact label/control grid and remember controls for dependency handling."""
            combo_specs = combo_specs or {}
            grid = ttk.Frame(parent)
            grid.pack(fill="x", anchor="n", pady=(4, 0))
            for row, (label, key) in enumerate(fields):
                label_widget = ttk.Label(grid, text=label)
                label_widget.grid(row=row, column=0, sticky="w", padx=(4, 18), pady=6)
                if key in combo_specs:
                    values, width = combo_specs[key]
                    widget = ttk.Combobox(grid, textvariable=variable_map[key], values=values,
                                          state="readonly", width=width)
                    base_state = "readonly"
                else:
                    widget = ttk.Entry(grid, textvariable=variable_map[key], width=32)
                    base_state = "normal"
                widget.grid(row=row, column=1, sticky="w", padx=4, pady=6)
                self.settings_field_widgets[key] = widget
                self.settings_field_labels[key] = label_widget
                self.settings_field_base_states[key] = base_state
            grid.columnconfigure(1, weight=1)
            return grid

        ttk.Label(basics_tab, text="Tournament type and general settings", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            basics_tab,
            text="Choose a starting template. The selection configures related options; you can still customize individual rules afterward.",
            foreground="#52606d", wraplength=850, justify="left"
        ).pack(anchor="w", pady=(4, 5))
        self.tournament_type_help_var = tk.StringVar(value=self._tournament_type_help_text(vars_["tournament_type"].get()))
        ttk.Label(
            basics_tab, textvariable=self.tournament_type_help_var,
            foreground="#52606d", wraplength=900, justify="left"
        ).pack(anchor="w", pady=(0, 7))
        add_field_grid(
            basics_tab,
            [("Tournament type", "tournament_type"), ("Tournament name", "name"),
             ("Starting chip stack", "stack")],
            vars_,
            combo_specs={
                "tournament_type": (["Standard Tournament", "Charity Tournament", "Home Game", "Freeroll"], 28),
            }
        )
        self.tournament_type_combo = self.settings_field_widgets["tournament_type"]
        self.tournament_type_combo.bind("<<ComboboxSelected>>", self._on_tournament_type_selected)

        ttk.Label(fees_tab, text="Entry options and fees", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            fees_tab,
            text="These fee and entry settings are commonly used for home games, and can also apply to charity events or freerolls with paid re-entries/add-ons.",
            foreground="#52606d", wraplength=900, justify="left"
        ).pack(anchor="w", pady=(4, 8))
        add_field_grid(
            fees_tab,
            [
                ("Original buy-in ($)", "buy_in"),
                ("Re-buy / re-entry fee ($)", "reentry_fee"),
                ("Add-on fee ($)", "add_on_fee"),
                ("Add-on chips per add-on", "add_on_chips"),
            ], vars_
        )
        entry_checks = ttk.LabelFrame(fees_tab, text="Entry options enabled", padding=10)
        entry_checks.pack(fill="x", pady=(12, 0), anchor="n")
        self.settings_check_widgets["rebuy_enabled"] = ttk.Checkbutton(
            entry_checks, text="Enable rebuys (include rebuy entries and fees in calculations)",
            variable=vars_["rebuy_enabled"], command=self._refresh_settings_dependencies
        )
        self.settings_check_widgets["rebuy_enabled"].pack(anchor="w", pady=4)
        self.settings_check_widgets["add_on_enabled"] = ttk.Checkbutton(
            entry_checks, text="Enable add-ons (show controls and include add-on fees/chips in totals)",
            variable=vars_["add_on_enabled"], command=self._refresh_settings_dependencies
        )
        self.settings_check_widgets["add_on_enabled"].pack(anchor="w", pady=4)

        ttk.Label(charity_tab, text="Tournament-specific options", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            charity_tab,
            text="This tab keeps special settings together. Benefit Pot fields appear when Charity is enabled; the house-fee field appears only for Home Game. Freeroll prize details are grouped with Payout Rules.",
            foreground="#52606d", wraplength=900, justify="left"
        ).pack(anchor="w", pady=(4, 8))
        add_field_grid(
            charity_tab,
            [
                ("Charity / Benefit Pot enabled? (Yes/No)", "charity_mode"),
                ("Benefit Pot calculation", "charity_method"),
                ("Benefit Pot amount ($) or percentage (%)", "charity_value"),
                ("Maximum paid places for charity events", "charity_max_paid_places"),
            ], vars_,
            combo_specs={
                "charity_mode": (["Yes", "No"], 28),
                "charity_method": (["Fixed per entry", "Percentage of each entry"], 28),
            }
        )
        add_field_grid(
            charity_tab,
            [("House fee per original entry ($) — Home Game only", "house_fee")],
            vars_
        )
        self.settings_field_widgets["charity_mode"].bind(
            "<<ComboboxSelected>>", lambda _event: self._refresh_settings_dependencies()
        )
        self.settings_field_widgets["charity_mode"].bind(
            "<<ComboboxSelected>>", lambda _event: self._on_charity_toggle_changed(), add="+"
        )
        self.settings_check_widgets["limit_charity_paid_places"] = ttk.Checkbutton(
            charity_tab,
            text="Enforce charity maximum paid places when Charity is enabled",
            variable=vars_["limit_charity_paid_places"], command=self._refresh_settings_dependencies
        )
        self.settings_check_widgets["limit_charity_paid_places"].pack(anchor="w", padx=4, pady=(12, 4))

        ttk.Label(management_tab, text="Tournament Management", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            management_tab,
            text="Administrative actions for the current tournament. Reset clears live player/entry counts and tournament history but keeps the reusable tournament configuration, including blinds and payout rules.",
            foreground="#52606d", wraplength=900, justify="left"
        ).pack(anchor="w", pady=(4, 14))
        reset_box = ttk.LabelFrame(management_tab, text="Reset current tournament", padding=12)
        reset_box.pack(fill="x", anchor="n")
        ttk.Label(
            reset_box,
            text="Use this only when you want to start the current tournament over from zero. A confirmation is required before any live data is cleared.",
            wraplength=850, justify="left"
        ).pack(anchor="w", pady=(0, 10))
        ttk.Button(reset_box, text="Reset Tournament to Zero", command=self.reset_tournament_data).pack(anchor="w")

        ttk.Label(payout_rules_tab, text="Payout method and payout rules", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            payout_rules_tab,
            text="Choose the overall method here, then configure its details below. Charity restrictions remain independent and may further cap paid places.",
            foreground="#52606d", wraplength=900, justify="left"
        ).pack(anchor="w", pady=(4, 8))

        payout_mode_box = ttk.LabelFrame(payout_rules_tab, text="Payout Method", padding=10)
        payout_mode_box.pack(fill="x", anchor="n", pady=(0, 10))
        ttk.Label(payout_mode_box, text="Payout mode", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=(4, 18), pady=5
        )
        self.payout_mode_combo = ttk.Combobox(
            payout_mode_box, textvariable=self.payout_mode_var,
            values=["Traditional Percentages", "Mixed Fixed + Percentage", "Freeroll Fixed Prizes"],
            state="readonly", width=31
        )
        self.payout_mode_combo.grid(row=0, column=1, sticky="w", padx=4, pady=5)
        self.payout_mode_combo.bind("<<ComboboxSelected>>", self._on_payout_mode_selected)
        ttk.Label(payout_mode_box, text="Payout rounding increment ($)").grid(
            row=1, column=0, sticky="w", padx=(4, 18), pady=5
        )
        self.payout_rounding_combo = ttk.Combobox(
            payout_mode_box, textvariable=vars_["payout_rounding_increment"],
            values=["1", "5", "10", "20", "25", "50", "100"],
            state="readonly", width=31
        )
        self.payout_rounding_combo.grid(row=1, column=1, sticky="w", padx=4, pady=5)

        payout_profile_box = ttk.LabelFrame(payout_rules_tab, text="Traditional Percentage Chart Templates", padding=8)
        payout_profile_box.pack(fill="x", pady=(0, 8), anchor="n")
        ttk.Label(payout_profile_box, text="Profile").grid(row=0, column=0, sticky="w", padx=(2, 8), pady=3)
        self.payout_template_var = tk.StringVar(value=self.payout_template_name)
        self.payout_template_combo = ttk.Combobox(
            payout_profile_box, textvariable=self.payout_template_var,
            values=list(BUILT_IN_PAYOUT_TEMPLATE_LABELS), state="readonly", width=30
        )
        if self.payout_template_name not in BUILT_IN_PAYOUT_TEMPLATE_LABELS:
            self.payout_template_combo.configure(values=list(BUILT_IN_PAYOUT_TEMPLATE_LABELS) + [self.payout_template_name])
        self.payout_template_combo.grid(row=0, column=1, sticky="w", padx=3, pady=3)
        ttk.Button(payout_profile_box, text="Apply Profile", command=self._apply_current_payout_template).grid(row=0, column=2, padx=4, pady=3)
        ttk.Button(payout_profile_box, text="Import Excel…", command=self._import_current_payout_template).grid(row=0, column=3, padx=4, pady=3)
        ttk.Label(
            payout_profile_box,
            text="Profiles contain percentage charts for 2–15 paid places. Paid-position rules still determine how many places are paid.",
            foreground="#52606d", wraplength=820, justify="left"
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=2, pady=(2, 0))

        payout_tools = ttk.Frame(payout_rules_tab)
        payout_tools.pack(fill="x", pady=(0, 8))
        self.configure_freeroll_button = ttk.Button(
            payout_tools, text="Configure Freeroll Prizes…", command=self._configure_freeroll_payouts
        )
        self.configure_freeroll_button.pack(side="left", padx=(0, 5))
        self.edit_payout_splits_button = ttk.Button(
            payout_tools, text="Edit Payout Percentages…", command=self.edit_payout_splits
        )
        self.edit_payout_splits_button.pack(side="left", padx=5)
        self.edit_mixed_payouts_button = ttk.Button(
            payout_tools, text="Edit Mixed Payouts…", command=self.edit_mixed_payouts
        )
        self.edit_mixed_payouts_button.pack(side="left", padx=5)

        position_toolbar = ttk.Frame(payout_rules_tab)
        position_toolbar.pack(fill="x", pady=(6, 4))
        self.paid_position_rules_button = ttk.Button(
            position_toolbar, text="Paid Position Rules…", command=self.configure_paid_position_rules
        )
        self.paid_position_rules_button.pack(side="left", padx=(0, 5))
        self.add_payout_rule_button = ttk.Button(position_toolbar, text="Add Entry Rule", command=self.add_payout_rule)
        self.add_payout_rule_button.pack(side="left", padx=5)
        self.edit_payout_rule_button = ttk.Button(position_toolbar, text="Edit Selected Rule", command=self.edit_payout_rule)
        self.edit_payout_rule_button.pack(side="left", padx=5)
        self.delete_payout_rule_button = ttk.Button(position_toolbar, text="Delete Selected Rule", command=self.delete_payout_rule)
        self.delete_payout_rule_button.pack(side="left", padx=5)

        self.payout_threshold_heading = ttk.Label(
            payout_rules_tab,
            text="Automatic entry thresholds (each rebuy/re-entry counts as a new entry)",
            font=("Segoe UI", 10, "bold")
        )
        self.payout_threshold_heading.pack(anchor="w", pady=(3, 5))
        cols = ("min", "max", "places")
        self.payout_rule_tree = ttk.Treeview(
            payout_rules_tab, columns=cols, show="headings", height=5, selectmode="browse"
        )
        for c, heading, width in [
            ("min", "Minimum Entries", 150), ("max", "Maximum Entries", 150), ("places", "Paid Places", 150)
        ]:
            self.payout_rule_tree.heading(c, text=heading)
            self.payout_rule_tree.column(c, width=width, anchor="center")
        self.payout_rule_tree.pack(fill="x", pady=(0, 8))
        self.payout_rule_tree.bind("<Double-1>", self._on_payout_rule_tree_double_click)
        ttk.Label(
            payout_rules_tab,
            text="Detailed payout amounts are shown on the Payout Calculator tab. Display & Sound and Blind Structure remain separate because they contain monitor/audio preferences and the level-by-level schedule editors.",
            foreground="#52606d", wraplength=900, justify="left"
        ).pack(anchor="w", pady=(5, 0))
        self._refresh_settings_dependencies()

    def _tournament_type_help_text(self, tournament_type):
        """Return concise guidance for the selected tournament template."""
        descriptions = {
            "Standard Tournament": (
                "Standard entry-funded template. Traditional percentage payouts are selected by default; "
                "you can still choose mixed payouts and enable rebuys or add-ons. House fees are Home Game only."
            ),
            "Charity Tournament": (
                "Charity template with the Benefit Pot enabled by default. You may disable it or combine it with any payout mode, "
                "including Freeroll Fixed Prizes. Rebuys and add-ons remain independently configurable; house fees are Home Game only."
            ),
            "Home Game": (
                "Flexible home-game template with editable buy-in, house fee, rebuys, add-ons, blinds, and payouts. "
                "You can also turn on the Benefit Pot if needed."
            ),
            "Freeroll": (
                "Sets the original entry and house fee to $0 and selects Freeroll Fixed Prizes. "
                "Paid re-entries/add-ons and the Benefit Pot remain optional."
            ),
        }
        return descriptions.get(tournament_type, descriptions["Standard Tournament"])

    def _on_tournament_type_selected(self, _event=None):
        """Apply sensible template defaults while allowing charity and freeroll to overlap."""
        vars_ = getattr(self, "settings_vars", {})
        selected = vars_.get("tournament_type").get() if vars_.get("tournament_type") else "Standard Tournament"
        allowed = ("Standard Tournament", "Charity Tournament", "Home Game", "Freeroll")
        if selected not in allowed:
            selected = "Standard Tournament"
            vars_["tournament_type"].set(selected)

        previous = getattr(self, "_last_selected_tournament_type", self.tournament_type)

        def form_float(key, fallback=0.0):
            try:
                value = float(vars_[key].get())
                return value if math.isfinite(value) and value >= 0 else fallback
            except (KeyError, TypeError, ValueError):
                return fallback

        if previous == "Home Game" and selected != "Home Game":
            # Cache the current Home Game amount before the UI is zeroed/disabled.
            self.home_game_house_fee = form_float("house_fee", self.home_game_house_fee)

        leaving_freeroll = previous == "Freeroll" and selected != "Freeroll"
        if selected == "Freeroll" and previous != "Freeroll":
            # Preserve the prior paid-event amounts/mode so leaving the freeroll template restores them.
            self._pre_freeroll_buy_in = form_float("buy_in", self.buy_in)
            self._pre_freeroll_house_fee = form_float("house_fee", self.house_fee)
            candidate_mode = vars_["payout_mode"].get()
            self._pre_freeroll_payout_mode = candidate_mode if candidate_mode in (
                "Traditional Percentages", "Mixed Fixed + Percentage", "Freeroll Fixed Prizes"
            ) else "Traditional Percentages"
            vars_["buy_in"].set("0")
            vars_["house_fee"].set("0")
            vars_["payout_mode"].set("Freeroll Fixed Prizes")
            # Leave Charity as-is so a charity event can become a charity freeroll.
        elif leaving_freeroll:
            buy_restore = self._pre_freeroll_buy_in if self._pre_freeroll_buy_in is not None else 30.0
            house_restore = self._pre_freeroll_house_fee if self._pre_freeroll_house_fee is not None else 0.0
            mode_restore = self._pre_freeroll_payout_mode or "Traditional Percentages"
            vars_["buy_in"].set(f"{buy_restore:g}")
            vars_["house_fee"].set(f"{house_restore:g}")
            vars_["payout_mode"].set(mode_restore)
            self._pre_freeroll_buy_in = None
            self._pre_freeroll_house_fee = None
            self._pre_freeroll_payout_mode = None

        if selected == "Charity Tournament":
            vars_["charity_mode"].set("Yes")
            # Do not force a payout mode here; this allows Charity + Freeroll or Charity + Mixed.
        elif selected in ("Standard Tournament", "Home Game"):
            vars_["charity_mode"].set("No")
            if not leaving_freeroll:
                vars_["payout_mode"].set("Traditional Percentages")
        elif selected == "Freeroll":
            # The initial entry is free, but re-entry/add-on fees may still be enabled separately.
            vars_["buy_in"].set("0")
            vars_["house_fee"].set("0")
            vars_["payout_mode"].set("Freeroll Fixed Prizes")

        # Keep the type-driven fields in model state so other settings actions operate on the same profile.
        self.tournament_type = selected
        # Display a neutral zero and disable the field outside Home Game, while
        # retaining a separate Home Game-only value for quick switching back.
        if selected == "Home Game":
            vars_["house_fee"].set(f"{self.home_game_house_fee:g}")
            self.house_fee = form_float("house_fee", self.home_game_house_fee)
            self.home_game_house_fee = self.house_fee
        else:
            vars_["house_fee"].set("0")
            self.house_fee = 0.0
        self._last_selected_tournament_type = selected
        self.buy_in = form_float("buy_in", self.buy_in)
        self.charity_mode = vars_["charity_mode"].get().strip().lower() == "yes"
        selected_payout_mode = vars_["payout_mode"].get()
        if selected_payout_mode in ("Traditional Percentages", "Mixed Fixed + Percentage", "Freeroll Fixed Prizes"):
            self.payout_mode = selected_payout_mode
        if hasattr(self, "tournament_type_help_var"):
            self.tournament_type_help_var.set(self._tournament_type_help_text(selected))
        self._refresh_settings_dependencies()
        self._refresh_payouts()

    def _on_charity_toggle_changed(self):
        """Keep charity activation synchronized with its dependent settings and the current profile."""
        vars_ = getattr(self, "settings_vars", {})
        if "charity_mode" in vars_:
            self.charity_mode = vars_["charity_mode"].get().strip().lower() == "yes"
        self._refresh_settings_dependencies()

    def _set_settings_field_enabled(self, key, enabled):
        """Enable/disable a settings control and its label without clearing its saved value."""
        widget = getattr(self, "settings_field_widgets", {}).get(key)
        label = getattr(self, "settings_field_labels", {}).get(key)
        base_state = getattr(self, "settings_field_base_states", {}).get(key, "normal")
        if widget is not None:
            widget.configure(state=base_state if enabled else "disabled")
        if label is not None:
            label.state(["!disabled"] if enabled else ["disabled"])

    def _set_settings_field_visible(self, key, visible):
        """Show or hide a field while preserving its grid position for later restoration."""
        widget = getattr(self, "settings_field_widgets", {}).get(key)
        label = getattr(self, "settings_field_labels", {}).get(key)
        if widget is None or label is None:
            return
        for control in (label, widget):
            try:
                if visible and not control.winfo_manager():
                    control.grid()
                elif not visible and control.winfo_manager():
                    control.grid_remove()
            except tk.TclError:
                pass

    def _refresh_settings_dependencies(self):
        """Show and enable only fields relevant to the selected tournament options."""
        vars_ = getattr(self, "settings_vars", {})
        if not vars_:
            return
        tournament_type = vars_.get("tournament_type").get() if vars_.get("tournament_type") else self.tournament_type
        is_freeroll_template = tournament_type == "Freeroll"

        # Tournament Type only applies to specialized formats. Hide it entirely for a
        # Standard Tournament so Charity/Benefit Pot controls are not presented as
        # standard-tournament settings. Keep its values available when switching to
        # a specialized type again, except that Standard explicitly disables Charity.
        sections = getattr(self, "settings_sections", None)
        type_tab = getattr(self, "tournament_type_tab", None)
        general_tab = getattr(self, "settings_general_tab", None)
        if sections is not None and type_tab is not None:
            show_type_tab = tournament_type != "Standard Tournament"
            try:
                if not show_type_tab and sections.select() == str(type_tab) and general_tab is not None:
                    sections.select(general_tab)
                sections.tab(type_tab, state="normal" if show_type_tab else "hidden")
            except tk.TclError:
                pass

        # A Standard Tournament is not a charity format. Normalize any inconsistent
        # legacy/configuration state rather than silently retaining a hidden Benefit Pot.
        if tournament_type == "Standard Tournament" and vars_.get("charity_mode") is not None:
            vars_["charity_mode"].set("No")
            self.charity_mode = False

        rebuy_on = bool(vars_.get("rebuy_enabled").get()) if vars_.get("rebuy_enabled") else self.rebuy_enabled
        addon_on = bool(vars_.get("add_on_enabled").get()) if vars_.get("add_on_enabled") else self.add_on_enabled
        charity_on = vars_.get("charity_mode").get().strip().lower() == "yes" if vars_.get("charity_mode") else self.charity_mode
        charity_cap_on = bool(vars_.get("limit_charity_paid_places").get()) if vars_.get("limit_charity_paid_places") else self.limit_charity_paid_places

        self._set_settings_field_enabled("buy_in", not is_freeroll_template)
        # Type-specific fields live together on the Tournament Type tab and disappear when irrelevant.
        self._set_settings_field_visible("house_fee", tournament_type == "Home Game")
        self._set_settings_field_enabled("house_fee", tournament_type == "Home Game")
        self._set_settings_field_enabled("reentry_fee", rebuy_on)
        self._set_settings_field_enabled("add_on_fee", addon_on)
        self._set_settings_field_enabled("add_on_chips", addon_on)
        self._set_settings_field_visible("charity_method", charity_on)
        self._set_settings_field_visible("charity_value", charity_on)
        self._set_settings_field_visible("charity_max_paid_places", charity_on and charity_cap_on)
        self._set_settings_field_enabled("charity_method", charity_on)
        self._set_settings_field_enabled("charity_value", charity_on)
        self._set_settings_field_enabled("charity_max_paid_places", charity_on and charity_cap_on)

        checkbox_widgets = getattr(self, "settings_check_widgets", {})
        cap_check = checkbox_widgets.get("limit_charity_paid_places")
        if cap_check is not None:
            cap_check.configure(state="normal" if charity_on else "disabled")
            if charity_on and not cap_check.winfo_manager():
                cap_check.pack(anchor="w", padx=4, pady=(12, 4))
            elif not charity_on and cap_check.winfo_manager():
                cap_check.pack_forget()

        if hasattr(self, "tournament_type_help_var"):
            self.tournament_type_help_var.set(self._tournament_type_help_text(tournament_type))
        # Payout setup buttons react immediately to a mode chosen in the form/template.
        if hasattr(self, "configure_freeroll_button"):
            requested_mode = vars_.get("payout_mode").get() if vars_.get("payout_mode") else self.payout_mode
            self._update_payout_mode_controls(mode=requested_mode)

    def _apply_tournament_settings_from_form(self):
        """Validate and apply Tournament Settings fields; return False on validation errors."""
        vars_ = getattr(self, "settings_vars", None)
        if not vars_:
            return True
        try:
            tournament_type = vars_["tournament_type"].get().strip()
            if tournament_type not in ("Standard Tournament", "Charity Tournament", "Home Game", "Freeroll"):
                raise ValueError("Choose a valid tournament type.")
            buy = float(vars_["buy_in"].get())
            reentry = float(vars_["reentry_fee"].get())
            addon = float(vars_["add_on_fee"].get())
            addon_chips = int(vars_["add_on_chips"].get())
            house_input = float(vars_["house_fee"].get())
            # Ignore house fees for every type except Home Game.
            house = house_input if tournament_type == "Home Game" else 0.0
            stack = int(vars_["stack"].get())
            payout_rounding_increment = int(vars_["payout_rounding_increment"].get())
            charity_mode = vars_["charity_mode"].get().strip().lower() == "yes"
            charity_method = vars_["charity_method"].get().strip()
            charity_value = float(vars_["charity_value"].get())
            charity_max_paid_places = int(vars_["charity_max_paid_places"].get())
            limit_charity_paid_places = bool(vars_["limit_charity_paid_places"].get())
            if tournament_type == "Freeroll":
                buy = 0.0
                house = 0.0
                vars_["buy_in"].set("0")
                vars_["house_fee"].set("0")
            elif tournament_type != "Home Game":
                # Keep the form consistent with the disabled field in non-Home-Game types.
                vars_["house_fee"].set("0")
            if min(buy, reentry, addon, house, charity_value, addon_chips) < 0 or (buy > 0 and house > buy) or stack < 1:
                raise ValueError("Fees must be nonnegative, house fee cannot exceed a paid buy-in, and stack must be positive.")
            if payout_rounding_increment not in (1, 5, 10, 20, 25, 50, 100):
                raise ValueError("Choose a payout rounding increment of $1, $5, $10, $20, $25, $50, or $100.")
            if not 1 <= charity_max_paid_places <= 100:
                raise ValueError("The maximum paid places for charity events must be between 1 and 100.")
            if not vars_["name"].get().strip():
                tournament_name = "MyPoker Tournament"
            else:
                tournament_name = vars_["name"].get().strip()
            if charity_method == "Percentage of each entry" and charity_value > 100:
                raise ValueError("Charity percentage must be between 0 and 100.")
            paid_entry_fees = []
            if buy > 0:
                paid_entry_fees.append(buy)
            if bool(vars_["rebuy_enabled"].get()) and reentry > 0:
                paid_entry_fees.append(reentry)
            if charity_method == "Fixed per entry" and charity_mode and paid_entry_fees and charity_value > min(paid_entry_fees):
                raise ValueError("Fixed Benefit Pot contribution cannot exceed the smallest paid entry fee.")
            self.tournament_name = tournament_name
            self.tournament_type = tournament_type
            self._last_selected_tournament_type = tournament_type
            self.buy_in = buy
            self.reentry_fee = reentry
            self.add_on_fee = addon
            self.add_on_chips = addon_chips
            self.house_fee = house
            if tournament_type == "Home Game":
                self.home_game_house_fee = house
            self.starting_stack = stack
            self.charity_mode = charity_mode
            self.charity_method = charity_method
            self.charity_value = charity_value
            self.limit_charity_paid_places = limit_charity_paid_places
            self.charity_max_paid_places = charity_max_paid_places
            self.tracking_mode = "Entry count only"
            selected_payout_mode = vars_["payout_mode"].get().strip()
            if selected_payout_mode not in (
                "Traditional Percentages", "Mixed Fixed + Percentage", "Freeroll Fixed Prizes"
            ):
                raise ValueError("Choose a valid payout mode.")
            self.payout_mode = selected_payout_mode
            self.ante_enabled = False
            self.rebuy_enabled = bool(vars_["rebuy_enabled"].get())
            self.add_on_enabled = bool(vars_["add_on_enabled"].get())
            self.payout_rounding_increment = payout_rounding_increment
            if hasattr(self, "name_var"):
                self.name_var.set(self.tournament_name)
            if hasattr(self, "window_size_summary_var"):
                self.window_size_summary_var.set(self._window_size_summary_text())
            self._refresh_settings_dependencies()
            self._refresh_all()
            return True
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc), parent=self)
            return False

    def _build_display_sound_tab(self):
        tab = self.display_sound_tab
        ttk.Label(tab, text="Display & Sound", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text="Adjust the main window to fit different monitors and configure tournament audio alerts.",
            wraplength=900, justify="left"
        ).pack(anchor="w", pady=(3, 14))

        window_box = ttk.LabelFrame(tab, text="Main Window Size", padding=14)
        window_box.pack(fill="x", pady=(0, 12), anchor="n")
        self.window_size_summary_var = tk.StringVar(value=self._window_size_summary_text())
        ttk.Label(window_box, textvariable=self.window_size_summary_var, justify="left").pack(anchor="w", pady=(0, 10))
        ttk.Button(window_box, text="Configure Window Size…", command=self._window_size_dialog).pack(anchor="w")

        theme_box = ttk.LabelFrame(tab, text="Full-screen Display Theme", padding=14)
        theme_box.pack(fill="x", pady=(0, 12), anchor="n")
        ttk.Label(
            theme_box,
            text="Choose the player-facing TV display style. Classic keeps the familiar layout; Modern adds a dark neon look, a bottom-docked control tab, and smooth hide/show animation.",
            wraplength=900, justify="left"
        ).pack(anchor="w", pady=(0, 8))
        theme_row = ttk.Frame(theme_box)
        theme_row.pack(fill="x", anchor="w")
        self.fullscreen_theme_var = tk.StringVar(value=self.fullscreen_theme)
        self.fullscreen_theme_combo = ttk.Combobox(
            theme_row, textvariable=self.fullscreen_theme_var,
            values=("Classic", "Modern"), state="readonly", width=18
        )
        self.fullscreen_theme_combo.pack(side="left", anchor="w")
        self.fullscreen_theme_combo.bind("<<ComboboxSelected>>", self._on_fullscreen_theme_changed)
        self.fullscreen_theme_status_var = tk.StringVar(
            value=f"Selected: {self.fullscreen_theme}. Applies the next time you open Full Screen Display."
        )
        ttk.Label(theme_row, textvariable=self.fullscreen_theme_status_var).pack(side="left", padx=(12, 0))

        control_appearance_box = ttk.LabelFrame(tab, text="Full-Screen Controls Appearance", padding=14)
        control_appearance_box.pack(fill="x", pady=(0, 12), anchor="n")
        ttk.Label(
            control_appearance_box,
            text="Open a live full-screen preview to adjust control-label font and button size while viewing the actual display. "
                 "Changes appear immediately; Save & Finish keeps them, while Cancel Preview restores the previous sizes.",
            wraplength=900, justify="left"
        ).pack(anchor="w", pady=(0, 8))
        self.fullscreen_control_status_var = tk.StringVar(
            value=f"Control font: {self.fullscreen_control_font_size} pt  |  Button size: {self.fullscreen_control_button_scale}%"
        )
        ttk.Label(control_appearance_box, textvariable=self.fullscreen_control_status_var).pack(anchor="w", pady=(0, 8))
        ttk.Button(
            control_appearance_box, text="Configure Full-Screen Controls…",
            command=self._fullscreen_controls_dialog
        ).pack(anchor="w")

        sound_box = ttk.LabelFrame(tab, text="Sound Settings", padding=14)
        sound_box.pack(fill="x", anchor="n")
        ttk.Label(
            sound_box,
            text="Choose the default alert sound, configure sounds for each tournament event, and test your gong and 60-second warning.",
            wraplength=800, justify="left"
        ).pack(anchor="w", pady=(0, 10))
        ttk.Button(sound_box, text="Open Sound Settings…", command=self._sound_settings_dialog).pack(anchor="w")

    def _fullscreen_controls_dialog(self):
        """Open the full-screen display and overlay a live control-appearance dialog."""
        original_font_size = self.fullscreen_control_font_size
        original_button_scale = self.fullscreen_control_button_scale

        # Use the actual player-facing display as the preview canvas, not a mockup.
        display_win = self._open_display()
        if display_win is None or not display_win.winfo_exists():
            return

        # Give Windows a moment to map the exclusive full-screen window before
        # showing the settings popup. Parent the popup to the main application,
        # not to the full-screen Toplevel: on some Windows display drivers a
        # transient dialog owned by a full-screen window can be stacked behind
        # that window. A modal grab on such an invisible dialog makes the whole
        # application appear frozen. Keep the popup topmost and non-modal instead.
        try:
            display_win.update_idletasks()
        except tk.TclError:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Full-Screen Controls — Live Preview")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)

        content = ttk.Frame(dlg, padding=16)
        content.pack(fill="both", expand=True)

        font_var = tk.DoubleVar(value=original_font_size)
        button_var = tk.DoubleVar(value=original_button_scale)
        font_value_var = tk.StringVar(value=f"{original_font_size} pt")
        button_value_var = tk.StringVar(value=f"{original_button_scale}%")
        status_var = tk.StringVar(value="Changes are previewed live on the full-screen controls behind this window.")

        ttk.Label(content, text="Control font size (8–15 pt)", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        ttk.Label(content, textvariable=font_value_var, width=8, anchor="e").grid(
            row=0, column=1, sticky="e", padx=(10, 0), pady=(0, 5)
        )
        ttk.Scale(
            content, from_=8, to=15, orient="horizontal", variable=font_var,
            command=lambda _value: apply_live_preview()
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        ttk.Label(content, text="Button size (75–150%)", font=("Segoe UI", 11, "bold")).grid(
            row=2, column=0, sticky="w", pady=(0, 5)
        )
        ttk.Label(content, textvariable=button_value_var, width=8, anchor="e").grid(
            row=2, column=1, sticky="e", padx=(10, 0), pady=(0, 5)
        )
        ttk.Scale(
            content, from_=75, to=150, orient="horizontal", variable=button_var,
            command=lambda _value: apply_live_preview()
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(
            content,
            text="The actual full-screen buttons resize as you move either slider. You can drag this popup by its title bar to uncover any part of the display. After saving, press Esc to return to the main application.",
            wraplength=470, justify="left"
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(content, textvariable=status_var, wraplength=470, justify="left").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        def apply_live_preview(*_args):
            font_size = max(8, min(15, int(round(float(font_var.get())))))
            button_scale = max(75, min(150, int(round(float(button_var.get())))))
            font_value_var.set(f"{font_size} pt")
            button_value_var.set(f"{button_scale}%")
            self.fullscreen_control_font_size = font_size
            self.fullscreen_control_button_scale = button_scale
            refresh = getattr(self, "_active_fullscreen_control_refresh", None)
            if callable(refresh):
                try:
                    refresh()
                except tk.TclError:
                    # If the preview display is being closed, leave the dialog usable.
                    pass

        def reset_recommended():
            font_var.set(10)
            button_var.set(100)
            apply_live_preview()

        def save_and_finish():
            apply_live_preview()
            self._save_data()
            if hasattr(self, "fullscreen_control_status_var"):
                self.fullscreen_control_status_var.set(
                    f"Control font: {self.fullscreen_control_font_size} pt  |  "
                    f"Button size: {self.fullscreen_control_button_scale}%  |  Saved"
                )
            # The preview is deliberately non-modal: do not release/acquire a
            # grab here. This avoids an invisible dialog trapping all input.
            dlg.attributes("-topmost", False)
            dlg.destroy()
            # Leave the full-screen preview open so the user can inspect the final layout.

        def cancel_preview(*_args):
            self.fullscreen_control_font_size = original_font_size
            self.fullscreen_control_button_scale = original_button_scale
            refresh = getattr(self, "_active_fullscreen_control_refresh", None)
            if callable(refresh):
                try:
                    refresh()
                except tk.TclError:
                    pass
            try:
                if dlg.winfo_exists():
                    dlg.attributes("-topmost", False)
                    dlg.destroy()
            except tk.TclError:
                pass
            try:
                if display_win.winfo_exists():
                    display_win.destroy()
            except tk.TclError:
                pass
            if getattr(self, "_active_fullscreen_display", None) is display_win:
                self._active_fullscreen_display = None
                self._active_fullscreen_control_refresh = None

        button_row = ttk.Frame(content)
        button_row.grid(row=6, column=0, columnspan=2, sticky="e")
        ttk.Button(button_row, text="Reset to Recommended", command=reset_recommended).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Cancel Preview", command=cancel_preview).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Save & Finish", command=save_and_finish).pack(side="left")

        content.columnconfigure(0, weight=1)
        dlg.protocol("WM_DELETE_WINDOW", cancel_preview)
        dlg.bind("<Escape>", cancel_preview)
        dlg.update_idletasks()
        screen_width = display_win.winfo_screenwidth()
        # Keep the popup near the top so the lower control dock stays visible while sizing.
        dlg_x = max(18, int((screen_width - dlg.winfo_reqwidth()) / 2))
        dlg_y = max(24, int(display_win.winfo_screenheight() * 0.055))
        dlg.geometry(f"+{dlg_x}+{dlg_y}")
        apply_live_preview()

        def raise_preview_dialog():
            """Bring the popup above the mapped full-screen display safely."""
            try:
                if not dlg.winfo_exists() or not display_win.winfo_exists():
                    return
                dlg.deiconify()
                dlg.attributes("-topmost", True)
                dlg.lift()
                dlg.focus_force()
            except tk.TclError:
                # If a display/driver does not support the foreground request,
                # leave the non-modal popup usable rather than locking input.
                pass

        # Full-screen mapping can finish after the button callback returns.
        # Retry briefly because some Windows mini-PC display drivers delay it.
        dlg.after(80, raise_preview_dialog)
        dlg.after(300, raise_preview_dialog)

    def _on_fullscreen_theme_changed(self, event=None):
        """Save the preferred full-screen theme; changes apply on the next display launch."""
        chosen = str(self.fullscreen_theme_var.get() or "Classic")
        self.fullscreen_theme = chosen if chosen in ("Classic", "Modern") else "Classic"
        self.fullscreen_theme_status_var.set(
            f"Selected: {self.fullscreen_theme}. Applies the next time you open Full Screen Display."
        )
        self._save_data()

    def _window_size_summary_text(self):
        try:
            return (f"Window size: {self.main_window_width_percent}% width × {self.main_window_height_percent}% height\n"
                    f"Detected monitor: {self.winfo_screenwidth()} × {self.winfo_screenheight()} pixels")
        except Exception:
            return f"Window size: {self.main_window_width_percent}% width × {self.main_window_height_percent}% height"

    def reset_tournament_data(self):
        """Clear the current tournament's roster, entry counters, add-ons, and history."""
        confirmed = messagebox.askyesno(
            "Reset Tournament to Zero",
            "This will permanently clear all registered player names, active-player counts, "
            "original entries, rebuys, add-ons, and tournament history. The clock will return "
            "to Level 1. Tournament fees/settings, payout rules, and blind structure will be kept.\n\n"
            "Are you sure you want to reset the tournament?",
            icon="warning",
            parent=self,
        )
        if not confirmed:
            return

        self.running = False
        self.deadline = None
        self.current_level = 0
        self._blind_start_sound_played = False
        self.remaining_seconds = int(self.levels[0].get("minutes", 0)) * 60 if self.levels else 0

        self.players = []
        self.next_player_id = 1
        self.anonymous_original_entries = 0
        self.anonymous_active_players = 0
        self.anonymous_reentries = 0
        self.anonymous_addons = 0
        self.start_time = None
        self.history = []

        self._save_data()
        self._refresh_all()
        messagebox.showinfo(
            "Tournament Reset",
            "The player list is clear and all player, entry, rebuy, and add-on counts are now zero.",
            parent=self,
        )

    def add_player(self):
        name = simpledialog.askstring("Add Player", "Player name:", parent=self)
        if not name or not name.strip():
            return
        if any(p["name"].strip().lower() == name.strip().lower() for p in self.players):
            if not messagebox.askyesno("Duplicate name", "A player with that name already exists. Add another record anyway?"):
                return
        p = {"id":self.next_player_id, "name":name.strip(), "entries":1, "status":"Active",
             "finish_place":"", "notes":"", "registered":datetime.now().isoformat(timespec="seconds")}
        self.players.append(p)
        self.next_player_id += 1
        self.history.append({"event":"player_added","player":p["name"],"time":datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def quick_add_entry_action(self):
        """Record a new initial entry and add that player to the active count."""
        if self.tracking_mode != "Entry count only":
            messagebox.showinfo(
                "Entry count mode",
                "Entry +/- controls are for Entry count only mode. In Named players mode, add players through the roster so each entry remains tied to a player record."
            )
            return
        self.anonymous_original_entries += 1
        self.anonymous_active_players += 1
        self.history.append({"event": "anonymous_entry_added", "time": datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def quick_remove_entry_action(self):
        """Undo one recorded initial entry without changing active players or rebuy count."""
        if self.tracking_mode != "Entry count only":
            messagebox.showinfo(
                "Entry count mode",
                "Entry +/- controls are independent counters for Entry count only mode. In Named players mode, use the player roster so entries remain tied to player records."
            )
            return
        if self.anonymous_original_entries <= 0:
            messagebox.showinfo("No entries to remove", "The initial-entry count is already zero.")
            return
        self.anonymous_original_entries -= 1
        self.history.append({"event": "anonymous_entry_removed", "time": datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def quick_add_player_action(self):
        if self.tracking_mode == "Entry count only":
            self.add_anonymous_player()
        else:
            self.add_player()

    def quick_bust_player_action(self):
        """Record a bust without reducing the total entries already paid for."""
        if self.tracking_mode == "Entry count only":
            self.bust_anonymous_player()
        else:
            self.eliminate_player()

    def quick_add_rebuy_action(self):
        if not self.rebuy_enabled:
            return
        if self.tracking_mode == "Entry count only":
            self.quick_add_rebuys(1)
        else:
            self.reentry_player()

    def quick_remove_rebuy_action(self):
        if not self.rebuy_enabled:
            return
        if self.tracking_mode == "Entry count only":
            self.remove_anonymous_rebuy()
        else:
            self.remove_named_reentry()

    def remove_named_reentry(self):
        if not self.rebuy_enabled:
            return
        p = self._selected_player()
        if not p:
            return
        entries = int(p.get("entries", 1))
        if entries <= 1:
            messagebox.showinfo("No re-buy to remove", "This player has no additional entry to remove.")
            return
        p["entries"] = entries - 1
        self.history.append({"event":"named_reentry_removed", "player":p["name"],
                             "time":datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def add_anonymous_player(self):
        """Increase active players only; silently do nothing at the paid-entry limit."""
        if self.tracking_mode != "Entry count only":
            return
        self._normalize_anonymous_counts()
        total_entries = self.anonymous_original_entries + self.anonymous_reentries
        if self.anonymous_active_players >= total_entries:
            return
        self.anonymous_active_players += 1
        self.history.append({"event": "anonymous_player_reinstated_or_count_corrected", "time": datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def bust_anonymous_player(self):
        """Reduce active players while preserving entries; silently do nothing at zero."""
        if self.tracking_mode != "Entry count only":
            return
        self._normalize_anonymous_counts()
        if self.anonymous_active_players <= 0:
            return
        self.anonymous_active_players -= 1
        self.history.append({"event": "anonymous_player_busted", "time": datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def quick_add_rebuys(self, count):
        """Record rebuys without changing the independently tracked active-player count."""
        if not self.rebuy_enabled:
            return
        if self.tracking_mode != "Entry count only":
            messagebox.showinfo("Entry count mode", "Set Player tracking mode to 'Entry count only' in Tournament Settings to use quick rebuy buttons.")
            return
        # Normalize any legacy count first, then preserve the active-player count while
        # recording a rebuy. The rebuy affects entries/fees only, never active players.
        self._normalize_anonymous_counts()
        active_before = self.anonymous_active_players
        count = max(1, int(count))
        self.anonymous_reentries += count
        self.anonymous_active_players = active_before
        self.history.append({"event": "anonymous_rebuys_added", "count": count, "time": datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def remove_anonymous_rebuy(self):
        """Subtract one anonymous rebuy while leaving players and add-ons unchanged."""
        if not self.rebuy_enabled:
            return
        if self.tracking_mode != "Entry count only":
            messagebox.showinfo(
                "Entry count mode",
                "Set Player tracking mode to 'Entry count only' in Tournament Settings to use the quick rebuy buttons."
            )
            return
        if self.anonymous_reentries <= 0:
            messagebox.showinfo("No rebuys to remove", "The rebuy count is already zero.")
            return
        self.anonymous_reentries -= 1
        # Removing a rebuy can reduce the allowable active-player count if entries are now lower.
        self._normalize_anonymous_counts()
        self.history.append({
            "event": "anonymous_rebuy_removed",
            "count": 1,
            "time": datetime.now().isoformat(timespec="seconds")
        })
        self._save_data()
        self._refresh_all()

    def add_anonymous_addon(self):
        """Record one add-on without changing active players or entry count."""
        if not self.add_on_enabled:
            return
        self.anonymous_addons += 1
        self.history.append({"event": "anonymous_addon_added", "time": datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def remove_anonymous_addon(self):
        """Remove one add-on without changing active players or entry count."""
        if not self.add_on_enabled or self.anonymous_addons <= 0:
            return
        self.anonymous_addons -= 1
        self.history.append({"event": "anonymous_addon_removed", "time": datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def _selected_player(self):
        selected = self.player_tree.selection()
        if not selected:
            messagebox.showinfo("Select a player", "Select a player first.")
            return None
        pid = int(selected[0])
        return next((p for p in self.players if int(p["id"]) == pid), None)

    def reentry_player(self):
        if not self.rebuy_enabled:
            return
        p = self._selected_player()
        if not p:
            return
        if p.get("status") == "Active":
            if not messagebox.askyesno("Re-entry", "This player is marked Active. Record another entry for this player?"):
                return
        # Only the player's paid-entry count changes here. Preserve their status
        # exactly: a rebuy must never create a new active player or reinstate an eliminated one.
        original_status = p.get("status", "Active")
        p["entries"] = int(p.get("entries",1)) + 1
        p["status"] = original_status
        self.history.append({"event":"reentry","player":p["name"],"entries":p["entries"],"time":datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def eliminate_player(self):
        p = self._selected_player()
        if not p:
            return
        if p.get("status") == "Eliminated":
            messagebox.showinfo("Already eliminated", "This player is already marked eliminated.")
            return
        place = simpledialog.askstring("Eliminate Player", "Finish place (optional, e.g. 12):", parent=self)
        p["status"] = "Eliminated"
        p["finish_place"] = (place or "").strip()
        self.history.append({"event":"player_eliminated","player":p["name"],"finish_place":p["finish_place"],
                             "time":datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def reinstate_player(self):
        p = self._selected_player()
        if not p:
            return
        p["status"] = "Active"
        p["finish_place"] = ""
        self.history.append({"event":"player_reinstated","player":p["name"],"time":datetime.now().isoformat(timespec="seconds")})
        self._save_data()
        self._refresh_all()

    def remove_player(self):
        p = self._selected_player()
        if not p:
            return
        if messagebox.askyesno("Remove player", f"Permanently remove {p['name']} from this tournament record?"):
            self.players = [x for x in self.players if x["id"] != p["id"]]
            self._save_data()
            self._refresh_all()

    def edit_player(self):
        p = self._selected_player()
        if not p:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Edit Player")
        dlg.transient(self)
        dlg.grab_set()
        name_var = tk.StringVar(value=p["name"])
        notes_var = tk.StringVar(value=p.get("notes",""))
        ttk.Label(dlg,text="Player name").grid(row=0,column=0,sticky="w",padx=12,pady=6)
        ttk.Entry(dlg,textvariable=name_var,width=32).grid(row=0,column=1,padx=12,pady=6)
        ttk.Label(dlg,text="Notes").grid(row=1,column=0,sticky="w",padx=12,pady=6)
        ttk.Entry(dlg,textvariable=notes_var,width=32).grid(row=1,column=1,padx=12,pady=6)
        def save():
            if name_var.get().strip():
                p["name"] = name_var.get().strip()
                p["notes"] = notes_var.get().strip()
                self._save_data()
                self._refresh_all()
                dlg.destroy()
            else:
                messagebox.showerror("Invalid name","Player name cannot be blank.",parent=dlg)
        ttk.Button(dlg,text="Save",command=save).grid(row=2,column=0,columnspan=2,pady=10)

    def export_report(self):
        path = filedialog.asksaveasfilename(title="Export Tournament Summary", defaultextension=".txt",
                                            filetypes=[("Text report","*.txt")],
                                            initialfile="tournament_report.txt")
        if not path:
            return
        text = self.report_text.get("1.0","end-1c")
        try:
            with open(path,"w",encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Export complete",f"Report saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export failed",str(e))

    def export_players_csv(self):
        path = filedialog.asksaveasfilename(title="Export Player List", defaultextension=".csv",
                                            filetypes=[("CSV file","*.csv")], initialfile="tournament_players.csv")
        if not path:
            return
        try:
            with open(path,"w",newline="",encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["id","name","entries","status","finish_place","notes","registered"])
                writer.writeheader()
                for p in self.players:
                    writer.writerow({k:p.get(k,"") for k in writer.fieldnames})
            messagebox.showinfo("Export complete",f"Player list saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export failed",str(e))

    def export_levels_csv(self):
        path = filedialog.asksaveasfilename(title="Export Blind Structure", defaultextension=".csv",
                                            filetypes=[("CSV file","*.csv")], initialfile="blind_structure.csv")
        if not path:
            return
        try:
            with open(path,"w",newline="",encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["order","name","kind","minutes","sb","bb"])
                writer.writeheader()
                for i, lev in enumerate(self.levels,1):
                    writer.writerow({"order": i, "name": lev.get("name", ""), "kind": lev.get("kind", "Play"),
                                     "minutes": lev.get("minutes", 20), "sb": lev.get("sb", 0), "bb": lev.get("bb", 0)})
            messagebox.showinfo("Export complete",f"Blind structure saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export failed",str(e))

    def _seconds_until_next_break(self):
        """Return seconds until the next future break starts, or None if there is none."""
        next_break_index = next(
            (i for i in range(self.current_level + 1, len(self.levels))
             if self.levels[i].get("kind") == "Break"),
            None,
        )
        if next_break_index is None:
            return None
        total = self._current_seconds()
        for i in range(self.current_level + 1, next_break_index):
            total += max(0, int(self.levels[i].get("minutes", 0))) * 60
        return total

    def _open_display(self):
        modern_theme = getattr(self, "fullscreen_theme", "Classic") == "Modern"
        win = tk.Toplevel(self)
        self._active_fullscreen_display = win
        self._active_fullscreen_control_refresh = None
        win.title("Tournament Display")
        win.configure(bg="#050a10" if modern_theme else "#176ba0")
        win.attributes("-fullscreen", True)

        def close_display(event=None):
            if getattr(self, "_active_fullscreen_display", None) is win:
                self._active_fullscreen_display = None
                self._active_fullscreen_control_refresh = None
            if win.winfo_exists():
                win.destroy()
        win.bind("<Escape>", close_display)

        if modern_theme:
            bg = "#050a10"
            bar_bg = "#111d29"
            dark_text = "#edf7ff"
            panel_bg = "#0b1621"
            white = "#f4f9ff"
            muted = "#26cfff"
            next_bg = "#142332"
            next_text = "#afc7dc"
            next_divider = "#367b9c"
            current_divider = "#28647e"
            slider_trough = "#28465a"
            panel_border = "#26cfff"
            title_font_size = 26
            info_caption_size = 10
            info_value_size = 14
            current_panel_padx = 22
            current_panel_pady = 1
            current_timer_size = 54
            current_caption_size = 11
            current_blinds_size = 42
            next_panel_padx = 95
            next_panel_pady = 1
            next_timer_size = 27
            next_caption_size = 9
            next_blinds_size = 24
            dashboard_padx = 12
            dashboard_pady = 3
            dashboard_heading_size = 16
            dashboard_body_size = 15
            dashboard_wraplength = 215
            prizes_wraplength = 230
            pie_width, pie_height = 220, 154
            pot_box_padx, pot_box_pady = 5, 4
            pot_header_size, benefit_amount_size, player_pot_size = 10, 17, 19
            control_border_pad = 2
        else:
            bg = "#176ba0"
            bar_bg = "#c2dbe9"
            dark_text = "#30383e"
            panel_bg = "#145b89"
            white = "#ffffff"
            muted = "#dcebf4"
            next_bg = "#a9c9dc"
            next_text = "#4c5c66"
            next_divider = "#829ca9"
            current_divider = "#788d99"
            slider_trough = "#c2dbe9"
            panel_border = "#c1dceb"
            title_font_size = 35
            info_caption_size = 12
            info_value_size = 17
            current_panel_padx = 20
            current_panel_pady = 10
            current_timer_size = 74
            current_caption_size = 13
            current_blinds_size = 50
            next_panel_padx = 150
            next_panel_pady = 4
            next_timer_size = 38
            next_caption_size = 10
            next_blinds_size = 31
            dashboard_padx = 22
            dashboard_pady = 12
            dashboard_heading_size = 22
            dashboard_body_size = 21
            dashboard_wraplength = 460
            prizes_wraplength = 330
            pie_width, pie_height = 190, 180
            pot_box_padx, pot_box_pady = 10, 8
            pot_header_size, benefit_amount_size, player_pot_size = 13, 23, 26
            control_border_pad = 0

        if modern_theme:
            # Use a much larger timer pie, while reserving room for up to ten
            # payout rows in the equal-height dashboard cards at 720p.
            screen_height = win.winfo_screenheight()
            pie_width = max(210, min(300, int(win.winfo_screenwidth() * 0.19)))
            if screen_height <= 800:
                pie_height = 154
                # The narrower Status/Statistics columns must stay readable at 720p.
                # Use a compact text size/wrap width in those cards; the clock and
                # blind figures remain large and the wider Prizes card is unchanged.
                dashboard_body_size = 12
                dashboard_wraplength = 155
            else:
                pie_height = max(210, min(270, int(screen_height * 0.245)))
                # Larger TVs have more vertical room; scale the core timer/blind
                # values and dashboard type up so the display does not feel sparse.
                title_font_size = 30
                info_caption_size = 11
                info_value_size = 16
                current_panel_pady = 4
                current_timer_size = 70
                current_caption_size = 14
                current_blinds_size = 52
                next_panel_pady = 3
                next_timer_size = 34
                next_caption_size = 11
                next_blinds_size = 30
                dashboard_pady = 8
                dashboard_heading_size = 19
                dashboard_body_size = 17
                dashboard_wraplength = 300
                prizes_wraplength = 270

        def add_modern_rounded_surface(frame, fill_color, outline_color=None, radius=16, border_width=2, outside_color=None):
            """Give a Modern-theme frame a rounded, resizable Canvas-backed surface."""
            if not modern_theme:
                return None
            outside = outside_color or bg
            outline = outline_color or panel_border
            frame.configure(bg=outside, bd=0, highlightthickness=0)
            canvas = tk.Canvas(frame, bg=outside, highlightthickness=0, bd=0)
            canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
            canvas.tk.call("lower", canvas._w)

            def redraw(event=None):
                width = max(4, canvas.winfo_width())
                height = max(4, canvas.winfo_height())
                r = max(3, min(radius, (width - 2) / 4, (height - 2) / 4))
                x0, y0, x1, y1 = 1, 1, width - 1, height - 1
                points = [(x0 + r, y0), (x1 - r, y0)]
                corners = [
                    (x1 - r, y0 + r, -90, 0),
                    (x1 - r, y1 - r, 0, 90),
                    (x0 + r, y1 - r, 90, 180),
                    (x0 + r, y0 + r, 180, 270),
                ]
                for cx, cy, start_deg, end_deg in corners:
                    for step in range(1, 13):
                        angle = (start_deg + (end_deg - start_deg) * step / 12) * 3.141592653589793 / 180
                        points.append((cx + r * __import__('math').cos(angle), cy + r * __import__('math').sin(angle)))
                    if (start_deg, end_deg) == (0, 90):
                        points.append((x0 + r, y1))
                    elif (start_deg, end_deg) == (90, 180):
                        points.append((x0, y0 + r))
                canvas.delete('rounded-surface')
                flattened = [coordinate for point in points for coordinate in point]
                canvas.create_polygon(
                    *flattened, fill=fill_color, outline=outline, width=border_width,
                    joinstyle=tk.ROUND, tags=('rounded-surface',)
                )
                canvas.tag_lower('rounded-surface')

            frame.bind('<Configure>', redraw, add='+')
            canvas.bind('<Configure>', redraw, add='+')
            return canvas

        # TV overscan-safe area: keep headings and lower controls away from the physical edges.
        # Percent-based insets adapt to different television resolutions/aspect ratios.
        safe_area = tk.Frame(win, bg=bg)
        safe_area.place(relx=0.035, rely=0.042, relwidth=0.93, relheight=0.916)

        def duration_text(seconds):
            """Use MM:SS for durations under one hour; H:MM:SS when hours are needed."""
            seconds = max(0, int(seconds))
            hours, remainder = divmod(seconds, 3600)
            minutes, sec = divmod(remainder, 60)
            if hours:
                return f"{hours:02d}:{minutes:02d}:{sec:02d}"
            # Avoid an unnecessary leading hours field for ordinary blind levels,
            # e.g. display a 13-minute blind as 13:00 rather than 00:13:00.
            return f"{minutes:02d}:{sec:02d}"

        # Header: tournament name on the left and the current level/status/break clock on the right.
        header = tk.Frame(safe_area, bg=bg)
        header.pack(side="top", fill="x", padx=8, pady=((0, 1) if modern_theme else (3, 4)))
        title = tk.Label(header, text=self.tournament_name, bg=bg, fg=white,
                         font=("Segoe UI", title_font_size, "bold"), anchor="w")
        title.pack(side="left", fill="x", expand=True)
        info = tk.Frame(header, bg=bg)
        info.pack(side="right", padx=(18, 0))
        info_vars = {}
        for idx, (key, caption) in enumerate([
            ("level", "LEVEL"), ("clock", "CLOCK"), ("break", "BREAK IN")
        ]):
            cell = tk.Frame(info, bg=bg, padx=(9 if modern_theme else 12))
            cell.pack(side="left", anchor="n")
            if idx:
                tk.Frame(info, bg=muted, width=2, height=(34 if modern_theme else 64)).pack(side="left", padx=1, pady=2)
            tk.Label(cell, text=caption, bg=bg, fg=white,
                     font=("Segoe UI", info_caption_size, "bold"), anchor="w").pack(anchor="w")
            value = tk.Label(cell, text="—", bg=bg, fg=white,
                             font=("Segoe UI", info_value_size, "bold"), anchor="w")
            value.pack(anchor="w", pady=((2 if modern_theme else 4), 0))
            info_vars[key] = value

        # Large current level clock and blind values on a single high-contrast band.
        current_panel = tk.Frame(safe_area, bg=(bg if modern_theme else bar_bg), padx=current_panel_padx, pady=current_panel_pady)
        add_modern_rounded_surface(current_panel, bar_bg, panel_border, radius=20, border_width=2)
        current_panel.pack(side="top", fill="x", padx=8, pady=((2, 2) if modern_theme else (4, 4)))
        # Keep the time and blind-value areas equal-width so the divider sits
        # on the true horizontal midpoint of the current-level band.
        current_panel.grid_columnconfigure(0, weight=5, uniform="currentrow")
        current_panel.grid_columnconfigure(1, weight=0)
        current_panel.grid_columnconfigure(2, weight=5, uniform="currentrow")
        timer = tk.Label(current_panel, text="00:20:00", bg=bar_bg, fg=dark_text,
                         font=("Segoe UI", current_timer_size, "bold"), anchor="center")
        timer.grid(row=0, column=0, sticky="nsew", padx=(2, 12))
        tk.Frame(current_panel, bg=current_divider, width=2).grid(row=0, column=1, sticky="ns", padx=7, pady=3)
        blind_block = tk.Frame(current_panel, bg=bar_bg)
        blind_block.grid(row=0, column=2, sticky="nsew", padx=(15, 8))
        current_caption = tk.Label(blind_block, text="CURRENT BLINDS", bg=bar_bg, fg=dark_text,
                                   font=("Segoe UI", current_caption_size, "bold"), anchor="w")
        current_caption.pack(anchor="w")
        # Center only the numeric blind value; keep the CURRENT BLINDS label
        # left-aligned so the label/value hierarchy remains familiar.
        blinds = tk.Label(blind_block, text="25 / 50", bg=bar_bg, fg=dark_text,
                          font=("Segoe UI", current_blinds_size, "bold"), anchor="center", justify="center")
        blinds.pack(fill="x", anchor="center")

        # Next-level preview: a smaller secondary bar similar to the reference display.
        next_panel = tk.Frame(safe_area, bg=(bg if modern_theme else next_bg), padx=(14 if modern_theme else 18), pady=next_panel_pady)
        add_modern_rounded_surface(next_panel, next_bg, next_divider if modern_theme else panel_border, radius=16, border_width=1)
        next_panel.pack(side="top", padx=next_panel_padx, pady=((0, 2) if modern_theme else (2, 5)), fill="x")
        # Match the current-level row: equal-width halves put this divider at
        # the center of the second band as well.
        next_panel.grid_columnconfigure(0, weight=4, uniform="nextrow")
        next_panel.grid_columnconfigure(1, weight=0)
        next_panel.grid_columnconfigure(2, weight=4, uniform="nextrow")
        next_timer = tk.Label(next_panel, text="00:20:00", bg=next_bg, fg=next_text,
                              font=("Segoe UI", next_timer_size, "bold"), anchor="center")
        next_timer.grid(row=0, column=0, sticky="nsew", padx=(2, 10))
        tk.Frame(next_panel, bg=next_divider, width=2).grid(row=0, column=1, sticky="ns", padx=5, pady=2)
        next_blind_block = tk.Frame(next_panel, bg=next_bg)
        next_blind_block.grid(row=0, column=2, sticky="nsew", padx=(10, 5))
        next_caption = tk.Label(next_blind_block, text="NEXT LEVEL", bg=next_bg, fg=next_text,
                               font=("Segoe UI", next_caption_size, "bold"), anchor="w")
        next_caption.pack(anchor="w")
        # Center the next-level blind values, while leaving NEXT LEVEL aligned
        # to the left above them.
        next_blinds = tk.Label(next_blind_block, text="50 / 100", bg=next_bg, fg=next_text,
                               font=("Segoe UI", next_blinds_size, "bold"), anchor="center", justify="center")
        next_blinds.pack(fill="x", anchor="center")

        # Controls are grouped in a single container so they can be hidden together.
        footer = tk.Frame(safe_area, bg=bg)
        footer.pack(side="bottom", fill="x", padx=0, pady=0)
        control_area = tk.Frame(
            footer, bg=bg,
            highlightbackground=("#26cfff" if modern_theme else bg),
            highlightthickness=(2 if modern_theme else 0),
            padx=(22 if modern_theme else 0),
            pady=((4 if win.winfo_screenheight() <= 800 else 8) if modern_theme else control_border_pad)
        )
        add_modern_rounded_surface(control_area, panel_bg, panel_border, radius=22, border_width=2)
        control_area.pack(side="top", fill="x")

        # The clock buttons are packed as one group and centered against the full
        # available width. Exit remains independently anchored to the left, so its
        # width can never pull the clock group away from the horizontal center.
        control_header = tk.Frame(control_area, bg=(panel_bg if modern_theme else bg))
        control_header.pack(fill="x", pady=(0, 3))
        exit_button = self._make_action_button(
            control_header, "Exit Full Screen", close_display,
            force="neutral", dark=True
        )
        exit_button.place(relx=0.0, rely=0.5, anchor="w", x=4)
        clock_controls = tk.Frame(control_header, bg=(panel_bg if modern_theme else bg))
        clock_controls.pack(anchor="center")
        self._make_action_button(clock_controls, "▶ Resume Clock", self.start_clock,
                                 force="positive", dark=True).pack(side="left", padx=4)
        self._make_action_button(
            clock_controls, "Ⅱ Pause Clock", self.pause_clock,
            force="negative", dark=True
        ).pack(side="left", padx=4)
        self._make_action_button(clock_controls, "↻ Reset Level", self.reset_level,
                                 force="neutral", dark=True).pack(side="left", padx=4)

        # Manual time control sits centered underneath the clock buttons, above the
        # tournament action groups. The slider changes actual remaining seconds.
        time_adjust_row = tk.Frame(control_area, bg=(panel_bg if modern_theme else bg))
        time_adjust_row.pack(fill="x", pady=((0, 3) if modern_theme else (0, 5)))
        time_adjust_inner = tk.Frame(time_adjust_row, bg=(panel_bg if modern_theme else bg))
        time_adjust_inner.pack(anchor="center")
        tk.Label(time_adjust_inner, text="ADJUST TIME", bg=(panel_bg if modern_theme else bg), fg=white,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=(2, 8))
        self._make_action_button(time_adjust_inner, "−30 sec", lambda: change_time_by(-30),
                                 force="negative", dark=True).pack(side="left", padx=4)
        time_slider_limit = {"value": self._current_level_duration_seconds(),
                             "level": self.current_level}
        initial_time_seconds = min(max(0, self._current_seconds()), time_slider_limit["value"])
        if initial_time_seconds != self._current_seconds():
            # Migrate any over-duration time left by older versions into the new per-level range.
            self.set_remaining_seconds(initial_time_seconds, save=True, record_history=False, refresh=False)
        time_slider_var = tk.DoubleVar(value=initial_time_seconds)
        time_adjust_value = tk.Label(time_adjust_inner, text=duration_text(initial_time_seconds), bg=(panel_bg if modern_theme else bg), fg=white,
                                     font=("Segoe UI", 12, "bold"), width=10, anchor="center")
        time_slider_state = {"dragging": False, "syncing": False}
        time_scale = tk.Scale(
            time_adjust_inner, from_=0, to=time_slider_limit["value"], orient="horizontal",
            variable=time_slider_var, showvalue=False, resolution=1, length=470,
            bg=(panel_bg if modern_theme else bg), fg=white, activebackground="#65d6a6", troughcolor=slider_trough,
            highlightthickness=0, bd=0, sliderlength=22, width=16,
            command=lambda value: on_time_slider(value), cursor="hand2",
        )
        time_scale.pack(side="left", padx=8)
        time_adjust_value.pack(side="left", padx=6)
        self._make_action_button(time_adjust_inner, "+30 sec", lambda: change_time_by(30),
                                 force="positive", dark=True).pack(side="left", padx=4)

        def sync_time_adjustment(seconds, new_level=False):
            if time_slider_state["dragging"]:
                return
            duration = self._current_level_duration_seconds()
            if new_level or time_slider_limit["level"] != self.current_level:
                time_slider_limit["level"] = self.current_level
                time_slider_limit["value"] = duration
            else:
                # Keep the scale's endpoint tied to this level's configured duration;
                # never expand it to represent the whole tournament or extra minutes.
                time_slider_limit["value"] = duration
            bounded_seconds = max(0, min(int(seconds), duration))
            if bounded_seconds != int(seconds):
                self.set_remaining_seconds(bounded_seconds, save=True, record_history=False, refresh=False)
                seconds = bounded_seconds
            time_slider_state["syncing"] = True
            try:
                time_scale.configure(from_=0, to=duration)
                time_slider_var.set(bounded_seconds)
                time_adjust_value.configure(text=duration_text(bounded_seconds))
            finally:
                time_slider_state["syncing"] = False

        def on_time_slider(value):
            if time_slider_state["syncing"]:
                return
            # The slider is limited to the current row's configured duration.
            time_slider_state["dragging"] = True
            duration = self._current_level_duration_seconds()
            seconds = max(0, min(duration, int(round(float(value)))))
            self.set_remaining_seconds(seconds, save=False, record_history=False, refresh=False)
            time_adjust_value.configure(text=duration_text(seconds))
            timer.configure(text=duration_text(seconds))

        def finish_time_slider(event=None):
            def finish():
                if not win.winfo_exists():
                    return
                time_slider_state["dragging"] = False
                seconds = max(0, int(round(float(time_scale.get()))))
                self.set_remaining_seconds(seconds, save=True, record_history=True, refresh=True)
                sync_time_adjustment(seconds)
            win.after_idle(finish)

        time_scale.bind("<ButtonPress-1>", lambda event: time_slider_state.update(dragging=True), add="+")
        time_scale.bind("<ButtonRelease-1>", finish_time_slider, add="+")

        def change_time_by(delta_seconds):
            duration = self._current_level_duration_seconds()
            current = max(0, min(self._current_seconds(), duration))
            seconds = max(0, min(duration, current + int(delta_seconds)))
            self.set_remaining_seconds(seconds)
            timer.configure(text=duration_text(seconds))
            sync_time_adjustment(seconds)

        quick_controls = tk.Frame(control_area, bg=(panel_bg if modern_theme else bg))
        quick_controls.pack(fill="x", pady=((1, 1) if modern_theme else (2, 3)))
        for col in range(5):
            quick_controls.grid_columnconfigure(col, weight=1, uniform="displaygroups")
        display_quick_groups = {
            "Entries": self._build_action_group(quick_controls, "Entries", [
                ("Add Entry +", self.quick_add_entry_action),
                ("Remove Entry −", self.quick_remove_entry_action),
            ], dark=True),
            "Players": self._build_action_group(quick_controls, "Players", [
                ("Add Player +", self.quick_add_player_action),
                ("Bust Player −", self.quick_bust_player_action),
            ], dark=True),
            "Re-buys": self._build_action_group(quick_controls, "Re-buys", [
                ("Re-buy +", self.quick_add_rebuy_action),
                ("Re-buy −", self.quick_remove_rebuy_action),
            ], dark=True),
            "Add-ons": self._build_action_group(quick_controls, "Add-ons", [
                ("Add-on +", self.add_anonymous_addon),
                ("Add-on −", self.remove_anonymous_addon),
            ], dark=True),
            "Level": self._build_action_group(quick_controls, "Level", [
                ("Next Level", self.next_level, "positive"),
                ("Previous Level", self.previous_level, "negative"),
            ], dark=True),
        }
        self._layout_quick_groups(quick_controls, display_quick_groups,
                                  include_rebuys=self.rebuy_enabled, include_addons=self.add_on_enabled)
        if modern_theme:
            compact_modern_controls = win.winfo_screenheight() <= 800
            for group in display_quick_groups.values():
                # Compact the action dock vertically at 720p so the ten-place
                # dashboard remains visible; larger displays restore generous
                # button padding and type size.
                group.configure(
                    bg=bg, highlightbackground="#267d9d",
                    padx=(8 if compact_modern_controls else 11),
                    pady=(2 if compact_modern_controls else 6),
                )
                add_modern_rounded_surface(group, "#101d29", "#267d9d", radius=13, border_width=1)
                for child in group.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(
                            bg="#101d29", fg="#f1f8ff",
                            font=("Segoe UI", 8 if compact_modern_controls else 10, "bold"),
                        )
                        child.pack_configure(pady=(0, 1) if compact_modern_controls else (0, 3))
                    elif isinstance(child, tk.Button):
                        child.configure(
                            font=("Segoe UI", 8 if compact_modern_controls else 10, "bold"),
                            padx=(5 if compact_modern_controls else 7),
                            pady=(1 if compact_modern_controls else 3),
                        )
                        child.pack_configure(pady=0 if compact_modern_controls else 1)
        # Apply the saved full-screen control font and sizing to all action labels/buttons.
        # This affects controls only; the player-facing dashboard remains independently sized.
        control_font_size = max(8, min(15, int(getattr(self, "fullscreen_control_font_size", 10))))
        control_button_scale = max(75, min(150, int(getattr(self, "fullscreen_control_button_scale", 100)))) / 100.0
        compact_modern_controls = modern_theme and win.winfo_screenheight() <= 800

        def apply_control_appearance(container):
            base_padx = 5 if compact_modern_controls else 7
            base_pady = 1 if compact_modern_controls else (3 if modern_theme else 4)
            for child in container.winfo_children():
                if isinstance(child, tk.Button):
                    child.configure(
                        font=("Segoe UI", control_font_size, "bold"),
                        padx=max(2, int(round(base_padx * control_button_scale))),
                        pady=max(1, int(round(base_pady * control_button_scale))),
                    )
                elif isinstance(child, tk.Label):
                    label_text = str(child.cget("text") or "").strip()
                    label_size = control_font_size + 1 if label_text in ("Entries", "Players", "Re-buys", "Add-ons", "Level", "ADJUST TIME") else control_font_size
                    if child is time_adjust_value:
                        label_size = control_font_size + 2
                    child.configure(font=("Segoe UI", label_size, "bold"))
                elif isinstance(child, tk.Scale):
                    child.configure(
                        width=max(12, int(round(16 * control_button_scale))),
                        sliderlength=max(18, int(round(22 * control_button_scale))),
                    )
                apply_control_appearance(child)

        apply_control_appearance(control_area)
        for group in display_quick_groups.values():
            if modern_theme:
                group_padx = 8 if compact_modern_controls else 11
                group_pady = 2 if compact_modern_controls else 6
            else:
                group_padx, group_pady = 6, 5
            group.configure(
                padx=max(3, int(round(group_padx * control_button_scale))),
                pady=max(2, int(round(group_pady * control_button_scale))),
            )

        display_rebuy_enabled = self.rebuy_enabled
        display_addon_enabled = self.add_on_enabled

        # Put the mouse-only control toggle in the header, where it remains visible even
        # when many payout rows make the dashboard taller than the available screen height.
        # place() does not participate in header geometry, so it cannot shift the panels.
        controls_visible = {"value": True}

        animation_state = {"busy": False}
        modern_dock = {"enabled": False, "control_height": 0, "tab_height": 40, "footer_top": 0}

        def _set_toggle_label(visible):
            if modern_theme:
                toggle_button.configure(text=("HIDE CONTROLS  ⌄" if visible else "SHOW CONTROLS  ⌃"))
            else:
                toggle_button.configure(text=("HIDE CONTROLS" if visible else "SHOW CONTROLS"))

        def _animate_modern_controls(target_visible):
            if animation_state["busy"] or not modern_dock["enabled"]:
                return
            animation_state["busy"] = True
            control_height = modern_dock["control_height"]
            tab_height = modern_dock["tab_height"]
            footer_top = modern_dock["footer_top"]
            # The tab is a fixed-size beacon, independent of the scaled control
            # dock. Anchor its hidden endpoint to the actual safe-area bottom, not
            # to footer_top + control_height (which can exceed the screen after
            # button-size scaling and cause the tab/mask to slide off-screen).
            safe_bottom_tab_y = max(0, safe_area.winfo_height() - tab_height)
            if target_visible:
                start_control_y, end_control_y = control_height, 0
                start_tab_y, end_tab_y = safe_bottom_tab_y, footer_top - tab_height
            else:
                start_control_y, end_control_y = 0, control_height
                start_tab_y, end_tab_y = footer_top - tab_height, safe_bottom_tab_y
            steps = 15
            interval_ms = 14

            def frame_step(step):
                if not win.winfo_exists():
                    return
                fraction = min(1.0, step / steps)
                control_y = round(start_control_y + (end_control_y - start_control_y) * fraction)
                tab_y = round(start_tab_y + (end_tab_y - start_tab_y) * fraction)
                control_area.place_configure(y=control_y)
                toggle_button.place_configure(y=tab_y)
                if step < steps:
                    win.after(interval_ms, lambda: frame_step(step + 1))
                else:
                    controls_visible["value"] = target_visible
                    _set_toggle_label(target_visible)
                    animation_state["busy"] = False
                    sync_toggle_beacon(self._current_seconds())

            frame_step(0)

        def toggle_controls():
            if not win.winfo_exists():
                return
            if modern_theme and modern_dock["enabled"]:
                if not animation_state["busy"]:
                    _animate_modern_controls(not controls_visible["value"])
                return
            if controls_visible["value"]:
                control_area.pack_forget()
                controls_visible["value"] = False
                _set_toggle_label(False)
            else:
                control_area.pack(side="top", fill="x")
                controls_visible["value"] = True
                _set_toggle_label(True)
            # Classic theme retains the established behavior; both themes keep
            # the beacon color tied to remaining time rather than visibility.
            sync_toggle_beacon(self._current_seconds())

        toggle_parent = safe_area if modern_theme else header
        toggle_button = tk.Button(
            toggle_parent, text="HIDE CONTROLS  ⌄" if modern_theme else "HIDE CONTROLS",
            command=toggle_controls,
            bg="#22a56b", activebackground="#22a56b", fg="#ffffff", activeforeground="#ffffff",
            font=("Segoe UI", 11 if modern_theme else 12, "bold"),
            relief=("raised" if modern_theme else "flat"), bd=(1 if modern_theme else 0),
            padx=(22 if modern_theme else 14), pady=(7 if modern_theme else 7), cursor="hand2",
            width=(21 if modern_theme else 16),
            highlightthickness=(2 if modern_theme else 0),
            highlightbackground=("#26cfff" if modern_theme else "#176ba0"),
            highlightcolor=("#26cfff" if modern_theme else "#176ba0")
        )
        toggle_button.configure(
            # The Modern beacon tab is a fixed-size animation anchor. Button-size
            # scaling applies to the control dock, not to this tab.
            font=("Segoe UI", 11 if modern_theme else control_font_size, "bold"),
            padx=(12 if modern_theme else max(4, int(round(14 * control_button_scale)))),
            pady=(4 if modern_theme else max(2, int(round(7 * control_button_scale)))),
        )
        if not modern_theme:
            # Classic retains the current top-centered toggle location.
            toggle_button.place(relx=0.5, rely=0.5, anchor="center")

        def sync_toggle_beacon(seconds):
            """Make the always-visible Hide/Show Controls button mirror the timer pie color."""
            if not toggle_button.winfo_exists():
                return
            beacon_color = self._time_pie_color(seconds)
            # Yellow uses dark text for contrast; green and red use white text.
            beacon_text = "#17232c" if beacon_color == "#f0c419" else "#ffffff"
            toggle_button.configure(
                bg=beacon_color,
                activebackground=beacon_color,
                fg=beacon_text,
                activeforeground=beacon_text,
            )

        # Dashboard is top-anchored directly below the current/next-level panels.
        # This keeps its position fixed when the control area is hidden or restored.
        dashboard = tk.Frame(safe_area, bg=bg)
        # Top-anchored, content-sized dashboard. The countdown pie is now on the
        # full-screen display, between Statistics and Prizes; the main page stays simple.
        # Packing at the top keeps its position stable when controls are hidden/restored.
        if modern_theme:
            dashboard_top_padding = 6 if win.winfo_screenheight() <= 800 else min(86, 6 + int((win.winfo_screenheight() - 800) * 0.18))
            # Keep the preferred dashboard height when it fits, but let its frame
            # claim only the free space left after the current control-dock size.
            dashboard.pack(side="top", fill="x", padx=0, pady=(dashboard_top_padding, 2))
        else:
            dashboard.pack(side="top", fill="x", padx=0, pady=(4, 4))
        dashboard.grid_rowconfigure(0, weight=1)
        # In Modern, keep the timer pie's center on the screen's horizontal
        # midpoint. The combined Status + Statistics widths must equal the
        # Prizes width; the center column gets extra room for the larger pie.
        # Classic keeps its original (2, 2, 2, 4) proportions unchanged.
        dashboard_weights = (8, 8, 12, 16) if modern_theme else (2, 2, 2, 4)
        for col, weight in enumerate(dashboard_weights):
            dashboard.columnconfigure(col, weight=weight, uniform="displaydashboard")
        screen_dashboard_vars = {}
        prizes_text_label = None
        time_pie_canvas = None
        dashboard_panels = {}
        dashboard_heading_labels = {}
        dashboard_body_labels = {}
        dashboard_dividers = {}
        dashboard_panel_base_padx = {}
        dashboard_base_required_height = {"value": None}
        dashboard_fit_scale = {"value": 1.0}
        dashboard_layout_signature = {"value": None}
        player_pot_amount_label = None
        pot_box = None
        prizes_body_frame = None
        for column, (heading, key) in enumerate([
            ("STATUS", "status"), ("STATISTICS", "statistics"),
            ("TIME REMAINING", "time_pie"), ("PRIZES", "prizes")
        ]):
            # Keep side-card text from clipping after narrowing Status and Statistics.
            # Less inner padding on those two cards compensates for their smaller width.
            if modern_theme and key in ("status", "statistics"):
                inner_panel_padx = 8
            else:
                inner_panel_padx = dashboard_padx + (3 if modern_theme else 0)
            panel = tk.Frame(dashboard, bg=(bg if modern_theme else panel_bg), highlightbackground=panel_border, highlightthickness=2,
                             padx=inner_panel_padx, pady=dashboard_pady)
            add_modern_rounded_surface(panel, panel_bg, panel_border, radius=17, border_width=2)
            panel.grid(row=0, column=column, sticky="nsew", padx=6)
            dashboard_panels[key] = panel
            dashboard_panel_base_padx[key] = inner_panel_padx
            # Center only the Time Remaining title over its pie chart; keep other
            # dashboard headings left-aligned as before.
            heading_anchor = "center" if key == "time_pie" else "w"
            heading_justify = "center" if key == "time_pie" else "left"
            label_side_padx = 4 if modern_theme and key in ("status", "statistics") else (8 if modern_theme else 0)
            heading_label = tk.Label(panel, text=heading, bg=panel_bg, fg=white,
                                     font=("Segoe UI", dashboard_heading_size, "bold"), anchor=heading_anchor,
                                     justify=heading_justify)
            heading_label.pack(fill="x", padx=label_side_padx, pady=(2 if modern_theme else 0, 0))
            dashboard_heading_labels[key] = heading_label
            divider = tk.Frame(panel, bg=("#26cfff" if modern_theme else "#c1dceb"), height=2 if modern_theme else 3)
            divider.pack(fill="x", padx=label_side_padx,
                         pady=((3, 5) if modern_theme else (5, 8)))
            dashboard_dividers[key] = divider
            body_var = tk.StringVar(value="")
            screen_dashboard_vars[key] = body_var
            if key == "time_pie":
                time_pie_canvas = tk.Canvas(
                    panel, width=pie_width, height=pie_height, bg=panel_bg,
                    highlightthickness=0, bd=0
                )
                time_pie_canvas.pack(fill="both", expand=True, padx=(7 if modern_theme else 2), pady=((3, 5) if modern_theme else (0, 2)))
                time_pie_canvas.bind(
                    "<Configure>",
                    lambda event, canvas=time_pie_canvas: self._draw_time_pie(canvas)
                )
            elif key == "prizes":
                prizes_body = tk.Frame(panel, bg=panel_bg)
                prizes_body_frame = prizes_body
                prizes_body.pack(fill="both", expand=True, padx=(7 if modern_theme else 0), pady=((3, 3) if modern_theme else (2, 0)))
                prizes_body.grid_columnconfigure(0, weight=3)
                prizes_body.grid_columnconfigure(1, weight=1)
                prizes_text_label = tk.Label(prizes_body, textvariable=body_var, bg=panel_bg, fg=white,
                                             font=("Segoe UI", (12 if modern_theme else dashboard_body_size), "bold"),
                                             justify="left", anchor="nw", wraplength=prizes_wraplength)
                prizes_text_label.grid(row=0, column=0, sticky="nw", padx=(0, 12))
                dashboard_body_labels[key] = prizes_text_label
                pot_box = tk.Frame(prizes_body, bg=panel_bg, highlightbackground=panel_border, highlightthickness=1,
                                   padx=(pot_box_padx + (3 if modern_theme else 0)), pady=(pot_box_pady + (2 if modern_theme else 0)))
                add_modern_rounded_surface(pot_box, panel_bg, panel_border, radius=12, border_width=1, outside_color=panel_bg)
                pot_box.grid(row=0, column=1, sticky="n", padx=(2, 0))
                benefit_var = tk.StringVar(value="")
                screen_dashboard_vars["benefit_pot"] = benefit_var
                benefit_header = tk.Label(pot_box, text="BENEFIT POT", bg=panel_bg, fg=white,
                                          font=("Segoe UI", pot_header_size, "bold"), justify="center", wraplength=120 if modern_theme else 160)
                benefit_amount_label = tk.Label(pot_box, textvariable=benefit_var, bg=panel_bg, fg="#f0c419",
                                                font=("Segoe UI", benefit_amount_size, "bold"), justify="center", anchor="center")
                player_pot_header = tk.Label(pot_box, text="TOTAL PLAYER POT", bg=panel_bg, fg=white,
                                             font=("Segoe UI", pot_header_size, "bold"), justify="center", wraplength=120 if modern_theme else 160)
                player_pot_header.pack(fill="x", pady=(2, 8))
                pot_var = tk.StringVar(value="$0")
                screen_dashboard_vars["player_pot"] = pot_var
                player_pot_amount_label = tk.Label(pot_box, textvariable=pot_var, bg=panel_bg, fg="#65d6a6",
                                                    font=("Segoe UI", player_pot_size, "bold"), justify="center", anchor="center")
                player_pot_amount_label.pack(fill="x")
            else:
                body_label = tk.Label(panel, textvariable=body_var, bg=panel_bg, fg=white,
                                      font=("Segoe UI", dashboard_body_size, "bold"), justify="left", anchor="nw",
                                      wraplength=dashboard_wraplength)
                body_label.pack(
                    fill="both", expand=True, padx=label_side_padx,
                    pady=((3, 5) if modern_theme else (2, 0))
                )
                dashboard_body_labels[key] = body_label

        # Classic retains the original content-sized dashboard and flexible gap.
        # Modern instead owns the available vertical space between the level bands
        # and the bottom dock. That gives us a real height budget to shrink the
        # dashboard contents when large control fonts/buttons take more room.
        spacer = tk.Frame(safe_area, bg=bg)
        if not modern_theme:
            spacer.pack(side="top", fill="both", expand=True)
        dashboard_propagation_disabled = {"value": False}

        def fit_modern_dashboard():
            """Shrink Modern dashboard panels to the real space left by the control dock.

            Classic uses Tk's natural geometry and remains unchanged. Modern has a
            larger pie and dashboard, so its content is scaled down as a group when
            larger control fonts/button padding reduce available vertical space.
            """
            if not modern_theme or footer_placeholder is None or not win.winfo_exists():
                return
            try:
                win.update_idletasks()
                safe_height = safe_area.winfo_height()
                if safe_height < 250 or dashboard.winfo_height() < 20:
                    return

                # Measure the dashboard once at its unscaled font/pie sizes. Keeping
                # this reference avoids cumulative shrink/grow oscillation as sliders
                # move repeatedly during the live preview.
                natural_heights = [
                    int(panel.winfo_reqheight()) for panel in dashboard_panels.values()
                ]
                measured_base_height = max(natural_heights + [int(pie_height)])
                if dashboard_base_required_height["value"] is None:
                    dashboard_base_required_height["value"] = measured_base_height
                else:
                    # A longer payout list can legitimately need more natural height
                    # than the initial empty-tournament dashboard. Grow the reference
                    # as needed, but never let previously scaled fonts lower it.
                    dashboard_base_required_height["value"] = max(
                        int(dashboard_base_required_height["value"]), measured_base_height
                    )
                if not dashboard_propagation_disabled["value"]:
                    dashboard.pack_propagate(False)
                    dashboard_propagation_disabled["value"] = True

                # Layout is event-driven in effect: the regular 500 ms tournament
                # refresh may call this function, but identical inputs must not
                # reconfigure fonts/padding again. Reapplying scaled fonts on every
                # refresh caused visible text/card flicker in Modern.
                payout_base = getattr(prizes_text_label, "_mypoker_base_payout_font_size", None) if prizes_text_label is not None else None
                signature = (
                    safe_height, int(dashboard.winfo_width()), int(footer_placeholder.winfo_reqheight()),
                    int(control_font_size), round(float(control_button_scale), 3),
                    tuple((key, str(var.get())) for key, var in screen_dashboard_vars.items()),
                    payout_base,
                )
                if dashboard_layout_signature["value"] == signature:
                    return
                dashboard_layout_signature["value"] = signature

                dashboard_top = int(dashboard.winfo_y())
                # Use the placeholder's requested height, not its assigned height:
                # the packer may temporarily clip it while resizing, and that is
                # precisely when the dashboard must give space back.
                reserved_dock_height = int(footer_placeholder.winfo_reqheight())
                bottom_gap = 2
                available_height = max(1, safe_height - dashboard_top - reserved_dock_height - bottom_gap)
                base_height = max(1, int(dashboard_base_required_height["value"]))
                target_height = max(1, min(base_height, available_height))
                if dashboard.winfo_height() != target_height:
                    dashboard.configure(height=target_height)

                # Leave a little vertical safety margin so multi-line labels don't
                # touch the lower border. The floor keeps the dashboard legible even
                # on 720p when control font and button scale are both set very high.
                fit_scale = 1.0 if target_height >= base_height else max(0.30, (target_height - 6) / float(base_height))
                dashboard_fit_scale["value"] = fit_scale

                for key, panel in dashboard_panels.items():
                    base_padx = dashboard_panel_base_padx.get(key, dashboard_padx)
                    panel.configure(
                        padx=max(4, int(round(base_padx * fit_scale))),
                        pady=max(1, int(round(dashboard_pady * fit_scale))),
                    )
                    heading_label = dashboard_heading_labels.get(key)
                    if heading_label is not None:
                        heading_label.configure(font=("Segoe UI", max(9, int(round(dashboard_heading_size * fit_scale))), "bold"))
                        heading_label.pack_configure(pady=(max(1, int(round((2 if modern_theme else 0) * fit_scale))), 0))
                    divider = dashboard_dividers.get(key)
                    if divider is not None:
                        divider.configure(height=max(1, int(round((2 if modern_theme else 3) * fit_scale))))
                        divider.pack_configure(pady=(max(1, int(round(3 * fit_scale))), max(2, int(round(5 * fit_scale)))))
                    body_label = dashboard_body_labels.get(key)
                    if body_label is not None and key in ("status", "statistics"):
                        body_label.configure(font=("Segoe UI", max(7, int(round(dashboard_body_size * fit_scale))), "bold"))
                        body_label.pack_configure(pady=(max(1, int(round(3 * fit_scale))), max(2, int(round(5 * fit_scale)))))
                    elif body_label is not None and key == "prizes":
                        base_payout_size = getattr(body_label, "_mypoker_base_payout_font_size", None)
                        if base_payout_size is None:
                            try:
                                base_payout_size = int(body_label.cget("font").split()[1])
                            except Exception:
                                base_payout_size = 12
                        body_label.configure(font=("Segoe UI", max(7, int(round(base_payout_size * fit_scale))), "bold"))

                if time_pie_canvas is not None:
                    time_pie_canvas.configure(height=max(64, int(round(pie_height * fit_scale))))
                if benefit_header is not None:
                    benefit_header.configure(font=("Segoe UI", max(7, int(round(pot_header_size * fit_scale))), "bold"))
                if benefit_amount_label is not None:
                    benefit_amount_label.configure(font=("Segoe UI", max(9, int(round(benefit_amount_size * fit_scale))), "bold"))
                if player_pot_header is not None:
                    player_pot_header.configure(font=("Segoe UI", max(7, int(round(pot_header_size * fit_scale))), "bold"))
                if player_pot_amount_label is not None:
                    player_pot_amount_label.configure(font=("Segoe UI", max(9, int(round(player_pot_size * fit_scale))), "bold"))
                    player_pot_amount_label.pack_configure(pady=(0, max(1, int(round(2 * fit_scale)))))
                if pot_box is not None:
                    pot_box.configure(
                        padx=max(3, int(round((pot_box_padx + (3 if modern_theme else 0)) * fit_scale))),
                        pady=max(2, int(round((pot_box_pady + (2 if modern_theme else 0)) * fit_scale))),
                    )
                if prizes_body_frame is not None:
                    prizes_body_frame.pack_configure(pady=(max(1, int(round(3 * fit_scale))), max(1, int(round(3 * fit_scale)))))
                if benefit_header is not None and benefit_header.winfo_manager():
                    benefit_header.pack_configure(pady=(max(1, int(round(2 * fit_scale))), max(2, int(round(6 * fit_scale)))))
                if benefit_amount_label is not None and benefit_amount_label.winfo_manager():
                    benefit_amount_label.pack_configure(pady=(0, max(3, int(round(9 * fit_scale)))))
                if player_pot_header is not None:
                    player_pot_header.pack_configure(pady=(max(1, int(round(2 * fit_scale))), max(2, int(round(8 * fit_scale)))))
                win.update_idletasks()
            except tk.TclError:
                # The display may be closing while the user hits Escape.
                return

        def update_display():
            nonlocal display_rebuy_enabled, display_addon_enabled
            if not win.winfo_exists():
                return
            if display_rebuy_enabled != self.rebuy_enabled or display_addon_enabled != self.add_on_enabled:
                self._layout_quick_groups(quick_controls, display_quick_groups,
                                          include_rebuys=self.rebuy_enabled, include_addons=self.add_on_enabled)
                display_rebuy_enabled = self.rebuy_enabled
                display_addon_enabled = self.add_on_enabled
            lev = self._current_level()
            sec = self._current_seconds()
            sync_time_adjustment(sec)
            title.configure(text=self.tournament_name)
            info_vars["level"].configure(text=f"{self.current_level + 1} / {len(self.levels)}")
            info_vars["clock"].configure(text="RUNNING" if self.running else "PAUSED")
            if lev.get("kind") == "Break":
                info_caption = "BREAK ENDS IN"
                break_secs = sec
            else:
                info_caption = "BREAK IN"
                break_secs = self._seconds_until_next_break()
            # The heading changes contextually when currently in a break.
            for child in info.winfo_children():
                if isinstance(child, tk.Frame) and child.winfo_children():
                    first = child.winfo_children()[0]
                    if isinstance(first, tk.Label) and first.cget("text") in ("BREAK IN", "BREAK ENDS IN"):
                        first.configure(text=info_caption)
            info_vars["break"].configure(text=duration_text(break_secs) if break_secs is not None else "NO MORE BREAKS")

            timer.configure(text=duration_text(sec))
            if lev.get("kind") == "Break":
                current_caption.configure(text="CURRENT STATUS")
                blinds.configure(text="BREAK")
            else:
                current_caption.configure(text=f"LEVEL {self.current_level + 1} BLINDS")
                blinds.configure(text=f"{int(lev['sb'])} / {int(lev['bb'])}")

            if self.current_level < len(self.levels) - 1:
                n = self.levels[self.current_level + 1]
                next_timer.configure(text=duration_text(max(0, int(n.get("minutes", 0)) * 60)))
                if n.get("kind") == "Break":
                    next_caption.configure(text=f"NEXT: {n['name'].upper()}")
                    next_blinds.configure(text="BREAK")
                else:
                    next_caption.configure(text=f"NEXT: {n['name'].upper()}")
                    next_blinds.configure(text=f"{int(n['sb'])} / {int(n['bb'])}")
            else:
                next_timer.configure(text="--:--")
                next_caption.configure(text="FINAL SCHEDULED LEVEL")
                next_blinds.configure(text="—")

            self._draw_time_pie(time_pie_canvas)
            # Use the same thresholds/colors as the time-remaining pie. This runs
            # on every display refresh, so the header beacon changes with the timer.
            sync_toggle_beacon(sec)
            dashboard_values = self._dashboard_texts()
            for key, value in dashboard_values.items():
                if key in screen_dashboard_vars:
                    screen_dashboard_vars[key].set(value)
            benefit_is_present = bool(dashboard_values.get("benefit_pot", ""))
            if benefit_is_present:
                if not benefit_header.winfo_manager():
                    benefit_header.pack(before=player_pot_header, fill="x", pady=(2, 6))
                    benefit_amount_label.pack(before=player_pot_header, fill="x", pady=(0, 9))
            else:
                if benefit_header.winfo_manager():
                    benefit_header.pack_forget()
                if benefit_amount_label.winfo_manager():
                    benefit_amount_label.pack_forget()
            # Preserve the large payout font for short lists. With 8+ places, scale
            # the payout text down modestly so the full list remains visible even when
            # the adjustment/action controls are showing on a typical TV resolution.
            payout_line_count = len(dashboard_values.get("prizes", "").splitlines())
            if modern_theme:
                # At 720p, 10 payout lines remain legible while fitting the
                # enlarged equal-height cards; HD resolutions can use larger type.
                screen_height = win.winfo_screenheight()
                if payout_line_count <= 7:
                    payout_font_size = 16 if screen_height >= 900 else 15
                elif payout_line_count <= 10:
                    payout_font_size = 14 if screen_height >= 900 else 12
                elif payout_line_count <= 12:
                    payout_font_size = 12 if screen_height >= 900 else 11
                else:
                    payout_font_size = 11 if screen_height >= 900 else 10
            else:
                if payout_line_count <= 7:
                    payout_font_size = 21
                elif payout_line_count <= 10:
                    payout_font_size = 18
                elif payout_line_count <= 12:
                    payout_font_size = 15
                else:
                    payout_font_size = 13
            if prizes_text_label is not None:
                # This is the unscaled type size selected by paid-place count; the
                # responsive fit below applies a temporary scale without losing it.
                prizes_text_label._mypoker_base_payout_font_size = payout_font_size
            fit_modern_dashboard()
            win.after(500, update_display)

        footer_placeholder = None
        if modern_theme:
            # The dock frame contains only the control panel so its background cannot
            # cover the lower edge of the dashboard. The beacon tab is a sibling on
            # safe_area and overlaps only the panel's top edge.
            win.update_idletasks()
            control_area.pack_forget()
            footer.pack_forget()
            # At 720p, use a compact dock: the controls' rows have already been
            # tightened for Modern, so reserving the full preferred widget height
            # would cover the bottom of a ten-place payout list. Larger displays
            # retain their natural dock height.
            if win.winfo_screenheight() <= 800:
                # Compact by default, but honor stored large fonts/padding so the
                # user's selected controls are never clipped on startup.
                control_height = max(155, int(control_area.winfo_reqheight()))
            else:
                control_height = max(180, int(control_area.winfo_reqheight()))
            tab_height = modern_dock["tab_height"]
            dock_height = control_height + tab_height
            footer_placeholder = tk.Frame(safe_area, bg=bg, height=dock_height)
            footer_placeholder.pack(side="bottom", fill="x")
            footer_placeholder.pack_propagate(False)
            footer.configure(bg=bg, height=control_height)
            footer.pack_propagate(False)
            control_area.place(x=0, y=0, relwidth=1.0, height=control_height)
            # The safe_area already provides the TV-overscan margin; align the dock with its reserved placeholder so the beacon tab never overlaps the dashboard.
            footer.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0, height=control_height)

            def finish_modern_dock_layout():
                # Full-screen geometry may not be finalized until Tk has mapped the
                # Toplevel. Wait for a real safe-area size before positioning the tab.
                if not win.winfo_exists():
                    return
                win.update_idletasks()
                if safe_area.winfo_height() < 250:
                    win.after(50, finish_modern_dock_layout)
                    return
                modern_dock["footer_top"] = footer.winfo_y()
                toggle_button.place(
                    relx=0.5, y=modern_dock["footer_top"] - tab_height, anchor="n"
                )
                footer.lift()
                toggle_button.lift()
                modern_dock["enabled"] = True
                modern_dock["control_height"] = control_height
                controls_visible["value"] = True
                _set_toggle_label(True)
                sync_toggle_beacon(self._current_seconds())

            win.after_idle(finish_modern_dock_layout)

        def refresh_control_appearance():
            """Apply current font/button settings to the live full-screen display."""
            nonlocal control_font_size, control_button_scale
            control_font_size = max(8, min(15, int(getattr(self, "fullscreen_control_font_size", 10))))
            control_button_scale = max(75, min(150, int(getattr(self, "fullscreen_control_button_scale", 100)))) / 100.0

            apply_control_appearance(control_area)
            for group in display_quick_groups.values():
                if modern_theme:
                    group_padx = 8 if compact_modern_controls else 11
                    group_pady = 2 if compact_modern_controls else 6
                else:
                    group_padx, group_pady = 6, 5
                group.configure(
                    padx=max(3, int(round(group_padx * control_button_scale))),
                    pady=max(2, int(round(group_pady * control_button_scale))),
                )

            # Keep the Modern SHOW/HIDE tab fixed-size. Scaling it with the
            # dock changes the animation endpoint and can push the tab off-screen.
            toggle_button.configure(
                font=("Segoe UI", 11 if modern_theme else control_font_size, "bold"),
                padx=(12 if modern_theme else max(4, int(round(14 * control_button_scale)))),
                pady=(4 if modern_theme else max(2, int(round(7 * control_button_scale)))),
            )

            # When the Modern dock grows, update its reserved space and beacon-tab
            # coordinates too, keeping the tab and controls aligned during preview.
            if modern_theme and modern_dock.get("enabled") and footer_placeholder is not None:
                win.update_idletasks()
                minimum_height = 155 if win.winfo_screenheight() <= 800 else 180
                new_control_height = max(minimum_height, int(control_area.winfo_reqheight()))
                new_tab_height = max(40, int(toggle_button.winfo_reqheight()))
                if modern_theme:
                    # The beacon tab is fixed-size; dock scaling must not alter it.
                    new_tab_height = 40
                modern_dock["control_height"] = new_control_height
                modern_dock["tab_height"] = new_tab_height
                reserved_height = (new_control_height + new_tab_height) if controls_visible["value"] else new_tab_height
                footer_placeholder.configure(height=reserved_height)
                footer.configure(height=new_control_height)
                control_area.place_configure(
                    y=(0 if controls_visible["value"] else new_control_height),
                    height=new_control_height,
                )
                footer.place_configure(height=new_control_height)
                win.update_idletasks()
                modern_dock["footer_top"] = footer.winfo_y()
                if controls_visible["value"]:
                    tab_y = modern_dock["footer_top"] - new_tab_height
                else:
                    # Hidden tab remains inside the safe area's visible bounds,
                    # regardless of the scaled control dock's height.
                    tab_y = max(0, safe_area.winfo_height() - new_tab_height)
                toggle_button.place_configure(y=tab_y)
                footer.lift()
                toggle_button.lift()
                dashboard_layout_signature["value"] = None

            sync_toggle_beacon(self._current_seconds())
            if win.winfo_exists():
                win.update_idletasks()
                fit_modern_dashboard()

        self._active_fullscreen_control_refresh = refresh_control_appearance
        update_display()
        return win

    def on_close(self):
        self.pause_clock()
        self._save_data()
        self.destroy()

if __name__ == "__main__":
    app = TournamentDirector()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
