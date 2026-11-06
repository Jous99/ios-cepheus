# Status summary

> This device is an **upgraded nabu**: **12 GiB** of physical DRAM, measured in TWRP's `/proc/meminfo`
> (`MemTotal = 11766512 kB`, that is, 12 GiB minus about 816 MB for modem/hyp/rmtfs).
> That is why `dram_size = 0x300000000` and `owned_memory_size = 0x130000000` are **values measured for this machine**,
> not those of a standard 6/8 GB model. Copying the `0x180000000` (6 GiB) from other projects would make physical memory above 6 GiB
> invisible to Darwin.

## Milestone: the kernel reached launchd

**On-screen evidence (night of 2026-10-23)**

```
Process 1 exec of /sbin/launchd failed, errno 2
/sbin/launchd
kern_exec.c

FAR=18446744042837921792
PC=18446744005117767160
LR=18446744005111703156
```

**The kernel went through this whole chain:**

```
bsd_autoconf()        ✅
  kminit()            ✅
    IOsurfaceRoot::installMemoryRegions()   ✅   ← it used to be believed it got stuck here, but no
bsd_init, second half         ✅
  vfs_mountroot()     ✅
  load_init_program() ✅   ← resolves /sbin/launchd
    execve("/sbin/launchd")   ❌  errno 2 (ENOENT)
```

**`errno 2` means the file does not exist: it is not a kernel problem; the root file system simply does not have that file.**

### This overturns three days of diagnosis

The `IOsurfaceRoot::installMemoryRegions()` line **was never the end**, it was only the last kprintf.
What comes right after it (`dtrace_postinit()`, `inittodr()` and the conditionally compiled network initialization) prints no logs, so
"the log stopped" was taken for "the kernel stopped".

What was always missing is **a real root**, not an own surface.

## Local Linux build working (12 times faster)

| Item | GitHub macOS runner | Local WSL Ubuntu |
|---|---|---|
| Build per round | 15-17 minutes | **72 seconds** |
| Output | 49.2 MB | **49 MB** |
| Reproducible | Only with CI | Can be run on the machine whenever you want |

Verification:

```
file            Mach-O 64-bit arm64 executable, flags:<NOUNDEFS|PIE>
__TEXT vmaddr   0xfffffff007004000      ← same as the original kernelcache
symbols         22708
nabu probes     nabu_mark / nabu_mark_map / nabu_mark_num / nabu_mark_putc
UFS probing     nabu_ufs_register_probe.cpp
sha256          c756ecdb88a9dd50156dc27d2cdf48a08ddf93fcf204040fa57804f814fc3c15
```

**Toolchain**: `Allenwdk/xnu-linux-toolchain` (Ubuntu 24.04 / clang 18 / 12 cores)

## 18 problems solved along the way

```
 1  libdispatch has no Ubuntu package    → build from source + hand-written .pc
 2  toolchain/csh is a symbolic link     → cp -L
 3  xcrun with hard-coded /usr/bin/xcrun → symbolic link
 4  sysctl with hard-coded /usr/sbin/sysctl → replaced by a Darwin shim
 5  /bin/sh is dash                      → point it to bash
 6  bison/flex/m4 are in /usr/sbin       → symbolic link
 7  hostcompat.h does not exist          → hand-written
 8  libc.h does not exist                → hand-written (OSAtomic / page alignment)
 9  copyfile.h / fcopyfile               → hand-written
10  setmode/getmode                      → hand-written (who shift + mask fix)
11  TargetConditionals.h                 → hand-written, and only in two places
12  sys/_types/_os_inline.h              → hand-written and replicated in the compat tree
13  mach/mach_init.h                     → hand-written
14  unrecognized -Wno-*                  → -Wno-unknown-warning-option
15  macOS clang 26 diagnostic names      → CCC_OVERRIDE_OPTIONS, downgrading them one by one
16  sed -i '' is BSD syntax              → handled per branch, and only run on Darwin
17  awk \( in GNU keeps the backslash    → turned into a patch (zzzz-nabu-awk-parens)
18  mockfs linked twice (23 duplicate symbols) → force_load removed
```

## Next step

**The only thing missing is a real root file system.**

```
./unixnu ipsw fetch                          # OS + Cryptex1,SystemOS
./unixnu build userdata                      # SHNGROOT manifest + two windows
fastboot flash userdata out/nabu/userdata/userdata-root.img
```

Known: the `[userdata]` LBAs were measured a while ago (`first_lba = 0x288C40` / `last_lba = 0x77BF3FA` /
`lba_bytes = 4096`).

**It is no longer a build or driver problem: it is a data problem.**
