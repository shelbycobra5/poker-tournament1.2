MyPoker Tournament v64.11 — Local Python Test

This package is based on the user-confirmed v64.11 baseline and is the source baseline for customer release v1.2.0.

To test on Windows:
1. Extract this ZIP into a new folder.
2. Run "Run MyPoker Tournament Local Test.bat".
3. In the Modern full-screen display, observe the time pie at the start of a level and as time elapses.

Expected pie behavior:
- At the start of a level, the pie is grey.
- The elapsed portion fills in green while more than 60 seconds remain.
- The elapsed portion turns yellow when less than 60 seconds remain.
- The elapsed portion turns red at 20 seconds remaining.
- The center percentage continues to show time remaining.

Classic, audio, and production/GitHub deployment are not changed by this local test package.

Changes in v64.11: pie warning turns red at 20 seconds remaining; Modern full-screen Pause Clock button uses the red negative-action style consistent with Classic.

Customer release v1.2.0 preparation: Statistics & Reports is hidden from main navigation; its implementation is retained. This remains a local source package and does not deploy to GitHub or replace an installed production build.
