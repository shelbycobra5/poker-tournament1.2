"""Capture the actual v63.9 live control-appearance popup under an X virtual display."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from PIL import ImageGrab
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import poker_tournament_director as app_module

app = app_module.TournamentDirector()
app.fullscreen_theme = "Modern"
app.fullscreen_control_font_size = 10
app.fullscreen_control_button_scale = 100
app.update_idletasks()
app._fullscreen_controls_dialog()
app.update()

def descendants(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(descendants(child))
    return out

display = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Tournament Display")
dialog = next(w for w in descendants(display) if isinstance(w, tk.Toplevel) and w.title().startswith("Full-Screen Controls"))
scales = [w for w in descendants(dialog) if isinstance(w, ttk.Scale)]
# Change sliders as a user would; slider commands apply the actual controls immediately.
scales[0].set(14)
scales[0].event_generate("<KeyPress-Right>")
app.update()
scales[1].set(120)
scales[1].event_generate("<KeyPress-Right>")
app.update()
# Force geometry/layout settlement before capture.
app.update_idletasks()
app.update()
output = Path('/mnt/data/MyPoker_Fullscreen_Controls_Live_Preview.png')
ImageGrab.grab().save(output)
# Cancel to avoid leaving Tk running in the capture process.
cancel = next(w for w in descendants(dialog) if isinstance(w, ttk.Button) and w.cget("text") == "Cancel Preview")
cancel.invoke()
app.update()
app.destroy()
print(output)
