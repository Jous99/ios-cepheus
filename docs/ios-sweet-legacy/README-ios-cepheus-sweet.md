# ios-cepheus

**iOS 16 port to the Xiaomi Mi 9 (`cepheus`, Qualcomm SM8150 / Snapdragon 855).**

> **Status: experimental, does not boot yet.** This repository is the starting point of the port. Nothing here has been tested on a Mi 9 yet. For the real state of the work, see the "Status" section and `NOTES.md`.

This repo is a fork of [ios-sweet](https://github.com/dipa-studio/ios-sweet), which brings iOS 16 to a Redmi Note 10 Pro (`sweet`, SM7150). The same approach is kept: the iOS 16 XNU kernel (xnu-8796) with its own patches, and on top of it the unmodified iPhone X userland (`iPhone10,3`, `D22AP`), 16.7.16 (20H392). What changes is the hardware layer, which here is specific to cepheus.

## Cepheus hardware

Data extracted from the official global MIUI 12.5.1 package for cepheus (`boot.img` and `firmware-update/dtbo.img`) and from the SM8150 v2 base dtb inside `boot.img` itself:

| Component | Cepheus | Notes |
| --- | --- | --- |
| SoC | Qualcomm SM8150 (Snapdragon 855), 1+3+4 cores | On sweet: SM7150 (732G) |
| PMIC | PM8150, PM8150B, PM8150L | On sweet: PM6150 / PM6150L |
| Display | 1080x2340, `SS NOTCH FHD EA8074` panel in command mode | On sweet: 1080x2400, DSC video |
| Touch | STMicro FTS, I²C `0x49`, on the GENI SE17 bus (`i2c@c8c000`) | On sweet: Goodix GT9896 on SE7 |
| Buttons | Volume and power through the PM8150 (`gpio-keys`) | |
| Storage | UFS at `ufshc@1d84000` | Same address as on sweet |
| Interrupts | GIC-v3, `GICD 0x17a00000`, `GICR 0x17a60000` | Same as on sweet |

## Checklist

### Done
- [x] Cepheus hardware identified: SM8150, PM8150, ST FTS touch on SE17, 1080x2340 panel
- [x] GIC and UFS addresses confirmed (they match sweet)
- [x] SM8150 v2 base dtb extracted from `boot.img`
- [x] CEPHEUS overlay extracted from `dtbo.img`
- [x] `tools/mkadt.py --board cepheus` created
- [x] iPhone X `d22ap.adt` extracted from the 16.7.16 (20H392) IPSW
- [x] The `.gitignore` files exclude images, firmware and backups

### Phase 0: Phone preparation
- [ ] Back up `boot`, `dtbo`, `vbmeta`, `persist`, `modemst1`, `modemst2`, `fsg` and `fsc`
- [ ] Bootloader unlocked with Mi Unlock (check the account status)
- [ ] Test `fastboot boot` with an unmodified Android boot.img

### Phase 1: Boot and on-screen console
- [ ] Boot probe that reads the live FDT from ABL: real DRAM (`dram-base`, `dram-size`) and framebuffer
- [ ] Adjust `mkadt.py` with the real memory
- [x] Review `shim/`: 2340 framebuffer with `BOARD=cepheus` (`-DBOARD_CEPHEUS`), dtb configurable with `DTB=`. Builds for sweet and cepheus. UFS and framebuffer match the dtb
- [x] CEPHEUS machine configuration in the kernel: patch `0082` (applies on top of the 0001-0081 series; pending a CI build)
- [x] Kernel patch: `SweetPlatformExpert` recognizes `xiaomi,cepheus` (in `0082`)
- [ ] Commit and kernel CI on GitHub Actions (watch the macOS minutes on private repos)
- [ ] **Milestone 1:** the kernel writes text on screen with `fastboot boot`

### Phase 2: Storage and userland
- [ ] The shim reads the ramdisk from UFS on cepheus
- [ ] iOS root image with `tools/mkiosroot.sh` from the IPSW
- [ ] Write `userdata` (erases Android; confirm first)
- [ ] **Milestone 2:** launchd and the userland start

### Phase 3: Input
- [x] Buttons: the SPMI arbitration is the same as on sweet (verified in the dtb). Volume up is on PM8150 GPIO6 (SID 0), so `sweet_keys.c` uses per-board constants (in `0082`)
- [ ] Check the button readout on the phone (`SWEET KEYS:` diagnostics in the log)
- [ ] New driver for the ST FTS touch on SE17, with `st_fts_f1.ftb`
- [ ] Touch, USB, RPMh and battery are still sweet-only: they must be ported to cepheus
- [ ] **Milestone 3:** SpringBoard and Setup can be used with touch

### Phase 4: Extras (not a priority)
- [ ] USB ECM to read logs over the network
- [ ] Command-mode panel (no DSC)
- [ ] Sensors and audio

### Pending decisions
- [ ] Dual boot: parked, to be picked up later
- [ ] Confirm that iOS may take over `userdata` before Phase 2

## How to build (when it is ready)

The procedure is the ios-sweet one, with these differences:

```sh
# 1. Kernel: built on GitHub Actions (xnu.yml workflow)
gh workflow run xnu.yml -R TU_USUARIO/ios-cepheus
gh run download RUN_ID -R TU_USUARIO/ios-cepheus -n xnu-kernel -D xnu/out

# 2. ADT for cepheus
python3 tools/mkadt.py shim/out/cepheus.adt --board cepheus --highmem

# 3. Boot image (the cmdline is the sweet one, still to be reviewed)
python3 tools/mkpayload.py xnu/out/kernel.development.cepheus shim/out/cepheus.adt shim/out/payload.bin --cmdline '...'
shim/build.sh ../shim/out/payload.bin
```

The iOS root (`tools/mkiosroot.sh`) is the same as on sweet, built from the iPhone X 16.7.16 (20H392) IPSW.

**Warning:** booting requires an unlocked bootloader and uses `fastboot boot`, without flashing the boot partitions. Even so, installing iOS overwrites `userdata` and erases the Android data. Make a backup before any test (`boot`, `dtbo`, `vbmeta`, `persist`, `modemst1`, `modemst2`, `fsg`, `fsc`).

## Layout

| Path | Contents |
| --- | --- |
| `shim/` | Boot shim in C and assembly (from sweet, still to be adapted) |
| `xnu/patches/` | XNU patches (from sweet, still to be adapted to cepheus) |
| `tools/mkadt.py` | ADT generator, with `--board cepheus` |
| `tools/mkiosroot.sh` | Builds the iOS root from the IPSW |
| `NOTES.md` | Engineering log |

## Credits

The approach and most of the code come from ios-sweet (dipa-studio). This repository only adds the cepheus layer on top.
