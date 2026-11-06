# Porting XNU to nabu: handover document

**Handover date**: 2026-10-23
**Reason for the handover**: a new window takes over, moving forward on a single line
**Current state**: reproducible baseline, checkpoint 123

> The early path (the probe injection method, the discovery of `boot_args.Video`, the origin of the MARK method) is in
> **`HANDOVER-legacy.md`**. This document is the entry point.

---

## I. The current state in thirty seconds

**What can be done**: build the kernel in the CI (13 minutes) → package the payload → flash → on the real phone it reaches
`IOsurfaceRoot::installMemoryRegions()` and stops; the screen shows checkpoint `123` and 16 colored blocks.

**What cannot be done**: the root file system is not mounted, `launchd` does not start, there is no image.

**Next step**: first confirm whether that "stops" is a real dead end or just a log cut-off (section V).

---

## II. Six hard facts you need to know

### 1. Both kernel log switches must be disabled

```c
// pe_kprintf.c
SECURITY_READ_ONLY_LATE(bool) disable_serial_output  = false;  // must be changed
SECURITY_READ_ONLY_LATE(bool) disable_kprintf_output = false;  // must be changed
...
if (!disable_serial_output && !disable_kprintf_output) { ... }
```

**Both default to `true`**; changing only one produces no output at all.

### 2. `PE_kputc` must be assigned unconditionally

`PE_init_kprintf` runs in `STARTUP(KPRINTF)`, **before** the framebuffer mapping. That is why you cannot write
`if (nabu_console_fb_ready()) PE_kputc = nabu_mark_putc;` —— the condition is always false and the hook is never installed.

### 3. The UART mapping at `0x9000000` only works in QEMU

This is the **real culprit of checkpoint 50**. `0x9000000` is a PL011 on QEMU virt, and on SM8150 it is another register.
`ml_io_map_unmappable` **returns success on both**, and writing the first character on the real hardware hangs.

Current fix: decide by panel size (QEMU 800x600 / nabu 1600x2560) and only map when `w <= 1024`.

### 4. The ADT must have the `RAMDisk` node

Otherwise DarwinBoot gives `boot refused: Compromised Data`:

```
/chosen/memory-map/RAMDisk   16 bytes, both halves set to 0
```

`make-nabu-adt.py --data-ramdisk` generates it. The `[payload.adt]` in `board.toml` **only has
`packed_data_ramdisk`, not the normal `data_ramdisk`** —— under the official flow, this is a gap.

### 5. The new Xcode 26.0.1 warnings must be suppressed in three places

`-Wunnecessary-virtual-specifier` becomes an error with `-Weverything -Werror`; `OSSymbol.h` triggers it.
There are three independent places, each with its own list of flags:

| Place | Handling |
|---|---|
| `WARNFLAGS_STD` in `makedefs/MakeInc.def` | `build-xnu-4k-baseline.sh` injects it directly |
| the `installhdrs` make call | pass `CFLAGS_EXTRA` |
| `build-arm-driver.py` / `audit-storage-interface.py` | each adds its own `-Wno-*` |

### 6. The cold build of `kernel.py` runs twice

The first pass only generates the compile record and **deliberately empties** 5 variables. Any "valid baseline" gate trips on the first pass.
Current fix: at the start of `build-xnu-4k-baseline.sh`, if `startup.o.json` does not exist, everything is downgraded.

---

## III. Reproducible baseline

| Item | Value |
|---|---|
| Build | `39905065571` / 13 minutes / success |
| Kernel | `kernel.macho` 49.2 MB |
| runner | `macos-26` + Xcode 26.6 |
| defconfig | **9 switches** |
| `[kernel] archives` | **8** |
| prelink roots | 20 |
| Branch | `main` (always buildable and flashable)|

**Recovery commands**:
```bash
gh run list --repo Lux12138/unixnu-nabu --limit 1 --workflow build-kernel.yml
gh run download <id> --repo Lux12138/unixnu-nabu -n kernel-nabu -D C:\Temp\nabu-base
# gh run download often fails; use the API directly:
#   curl.exe -sL -H "Authorization: token $(gh auth token)" -o out.zip \
#     https://api.github.com/repos/Lux12138/unixnu-nabu/actions/artifacts/<AID>/zip
wsl -e bash -c 'KM=/mnt/c/Temp/nabu-base/kernel/kernel.macho bash /mnt/c/Temp/payload2.sh'
cd C:\platform-tools
.\fastboot.exe flash cust C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\cust-payload.img
.\fastboot.exe boot C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\nabu-xnu64-Z.img
```

---

## IV. Today's biggest lesson

> **Treating "enable every official feature" as paying off a debt cost a dozen build rounds.**

`CONFIG_XNU_BOOT_PROGRESS` / `NATIVE_UFS` / `NATIVE_AES` / `VIRTIO_BLOCK` / `OWNER_ROOT_AUDIT`
**are not switches**, but a whole set of valid baselines that depend on each other:

