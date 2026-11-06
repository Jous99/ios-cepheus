# UniXNU on Xiaomi Pad 5 (nabu / SM8150) — Full handover document

> State: **the XNU kernel already starts running on the real phone** (DarwinBoot `exiting boot services` → `hand-off to the kernel`).
> Current work: installing "visibility probes" in the kernel (turning the black box into a white box).
> ✅ The injection chain is fixed and **the CI passes** (UniXNU `0c4e9a1` / unixnu-nabu `b7642cf`, run `39612555624` success,
> the MARK1–4 block markers are already linked into `kernel.macho`).
> ✅ The **real cause** of "the kernel gives no output" was also confirmed: DarwinBoot's `boot_args.Video` had been changed to the old array order,
> misaligned with the fields of the kernel's `struct Boot_Video` (see **Pitfall 8, correction**).
> ⬜ Next step: **rebuild the firmware + flash and count the blocks** (section 7, step 5; the device must be connected).

---

## 0. Location of the repository and the outputs

| Item | Path |
|---|---|
| This repository (documents/scripts/kits) | `C:\Users\Administrator\Documents\unixnu-nabu-gh` → https://github.com/Lux12138/unixnu-nabu |
| UniXNU fork (kernel build scripts) | `C:\Users\Administrator\Documents\UniXNU` → https://github.com/Lux12138/UniXNU |
| Kernel/payload/image outputs | `C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs` (**all the nabu-xnu64-*.img are here**)|
| WSL (firmware build) | `/root/Mu-Silicium` (EDK2/Mu UEFI), `/root/UniXNU` (upstream), `/root/xnu` (partial xnu clone for reference)|
| fastboot/adb | `C:\platform-tools` |
| git | `C:\Users\Administrator\.dsh-tools\PortableGit\cmd\git.exe` |
| gh | `C:\Program Files\GitHub CLI\gh.exe` |

> ⚠️ Source of mistakes: both `Documents\unixnu-nabu-kernel-ufs` and `Desktop\unixnu-nabu-kernel-ufs` exist,
> **the boot image is in the Desktop one**; several times there was a `No such file` from typing the path wrong.

---

## 1. Chain already working (verified step by step on the phone)

```
fastboot boot → BootShim → Mu UEFI → UniXNU menu → FAT payload from the cust partition
→ DarwinBoot → reads the 51 MB kernel → parses the Mach-O → reads the ADT → checks the ADT
→ allocates the window → maps segments → ExitBootServices → jumps to the XNU kernel ✅
```

Real phone log (photo):
```
UNIXNU: runxnu entry vol=A2142798 path=\EFI\UniXNU\Payloads\kernel.macho cfgerr=
DB1 kernel read  Success size=0x3345000      (≈51.2 MB; note, it is printed in hexadecimal)
DB2 kernel parse Success
DB3 adt read     Success size=0x330C
DB4 adt ok  win=0x130000000 keep=0 rd=ffffffffffffffff
DB6 va=0xFFFFFFF00427C000 pa=0x8007C000 args=0xC4364000
DARWINBOOT: inputs validated; exiting boot services
still-there kernel entry code ran
```

---

## 2. Hard pitfalls and fixes (in the order they were hit)

### Pitfall 1: Load Error
- It was believed that "the modified ABL disabled boot"; **the real cause was the USB cable**
- A bad cable loses data when transferring large images → the ABL fails verification
- ✅ Switch to the original data cable + the rear motherboard USB port

### Pitfall 2: ramdisk size range
| ramdisk | ABL | UEFI |
|---|---|---|
| 16 MB | ❌ Load Error | — |
| 32 MB | ✅ | ✅ |
| 64 MB | ✅ | ✅ |
| 96 MB | ✅ | ❌ black screen |

→ **usable range 32–64 MB**; `header_version=1`, `page_size=2048`

### Pitfall 3: the device must be rebooted before each boot
The **first boot after a reboot is the one that works most often**; back-to-back boots give Load Error (leftovers in the download buffer).

### Pitfall 4: the kernel cannot go in the firmware volume (PEI decompression budget)
| FVMAIN | Result |
|---|---|
| 8 MB (original) | ✅ |
| 62 MB (uncompressed kernel) | ❌ |
| 15 MB (LZMA kernel) | ❌ |

Limit of the FD itself: **3 MB usable; with 32 MB/60 MB nothing boots** (`[uefi_fd] size` stays at `0x300000`).

### Pitfall 5: there is no FAT volume at all (the most fundamental one)
The firmware ships its storage stack (`UFSDxe`/`PartitionDxe`/`DiskIoDxe`/`Fat`), but the Android partitions are all ext4/f2fs →
`Config->Volume=NULL` → DarwinBoot gives `NULL input`.

✅ **The payload is flashed to the `cust` partition** (1 GB, factory resources partition, does not affect booting the system):
```
\EFI\UniXNU\unixnu.toml
\EFI\UniXNU\Payloads\kernel.macho        (51MB)
\EFI\UniXNU\Payloads\kernel.macho.adt    (13KB)
```
⚠️ Before flashing, check that it is complete: `Sending 'cust' (65536 KB)`; once it was truncated to 1.2 MB and showed up as `config error: unixnu.toml line 1: expected '='`

### Pitfall 6: DarwinBoot is not dispatched
✅ It is added to the **first** `APRIORI DXE { }` block of `Include/APRIORI.inc` (a new block gives `GenFv ERROR 2000`)

### Pitfall 7: the ADT RAMDisk marker must match reality
```c
else if (RamdiskOffset != MAX_UINTN) { Status = EFI_UNSUPPORTED; goto Fail; }
```
✅ When generating the ADT **do not use** `--data-ramdisk` / `--packed-data-ramdisk`, so that it ends up as `rd=ffffffffffffffff keep=0`

### Pitfall 8: `boot_args.Video` layout (⚠️ the earlier conclusion was wrong, see below)
`BootVideo.h` originally wrote `[base, 1, rowBytes, width, height, 32]`, and at the time it was believed that XNU expected
`[base, rowBytes, width, height, depth, display]`
→ the kernel read `rowBytes=1 / depth=2560` → `initialize_screen()` fails → **silently falls back to the serial port**
✅ It was rewritten once (and the indices DarwinBoot draws with were changed at the same time); DarwinBoot reports `base=0x50000000 row=6400 1600x2560 depth=32`

