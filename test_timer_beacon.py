"""Regression checks for the full-screen timer-color beacon."""
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "poker_tournament_director.py").read_text(encoding="utf-8")

# Import the module without constructing the Tk app; the color helper itself is pure.
sys.path.insert(0, str(HERE))
import poker_tournament_director as app_module


def color(seconds):
    return app_module.TournamentDirector._time_pie_color(object(), seconds)


def main():
    assert color(600) == "#22a56b", "Normal time should be green"
    assert color(60) == "#22a56b", "Exactly 60 seconds should remain green, matching the pie"
    assert color(59) == "#f0c419", "Below 60 seconds should be yellow"
    assert color(21) == "#f0c419", "21 seconds should be yellow"
    assert color(20) == "#e03131", "20 seconds or less should be red"
    assert color(11) == "#e03131", "11 seconds should be red"
    assert color(0) == "#e03131", "Zero seconds should be red"

    # The full-screen button styling must call the exact same helper as the pie.
    assert 'beacon_color = self._time_pie_color(seconds)' in SOURCE
    assert 'bg=beacon_color' in SOURCE
    assert 'activebackground=beacon_color' in SOURCE
    assert 'sync_toggle_beacon(sec)' in SOURCE, "Beacon should update on every display refresh"
    assert 'sync_toggle_beacon(self._current_seconds())' in SOURCE, "Beacon should refresh immediately on toggle"
    # Classic and Modern toggle labels remain theme-aware without overriding beacon colors.
    assert 'def _set_toggle_label(visible):' in SOURCE
    assert '"HIDE CONTROLS  ⌄" if visible else "SHOW CONTROLS  ⌃"' in SOURCE
    assert '"HIDE CONTROLS" if visible else "SHOW CONTROLS"' in SOURCE
    block = SOURCE[SOURCE.index('        def toggle_controls():'):SOURCE.index('        toggle_parent =', SOURCE.index('        def toggle_controls():'))]
    assert '_set_toggle_label(False)' in block
    assert '_set_toggle_label(True)' in block
    assert 'bg="#f0c419"' not in block and 'bg="#1d2b36"' not in block
    print("Timer beacon regression checks passed.")


if __name__ == "__main__":
    main()
