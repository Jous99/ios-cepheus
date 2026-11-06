# Extra patches (not applied by default)

The CI only copies `xnu-8796/patches/*.patch`. These are the project's own, ported from ios-cepheus (sweet):
`sweet_early_mark` -> `cepheus_early_mark`, `arm64/sweet_early.h` -> `arm64/cepheus_early.h`.
They are applied **in order E01..E09** on top of the full series (verified on a clean xnu-8796.141.3).

- E01: removes the `TARGET_OS_OSX` guard from `iBoot_Stage_2_version` (only if the kernel fails because of that symbol).
- E02-E09: on-screen boot markers (startup, bsd_init, procinit).

`0093-cepheus-test-procinit-off` was left out (it disabled `procinit` for a hang test;
it is in `legacy/sweet-unique-patches/`).
To use them, copy them to `xnu-8796/patches/` with free numbers (0085 onwards).