> **⚠️ Correction (verified in this session)**: in xnu-10063.141.1 `boot_args.Video` **is not an array**, but
> `struct Boot_Video`, defined in `pexpert/pexpert/arm64/boot.h:31-38`:
> ```c
> struct Boot_Video {
>     unsigned long v_baseAddr;  // [0]
>     unsigned long v_display;   // [1]  ← the 2nd! not the last
>     unsigned long v_rowBytes;  // [2]
>     unsigned long v_width;     // [3]
>     unsigned long v_height;    // [4]
>     unsigned long v_depth;     // [5]
> };
> ```
> and `pexpert/arm/pe_init.c:419-429` takes the values one by one **by field name**:
> ```c
> PE_state.video.v_baseAddr = boot_args_ptr->Video.v_baseAddr;
> PE_state.video.v_display  = boot_args_ptr->Video.v_display;
> PE_state.video.v_rowBytes = boot_args_ptr->Video.v_rowBytes;
> PE_state.video.v_width    = ...->Video.v_width;
> PE_state.video.v_height   = ...->Video.v_height;
> PE_state.video.v_depth    = (...->Video.v_depth >> 0) & 0xFF;   // the depth is only the low 8 bits
> PE_state.video.v_rotate   = (v_depth>>8 & 0xFF) + (v_depth>>24 & 0xFF);
> PE_state.video.v_scale    = ((v_depth>>16) & 0xFF) + 1;
> ```
> That is: **if DarwinBoot really wrote `[base, rowBytes, width, height, depth, display]`**,
> the kernel would read `v_display=rowBytes (non-zero, so it goes graphical), v_rowBytes=width,
> v_width=height, v_height=depth, v_depth=display bits all 0` ——
> **all the video parameters misaligned**; `vcattach` gets the row width and the width/height wrong, and the result is "no output".
>
> ⇒ **This is** the real cause of "the kernel dies silently before `PE_create_console`" (verified, not a guess):
> `vcattach` receives `v_rowBytes=1600` (real 6400), `v_width=2560` (real 1600),
> `v_height=32` (real 2560), `v_depth=0` —— the screen parameters are all wrong and the graphical console does not start.
>
> **Chain of evidence**:
> 1. `pexpert/arm/pe_init.c:419-429` reads **by field name** (not by array index)
> 2. `pexpert/pexpert/arm64/boot.h:31-38` the structure order = base, display, rowBytes, width, height, depth
> 3. The `git diff` of `drivers/DarwinBoot/DarwinBootPkg/Driver/BootVideo.h` shows:
>    **the original upstream version already had the correct structure order**
>    ```c
>    Video[0] = FrameBufferBase;              Video[1] = 1;      // v_display
>    Video[2] = RowBytes;                     Video[3] = HorizontalResolution;
>    Video[4] = VerticalResolution;           Video[5] = 32;
>    ```
>    and the "pitfall 8 fix" changed it to `Video[1]=RowBytes … Video[5]=0` —— **it was changed in the wrong direction**.
> 4. The `DiagDraw` in `DarwinBoot.c` was changed at the same time to use `Video[1]` as rowBytes (also backwards),
>    while `Video[2]*Video[4]` (FB size), `Video[3]/Video[4]` (width/height) and other call sites
>    **always had structure semantics and were not touched** —— which proves the original code was correct.
>
> ✅ **Reverted (WSL `/root/UniXNU/drivers/DarwinBoot`)**:
> - `git checkout -- DarwinBootPkg/Driver/BootVideo.h` → the upstream structure order is restored
> - The 5 `DiagDraw` indices go back to `Video[2]`=rowBytes / `Video[3]`=width / `Video[4]`=height
> - The other call sites (`Video[2]*Video[4]`=FB size, `Video[3]`/`Video[4]`=width/height,
>   base/width/height/row/depth in the log) **already had structure semantics and do not need changing**
>
> ⇒ **Conclusion: the upstream HEAD DarwinBoot is correct. No patches or fork are needed.**
> The only thing to do is "not change it back to the array order". After rebuilding the firmware, the `Video` layout matches the kernel's.

