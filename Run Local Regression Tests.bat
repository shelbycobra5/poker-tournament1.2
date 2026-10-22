@echo off
setlocal
cd /d "%~dp0"
echo.
echo MyPoker Tournament v64.0 Local Regression Tests
echo =============================================
py -3 -m py_compile poker_tournament_director.py
if errorlevel 1 goto failed
py -3 test_scenario_snapshot.py
if errorlevel 1 goto failed
py -3 test_header_save_updates_active_scenario.py
if errorlevel 1 goto failed
py -3 test_selected_durations_and_pause_settings.py
if errorlevel 1 goto failed
py -3 test_blind_pause_runtime.py
if errorlevel 1 goto failed
py -3 test_auto_advance_and_clock_tab.py
if errorlevel 1 goto failed
py -3 test_builtin_blind_templates.py
if errorlevel 1 goto failed
py -3 test_excel_pause_import.py
if errorlevel 1 goto failed
py -3 test_payout_templates.py
if errorlevel 1 goto failed
py -3 test_timer_beacon.py
if errorlevel 1 goto failed
py -3 test_audio_cache_fast_path.py
if errorlevel 1 goto failed
py -3 test_display_themes.py
if errorlevel 1 goto failed
py -3 test_modern_layout_refinements.py
if errorlevel 1 goto failed
py -3 test_modern_dashboard_sizing.py
if errorlevel 1 goto failed
py -3 test_tournament_type_tab_visibility.py
if errorlevel 1 goto failed
py -3 test_modern_timer_centering.py
if errorlevel 1 goto failed
py -3 test_live_control_appearance_preview.py
if errorlevel 1 goto failed
py -3 test_modern_adaptive_dashboard_runtime.py
if errorlevel 1 goto failed
echo.
echo ALL LOCAL CHECKS PASSED.
echo This does not replace interactive testing on your Windows PC and TV.
pause
exit /b 0
:failed
echo.
echo A CHECK FAILED. Review the output above.
pause
exit /b 1
