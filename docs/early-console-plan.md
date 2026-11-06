# Early kernel console on the framebuffer (getting the panic out without opening the device)

> Document from the Xiaomi Pad 5 (nabu), translated to English for reference. The Chinese original is in `docs/original-zh/`.

## The problem

The kernel already starts running (`DARWINBOOT: hand-off to the kernel` / `still-there kernel entry code ran`),
but **no panic text appears on screen**, and control returns to UniXNU (the menu is redrawn).

Cause: XNU's early `kprintf` outputs to the **serial port** by default; without a UART it is a black box.
And the UART requires opening the device and soldering wires, and at this point neither `fastboot` nor ADB exist.

## Favorable conditions that already exist

DarwinBoot already hands the video memory information to the kernel (`Video[6]` in the boot args):

```
video base=0x50000000   1600x2560   row 6400 bytes   32 bpp
```

That is, `PE_state.video` already has `v_baseAddr / v_rowBytes / v_width / v_height / v_depth`.
The framebuffer is normal mapped memory, writable from EL1: **no extra hardware is needed**.

## Plan: bring up a minimal framebuffer console

It does not depend on Apple's `video_console` (that subsystem mainly serves the boot screen on x86 and is not
active on ARM). Writing a self-contained `putc` backend is the lowest-risk option.

```
scripts/nabu-early-fb-console/
├── nabu_fb_console.c    ~150 lines
│     - 8x16 bitmap font (ASCII 32..126; can start with just 0x20..0x7E)
│     - nabu_fb_putc(c): handles \n / \r / scrolling
│     - pixel writes: base + rowBytes*y + 4*x, 32 bpp, writes 0x00FFFFFF
│     - everything is based on PE_state.video; no MMIO, no registers
└── inject.py            build-time injection
```

### Injection points

1. `PE_init_kprintf()` (`pexpert/gen/pe_gen.c` or the arm implementation)
   → add after initialization:
   ```c
   if (PE_state.video.v_baseAddr != 0) { nabu_fb_init(); }
   ```
2. `vputchar()` (`osfmk/console/printf.c` or the pexpert equivalent)
   → add after the serial output: `nabu_fb_putc(c);`

### Safety constraints

- `v_baseAddr == 0`, or `v_depth != 32`, or abnormal width/height → **enable nothing** (return immediately).
- Only normal memory writes; no SoC register is read or written.
- No memory allocation (there is no malloc early on): static arrays for the cursor and color.
- A failure never panics; in the worst case, "nothing more appears on screen".

## Implementation order

1. Get the xnu code (in the CI or cloned into `~/xnu`) and confirm:
   - the real path and body of `PE_init_kprintf`
   - the real path and signature of `vputchar`
   - name and type of the `PE_state.video` fields (`video_info_t`)
2. Write `nabu_fb_console.c` with the real names; run `clang -fsyntax-only` on it locally first.
3. `inject.py`: insert using anchor strings; after inserting, **check that the anchor is unique and that the insertion
   succeeded**; if it fails, make the build fail.
4. Push to the CI to build the kernel → rebuild boot.img (same flow as `nabu-xnu64-*.img`) → boot on the device.
5. Criteria:
   - Early kernel text / `panic(...)` appears on screen → the console works ✅
   - Only the UniXNU menu is still visible → the kernel dies before `PE_init_kprintf`
     → move the fb initialization earlier (before `arm_init` / `machine_startup`), or put it on the first line
       of the C entry after `Entry.S`.

## Relation to PMGR

It is a **prerequisite**: without early output, every PMGR step is a blind change.
With the console working, the PMGR debugging loop becomes:
edit `NabuPlatformPower.cpp` → build → boot → see the voltage/clock values read on screen.

---

## Measured progress (2026-10-21 19:49)

### Fixed: shifted video array (one of the real causes)

`DarwinBootPkg/Driver/BootVideo.h` wrote `boot_args.Video[6]` as

```
[0]=base  [1]=1  [2]=rowBytes  [3]=width  [4]=height  [5]=32
```

while XNU (`pexpert/arm/pe_init.c:425`) expects

```
[0]=base  [1]=rowBytes  [2]=width  [3]=height  [4]=depth  [5]=display
```

