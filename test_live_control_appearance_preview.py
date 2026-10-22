"""Regression checks for the full-screen live control-appearance preview."""
from pathlib import Path
import ast

SOURCE = Path(__file__).with_name("poker_tournament_director.py").read_text(encoding="utf-8")


def method_source(name):
    tree = ast.parse(SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(SOURCE, node)
    raise AssertionError(f"Method not found: {name}")


def main():
    dialog = method_source("_fullscreen_controls_dialog")
    display = method_source("_open_display")
    settings = method_source("_build_display_sound_tab")

    assert "display_win = self._open_display()" in dialog
    assert "Open a live full-screen preview" in settings
    assert "Changes appear immediately" in settings
    assert "dlg = tk.Toplevel(self)" in dialog
    assert dialog.index("display_win = self._open_display()") < dialog.index("dlg = tk.Toplevel(self)")
    assert "dlg.transient(display_win)" not in dialog, "A fullscreen-owned transient can hide the popup on some Windows systems."
    assert "dlg.grab_set()" not in dialog, "A hidden modal grab can make the entire app appear frozen."
    assert "dlg.after(80, raise_preview_dialog)" in dialog
    assert "dlg.after(300, raise_preview_dialog)" in dialog
    assert dialog.count("command=lambda _value: apply_live_preview()") == 2, "Both sliders must refresh the live preview."
    assert "_active_fullscreen_control_refresh" in dialog
    assert "Save & Finish" in dialog and "Cancel Preview" in dialog
    assert "self.fullscreen_control_font_size = original_font_size" in dialog
    assert "self.fullscreen_control_button_scale = original_button_scale" in dialog
    assert "self._save_data()" in dialog
    assert "self._active_fullscreen_control_refresh = refresh_control_appearance" in display
    assert "return win" in display
    assert 'reserved_height = (new_control_height + new_tab_height) if controls_visible["value"] else new_tab_height' in display
    assert "safe_area.winfo_height() - new_tab_height" in display
    assert "toggle_button.place_configure(y=tab_y)" in display
    print("Live full-screen control-appearance preview regression check passed.")


if __name__ == "__main__":
    main()
