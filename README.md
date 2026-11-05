# ios-cepheus

**Port of iOS/XNU (xnu-8796, iOS 16) to the Xiaomi Mi 9 (`cepheus`, Snapdragon 855 / SM8150).**

> **Status (2026-11-02): iOS 16.7.16 boots on the Mi 9 and reaches the home screen with icons.** Settings opens, the buttons reach iOS and the
> physical touch delivers touches (the first one was confirmed in the log). No GPU: iOS draws on the CPU. No Wi-Fi, audio, battery or sensors.
> Details of the latest stretch in `docs/progreso-2026-11-02.md`. The GPU (Adreno 640) lives in the separate repo `ios-cepheus-gpu`.
> Read `MIGRATION.md` before touching anything. For the detailed status, see `STATUS.md` and `TODO-MEASURE.md`.

## Boot chain

```
Android boot image -> BootShim -> Mu-Silicium UEFI -> DarwinBoot -> XNU
```

It replaces ios-sweet's own shim (kept in `legacy/sweet-shim/`).

## Cepheus hardware

| Component | Cepheus |
| --- | --- |
| SoC | SM8150, 1+3+4 cores |
| PMIC | PM8150 / PM8150B / PM8150L |
| Display | 1080x2340, panel `SS NOTCH FHD EA8074` (command mode) |
| Touch | STMicro FTS, I²C `0x49`, GENI SE17 bus (`i2c@c8c000`) |
| Buttons | Volume and power through PM8150; volume+ = GPIO6, SID 0 (patch `0084`, not verified on the phone) |
| UFS | `ufshc@1d84000` |
| GIC-v3 | GICD `0x17a00000`, GICR `0x17a60000` |

## Checklist

### Done
- [x] Cepheus hardware identified: SM8150, PM8150, ST FTS touch (I²C `0x49`, SDA/SCL on gpio55/gpio56), 1080x2340 panel
- [x] GIC and UFS addresses confirmed (they match sweet)
- [x] Base SM8150 v2 dtb extracted from `boot.img`; CEPHEUS overlay extracted from `dtbo.img`
- [x] ADT generator for cepheus (`scripts/make-cepheus-adt.py`) and iPhone X identity (`scripts/adt-edit.py`: real `/product` of the D22AP)
- [x] Migration to the UniXNU-cepheus base (2026-10-25): the patch series applies on xnu-8796.141.3
- [x] The `.gitignore` files exclude images, firmware and backups

### Phase 0: Phone preparation
- [x] Backup of `boot`, `dtbo`, `vbmeta`, `persist`, `modemst1`, `modemst2`, `fsg` and `fsc`
- [x] Bootloader unlocked with Mi Unlock
- [x] Try `fastboot boot` with an unmodified Android boot.img

### Phase 1: Boot and console
- [x] xnu-8796 kernel CI building (`build-kernel-8796.yml`; artifact `xnu-8796-kernel` with `out/kernel.development.cepheus`)
- [x] UEFI image (`cepheus-xnu.img`) built and booting with `fastboot boot`
- [x] **Milestone 1:** the kernel boots from the `cust` partition
- [x] Live log over USB (CDC-ECM, UDP 5140) with `cepheususb=2`

### Phase 2: Storage and userland
- [x] iPhone X 16.7.16 (20H392) userland, HFS+ `iOSRoot` root in `userdata`
- [x] Flashing of `userdata` in pieces with `simg2simg` (Windows `fastboot` corrupts from 4 GiB on): `scripts/flash-pieces.py` and `verify-simg2.py`
- [x] **Milestone 2:** launchd and the userland boot; SpringBoard with iPhone X identity

### Phase 3: Input
- [x] Buttons: power, volume− and volume+ reach iOS (patch `0095`)
- [x] ST FTS touch: I²C over GPIO (SE17 is GPI-DMA only); new-generation protocol: queue with `0x86`, events `13/23/33`, scan `A0 00 FF` (patches `0097` to `0108`)
- [x] Input from the PC over UDP, port 5141 (`0106`; `scripts/phone-touch.py`)
- [x] Touch chip debug console over UDP (`0107`; `scripts/ts-console.py` and `scripts/ts-poll.py`)
- [x] **Milestone 3 (partial):** SpringBoard reaches the home screen, opens Settings and physical touches reach iOS (`CEPHEUS HID: touch` in the log)
- [ ] Validate prolonged use with the finger: coordinate scale and the "lift" event (`33`, assumed from the pattern)

### Phase 4: Extras
- [x] USB ECM to read logs over the network
- [x] `0110` verified (2026-11-02): after `usbipd detach`/`attach` the device re-enumerates and the network comes back (the IP has to be set again if `sweet-usbnet.sh` does not do it)
- [ ] Date and time (iOS boots on December 31st: there is no RTC)
- [ ] iOS network over the USB cable (today only the log uses it)
- [ ] Panel in command mode (without DSC)
- [ ] Wi-Fi, audio, battery and sensors

### Phase 5: GPU (Adreno 640), in `ios-cepheus-gpu`
- [x] Firmware identified: `a630_sqe.fw`, `a640_gmu.bin` and `sm8150/a640_zap.mbn` (linux-firmware, redistributable; not committed to git)
- [x] Clock and domain map: gpucc `0x2c90000`, CX GDSC `0x106c`, GX `0x100c`
- [x] Read-only register console over UDP (`0109`)
- [x] `0111` verified (2026-11-02): the full `survey` no longer panics; the GPU is off (G0 inventory in `ios-cepheus-gpu`)
- [x] G1 (2026-11-03): CX domain and GMU clocks on; GMU registers readable (patch `0112`)
- [ ] G2 GMU SMMU and its firmware; G3 HFI and GX; G4 SQE and zap (TrustZone); G5 minimal command
- [ ] Make iOS use that GPU: no guarantee (AdrenoMetal is tied to the iPadOS 17.7.11 ABI)