### Pitfall 11: the kernel **cannot** write to the framebuffer early on (the probe ended up killing the kernel)
After `ExitBootServices`, the framebuffer **is still writable and visible** (shown with DarwinBoot's two-color probe, see below),
but that is **under the UEFI page tables**. After `start.s`, the kernel uses its own tables, and the **physical address** `0x50000000`
is not mapped in them → the write in `arm_init` **faults immediately**,
the kernel dies right there and the screen stays the same, exactly as if "the kernel had not run".

**Characteristic symptoms**: there is a log, there is a screen, there are no blocks, and the behavior does not change before and after adding the mark (because the mark itself is the cause of death).

✅ **Fix (UniXNU `9ad570c`)**:
- `nabu_mark_init()` only clears the state and **does not touch the fb**
- `NABU_MARK(n)` only records the hit in a RAM bitmap `g_hits` (RAM is always writable)
- `nabu_mark_rebind()` is hooked **at the end of `vcattach()`** and replays the hits on screen in one go

> ⚠️ **The mapping point is not `PE_create_console()`!** (the first version got this wrong and two rounds were flashed for nothing)
> - `vcattach()` is called by **`PE_init_printf(TRUE)`** (`pexpert/gen/pe_gen.c:135-140`)
> - and in `arm_init` there is only `PE_init_printf(FALSE)` → **during `arm_init` the fb is never mapped**
> - The real mapping is in `vcattach` → `initialize_screen(NULL, kPEAcquireScreen)`
>   → `ml_io_map_unmappable(...)` (`osfmk/console/video_console.c:2880`)
>
> That is why the injection point is before the final `}` of `vcattach`, with a **kernel VA guard**:
> ```c
> if ((unsigned long)PE_state.video.v_baseAddr >= 0xFFFFFFF000000000UL) {
>     nabu_mark_rebind((const unsigned long *)&PE_state.video);
> }
> ```
> If the address does not look like a kernel VA yet, **it is skipped**; even if the guess is wrong, there is no fault.
>
> **Side conclusion**: since the rebind (after the console) ended up killing the kernel, this proves that **the kernel does get
> past `PE_create_console`**, much further than the previous HANDOVER noted ("dies before `PE_create_console`").

### Pitfall 12: the green bar at the top of the screen does **not** mean "kernel entry code ran"
The message in `DarwinBoot.c` is wrong. Evidence:
1. `BootShim.S` has no code anywhere in its text that draws a green bar; nor does it appear in Mu-Silicium / UniXNU
2. In the four photos, the height of the green bar and the font size keep a **constant ratio**; only the photo distance changes
3. The A/B probe experiment confirmed that the red/green blocks drawn **below** the green bar show up normally

⇒ The green bar is just a fixed UEFI-side banner and **is not useful** as kernel progress. To interpret, look only at the blocks.

#### A/B probe experiment (decisive)
In DarwinBoot, two blocks are drawn in the same boot (both below the green bar, y=800):
| Probe | Moment | Result |
|---|---|---|
| Green block (700,800) | **before** `ExitBootServices` | ✅ appears |
| Red block (32,800) | **after** `ExitBootServices` | ✅ appears |

⇒ After the handoff, the fb is writable and visible; the "invalid framebuffer" path **is ruled out**.

### Pitfall 10: `nabu_mark_init(args->Video)` does not compile (fixed)
```
error: passing 'Boot_Video' (aka 'struct Boot_Video') to parameter of
       incompatible type 'const unsigned long long *'
```
✅ Changed to pass it as an "`unsigned long` stream": `nabu_mark_init((const unsigned long *)&args->Video);`
The mark implementation accepts both interpretations (structure order first, with automatic fallback to the old array order),
and **draws a red block** when `depth&0xFF != 32` or the fallback was used, so the layout problem shows up directly on screen.

### Pitfall 9: the EL is not the problem, do not investigate it further
- `EL1_OR_EL2` branch of `ModuleEntryPoint.S`: if it starts at EL2 it stays at EL2, if it starts at EL1 it stays at EL1
- Measured `EL=4` (EL1) → **the ABL hands off at EL1**, **raising the EL is impossible**
- DarwinBoot's own code requires EL1, consistent with the UniXNU design ✅

---

## 3. The only current blocker (in progress)

The kernel already jumps and runs, but **dies silently before `PE_create_console()` (arm_init.c:616)** and there is no kernel output on screen.

### Fix: draw "checkpoint blocks" at the earliest kernel entry
Principle: `boot_args.Video` already gives the framebuffer; the kernel draws 48×48 colored blocks at the start of `arm_init()`, **without needing a console or a text font**.

| No. of blocks | Color | Meaning |
|---|---|---|
| 0 | — | dies in the assembly/MMU entry, or the framebuffer is not mapped |
| 1 | white | entered `arm_init` |
| 2 | yellow | passed `PE_init_platform` |
| 3 | cyan | passed `PE_create_console` ← **the console works** |
| 4 | green | passed the second `PE_init_platform` |

The blocks start at `(32,32)`, 64 px apart, with a black background strip above.

### Already implemented
- `kits/nabu/nabu_early_mark.{c,h}` (pure C, passes `gcc -fsyntax-only`)
- `scripts/inject-early-marks.sh` (**reference only**: injects into any given xnu tree; the CI no longer calls it)
- ✅ **The authoritative implementation is in** `UniXNU/scripts/build-xnu-4k-baseline.sh` (commit `18ca785`):
  it is injected into `.cache/xnu-work` after the patch loop, with a re-entrant pre-clean, indentation-independent anchors and complete MARK1–MARK4

> The "inject into `refer/xnu`" step of `.github/workflows/build-kernel.yml` was removed: that tree takes no part in the build
> and keeping it only confuses; now there is a new step after the build, `Verify early checkpoint marks`, which automatically prints
> three checks: `marks inserted` / `WARN: mark? anchor` / symbol check with `llvm-nm`.

### History of the injection pitfalls (important!)
1. Standalone CI step → `refer/xnu` does not exist (**the refer source is downloaded lazily**, `tree.py` comment: `fetched when a step needs it`)
2. Inside the Build kernel step → `ls refer/` shows `total 0`
3. In the build script, but **inside the `if [ ! -d refer/xnu/.git ]; then` block** → the CI had already downloaded it, the block is skipped
4. Moved out of the if block → PowerShell's `Set-Content -Encoding UTF8` writes **BOM+CRLF** → bash cannot parse it (normalized to LF with Python)
5. Injected into `refer/xnu` → no effect, **the real build directory is `.cache/xnu-work`** ✅ already changed
6. Changed to `.cache/xnu-work` → the CI **fails**: the injection modified `arm_init.c` and **conflicts** with the later official `git apply` patches
   → ✅ **fixed**: the injection block was moved **after** the `done` of the patch loop (line 113), with reverse pre-clean
   (`native-4k-user-abi.patch` and `zzz-boot-progress.patch` modify `osfmk/arm/arm_init.c`;
   `source-machine-layer.patch` modifies `osfmk/conf/files.arm64`)
7. The anchor was an `assert`, and it turned out to be **indentation-sensitive** (`\t` vs spaces) and gave false results
   → ✅ changed to an **indentation-independent regular expression** + on no match only `print WARN` without aborting; if the `#include` anchor is missing, it falls back to the last `#include` line
8. The kernel build runs the script **twice** (the bootstrap pass generates the compile records → real pass), on the same `.cache/xnu-work`
   → ✅ the pre-clean makes the injection re-entrant (`MKU` first undoes, `MKP` then injects), so even if the CI reuses the work tree the patch context is not polluted

### Checking that the injection took effect
- ❌ Do not look only at the CI console (the script's stdout is redirected to the output)
- ✅ Look at the output's `kernel.log`: `marks inserted` / `nabu_early_mark`
- ✅ Check that the `kernel.macho` binary contains `nabu_mark`

---

## 4. Key source anchors (xnu-10063.141.1 / commit d8b80295, verified)

| File | Line | Content |
|---|---|---|
| `osfmk/arm/arm_init.c` | 199 | `void arm_init(boot_args * args);` |
| | 370 | `PE_init_platform(FALSE, args);` ← MARK1 anchor |
| | 616 | `PE_create_console();` ← MARK2/3 anchor |
| | 619 | `PE_init_printf(FALSE);` |
| `pexpert/arm/pe_init.c` | 425-436 | fills `PE_state.video` from `boot_args.Video` (generic arm64)|
| `pexpert/gen/pe_gen.c` | 135 | `PE_init_printf(boolean)` (`TRUE`→vcattach)|
| `osfmk/conf/files.arm64` | 51 | `osfmk/arm/arm_init.c	optional config_pmap_ppl`(for new files, add them in this format)|

Build script `UniXNU/scripts/build-xnu-4k-baseline.sh` (line numbers as of commit `18ca785`):

| Line | Content |
|---|---|
| 13 | `if [ ! -d refer/xnu/.git ]; then git clone ...; fi` (refer source, **takes no part in the build**)|
| 21 | `if [ ! -d .cache/xnu-work/.git ]; then git clone --shared refer/xnu .cache/xnu-work; fi` |
| 40-66 | **nabu pre-clean (MKU)**: undoes the previous injection, so the `apply --check` context of the patches is clean |
| 76-81 | **patch application loop** (the `done` is on line 81)|
| 82-169 | **nabu injection block (MKP)**: writes `nabu_early_mark.{c,h}` + `files.arm64` + the four MARKs in `arm_init.c` |
| 992 | `make -C .cache/xnu-work "${XNU_BUILD_TARGET:-build}" ...` (the real build)|

> ⚠️ The injection **must** go after the patch loop: `native-4k-user-abi.patch` and `zzz-boot-progress.patch` both modify
> `osfmk/arm/arm_init.c`, and `source-machine-layer.patch` modifies `osfmk/conf/files.arm64`.
> In addition, the kernel build runs the script **twice** (bootstrap pass + formal pass), so the pre-clean is essential, not optional.

---

## 5. Measured hardware data

| Item | Value |
|---|---|
| DRAM | 12 GiB |
| **RPMh RSC** | **`0x18200000` ×3 bank** |
| IPCC/apss_shared | `0x17c00000` (**only a mailbox, not RPMh**)|
| cmd-db / SMEM | `0x85f20000` / `0x86000000` |
| SPMI / PDC | `0xc440000` / `0xb220000` |
| GCC | `0x100000 +0x1f0000` (`#clock-cells=1`)|
| UFS HC / PHY | `0x1d84000` (ice `0x1d90000`) / `0x1d87000` |
| Timebase | 19200000 Hz |
| cust partition | `0x40000000` (1 GB)|
| CPU | `reg 0x0..0x700`, psci, kryo485 (matches the ADT `--cpu-regs`)|
| UFS supplies | vcc 2.504–2.95V(L10A), vccq 1.2V(L9A), vccq2 1.8V(S4A), vdda-phy 0.88V(L5A), vdda-pll 1.2V(L3C) |
| PMIC | pm8150=0, pm8150b=2, pm8150l=4 (**no pm8009**)|

---

## 6. Command quick reference

```bash
# ADT (no RAMDisk marker, please)
python3 UniXNU/scripts/make-nabu-adt.py --dram-size 0x300000000 \
  --owned-memory-size 0x130000000 --cpu-regs "0,0x100,0x200,0x300,0x400,0x500,0x600,0x700" \
  --ipad-identity --chip-id 0x207 --unique-chip-id 0x0000000000000001 --output kernel.macho.adt

# cust payload
bash unixnu-nabu-gh/scripts/make-cust-payload.sh kernel.macho kernel.macho.adt cust-payload.img

# Flash + boot (fastboot needed)
fastboot flash cust cust-payload.img
fastboot boot C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\nabu-xnu64-T.img

# Firmware (WSL)
cd /root/Mu-Silicium && python3 build_uefi.py -d nabu -r DEBUG
```

**Recovery**: hold the power button for 10 s; throughout the whole process **only `cust` has been written**, `abl`/`xbl`/`bootloader` have never been flashed.

---

## 7. First things for the next session (in order)

> ✅ 1–3 completed (commit `18ca785` @ UniXNU main). **Continue from step 4.**

| # | Task | Status |
|---|---|---|
| 1 | Move the injection block after the `done` of the patch loop | ✅ done |
| 2 | Make the `assert` tolerant (and turn it into an indentation-independent regex) | ✅ done |
| 3 | Validate with `bash -n` → UniXNU commit/push → launch the CI | ✅ done (`18ca785`)|
| 3.5 | First CI: fix the injection conflict → a build error appears → fix again | ✅ done (see below)|
| 4 | Download the outputs → check logs/symbols | ✅ done (run `39612555624` success)|
| 4.5 | Find the real cause: `boot_args.Video` layout misalignment | ✅ confirmed (see the pitfall 8 correction)|
| 5 | Rebuild the firmware (fix Video) → redo the cust payload → flash + boot → count blocks | 🔄 first round flashed: **0** blocks (see below), MARK1 etc. moved down in the third kernel round |
| 6 | If there are 0 blocks: switch to "write to writable RAM + read back by DarwinBoot" | ⬜ triggered by condition |

### Step 5, measured on the phone (round by round)

| Round | Kernel change | On-screen result | Conclusion |
|---|---|---|---|
| 1 | MARK1–4, writing directly to the physical fb | **0 blocks** | the probe itself faults (fb not mapped) |
| 2 | MARK1 moved down to the `arm_init` entry | 0 blocks | same as before |
| 3 | Early on only recorded in RAM, rebind after `PE_create_console` | 0 blocks | the fb is still not mapped at that point |
| 4 | rebind hooked at the end of `vcattach` | 0 blocks | the kernel did not reach `vcattach` |
| 5 | **`nabu_mark_map()` creates its own mapping with `ml_io_map_unmappable`** | **5 blocks** ✅ | the `arm_init` trunk works |
| 6 | real-time redraw + MARK7 (before `machine_startup`) + MARK8/9 (`kernel_bootstrap`)| **8 blocks** ✅✅ | **gets past `machine_startup` and enters `kernel_bootstrap()`** |

**Key reading of round 6**: 8 blocks = MARK1–8 all hit, that is
`arm_init` completes → `machine_startup(args)` → enters `kernel_bootstrap()`.
But block 9 (after `PE_init_iokit()`) does not appear, and **there is no kernel text on screen** ——
⇒ the point of death is narrowed down to **inside `PE_init_iokit()`**, that is, the `PE_init_printf(TRUE)` → `vcattach`
→ `initialize_screen(NULL, kPEAcquireScreen)` chain, the console initialization path.

> ⚠️ **This completely overturns the old conclusion that "the kernel dies silently before `PE_create_console`".**
> The kernel actually reaches `kernel_bootstrap`; that no output was seen before was simply because
> **nobody mapped the video memory early in the kernel** (see pitfall 11).

**Action taken**: 4 new probes are added to split up the inside of `PE_init_iokit` (UniXNU `cb2a921`):
```
10 = PE_init_iokit entry
11 = vcattach entry
12 = after initialize_screen(NULL, kPEAcquireScreen)
13 = after PE_init_printf(TRUE)
```

Block semantics (v4: real-time redraw, 13 slots):

> ⚠️ The green bar is not a progress signal (see pitfall 12). Count only the blocks.
> The blocks are **refreshed instantly** on each hit, so what the screen shows is the kernel's most recent position.

| No. of blocks | How far it got |
|---|---|
| 0 | start of `arm_init` (or before `nabu_mark_map`)|
| 5 | after the second `PE_init_platform` |
| 6 | `arm_vm_init` + automatic mapping correct |
| 7 | before `machine_startup(args)` → **`arm_init` finished** |
| 8 | enters `kernel_bootstrap()` |
| 9 | passed `PE_init_iokit()` |
| 10 | enters `PE_init_iokit()` |
| 11 | enters `vcattach()` |
| 12 | after `initialize_screen(kPEAcquireScreen)` |
| 13 | after `PE_init_printf(TRUE)` → **console fully ready** |
| extra red block | a separate red block at the top right = suspicious Video layout/depth (the firmware did not take effect)|

### Result of the step 4 verification (run `39612555624`, success)
```
① Patch conflicts: no patch failed / does not apply
② Injection record:
   kernel-bootstrap.log : marks inserted: MARK1=True MARK2=True MARK3=True MARK4=True
   kernel.log           : nabu pre-clean: reverted .cache/xnu-work/osfmk/arm/arm_init.c
                          nabu pre-clean: reverted .cache/xnu-work/osfmk/conf/files.arm64
                          marks inserted: MARK1=True MARK2=True MARK3=True MARK4=True
   ← two script passes, the pre-clean works and the second pass re-injects correctly: design validation passed
③ Symbols (kernel.macho 53,760,000 B): _nabu_mark ×6, _nabu_mark_init ×2
```

### Step 3.5: result of the first CI (kept for the record)
- run `39611266428` **failure**, but **no longer because of a patch conflict**: the conflict is fixed.
  Evidence: in the whole `apply --check` of `zzz-boot-progress.patch` there is no `patch failed`.
- The new error is a build error:
  `arm_init.c:373: passing 'Boot_Video' to parameter of incompatible type 'const unsigned long long *'`
  → see **pitfall 10**: `args->Video` is a `struct Boot_Video`, not an array.
- At the same time, looking at `pexpert/arm/pe_init.c:419-429`, it turned out that **the pitfall 8 conclusion was wrong** (display is in the 2nd position),
  and the correction and the points to verify were already noted in that section.
- Fix: pass `(const unsigned long *)&args->Video`; the implementation adapts to both layouts and draws a red block if the layout is suspicious.

### Step 4: confirm that the injection really made it into the binary

How to launch it (workflow_dispatch, `build-kernel.yml`):
```bash
gh workflow run build-kernel.yml --repo Lux12138/unixnu-nabu
gh run watch --repo Lux12138/unixnu-nabu
gh run download --repo Lux12138/unixnu-nabu -n kernel-nabu -D /tmp/nabu-kernel
```

Three checks (**the new `Verify early checkpoint marks` step already prints these three**):

```bash
# ① The incremental patches apply cleanly (no apply failed = the injection does not conflict with the patches)
grep -a 'error: patch failed' /tmp/nabu-kernel/logs/kernel.log || echo clean
# ② Injection record: MARK1..MARK4 must all show True
grep -a 'marks inserted' /tmp/nabu-kernel/logs/kernel.log
# Expected: marks inserted: MARK1=True MARK2=True MARK3=True MARK4=True
# If WARN: mark? anchor missing shows up → the upstream source anchors drifted; check again with the line numbers in section 4
# ③ The symbols actually linked into the kernel
xcrun llvm-nm --defined-only /tmp/nabu-kernel/kernel/kernel.macho | grep nabu_mark
# Expected: two lines _nabu_mark / _nabu_mark_init (T)
```
⚠️ **Do not look only at the CI console** (the script's stdout is redirected to `out/nabu/logs/kernel.log`);
`kernel-bootstrap.log` is the bootstrap pass log; the injection runs in both passes and `marks inserted` should appear in both.

### Step 5: flash + count blocks

**5a. Rebuild the firmware (this must be done first! otherwise Video is still wrong)**
DarwinBoot has already been reverted to the correct upstream version; rebuilding is enough for it to take effect:
```bash
wsl -e bash
cd /root/Mu-Silicium && python3 build_uefi.py -d nabu -r DEBUG
cd /root/UniXNU && ./unixnu bootimg        # packages it as an Android boot image (UEFI FD + dtb + ramdisk)
```
The output is numbered after the existing name, incrementing (the latest now is `nabu-xnu64-T.img`, the suggested next one `-U`), and is placed in
`C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\`.

**5b. Redo the cust payload (kernel side)**
```bash
# ADT (no RAMDisk marker, please)
python3 UniXNU/scripts/make-nabu-adt.py --dram-size 0x300000000 \
  --owned-memory-size 0x130000000 --cpu-regs "0,0x100,0x200,0x300,0x400,0x500,0x600,0x700" \
  --ipad-identity --chip-id 0x207 --unique-chip-id 0x0000000000000001 --output kernel.macho.adt
bash unixnu-nabu-gh/scripts/make-cust-payload.sh kernel.macho kernel.macho.adt cust-payload.img
```
`kernel.macho` uses the CI output `C:\Temp\nabu-ok\kernel\kernel.macho` (run `39612555624`).

**5c. Flash + boot** (before flashing, check `Sending 'cust' (65536 KB)`, that it is not truncated)
```bash
fastboot flash cust cust-payload.img
fastboot boot C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\nabu-xnu64-U.img
```
**Before each boot, reboot with a 10 s long press of the power button** (pitfall 3).

**How to read the new "red block" signal**: if a red block appears at the top right (slot 8), it means the kernel believes
`Video` still does not add up —— that would imply the firmware was not rebuilt properly, not a framebuffer problem.

Block semantics (v3: early on only recorded in RAM and replayed in one go after `PE_create_console`; from `(32,32)`, 64 px apart):

> ⚠️ **The green bar is not a progress signal** (see pitfall 12). Count only the blocks.
> Since the screen cannot be written before `PE_create_console`, **"0 blocks" only indicates "dies before the console" and
> cannot be narrowed down further** —— it is a hard limit of the current means of observation.

| No. of blocks | Color | Meaning |
|---|---|---|
| **0** | — | dies before `PE_create_console()` (start of `arm_init` / JOP signing / `arm_vm_init`)|
| 4 | white yellow cyan green | reached `PE_create_console()`, and 1/2/3 passed (normal case)|
| 5 | +magenta | everything passed, including the second `PE_init_platform` |
| extra red block | red | a separate red block at the top right = suspicious Video layout/depth (the firmware did not take effect, or the fallback kicked in)|
| only 1~3 blocks | — | should not happen: the replay draws all hits; missing numbers indicate a bitmap/geometry problem |

### Step 6 (only with 0 blocks)
The `Video` base address is not mapped in the kernel's early page tables (the kernel's `start.s` reuses the UEFI tables, but only guarantees the RAM regions),
so the `nabu_mark_init` write faults. Two directions:
1. **First confirm whether the fb is really not writable**: have DarwinBoot, after `ExitBootServices` and before `DarwinEnter`,
   draw a "relay block" with the fb it has already verified. If the relay block appears on screen but there is **no** MARK1 ⇒ the fb is not writable from the kernel side (diagnosis confirmed).
2. **Go through RAM**: at the start of `arm_init` write only static variables (bss is always writable),
   and after `arm_vm_init` map the fb with pmap and dump all the checkpoints to the screen in one go.

### Alternatives (if the marks path gets blocked)
- B: DarwinBoot hands off at EL2 (requires an EL switch, a big change)
- C: UART at 115200 (requires opening the device; **the user does not accept this**)
- D: early kernel console over GOP (`vcattach` only takes effect after `PE_create_console`, it does not help with earlier deaths)

---

## 8. Document index

| File | Contents |
|---|---|
| `README.md` | Field report: chain + pitfalls + reproduction |
| `HANDOVER.md` | This document |
| `docs/firmware-patches.md` | List of firmware changes + known useless attempts |
| `docs/nabu-dts-extract.md` | DTS digest (RPMh address correction + UFS/PMIC/clocks)|
| `docs/pmgr-plan.md` | PMGR plan + minimal RPMh read path |
| `docs/early-console-plan.md` | Early console + checkpoint block mechanism |
| `docs/prior-art-0xDive-ios-nabu.md` | Comparison with similar projects |
| `kits/nabu/NabuPlatformPower.cpp` | PMGR skeleton |
| `kits/nabu/nabu_early_mark.{c,h}` | Checkpoint blocks (pure C)|
| `scripts/make-cust-payload.sh` | cust payload generation |
| `scripts/inject-early-marks.sh` | Mark injector |

---

## 13. The xnu-10063 boot stops in mig_init (localization conclusion of this round)

### Chain of facts (all with hardware evidence)

| Checkpoint | Reading | Meaning |
|---|---|---|
| `NABU_MARK(8)` | 8 | enters `kernel_bootstrap` |
| automatic numbering 18..44 | 26 | reached `mac_policy_init` |
| 45 / 46 | **45** | `mac_policy_init()` returned; falls inside `kernel_startup_initialize_upto(STARTUP_SUB_MACH_IPC)` |
| subsystem + entry | 13 / 27 | entry 28 of the MACH_IPC round |
| hash of `cur->func` | 56 → 50 | with both toolchain versions it maps uniquely to **`_mig_init`** |
| `mig_e[i]` index | **0** | `_mach_vm_subsystem` |
| routine index j | **0** | `mach_vm_allocate` (msgid 4800) |
| stub pointer hash | 19 | `0x...153c >> 4 & 0x3F`, matches the static dump → kstub **non-zero** |

`mig_init()` has five panic branches; the one that fires is:

```c
panic("kroutine must have precise size %d %d", mig_e[i]->start, j);
```

that is, `max_reply_msg == 0` for `mach_vm_allocate`. But in `mach_vm.defs` it has `out` parameters,
and the descriptor **should** carry the reply size —— so **the mig generation step of the build lost that field**; it is not a problem with the definition.

### Already ruled out

- Duplicate registration: 31 ops, 31 unique `iko_op_type`
- Array overflow: `__init_entry_set` 95856 B = 3994×24; `ipc_kobject_ops_array` 1728 B = 54×32
- Toolchain version: after `picked: /Applications/Xcode_15.0.app` it still stops at the same panic
- Our patches: the patch set has no `IKOT` / `mig` change
- Passing data in RAM across boots: `keep probe` on the second boot is still `fresh RAM`, the DRAM is not preserved

### Treatment adopted

Change the panic into a fallback:

```c
} else {
    mig_buckets[pos].kreply_size = mig_e[i]->maxsize;   /* conservative value */
    mig_buckets[pos].kreply_desc_cnt =
        mig_e[i]->kroutine[j].reply_descr_count;
}
```

It is a **pragmatic workaround** (a size that is too large only wastes memory, while the panic loses the whole boot). Side effects and risks:
the reply buffer is allocated with the subsystem maximum (4140 B for mach_vm); if later there is kalloc pressure or
a failure parsing replies, suspect this first.

### Probe experience (so it is not hit again)

- The framebuffer is **unmapped** for the whole of `arm_init`; it can only be written after creating our own mapping with `ml_io_map_unmappable`
- The block bar has at most 24 cells and is drawn **from lowest to highest** number, so the late 45/46/50/60 get shifted (it was changed to draw the last 24)
- `draw_number` must clear the cell before drawing, or remnants of the tens are left (50 would read as 54/58)
- A single number does not give enough information: the mach startup table has 1736 entries (`subsystem <= 14`), and ZALLOC alone takes 767,
  it was changed to a double "subsystem + entry no." cell, and then raised to four cells `nabu_mark_quad`
---

## 14. Got past mach IPC: the kernel enters IOKit kext loading

### Milestone

Today, for the first time, `kernel_startup_initialize_upto(STARTUP_SUB_MACH_IPC)` is passed.
The previous conclusion ("stops at the mig_init kroutine panic") was correct, but **it was only the first layer**.

### Full chain of causes of death (each layer backed by screen readings)

| Layer | Symptom | Evidence | Treatment |
|---|---|---|---|
| 1 | `panic("kroutine must have precise size")` | i=0/j=0 → `mach_vm_allocate`, `max_reply_msg=0` | fallback to the subsystem `maxsize` |
| 2 | the final `printf` triggers kprintf | after removing it, it still stops | delete that diagnostic printf |
| 3 | false positive of `assert3u(grp,<,TASK_GRP_COUNT)` | panel `line=283 x=120675180 y=32` | it was actually the next layer |
| 4 | **`reply_descr_count <= IPC_KOBJECT_RDESC_MAX`** | original assertion text + `x=120675180` (low bits of a pointer), `y=32` | **disable both descriptor count assertions** |
| 5 | **`OSMetaClass: Kext %s class %s is a duplicate`** | original text in green | current problem (prelink layer)|

Layer 4 is the real culprit: the field offsets of `kern_routine_descriptor` do not match this build,
`reply_descr_count` reads the low bits of a pointer (0x731_4xxx), and the assertion fails every time.
This also explains why, earlier, in all the static dumps "however the layout was computed, it never added up".

### Evolution of the means of observation (key engineering lesson)

1. **Automatic mapping of the physical framebuffer**: `nabu_mark_map()`, usable after `arm_vm_init`
2. **Block / number probes**: early on they were used to locate `mig_init`
3. **5x7 font + `nabu_mark_text()`**: draws the panic format string directly on screen
4. **The panic hook parses varargs**: draws the assertion expression, the line number and the real x/y values
5. All probes were moved down to the bottom half of the screen (`y≈1000+`), leaving the top for console/text

> Lesson: **do not go back to guessing values with two-digit cells**. `x=5180/y=32` was a misreading,
> it was actually `x=120675180/y=32`, and the conclusion is completely different. Use `nabu_mark_num()` to print decimal text.

### Paths tried that did not work

- **Early console** (calling `PE_init_printf(TRUE)` in `arm_init`):
  `vcattach` is left half-initialized and later `gc_update_color` hits `assert(gc_ops.update_color)`
  (`video_console.c:1226`) —— self-inflicted, already removed
- **Passing data in RAM across boots**: the DRAM is not preserved on reboot, `keep probe` the second time is still `fresh RAM`
- **UART serial port**: xnu has the `serial_console` framework, but the platform UART base address is missing + hardware wiring is needed
- **USB log** (what Pagani/giulia do): only exists after entering userspace, useless early on

### Build chain pitfalls (more than a dozen rounds were lost)

- `unixnu tree` already applied the patches and the build script applies them again → `patch does not apply`,
  and the error is swallowed by `|| true`. **Fix: before applying the patches, `git reset --hard` + `clean -fdq`**
- `source-machine-layer.patch` adds 4 `amcc_rorgn_*.c` to `files.arm64`,
  files that do not exist in 10063 → `Error 2` in the file list phase, with no diagnostics
- `pexpert/arm/` does not have the osfmk include root, and `<arm/nabu_early_mark.h>` does not resolve;
  `"../../osfmk/arm/nabu_early_mark.h"` must be used
- The kernel **has no `strstr`**, and linking would fail; it is replaced by comparing literal prefixes
- Injected code that refers to `static` variables of `nabu_early_mark.c` (such as `g_h`) does not compile,
  only fixed coordinates can be used

### Current problem

`OSMetaClass: Kext %s class %s is a duplicate; kext %s already has a class with this name`

IOKit reports duplicate kext class names during initialization. It is a problem in the **prelink packaging** layer (`kits/NativePrelink` submodule),
not in the kernel logic. Next step: read the duplicate kext names and cross-check them with the prelink list.

---

## 15. Fast QEMU iteration environment (set up today)

### Why

A kernel build in the CI takes **8.1 minutes** (87 % of the total 9.3 minutes is compilation),
and each flashing round adds 2 more minutes + photographing and interpreting by hand. Without a macOS host it cannot be built locally,
so only the **validation** half can be brought local: **QEMU, 45 seconds per round, with a directly readable serial log**.

### Components (all already in place)

| Piece | Location | Explanation |
|---|---|---|
| QEMU | `C:\Program Files\qemu` | 11.1.0, with `edk2-aarch64-code.fd` |
| Mu_Basecore | `UniXNU/package/Mu_Basecore` | EDK2 branch `release/202608`, 8.3k files |
| UniXNU.efi | `package/Build/Out/AARCH64-DEBUG/UniXNU.efi` | 94 KB, `./build.sh -b DEBUG -t GCC` |
| DarwinBoot.efi | `package/Build/UniXNU/DEBUG_GCC/AARCH64/DarwinBoot.efi` | 36 KB, provides the XNU loader protocol |
| ESP | `C:\Temp\qemu-test\esp` | `EFI/BOOT/BOOTAA64.EFI` + `EFI/UniXNU/{Drivers,Payloads,unixnu.toml}` |

### Key pitfalls

- In `build.sh`, `PACKAGES_PATH` originally only had `package` + `edk2`;
  `DarwinBootPkg` is under `drivers/DarwinBoot/`, so it needs
  `$ROOT/../drivers/DarwinBoot:$ROOT/../drivers:$ROOT:$EDK2`
- The `Test/Validation.inf` path in `DarwinBoot.dsc` is written relative to `DarwinBootPkg/`,
  but the real file is in `drivers/DarwinBoot/Test/`, it does not resolve and was removed
- When the EDK2 `build` fails it only prints `- Failed -`; `-d 9` is needed to see the cause
- **When calling Windows QEMU from WSL, the paths on the QEMU command line must be in Windows form**
  (`C:/...`); only the log file stays on the WSL side
- With `-m 4096` DarwinBoot gives `boot refused: Out of Resources`; **8 GB is enough**

### Facts already verified in QEMU

```
UNIXNU: UniXNU 0.1.0 starting as application, firmware EDK II
UNIXNU: driver \EFI\UniXNU\Drivers\DarwinBoot.efi (config): started
DARWINBOOT: loader v2 installed EL1
DARWINBOOT: ARM64 va=0xFFFFFFF00427C000 pa=0x4807C000 entry=0x4B1EB488
DARWINBOOT: hand-off to the kernel
```

**The kernel entry code ran (green bar at the top), and the exception trace shows the kernel running normally:**
852 exceptions, all the final ones are `Taking exception 5 [IRQ]`, `SPSR 0x205` (EL1h),
**no abort**. So the kernel is alive in QEMU; it just does not output anything on the serial port.

### Pending

- After adding a **tee to PL011** (`0x9000000`) to `nabu_mark_putc`, QEMU will be able to capture the kernel text;
  on the real phone that address is not mapped, the write is swallowed by the page fault handling and does not affect the fb path
- Once serial works, the `-d int` trace will no longer be needed

### Fully automatic

- `C:\Temp\auto\run.ps1` —— one pass: waits for the latest build → downloads → flashes ESP → QEMU → summary
- `C:\Temp\auto\loop.ps1` —— loop: launches build → waits → downloads → QEMU → analysis → next round,
  each round's log is saved in `C:\Temp\auto\rounds\<n>\`
- The CI already has `actions/cache` (`xnu-work/build`); from next time the build should be incremental


---

## 16. Kernel log through QEMU working (tonight's achievement)

### Result

Local QEMU can now print **real kernel logs**:

```
NABU                                                          <- mark that the UART mapping worked
kprintf initialized
Serial mode specified: 00000003
initialize_screen: b=23C7A0000, w=320, h=258, r=0xC80
pe_arm_init_interrupts: args: 0xfffffff007a62860
corecrypto_kext_start (tracing disabled)
FIPSPOST_KEXT ... all tests PASSED (1690 ms)
corecrypto_kext_start completed successfully
ulock_initialize>thread_max=1536, ull_hash_buckets=512        <- stops here
```

A verification round takes **40 seconds** (CI 8.5 minutes + flashing 2 minutes + photo).

### Four obstacles (each with a clear root cause)

| # | Symptom | Root cause |
|---|---|---|
| 1 | no log | the `kprintf` condition is `if (!disable_serial_output && !disable_kprintf_output)`, **both are true by default**; clearing only one does not help |
| 2 | after clearing them there is still no log | `PE_init_kprintf` runs in `STARTUP(KPRINTF)`, **before the fb mapping**; deciding by "fb ready" means the hook is never installed |
| 3 | the UART tag does not appear either | `0x9000000` is a **physical address**, the kernel VM does not have it mapped and the write fault is swallowed; it must first be mapped with `ml_io_map_unmappable` |
| 4 | Undefined Instruction | QEMU's `-cpu cortex-a72` does not recognize `MSR S3_0_C4_C1_4` (0xd500419f); **only `-cpu max` works** |

### QEMU's limit

It gets stuck in `zalloc_permanent` of `ulock_initialize()` (`STARTUP(EARLY_BOOT, STARTUP_RANK_FIRST)`).
**The real phone gets past this step** (the real one already reached IOKit), so it is due to QEMU missing hardware or to differences in
memory layout, not to a kernel defect. **QEMU's validation depth ends here**.

### What can be reused

| Piece | Location |
|---|---|
| Mu_Basecore | `UniXNU/package/Mu_Basecore` (`release/202608`)|
| UniXNU.efi | `package/Build/Out/AARCH64-DEBUG/UniXNU.efi` |
| DarwinBoot.efi | `package/Build/UniXNU/DEBUG_GCC/AARCH64/DarwinBoot.efi` |
| ESP | `C:\Temp\auto\esp` |
| QEMU device tree | `C:\Temp\auto\qemu.adt` |
| Screenshot | `C:\Temp\auto\shot.ps1` |
| Full automation | `C:\Temp\auto\loop.ps1` |

**QEMU command line (no option can be missing)**

```
-M virt -cpu max -m 8192 -smp 1
-drive if=pflash,format=raw,readonly=on,file=edk2-aarch64-code.fd
-drive if=none,id=esp,format=raw,readonly=on,file=fat:<ESP directory>
-device virtio-blk-pci,drive=esp -device ramfb
-display none -serial file:<log>
```

- `-cpu max`: cortex-a72 hits an undefined instruction
- `-m 8192`: with 4096 DarwinBoot gives `boot refused: Out of Resources`
- The ESP is used as a **directory** (`fat:`), there is no need to create an image with dd/mkfs.vfat
- When calling Windows QEMU from WSL, **the command-line paths must be in the form `C:/...`**

### The device tree has to be the QEMU one, not the nabu one

It is generated with `make-dt.py --armvirt --armcpu --smp 1`. With the nabu `.adt` you get:

```
*** CPU id 256 from CPU ordinal 1 'reg' property is out of range [0..7]
*** Missing 'interrupts' property for CPU 0
*** Missing 'function-ipi_dispatch' property for CPU 0
```

### The essence of IOSurface on the real phone (now clarified)

Getting stuck after `IOsurfaceRoot:installMemoryRegions()` **is neither an assertion nor a lack of memory**; rather,
**Apple's closed IOSurface kext does not work on non-Apple platforms**.

ios-nabu's solution is to **rewrite**: `NabuSurface.cpp` (IOCoreSurfaceRoot) +
`NabuFramebuffer.cpp` (AppleCLCD), registered in `iokit/KernelConfigTables.cpp`,
and in `NabuPlatformExpert` nubs are created for the children of `arm-io`. **Weeks of work**.