- The `boot-progress` implementation is in `UniXNU-sheng/kits/sheng/BootProgress.c` (82 KB) + 3 probes ≈ **136 KB**
- Its builder (`build-boot-progress.py`) **exists neither in the fork nor in the UniXNU upstream**
- Enabling it trips the chain of gates: AES closure → CPU/pthread → owner crypto → virtio archive, **you fix one and another shows up**
- The `kernel.py` bootstrap pass deliberately empties these variables → the gate **always hits** on the cold build

**Rules that were set**:
1. **Do not change defconfig in the middle of the bring-up**
2. **If debugging the build chain goes beyond 2 rounds, back off**
3. **`main` always buildable**

---

## V. Next steps (in order, without skipping any)

### Step 1: rule out the "log cut-off" possibility (half a day)

**The current hypothesis may be wrong.** We always believed IOSurface was a dead end, but **we never verified whether the kernel kept running**.

```c
bsd_autoconf();                              // it now gets stuck inside this
kprintf("NABU: bsd_autoconf returned\n");    // add this line
```

- **Something comes out** → the kernel is still alive, IOSurface was only a log cut-off → **go straight to step 2**
- **Nothing comes out** → the dead end is confirmed → go to step 3

### Step 2: root file system (1-2 weeks)

Following `/guide/userdata` + `/concepts/userdata`:

```
1. add "OS" and "Cryptex1,SystemOS" to the [ipsw] fetch in board.toml   ← already added, not verified
2. ./unixnu ipsw fetch          # downloads two components, several GB
3. ./unixnu build userdata      # SHNGROOT manifest + two windows
4. in [payload.adt] set root_match_volume_uuid = <UUID of the OS volume>
5. fastboot flash userdata out/nabu/userdata/userdata-root.img
6. watch whether it mounts and whether launchd starts
```

**Known**: the `[userdata]` LBAs were measured a while ago (`first_lba = 0x288C40` /
`last_lba = 0x77BF3FA` / `lba_bytes = 4096`).

### Step 3: display (3-4 weeks, only after step 2)

Following `UniXNU-sheng`: own `IOCoreSurfaceRoot` + `AppleCLCD`, registered in
`iokit/KernelConfigTables.cpp`, and in the platform expert create nubs for the children of `arm-io`.

**Do not do this step first** —— it answers "whether it can be seen", not "whether it boots".

---

## VI. Reference material

| Reference | Use |
|---|---|
| **`UniXNU-sheng`** | **The only correct reference**: complete example of roots / archives / defconfig |
| `UniXNU/UniXNU` | The framework itself; our fork is 163 commits behind and cannot simply be switched (`-mach_msg2`)|
| `glebenekt/ios-nabu` | Same device, iPadOS 16.6.1, 83 patches up to SpringBoard |
| `unixnu.com` | Official documentation |

**Two misleading points in the documentation** (already hit):
1. `/guide/debugging` presents `boot-progress` as a general feature, but it is actually sheng's, 136 KB
2. The `macos-26` image **does not have** Xcode 26.6, only 26.0 / 26.0.1

---

## VII. Tool list

| Tool | Use |
|---|---|
| `C:\Temp\auto\watch.ps1` | polls the build every minute |
| `C:\Temp\payload2.sh` | packages the payload (**watch out**: it calls `make-nabu-adt.py` by hand, bypassing the official `build payload`)|
| `C:\Temp\auto\shot.ps1` | QEMU boot + screenshot |
| `C:\Temp\findsym.py` | reverse lookup of kernel symbols |

**QEMU parameters (none can be missing)**:
```
-M virt -cpu max -m 8192 -smp 1
-drive if=pflash,...,file=edk2-aarch64-code.fd
-drive if=none,id=esp,...,file=fat:<ESP directory>
-device virtio-blk-pci,drive=esp -device ramfb
-display none -serial file:<log>
```
`-cpu max` (cortex-a72 does not recognize `MSR S3_0_C4_C1_4`); `-m 8192` (with 4096 DarwinBoot gives
`Out of Resources`).

---

## VIII. File map

| File | Function |
|---|---|
| `board.toml` | Board configuration: prelink roots / archives / userdata / payload |
| `configs/nabu_defconfig` | 9 switches (**do not add things for the sake of it**)|
| `patches/xnu/*.patch` | Kernel patches, applied in name order |
| `.github/workflows/build-kernel.yml` | CI (17 steps, including `build payload`)|
| `STATUS.md` | Summary of the current state |
| `FLOW.md` | Flow diagram (seven stages + two routes)|
| `HANDOVER-legacy.md` | Early path (origin of the probe method)|

**External dependencies**:
- `C:\Users\Administrator\Documents\UniXNU` — local clone of the `UniXNU` repo; **the CI actually uses the version pushed to the fork** (this matters: if you change the local copy without pushing, the CI does not see it)
- `C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs` — working directory for the payload and the boot image

---

## IX. The first command in the new window

```powershell
cd C:\Users\Administrator\Documents\unixnu-nabu-gh
git log --oneline -10
Get-Content STATUS.md | Select-Object -First 60
gh run list --repo Lux12138/unixnu-nabu --limit 3 --workflow build-kernel.yml
```

**Then, start with the first step of section V.**
