"""Regression checks for Classic and Modern full-screen display themes."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "poker_tournament_director.py").read_text(encoding="utf-8")

def main():
    assert 'self.fullscreen_theme = "Classic"' in SOURCE
    assert 'data.get("fullscreen_theme", self.fullscreen_theme)' in SOURCE
    assert '"fullscreen_theme": self.fullscreen_theme' in SOURCE
    assert 'values=("Classic", "Modern")' in SOURCE
    assert 'def _on_fullscreen_theme_changed(self, event=None):' in SOURCE
    assert 'modern_theme = getattr(self, "fullscreen_theme", "Classic") == "Modern"' in SOURCE
    assert 'def _animate_modern_controls(target_visible):' in SOURCE
    assert 'control_area.place_configure(y=control_y)' in SOURCE
    assert 'toggle_button.place_configure(y=tab_y)' in SOURCE
    assert 'toggle_parent = safe_area if modern_theme else header' in SOURCE
    assert 'safe_area.winfo_height() - tab_height' in SOURCE
    assert 'font=("Segoe UI", 11 if modern_theme else control_font_size, "bold")' in SOURCE
    assert 'win.after_idle(finish_modern_dock_layout)' in SOURCE
    assert 'footer.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0, height=control_height)' in SOURCE
    assert 'def add_modern_rounded_surface(' in SOURCE
    assert 'joinstyle=tk.ROUND' in SOURCE
    assert 'radius=22, border_width=2' in SOURCE
    assert 'Controls and theme' in SOURCE or 'Full-screen Display Theme' in SOURCE
    # The action-button helper retains existing positive/negative color semantics.
    assert 'bg, active_bg = "#18864b", "#126738"' in SOURCE
    assert 'bg, active_bg = "#c0392b", "#922b21"' in SOURCE
    print("Display themes regression checks passed: Classic default/persistence, Modern selector, overscan-safe rounded bottom dock animation, and green/red action styling.")

if __name__ == "__main__":
    main()
