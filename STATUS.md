# Status summary (cepheus)

> This repo was adapted from the nabu port skeleton (2026-10-23). The original nabu status log is in
> `docs/nabu-reference/STATUS.md`. The Chinese original of this file is in `docs/original-zh/STATUS.md`.

## Current state: skeleton complete, measurements on the real phone still missing

- [x] Copied and renamed from nabu: configs / kits / scripts / CI workflow
- [x] The contents of the 83 XNU patches renamed uniformly (the cepheus-fbcon / cepheus_early symbol chain is consistent)
- [x] `scripts/make-cepheus-adt.py` finished (includes the /cepheus-fbcon node, verified locally)
- [x] Workflow `MACHINE_CONFIG` changed to CEPHEUS (matches `MASTER.arm64.cepheus` from patch 0006)
- [x] `board.toml` changed to cepheus (with TODO_MEASURE markers)
- [x] `TODO-MEASURE.md`: list of measurements
- [ ] Clone the Lux12138/UniXNU fork and take `make-nabu-adt.py` as the base -> `make-cepheus-adt.py`
      (translator's note: the script already exists in `scripts/`; this item seems to have been left unchecked)
- [ ] Measurements on the real phone: DRAM / userdata / fbcon address (see `TODO-MEASURE.md`)
- [ ] Get the first kernel build CI to pass (no phone needed! After the push, run `workflow_dispatch` by hand)
      - Progress of the CI fixes: ipsw pin -> hostcompat environment -> iig v1 declaration (ambiguous) -> v2 (re-signed,
        duplicate symbols at link time) -> **v3 (current)**: the iig from Xcode 26.6 (DriverKit-440) compiles
        `IOService.iig.cpo` / `IOUserClient.iig.cpo` inside the kernel, which already carries three forwarding definitions;
        the hand-written definitions from the fork's `iig-method-forwarders.patch` are removed (exact inverse hunk),
        keeping the `OSContainer` typedef in `IOService.h`. Patch =
        `patches/macos-iig-forwarder-decls.patch`.
- [ ] UEFI repo `uefi-cepheus` (using uefi-sheng + nabu's `firmware-patches.md` as references)
- [ ] Bring-up in phases 1-7 (see `../notes/cepheus-plan.md` §5; that file is not in this repo)

## 2026-10-25 - Migration
Base changed to UniXNU-cepheus. See `MIGRATION.md`. Pending: measure on the Mi 9, choose the IPSW, first CI, `uefi-cepheus`.
