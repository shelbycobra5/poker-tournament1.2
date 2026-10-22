"""Capture adaptive Modern dashboard previews at common TV resolutions."""
from pathlib import Path
import sys, time, tkinter as tk
from PIL import ImageGrab
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import poker_tournament_director as app_module

DASHBOARD_VALUES={
    "status":"Active Players: 12\nTotal Entries: 18\nRe-buys: 4\nAdd-ons: 3",
    "statistics":"Avg. stack: 28,000\nTotal chips: 504,000\nTotal prize: $900\nElapsed levels: 4",
    "prizes":"1st: $450\n2nd: $225\n3rd: $135\n4th: $90\n5th: $70\n6th: $55\n7th: $45\n8th: $35\n9th: $25\n10th: $20",
    "benefit_pot":"", "player_pot":"$1,150"
}

def capture(width,height,font_size,button_scale,name):
    app=app_module.TournamentDirector()
    app.fullscreen_theme="Modern"
    app.fullscreen_control_font_size=font_size
    app.fullscreen_control_button_scale=button_scale
    app._dashboard_texts=lambda: dict(DASHBOARD_VALUES)
    win=app._open_display()
    win.geometry(f"{width}x{height}+0+0")
    win.lift()
    try: win.attributes("-topmost", True)
    except tk.TclError: pass
    for _ in range(5):
        app.update(); time.sleep(.15)
    app.update_idletasks(); app.update()
    out=Path(name)
    ImageGrab.grab().save(out)
    win.destroy(); app.on_close()
    print(out)

capture(1280,720,15,125,HERE/"Modern Theme Adaptive Preview 720p - 15pt 125pct.png")
capture(1280,720,18,150,HERE/"Modern Theme Adaptive Preview 720p - 18pt 150pct.png")
capture(1920,1080,15,125,HERE/"Modern Theme Adaptive Preview 1080p - 15pt 125pct.png")
