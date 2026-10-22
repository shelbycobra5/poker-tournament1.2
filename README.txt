MYPOKER TOURNAMENT v1.2.0 — WINDOWS RELEASE CANDIDATE
=====================================================

This customer-facing release is based on the approved internal v64.11 application build. Statistics & Reports is hidden from the main navigation while its code is retained for possible future use. The Modern timer pie starts grey, fills green as time elapses, turns yellow below 60 seconds, and red at 20 seconds remaining. Modern Pause Clock uses the red action style; Modern show/hide controls switch instantly.

This source package is a release candidate. The native Windows executable and installer must still be built and tested by the Windows workflow before public distribution.

INSTALLATION
------------
Run MyPokerTournament-Setup-1.2.0.exe and follow the setup wizard. This installer targets 64-bit Windows (x64-compatible). A Start Menu shortcut is created automatically. You may choose an additional desktop shortcut. Python does not need to be installed separately when using the installed application.

LAUNCH AND HELP
---------------
Launch MyPoker Tournament from the Start Menu or desktop shortcut. In the black application header, click Help / User Guide (immediately to the left of Save) to open the offline Help window. Press F1 from a main tab for topic-specific help. User Manual.pdf is installed in the application folder, and a shortcut is available in the Start Menu.

FIRST TOURNAMENT CHECKLIST
--------------------------
1. Open Tournament Settings and choose Standard Tournament, Charity Tournament, Home Game, or Freeroll.
2. Review Entries & Fees, Charity / Benefit Pot, and Payout Rules. Blind levels advance automatically; each break pauses only when its own Pause? checkbox is checked.
3. Open Blind Structure and verify each play level and break.
4. Click Save.
5. Create a scenario on the Scenarios tab, or select a saved scenario to launch a new tournament.
6. Confirm the active player and entry counts using the current tournament controls.
7. Test Start/Pause, the gong at a blind start, the low-time warning, and the payout list before using the app for a live tournament.
8. Open Full Screen Display for the TV and confirm that the display edges are visible on your monitor.

FEATURES
--------
- Scenario Manager and New Scenario Wizard
- Standard, Charity, Home Game, and Freeroll templates; Charity and Freeroll can be combined
- Count-based player and entry tracking, rebuys, and add-ons
- Traditional percentage payouts, mixed fixed-dollar/percentage payouts, and fixed freeroll prizes
- Paid-place rules, maximum caps, whole-dollar payout display and configurable rounding
- Blind structure editor/imports, including direct blind-template import from the New Scenario Wizard, breaks, automatic level transitions, and per-level time adjustment
- Full-screen TV display with Classic and optional Modern themes, timer pie/Timer Beacon, instant bottom-docked Hide/Show Controls in Modern, and live-preview adjustable control-label fonts/button sizes
- Modern dashboard automatically shrinks its cards, pie, text and spacing when large control font/button settings need more vertical space; Classic retains its current layout
- Blind-start Long Gong and One Minute low-time warning sounds
- Offline searchable Help window and PDF/Word user manuals
- Reset Tournament to Zero under Tournament Settings > Tournament Management; quick count controls are on Tournament Clock (the separate Players & Entries navigation tab is hidden)

SAVED DATA AND BACKUPS
----------------------
Tournament data is stored separately from the program in the current Windows user's home folder:
- mypoker_tournament.json - current tournament, settings, counts, timer, and level data
- mypoker_tournament_scenarios.json - reusable scenario definitions
- mypoker_tournament_sessions.json - archived tournament sessions

Close the application before backing up these files. Copy all three together to preserve your configuration, scenarios, and session archive. The current release does not include a dedicated archive browser/restore screen, so retain your own backups. The Statistics & Reports tab is hidden in v1.2.0; its code is retained for possible future use. The installer and uninstaller do not intentionally remove these files.

SOUNDS
------
The installer includes Long Gong.wav and One Minute.wav. Use Display & Sound -> Open Sound Settings to test the gong and 60-second warning on the PC connected to the TV. Custom WAV sounds must be uncompressed PCM WAV. Windows output-device selection and mixer volume can affect playback.

UPDATES AND WINDOWS SECURITY
----------------------------
Install a new release using its Windows installer. The data files are outside the installation folder, but make a backup before updating. The first installer build is unsigned; Windows SmartScreen or antivirus software may show a warning. Only run an installer obtained from a trusted build of this project. Do not bypass a security warning unless you understand and trust the file.

SUPPORTING FILES
----------------
User Manual.pdf - printable user guide
User Manual.docx - editable source for the manual
Release Notes.txt - release details and known limitations
MyPokerTournament.ico - application and shortcut icon
MyPokerTournament_Banner.png - product branding graphic
Long Gong.wav - blind-start sound
One Minute.wav - low-time warning sound

SCENARIO SAVE FIX (v57 patch)
-----------------------------
This patched build captures the active blind schedule before settings-form refreshes and uses that same captured schedule for Save Current Setup as Scenario and the New Scenario Wizard's Current blind structure option. Imported levels and breaks are copied into the saved scenario and normalized before persistence.

Scenario names are saved as scenario-library metadata. The tournament display name is a separate setting. Use Scenario Manager > Save Current Setup as Scenario to create a named reusable scenario, or use the wizard's Save Scenario button. When a saved scenario is launched, the upper-right Save button now writes the current reusable settings and active blind structure back to that scenario, and separately saves the live tournament session. If no saved scenario is active, the upper-right Save button saves the session only. The scenario library display name is separate from the tournament display name; use Scenario Manager > Rename or Edit Selected to change the library name.


Branding update v60: product branding is MyPoker Tournament. The former subtitle has been removed from the user manual cover graphic.


Current pause behavior (v63.4): Play/blind levels always advance automatically when their timer reaches zero. Each break has its own Pause? checkbox; only a checked break pauses before the next level. The old global pause-after-blind and global pause-after-break settings are ignored.


LOCAL TEST BUILD v63.5
Modern full-screen dashboard columns are balanced so Time Remaining is centered horizontally, with narrower Status and Statistics columns. Classic is unchanged.

Local test update v63.6: restores the audio cache fast path. See README_LOCAL_TESTING.txt.


LOCAL TEST UPDATE v63.7
Full-screen control labels can be enlarged from 8–15 pt and the buttons scaled from 75–150%. The full-screen timer uses unslashed zeros, and blind values omit thousands separators.

V63.8: LIVE CONTROL-APPEARANCE PREVIEW
- Configure Full-Screen Controls opens the actual full-screen display with a floating settings popup. The popup stays topmost without taking a modal input grab, avoiding a hidden-popup freeze on some Windows systems.
- Font and button sliders update the displayed controls live. Save & Finish keeps changes; Cancel Preview restores old values and closes the preview.
- See README_LOCAL_TESTING.txt for validation instructions.
