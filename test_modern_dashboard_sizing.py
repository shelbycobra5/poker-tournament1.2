"""Regression checks for the enlarged Modern dashboard and 10-place payout view."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "poker_tournament_director.py").read_text(encoding="utf-8")

def main():
    assert "current_timer_size = 54" in SOURCE
    assert "current_blinds_size = 42" in SOURCE
    assert "next_timer_size = 27" in SOURCE
    assert "next_blinds_size = 24" in SOURCE
    assert "pie_height = 154" in SOURCE
    assert "pie_height = max(210, min(270, int(screen_height * 0.245)))" in SOURCE
    assert "dashboard_weights = (8, 8, 12, 16) if modern_theme else (2, 2, 2, 4)" in SOURCE
    assert 'font=("Segoe UI", (12 if modern_theme else dashboard_body_size), "bold")' in SOURCE
    assert "payout_font_size = 14 if screen_height >= 900 else 12" in SOURCE
    assert "control_height = max(155, int(control_area.winfo_reqheight()))" in SOURCE and "win.winfo_screenheight() <= 800" in SOURCE
    assert "def fit_modern_dashboard()" in SOURCE
    assert "footer_placeholder.winfo_reqheight()" in SOURCE
    assert "dashboard.configure(height=target_height)" in SOURCE
    assert "time_pie_canvas.configure(height=max(64, int(round(pie_height * fit_scale))))" in SOURCE
    assert "dashboard_top_padding = 6 if win.winfo_screenheight() <= 800 else" in SOURCE
    assert 'pady=((4 if win.winfo_screenheight() <= 800 else 8) if modern_theme else control_border_pad)' in SOURCE
    print("Modern dashboard sizing checks passed: larger timer/blinds, bigger time pie, 10-place payout sizing, and compact TV-safe 720p controls.")

if __name__ == "__main__":
    main()
