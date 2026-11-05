# TODO-MEASURE: list of measurements on the real Xiaomi Mi 9

> Chinese original: `docs/original-zh/TODO-MEASURE.md`.
> Every item has a destination in `board.toml` or in a script. Tools: TWRP (or any recovery that allows entering the system)
> + fastboot + a Mi 9 with the bootloader unlocked.
> Platform reference values (which can be reused from raphael/nabu) are distinguished from those that must be measured.

## 1. DRAM (-> `board.toml` `[payload.adt]` `dram_size`)

```bash
# TWRP shell:
cat /proc/meminfo | head -3        # note MemTotal
```
- 6 GB version: MemTotal ~ 5.6-5.8x10^6 kB -> initial value `dram_size = 0x180000000`
- 8 GB version: MemTotal ~ 7.6-7.8x10^6 kB -> initial value `dram_size = 0x200000000`
- Calibration method in nabu's STATUS.md: MemTotal + reservations (modem/hyp/rmtfs, about 816 MB) ~ physical capacity
- The base is fixed: `0x80000000` (common to SM8150)

## 2. Userdata partition (-> `board.toml` `[userdata]` `first_lba`/`last_lba`)

```bash
# TWRP shell (first confirm which sda number is userdata):
ls -l /dev/block/by-name/userdata
cat /sys/block/sda/sdaXX/start     # 512 B sectors
cat /sys/block/sda/sdaXX/size
```
Conversion: `first_lba = start / 8`, `last_lba = first_lba + size/8 - 1` (UFS LBA = 4096 B)
Cross-check: `fastboot partition-size:userdata` (the bytes must be = (last-first+1)*4096)

## 3. Panel framebuffer address (-> reg of the fbcon node in `make-cepheus-adt.py`)

```bash
# TWRP shell:
cat /proc/device-tree/soc/qcom,mdss-sspp@0/... # or directly
dmesg | grep -i "mdss\|framebuffer\|s6e3fc"
```
Mi 9 panel: Samsung s6e3fc2x01, 1080x2340. The physical address and the length of MDSS/framebuffer have to be found in the
cepheus device tree (on nabu it is `reg=<0x9C000000 0xC00000>`; on cepheus it is different).
The method to extract the device tree is copied from nabu's `docs/nabu-dts-extract.md` (for the dtb of boot.img).

## 4. OS volume UUID (-> `board.toml` `root_match_volume_uuid`)

```bash
# On the PC, on the OS dmg extracted from the IPSW:
7z l -slt 044-76040-038.dmg | grep vol_uuid
```
If the same IPSW as nabu is used, one can start directly with nabu's value `04769d26-2ca0-4825-b443-e2e5f88300f2`.

## 5. ADT generator (done: `scripts/make-cepheus-adt.py`)

- Already adapted from `make-nabu-adt.py` of the Lux12138/UniXNU fork, and the `/cepheus-fbcon` node was added
  (consumed by patch 0003: reg=<physical address size> + width/height/stride).
- **Still to measure**: the reg/size of the fbcon (after measuring item 3, pass it with `--fbcon-reg/--fbcon-size` or change the script's
  default values; they are now nabu's provisional values `0x9C000000/0xC00000`).

## 6. Fork address in the CI

`.github/workflows/build-kernel.yml` now clones `Lux12138/UniXNU`. At first it can be used as is (all the kernel
work for SM8150 is there); in the long run it is better to fork `UniXNU` with your own remote and add `make-cepheus-adt.py` there.

## 7. Contents of the device-specific kernel patches (later task, does not block the build)

The 83 patches in `xnu-8796/patches/` are nabu's accumulated kernel work for SM8150; the file names are kept.
What has to be touched for cepheus (after measuring):
- `0004-nabu-machine-config.patch`: platform addresses / DRAM related
- `0010-nabu-early-framebuffer-debug.patch`: fbcon address
- `0060~0063` (touch drivers): the Mi 9 touch IC differs from nabu's (NT36672?); it has to be changed according to the cepheus device tree
- `0061-nabu-iphone-x-display-size.patch`: resolution adaptation
- UFS/USB/PMIC are probably common; they are left alone for now

## 6 (bis). Conclusions from the last session with the nabu fork (2026-10-24)

(The original repeats the numbering "6".)

- nabu's current blocker is a panic after `execve`, already located: the ADT lacks `maxmem` (the "owned" memory limit), which
  inflates the VM page counter 116 times (freepg=91,199,444 pages ~ 373 GB), and page allocation blows up inevitably.
  Fix = inject `maxmem=4864` into the ADT (equal to `owned_memory_size`).
  -> **What it means for cepheus: once `dram_size` / `owned_memory_size` are measured,
  `maxmem` must equal `owned_memory_size` (on a 6 GB machine, about 6144 minus the reserved area; whatever is measured).**
  The CI clones the latest fork code, so that fix is already included; the local `repos/UniXNU-nabu-fork` was out of date and,
  if needed, is synchronized with `git -C repos/UniXNU-nabu-fork pull`.
- The fork builds only in a local WSL, and its CI workflow has not been maintained with the new runner images:
  the hostcompat trap we stepped on was the first one; the fix is in the `HOST_COMPAT_CFLAGS` comment of `build-kernel.yml`.

> **Translator's note (2026-10-25):** in this repo, `scripts/make-cepheus-adt.py` **does not set `maxmem`** (checked with grep in
> scripts, kits, configs, board.toml and workflows; it only uses `darwinboot-memory-size`), and `board.toml` has
> `owned_memory_size = "0x20000000"`. Review this point when measuring the DRAM: it is the same kind of failure this section describes.
