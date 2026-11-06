# Working on ios-cepheus

- Read `NOTES.md` before starting; it contains the project goal, hardware facts,
  current blocker, local artifact locations and the next concrete action.
- The user switches agents frequently. Update the active handoff in `NOTES.md`
  after each milestone and before stopping. Record commits, CI run IDs, exact
  build/boot results and unfinished work. Distinguish observations from guesses.
- Commit completed changes. Use `gh` for GitHub Actions kernel builds and logs.
  Local single-file cross-compiles are useful before spending a CI run.
- Device bring-up uses temporary `fastboot boot` images. Preserve the Android
  installation and partition backups. The user approved (2026-10-15) using
  internal UFS for iOS and said Android may be deleted: the iOS root goes
  into the existing `userdata` partition (no GPT changes). Keep bootloaders,
  recovery, modem, persist and the backups intact, and confirm each
  destructive step with the user before running it.
- Keep device dumps, serial numbers and downloaded Apple artifacts out of git.

## Naming convention (phase 2)
- New code (patches, functions, macros and debug messages) uses `cepheus_*` / `CEPHEUS`, and debug comments say `CEPHEUS debug`.
- New guards are `#if CEPHEUS` or `defined(CEPHEUS)`, never `SWEET`.
- Existing sweet code is not renamed until phase 3.
- Strings that the firmware or the kernel compare (`SWEETXNU`, `sweet-shim`) are not touched.
- New patches start at 0094.