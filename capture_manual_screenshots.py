from pathlib import Path
import sys, time
import tkinter as tk
from PIL import ImageGrab
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import poker_tournament_director as app_module
OUT = Path('/mnt/data/v638_manual_screenshots')
OUT.mkdir(parents=True, exist_ok=True)
app = app_module.TournamentDirector()
app.fullscreen_theme = 'Classic'
app.fullscreen_control_font_size = 10
app.fullscreen_control_button_scale = 100
app.geometry('1470x820+45+25')
app.update()

def capture_window(window, filename):
    app.update_idletasks(); app.update()
    x, y = window.winfo_rootx(), window.winfo_rooty()
    w, h = window.winfo_width(), window.winfo_height()
    ImageGrab.grab(bbox=(x, y, x+w, y+h)).save(OUT / filename)
    print(filename, x, y, w, h)

# Current main Tournament Clock interface.
app.notebook.select(app.clock_tab)
capture_window(app, 'main_interface.png')
# Scenario manager.
app.notebook.select(app.scenarios_tab)
capture_window(app, 'scenario_manager.png')
# Current Tournament Settings general subtab.
app.notebook.select(app.settings_tab)
app.update()
capture_window(app, 'tournament_settings.png')
# Current Classic full-screen TV display.
app.notebook.select(app.clock_tab)
display = app._open_display()
app.update()
ImageGrab.grab().save(OUT / 'fullscreen_classic.png')
print('fullscreen_classic.png', display.winfo_width(), display.winfo_height())
display.event_generate('<Escape>')
app.update()
# Current standalone Help / User Guide window.
app._open_help_tab('Quick Start')
app.update()
help_window = app.help_window
help_window.geometry('1050x665+115+20')
app.update()
capture_window(help_window, 'help_window.png')
app.on_close()
print('Wrote screenshots to', OUT)
