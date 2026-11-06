# List of predictions (updated 2026-10-22 21:58)

Sorted by the execution order of `bsd_init.c` / `bsdinit_task()`. When one is hit, it is identified directly.

| # | Blocking point | Trigger condition | Status |
|---|---|---|---|
| 1 | `panic("rootvp not authenticated after mounting")` | On non-macOS `require_rootauth = TRUE` is forced; the mockfs/ramdisk root has no sealed signature | ✅ already fixed in advance (`zzzz-nabu-unsealed-root.patch`)|
| 2 | `cannot mount root, errno = N` | No usable root device (NativeUfs disabled, no ramdisk)| **still to be hit, the first hard nut** |
| 3 | `imageboot_setup` | `CONFIG_IMAGEBOOT` looks for a system disk image | to be observed |
| 4 | `devfs_kernel_mount("/dev")` | devfs not initialized | to be observed |
| 5 | `load_init_program` does not find init | see below | **the second hard nut** |
| 6 | loopattach race with 8 cores | real multi-core phone; avoided in QEMU with `-smp 1` | known |

## Detail of point 5 (confirmed)

`kern_exec.c`:

```c
static const char * init_programs[] = ('/usr/appleinternal/sbin/launchd.debug', '/usr/appleinternal/sbin/launchd.development', '/sbin/launchd');
```

It is a DEVELOPMENT build, so the order is
`launchd.development` → `/sbin/launchd`.
`appleinternal` will not exist, so **we have to rely on `/sbin/launchd` in the root file system**.

**This means: once the kernel gets this far, everything else depends on the root file system.**
It is not a kernel logic problem, but a matter of "whether the iOS userland is installed or not".

## Known good practices (so mistakes are not repeated)

- **Boot-args go in the `[[entry]] args` of `unixnu.toml`**, not in the ADT or in `make-nabu-adt.py`
- **kprintf needs two switches disabled at the same time**: `disable_serial_output` and `disable_kprintf_output`
  (the condition is `if (!disable_serial_output && !disable_kprintf_output)`)
- **`PE_kputc` must be assigned unconditionally**: `PE_init_kprintf` runs in `STARTUP(KPRINTF)`, before the fb mapping
- **New instrumentation, always as patch files**: the injection script has failed silently 5 times
- **Protect headers with `extern "C"`** (when a C++ file includes them)
- **Relative includes**: outside `osfmk/`, always `"../../osfmk/arm/nabu_early_mark.h"`
- **The probe numbering limit** was raised to 128 (with 64, probes 65+ were silently dropped)

## Facts verified in QEMU

- The kernel entry works (green bar at the top)
- The exception trace only has IRQs, **no abort** → the kernel is alive in QEMU
- `disable_serial_output=0 / disable_kprintf_output=0 / nabu_mark_putc` are verified in the binary
- Serial still has no text → a "fixed UART tag" is being used to tell "the UART does not write" apart from "kprintf was not reached"
- **QEMU cannot reproduce the IOSurface blocker** (that is IOKit against real hardware)


## The essence of the IOSurface blocker on the real phone (important)

ios-nabu's `0046-nabu-iosurface-iomfb.patch` reveals the cause: **they did not use Apple's closed
IOSurface kext**, but implemented on their own:

    iokit/Kernel/arm/NabuSurface.cpp       -> IOCoreSurfaceRoot
    iokit/Kernel/arm/NabuFramebuffer.cpp   -> AppleCLCD

and register those two classes in `iokit/KernelConfigTables.cpp`; in addition, in `NabuPlatformExpert` they create nubs for
the children of `arm-io`, so that the built-in drivers can match.

**Conclusion: the block after `IOsurfaceRoot:installMemoryRegions()` is neither an assertion nor a lack of memory;
the closed IOSurface kext simply does not work on non-Apple platforms.** Getting past it requires rewriting
the surface / framebuffer driver, weeks of work that one or two rounds of patches will not solve.

This also explains why ios-nabu has 83 patches and took several months to reach SpringBoard.