### Pending decisions
- [x] iOS may occupy `userdata` (approved on 2026-10-15); confirm each destructive step before running it
- [ ] Dual boot: parked, to be resumed later
- [ ] License of the GPU repo

## Structure

| Path | Contents |
| --- | --- |
| `board.toml` | Board description (**see the measurement warning in `MIGRATION.md`**) |
| `xnu-8796/patches/` | Patch series applied by the CI (0001-0082 and 0084-0112) |
| `xnu-8796/patches-extra/` | Ported debug patches from the previous repo; **not** applied by default |
| `uefi/`, `docs/uefi-cepheus.md` | Mu-Silicium patch (`cepheusPkg` + UniXNU/DarwinBoot) and build recipe |
| `xnu-8796/patches-disabled/` | Patches disabled on purpose (hardware the Mi 9 does not have) |
| `scripts/`, `kits/`, `configs/` | ADT, payload, platform and defconfig |
| `scripts/phone-touch.py`, `ts-console.py`, `ts-poll.py` | PC tools: touch iOS and debug the touch chip over UDP |
| `docs/progreso-*.md` | Progress log by stretches |
| `.github/workflows/` | CI (`build-kernel-8796.yml` is the one for xnu-8796) |
| `STATUS.md`, `TODO-MEASURE.md` | Status and measurement list (translated) |
| `docs/` | Technical notes (originally in Spanish, now in English); `docs/original-zh/` keeps the Chinese originals |
| `docs/ios-sweet-legacy/` | The full log of the previous port |
| `legacy/` | The previous shim, tools and own patches |

`docs/nabu-reference/` holds historical notes of the Pad 5, also translated (text that was already in English and commands were left as they were).

## Known SM8150 traps (from UniXNU/nabu)

- Usable ramdisk between 32 and 64 MB; boot header `header_version=1`, `page_size=2048`.
- The firmware volume (FVMAIN) allows 8-10 MB: the kernel goes through the `cust` partition.
- `DarwinBoot` must be the first DXE in `APRIORI.inc`.
- The ADT carries no RAMDisk marker unless an initrd is given.
- `build-libpthread-kernel.py` must be in `archives`, or there is a pthread panic.
- "The log stops" does not mean "the kernel stopped": use `boot-progress=2` to see checkpoints.
- Bad USB cable: the 96 MB image gives `Load Error`.
- Windows `fastboot` corrupts sparse images from 4 GiB on: split with `simg2simg` and flash with `scripts/flash-pieces.py`.
- The live log only collects what is printed once the PC already has an IP: start `sweet-usbnet.sh` before `fastboot boot`.
- The legacy USB driver lost the network when the device re-enumerated (any `usbipd detach`/`attach`); fix `0110`, verified.
- The touch SE17 is GPI-DMA only (`GENI_IF_DISABLE_RO` stays at 1): I²C goes over GPIO.
- A register read outside the mapped window is a kernel access fault (panic): check the offset against the size.

## Flashing and booting

Only `cust` is written (kernel and configuration); `userdata`, with iOS, is not touched. Three windows: **A** WSL, **C** CMD, **B** administrator CMD.

1. **WSL:** CI kernel in `out/kernel.macho` and a payload with touch enabled (`cepheusts=4`):
   `bash scripts/make-cepheus-cust-payload.sh out/kernel.macho out/kernel.macho.adt.fixed out/cust-payload.img`, and copy it to `out\` on Windows.
2. **Window A (WSL), before booting:** `sudo modprobe cdc_ether`, `sudo -v` and
   `bash legacy/sweet-tools/sweet-usbnet.sh logs/liveN.txt`. Whatever the kernel prints before the PC has an IP is lost.
3. **Window C (CMD), phone in fastboot (Vol− + Power), inside `out\`:**
   ```
   fastboot flash cust cust-payload.img   # only write: cust partition
   fastboot boot cepheus-xnu.img          # temporary boot, does not write to disk
   ```
4. **Window B (administrator CMD), when `Booting OKAY` appears:** `usbipd list` (row `1209:0001`) and
   `usbipd bind --busid BUSID` (first time only) and `usbipd attach --wsl --busid BUSID --auto-attach`.
5. If the network drops, `usbipd detach` and `attach` recover it (patch `0110`); after re-enumerating, set the IP: `sudo ip addr add 192.168.7.1/24 dev enx02005e77ee01`.

PC tools, once the network is up (`ping 192.168.7.2`): `scripts/phone-touch.py` (touch iOS), `scripts/ts-console.py` and `scripts/ts-poll.py` (touch chip).
If it hangs, hold the power button for 10-15 s to turn it off.

## Credits

- UniXNU-cepheus (sxl47) and unixnu-nabu (Lux12138): structure, kits and the patch series.
- ios-sweet (dipa-studio): origin of the XNU patches.
- blacktop/darwin-xnu-build: kernel build system.
- Cepheus hardware layer and patch `0084`: the previous repo.

Note: UniXNU-cepheus does not include a license file. Before publishing this repo, check the license of each origin.
