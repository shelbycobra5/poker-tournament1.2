import os, time, tkinter as tk
from tkinter import ttk
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import poker_tournament_director as app_module

app = app_module.TournamentDirector()
app.fullscreen_theme = "Modern"
app.fullscreen_control_font_size = 10
app.fullscreen_control_button_scale = 100
app.update_idletasks()
app._fullscreen_controls_dialog()
time.sleep(0.35)
app.update()

def descendants(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(descendants(child))
    return out

tops = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
display = next((w for w in tops if w.title() == "Tournament Display"), None)
dialog = next((w for w in tops if w.title().startswith("Full-Screen Controls")), None)
assert display and dialog, [(type(w).__name__, w.title()) for w in tops]
assert dialog.winfo_viewable(), "Live-preview popup should be visible after opening."
assert str(dialog.attributes("-topmost")) in ("1", "true"), "Preview popup should be kept topmost."
assert app.grab_current() is None, "Preview must not hold a modal input grab that can freeze the app if hidden."
scales = [w for w in descendants(dialog) if isinstance(w, ttk.Scale)]
assert len(scales) == 2, f"Expected two live sliders, found {len(scales)}"
# Exercise slider callbacks with keyboard input so the widgets dispatch their actual ttk command.
font_scale, button_scale = scales
font_scale.focus_force()
for _ in range(4):
    font_scale.event_generate("<KeyPress-Right>")
    app.update()
assert app.fullscreen_control_font_size != 10, f"font scale did not live-update: {app.fullscreen_control_font_size}"
assert callable(getattr(app, "_active_fullscreen_control_refresh", None))
# Cancel should restore previous sizes and close both preview windows.
cancel = next(w for w in descendants(dialog) if isinstance(w, ttk.Button) and w.cget("text") == "Cancel Preview")
cancel.invoke()
app.update()
assert app.fullscreen_control_font_size == 10
assert app.fullscreen_control_button_scale == 100
assert not display.winfo_exists()
# Open a second time; reset + save should preserve the new values and leave display open.
app._fullscreen_controls_dialog()
time.sleep(0.35)
app.update()
tops = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
display = next(w for w in tops if w.title() == "Tournament Display")
dialog = next(w for w in tops if w.title().startswith("Full-Screen Controls"))
scales = [w for w in descendants(dialog) if isinstance(w, ttk.Scale)]
scales[0].focus_force()
for _ in range(3):
    scales[0].event_generate("<KeyPress-Right>")
    app.update()
font_size = app.fullscreen_control_font_size
save = next(w for w in descendants(dialog) if isinstance(w, ttk.Button) and w.cget("text") == "Save & Finish")
save.invoke()
app.update()
assert display.winfo_exists()
assert not dialog.winfo_exists()
assert font_size == app.fullscreen_control_font_size
# Close the full-screen display and root cleanly.
display.event_generate("<Escape>")
app.update()
app.on_close()
print("GUI smoke test passed: popup overlays the live full-screen display, sliders update immediately, Cancel reverts/closes, and Save leaves the preview open.")
