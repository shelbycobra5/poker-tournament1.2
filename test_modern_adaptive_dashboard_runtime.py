"""Runtime checks that the Modern dashboard compresses instead of clipping at large controls."""
import sys, time, tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import poker_tournament_director as app_module


def descendants(widget):
    result=[]
    for child in widget.winfo_children():
        result.append(child); result.extend(descendants(child))
    return result


def find_text(root, text):
    return next(w for w in descendants(root) if isinstance(w, tk.Label) and str(w.cget("text")) == text)


def main():
    app=app_module.TournamentDirector()
    app.fullscreen_theme="Modern"
    app.fullscreen_control_font_size=10
    app.fullscreen_control_button_scale=100
    # Pressure the cards with realistic multi-line status/statistics and ten payouts.
    app._dashboard_texts=lambda: {
        "status":"Active Players: 12\nTotal Entries: 18\nRe-buys: 4\nAdd-ons: 3",
        "statistics":"Avg. stack: 28,000\nTotal chips: 504,000\nTotal prize: $900\nElapsed levels: 4",
        "prizes":"1st: $450\n2nd: $225\n3rd: $135\n4th: $90\n5th: $70\n6th: $55\n7th: $45\n8th: $35\n9th: $25\n10th: $20",
        "benefit_pot":"", "player_pot":"$1,150"
    }
    win=app._open_display()
    assert win and win.winfo_exists()
    # Some headless X servers do not honor Tk fullscreen attributes; size to the
    # virtual display. Actual Windows launch still uses the normal fullscreen path.
    win.geometry(f"{app.winfo_screenwidth()}x{app.winfo_screenheight()}+0+0")
    app.update(); time.sleep(.15); app.update()
    status_heading=find_text(win,"STATUS")
    stats_heading=find_text(win,"STATISTICS")
    dashboard=status_heading.master.master
    status_panel=status_heading.master
    stats_panel=stats_heading.master
    prizes_panel=find_text(win,"PRIZES").master
    status_body_label=next(w for w in descendants(status_panel) if isinstance(w,tk.Label) and str(w.cget("textvariable")))
    stats_body_label=next(w for w in descendants(stats_panel) if isinstance(w,tk.Label) and str(w.cget("textvariable")))
    prizes_label=next(w for w in descendants(prizes_panel) if isinstance(w,tk.Label) and str(w.cget("textvariable")))
    initial_dashboard_h=dashboard.winfo_height()
    base_dashboard_font = 12 if app.winfo_screenheight() <= 800 else 17

    # Exercise combinations because clipping depends on font AND button padding,
    # not on either setting in isolation. After each setting, every text label
    # must fit its requested height and all 10 payout rows must remain present.
    combinations=[(10,100),(12,125),(15,100),(10,150),(15,116),(15,117),
                  (15,125),(16,130),(18,150),(12,100)]
    measured=[]
    for font_size,button_scale in combinations:
        app.fullscreen_control_font_size=font_size
        app.fullscreen_control_button_scale=button_scale
        app._active_fullscreen_control_refresh()
        app.update(); time.sleep(.18); app.update()
        h=dashboard.winfo_height()
        current_fonts=[]
        for label in (status_body_label,stats_body_label,prizes_label):
            actual_h=label.winfo_height()
            requested_h=label.winfo_reqheight()
            assert actual_h >= requested_h, (
                f"{app.winfo_screenwidth()}x{app.winfo_screenheight()}, {font_size}pt/{button_scale}%: "
                f"label clipped: {actual_h} < {requested_h}, text={label.cget('text')!r}"
            )
            current_fonts.append(int(tkfont.Font(root=app,font=label.cget("font")).actual("size")))
        assert "10th: $20" in app._dashboard_texts()["prizes"], "10th payout missing"
        assert h > 0
        measured.append((font_size,button_scale,h,current_fonts))

    # Larger controls must cause the Modern dashboard to surrender space; returning
    # to default settings should recover dashboard height. Classic is untouched.
    max_h=next(item[2] for item in measured if item[0:2]==(18,150))
    app.fullscreen_control_font_size=10
    app.fullscreen_control_button_scale=100
    app._active_fullscreen_control_refresh()
    app.update(); time.sleep(.25); app.update()
    restored_dashboard_h=dashboard.winfo_height()
    assert restored_dashboard_h >= max_h, (restored_dashboard_h,max_h)
    assert initial_dashboard_h > 0 and restored_dashboard_h > 0
    screen_size=f"{app.winfo_screenwidth()}x{app.winfo_screenheight()}"
    win.destroy(); app.on_close()
    print(f"PASS adaptive Modern dashboard on {screen_size}: "
          f"checked {len(combinations)} font/button combinations; "
          f"dashboard restored to {restored_dashboard_h}px after large controls.")

if __name__=="__main__":
    main()
