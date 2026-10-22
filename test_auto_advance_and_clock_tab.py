"""Ensure blind levels always advance and the empty Settings > Clock subtab is gone."""
from pathlib import Path
SOURCE = (Path(__file__).with_name("poker_tournament_director.py")).read_text(encoding="utf-8")
assert 'sections.add(clock_tab, text="Clock")' not in SOURCE
assert 'text="Pause after each play/blind level ends' not in SOURCE
assert '"pause_after_blind_level": tk.BooleanVar' not in SOURCE
assert '"Pause after each blind level"' not in SOURCE
assert 'should_pause_after_blind' not in SOURCE
assert '"paused_after_blind_level"' not in SOURCE
assert 'expired_level.get("pause_after", False)' in SOURCE
assert 'cfg.pop("pause_after_blind_level", None)' in SOURCE
print("PASS: no Tournament Settings Clock subtab or global blind-pause option; only individual break rows can pause.")