→ the kernel read `rowBytes=1 / width=6400 / height=1600 / depth=2560`,
`initialize_screen()` treated it as failed → **silently fell back to the serial port** → there was never kernel output on screen.

It was fixed to the correct format (along with the indices DarwinBoot uses to draw its own text).
Measured afterwards: `base=0x50000000 row=6400 width=1600 height=2560 depth=32 display=0` ✅

### But still no kernel output → the kernel dies before `PE_create_console`

`PE_create_console()` in `osfmk/arm/arm_init.c:616` is the first point where text could come out.
With the video parameters now correct and still no output, it means **it does not get that far**.

## Current main suspect: the starting exception level (EL) does not match

| Fact | Explanation |
|---|---|
| The DarwinBoot probe measures `EL=4` (= EL1) | We now hand off the kernel **at EL1** |
| DarwinBoot's code requires `DarwinCurrentEl() == 4` | Forces EL1 |
| Real Apple chain | **iBoot hands off at EL2 and XNU drops to EL1 by itself** |

Early on, XNU's `arm_init` / `arm_start` access EL2 system registers
(`HCR_EL2`, `VTCR_EL2`, `VHE`, etc.). **If the kernel believes it is at EL2 but is at EL1, the first related
instruction raises an exception, and no console has been initialized yet → silent death.**
This matches exactly what was observed: correct video parameters, the kernel entry code ran,
and not a single letter.

### How to check it (next step, one of two)

**A. Make the kernel speak for itself** (the most direct)
On the first line of `arm_init()` in `osfmk/arm/arm_init.c`, inject a self-contained framebuffer `putc`
(that only writes to the video memory pointed to by `boot_args_ptr->Video`, without depending on any console):

```c
nabu_fb_early_init(boot_args_ptr->Video);
nabu_fb_early_puts("arm_init enter\n");
```
And put a marker before and after `machine_startup`, `PE_init_platform` and `PE_create_console`:
this shows precisely up to which line the kernel gets.

**B. Change DarwinBoot to hand off at EL2**
Change the `DarwinCurrentEl() != 4` check to accept EL2 (or remove it), so that the kernel starts
from EL2 as in the real Apple chain. Risk: DarwinBoot now runs at EL1; to hand over control at EL2
an extra EL switch is needed (`eret` to EL2), a bigger change.

> Starting with A is recommended (it gives more information and has less risk); once the point of death is located,
> decide whether B is needed.

---

## Plan adjustment: "checkpoint blocks" first, no text font

Writing an 8×16 font requires ~1500 bytes of bitmap data, is easy to draw wrong and hard to verify;
and **locating the point of death does not need text**: it is enough to know which checkpoint is reached.

### Mechanism

`kits/nabu/nabu_early_mark.c`: draws **48×48 colored blocks** into the video memory pointed to by
`boot_args.Video`; it does not depend on the console, allocates no memory, touches no registers, and if the parameters are invalid
it gives up silently (`depth!=32` / `base==0`).

### How to read it (one row of blocks at the top left)

| Blocks visible | Meaning |
|---|---|
| **0** | Did not even enter `arm_init`: dies in the assembly entry / while setting up the MMU |
| **1 (white)** | Entered `arm_init` |
| **2 (yellow)** | Passed `PE_init_platform` |
| **3 (cyan)** | Passed `PE_create_console` |
| **4 (green)** | Passed `machine_startup` |
| **N in red** | Invalid parameters (gave up safely, without corrupting memory) |

### Injection points (next round, modifying the XNU source code)

```c
// osfmk/arm/arm_init.c : first line of arm_init()
nabu_mark_init(boot_args_ptr->Video);
NABU_MARK(1);

// then, one after each key step
PE_init_platform(...);   NABU_MARK(2);
PE_create_console();     NABU_MARK(3);
// inside machine_startup
```

### Why this method is better

- ~110 lines of code, no bitmap data: almost impossible to "draw it wrong".
- Interpreting it only takes counting blocks; it shows up well in a photo or video.
- A failure is completely safe (only video memory writes after bounds checking).
- Once the specific phase is located, decide whether the text font is needed (by then it may no longer be).
