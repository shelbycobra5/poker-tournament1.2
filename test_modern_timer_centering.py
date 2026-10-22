"""Regression check: Modern Time Remaining pie is centered across the display."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "poker_tournament_director.py").read_text(encoding="utf-8")


def main():
    expected = (8, 8, 12, 16)
    status, statistics, timer, prizes = expected
    # A grid-column center is at the horizontal midpoint when the sum of all
    # columns before the timer plus half its own weight equals half of total.
    assert status + statistics + timer / 2 == sum(expected) / 2
    # Keep the center timer roomy and each side balanced, with a narrower
    # Status/Statistics pair than the older v63.4 layout.
    assert status + statistics == prizes
    assert "dashboard_weights = (8, 8, 12, 16) if modern_theme else (2, 2, 2, 4)" in SOURCE
    assert "dashboard_body_size = 12" in SOURCE
    assert "dashboard_wraplength = 155" in SOURCE
    assert 'if modern_theme and key in ("status", "statistics")' in SOURCE
    assert '("STATUS", "status"), ("STATISTICS", "statistics")' in SOURCE
    assert '("TIME REMAINING", "time_pie"), ("PRIZES", "prizes")' in SOURCE
    print("Modern timer-centering check passed: timer centered horizontally; Status/Statistics narrowed; Classic widths unchanged.")


if __name__ == "__main__":
    main()
