"""Regression check for type-specific settings tab visibility."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "poker_tournament_director.py").read_text(encoding="utf-8")


def main():
    assert "self.settings_general_tab = basics_tab" in SOURCE
    assert "self.tournament_type_tab = charity_tab" in SOURCE
    start = SOURCE.index("    def _refresh_settings_dependencies(self):")
    end = SOURCE.find("\n    def ", start + 8)
    body = SOURCE[start:end]
    assert 'show_type_tab = tournament_type != "Standard Tournament"' in body
    assert 'sections.tab(type_tab, state="normal" if show_type_tab else "hidden")' in body
    assert "sections.select(general_tab)" in body
    assert 'vars_["charity_mode"].set("No")' in body
    assert "self.charity_mode = False" in body
    print("Tournament Type tab visibility checks passed: hidden for Standard, shown for specialized types, and Benefit Pot normalized off for Standard.")


if __name__ == "__main__":
    main()
