# Working on ios-cepheus (UniXNU base)

- Read `MIGRATION.md` and `STATUS.md` before starting. Update `STATUS.md` after every milestone: commits, CI IDs, exact build/boot results and pending work. Distinguish observations from assumptions.
- Test boots are always temporary (`fastboot boot`). Keep Android and the partition backups.
  Approved on 2026-10-15: iOS may occupy `userdata`; confirm every destructive step with the user.
- Naming: new code `cepheus_*` / `CEPHEUS`, debug comments "CEPHEUS debug", guards `#if CEPHEUS`.
- New patches: from `0085` on in `xnu-8796/patches/`. Debug ones go in `patches-extra/`.
- Do not commit device dumps, serial numbers or Apple artifacts to git.
- Earlier history (sweet): `docs/ios-sweet-legacy/`.
