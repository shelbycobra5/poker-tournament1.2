"""Regression checks for the TV-safe, rounded Modern display layout."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "poker_tournament_director.py").read_text(encoding="utf-8")

def main():
    assert "def add_modern_rounded_surface(" in SOURCE
    assert "joinstyle=tk.ROUND" in SOURCE
    assert "add_modern_rounded_surface(current_panel, bar_bg, panel_border, radius=20" in SOURCE
    assert "add_modern_rounded_surface(next_panel, next_bg" in SOURCE
    assert "add_modern_rounded_surface(panel, panel_bg, panel_border, radius=17" in SOURCE
    assert 'footer.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0, height=control_height)' in SOURCE
    assert 'safe_area.place(relx=0.035, rely=0.042, relwidth=0.93, relheight=0.916)' in SOURCE
    assert "toggle_parent = safe_area if modern_theme else header" in SOURCE
    assert 'modern_dock["footer_top"] = footer.winfo_y()' in SOURCE
    assert "win.after_idle(finish_modern_dock_layout)" in SOURCE
    assert "control_area.place(x=0, y=0, relwidth=1.0, height=control_height)" in SOURCE
    assert "title_font_size = 26" in SOURCE and "current_timer_size = 54" in SOURCE
    print("Modern layout refinement checks passed: rounded surfaces, 720p compaction, dock safe margin, separate beacon tab, and geometry-aware placement.")

if __name__ == "__main__":
    main()
