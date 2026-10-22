"""Regression tests: play levels auto-advance; only individually checked breaks pause."""
import importlib.util
from pathlib import Path

SOURCE = Path(__file__).with_name("poker_tournament_director.py")
spec = importlib.util.spec_from_file_location("mypoker_v634_auto_advance", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class FakeRuntime:
    _tick = module.TournamentDirector._tick
    def __init__(self, levels):
        import time
        self.levels = levels
        self.current_level = 0
        self.running = True
        self.deadline = time.monotonic() - 1
        self.remaining_seconds = 0
        self.history = []
        # Simulate legacy state. The new timer must ignore these obsolete flags.
        self.pause_after_blind_level = True
        self.pause_after_blind_level_var = type("FakeVar", (), {"get": lambda self: True})()
        self.pause_after_break = True
        self.sound_warning_seconds = 60
        self._low_time_warned_level = None
        self._blind_start_sound_played = False
        self.after_calls = 0
        self.started_again = False
        self.played_sounds = []
        self.saved = 0
        self.refreshed = 0
    def _current_level(self):
        return self.levels[self.current_level]
    def _current_seconds(self):
        import time
        return max(0, int(self.deadline - time.monotonic())) if self.running and self.deadline is not None else self.remaining_seconds
    def _play_event_sound(self, event_key):
        self.played_sounds.append(event_key)
    def next_level(self, automatic=False):
        self.running = False
        self.deadline = None
        if self.current_level < len(self.levels) - 1:
            self.current_level += 1
            self.remaining_seconds = int(self.levels[self.current_level].get("minutes", 1)) * 60
    def start_clock(self):
        self.started_again = True
        self.running = True
        self._play_event_sound("clock_started")
        if self._current_level().get("kind") != "Break":
            self._play_event_sound("blind_level_starts")
    def _save_data(self):
        self.saved += 1
    def _refresh_all(self):
        self.refreshed += 1
    def _refresh_clock(self):
        pass
    def after(self, _milliseconds, _callback):
        self.after_calls += 1
        return self.after_calls

PLAY = lambda name: {"name": name, "kind": "Play", "minutes": 1, "sb": 10, "bb": 20}
BREAK = lambda pause=None: ({"name": "Break 1", "kind": "Break", "minutes": 1, "sb": 0, "bb": 0, **({} if pause is None else {"pause_after": pause})})

# Legacy global blind-pause state must be ignored: every play level auto-advances.
play_transition = FakeRuntime([PLAY("Level 1"), PLAY("Level 2")])
play_transition._tick()
assert play_transition.current_level == 1
assert play_transition.running is True
assert play_transition.started_again is True
assert not any(row.get("event") == "paused_after_blind_level" for row in play_transition.history)
assert "blind_level_starts" in play_transition.played_sounds

# An individually checked break pauses at its end and plays Break Ends.
paused_break = FakeRuntime([BREAK(True), PLAY("Level 2")])
paused_break._tick()
assert paused_break.current_level == 1
assert paused_break.running is False
assert paused_break.started_again is False
assert "break_ends" in paused_break.played_sounds
assert "blind_level_starts" not in paused_break.played_sounds

# An unchecked (or legacy unspecified) break ignores the obsolete global pause flag.
for break_row in (BREAK(False), BREAK(None)):
    flowing_break = FakeRuntime([break_row, PLAY("Level 2")])
    flowing_break._tick()
    assert flowing_break.current_level == 1
    assert flowing_break.running is True
    assert flowing_break.started_again is True
    assert "break_ends" not in flowing_break.played_sounds
    assert "blind_level_starts" in flowing_break.played_sounds

print("PASS: play levels always auto-advance; only individually checked breaks pause and play Break Ends.")
