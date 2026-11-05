# Migration ios-cepheus (ios-sweet) -> UniXNU-cepheus base

Date: 2026-10-25. Source: the previous `ios-cepheus` repo (fork of ios-sweet, own shim). Target: UniXNU-cepheus (UEFI + DarwinBoot).

## What was found when comparing
- Of the first 81 XNU patches, 79 are identical after normalizing sweet/nabu/cepheus. The other two (0046, 0070) differ only in `#if` guards.
- UniXNU-cepheus is largely the sweet series renamed. That is why it carries sweet constants in hardware places
  (e.g. the buttons: PM6150L SID 4). The previous repo had the correct PM8150 values for the Mi 9 -> patch `0084`.

## What changed
| Change | Detail |
| --- | --- |
| Base | Full UniXNU-cepheus tree |
| **Added** `0084-cepheus-keys-pm8150` | Volume+ on PM8150 GPIO6 (SID 0), ported from the previous `0082`. **Not verified on the phone** |
| **Disabled** `0083` (NT36523 SPI) | Touch controller of the Pad 5, which the Mi 9 does not have. In `patches-disabled/` |
| **Extras** E01-E09 | The previous debug markers, renamed to `cepheus_*`. Not applied by default |
| **Excluded** 0093 | Test that disabled `procinit`; it stays in `legacy/` |
| **Not ported** the previous `0082`/`0083` | They were the `|| CEPHEUS` guards and the machine config on top of sweet; in this series it is already pure CEPHEUS |
| Legacy | `legacy/` (shim, tools, own earlier patches) and `docs/ios-sweet-legacy/` (NOTES, GUIDE, README, AGENTS) |

## Verification done
On a clean `xnu-8796.141.3` (macOS 13.5): the series 0001-0082 + 0084 applies without failures with `git apply`, and so do E01-E09, in that order.
**Limits:** it was not compiled (the CI is macOS) and the `stage-*` scripts could not be fully run here
(no `xcrun`, and bearssl.org is not reachable), so the patches that depend on those prepared files were not checked.

## Documentation
`STATUS.md`, `TODO-MEASURE.md` and the documents in `docs/` were translated from Chinese to Spanish (2026-10-25) and then to English (2026-11-05); the Chinese originals are in `docs/original-zh/`.
`docs/nabu-reference/` (historical notes of the Pad 5) and the Chinese comments in `board.toml`, `kits/` and `scripts/` were translated as well.
Text that was already in English, commands and identifiers were left as they were.

## What was NOT done (the owner's decisions)
1. **IPSW:** `board.toml` points to the iPad 17.7.11 (xnu-10063); the project used the iPhone X 16.7.16 with xnu-8796.
   The `build-kernel-8796.yml` workflow does not use that section, but the root packaging does. One has to be chosen.
2. **The current root:** `userdata` holds an iOS 16 root. This chain would overwrite it with the one from the chosen IPSW.
3. **`maxmem` in the ADT:** `make-cepheus-adt.py` does not set it and `board.toml` has `owned_memory_size = 0x20000000`; review it when measuring the DRAM (see `TODO-MEASURE.md`).
4. **Ramdisk/logs:** the earlier RAM tests for logs (0x9d000000, 0x1f0000000) did not survive a reboot; the screen is still valid.

## Measure on the Mi 9 (mandatory before flashing)
From TWRP (`adb shell`):
```
cat /proc/meminfo | head -3
ls -l /dev/block/by-name/userdata
cat /sys/block/sda/sdaXX/start /sys/block/sda/sdaXX/size    # XX = the number shown above
fastboot getvar partition-size:userdata
```
`first_lba = start/8`, `last_lba = first_lba + size/8 - 1`. If they do not match `board.toml`, fix them.
The current values (6 GB, userdata ~111 GiB) come from the original repo and have not been confirmed on this unit.

## State of the branches
The migration, the translations and the UEFI recipe (`docs/uefi-cepheus.md`) are in `main`, on GitHub and on Forgejo.
The temporary branches (`unixnu-migration`, `traduccion-es`, `uefi-cepheus`, `cepheus-port`) were deleted on 2026-10-25 after checking
that all their commits were inside `main`. The earlier history (ios-sweet shim) remains in the history of `main`.
