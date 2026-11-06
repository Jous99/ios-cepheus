# UniXNU on Xiaomi Pad 5 (nabu / SM8150)

Full record of the port that boots **Apple's XNU kernel** through UEFI on the **Xiaomi Pad 5 (nabu, Snapdragon 860 / SM8150)**.

> **This device is the upgraded version:** **12 GiB** of physical DRAM (measured in TWRP: `MemTotal = 11766512 kB`,
> that is, 12 GiB minus about 816 MB for modem/hyp/rmtfs) and userdata of **about 468 GiB**
> (`fastboot partition-size:userdata = 0x74167BB000`).
> That is why `dram_size = 0x300000000` is **measured for this machine**; it is not the value of a standard 6/8 GB model.

> **Status**: **the kernel already runs up to `execve("/sbin/launchd")`**
> (`Process 1 exec of /sbin/launchd failed, errno 2`).
> Everything on the kernel side passes; what is missing is a root file system with the system files.

---

## I. Milestone: the kernel reached launchd

**On-screen evidence**

```
Process 1 exec of /sbin/launchd failed, errno 2
/sbin/launchd
kern_exec.c

FAR=18446744042837921792
PC=18446744005117767160
LR=18446744005111703156
```

**Full chain**

```
bsd_autoconf()                            OK
  kminit()                                OK
    IOsurfaceRoot::installMemoryRegions() OK   <- it had been believed it got stuck here
bsd_init, second half                     OK
  vfs_mountroot()                         OK
  load_init_program()                     OK   <- resolves /sbin/launchd
    execve("/sbin/launchd")               errno 2 (ENOENT)
```

**`errno 2` means the file does not exist; it is not a kernel failure.**

### We were wrong for three days

The `IOsurfaceRoot::installMemoryRegions()` line **was never the end, only the last kprintf**.
After it, `dtrace_postinit()`, `inittodr()` and the network initialization (conditional compilation) **print no log at all**,
so "the log stopped" was read as "the kernel stopped".

What was always missing was a root file system.

---

## II. Boot chain (verified on the device)

```
fastboot boot -> Mu UEFI -> UniXNU menu -> payload from the cust partition
-> DarwinBoot -> reads the 51 MB kernel -> parses the Mach-O -> checks the ADT
-> allocates the window -> maps segments -> ExitBootServices -> jumps to XNU -> the kernel runs
```

Key logs:

```
UNIXNU: runxnu entry vol=A2142798 path=\EFI\UniXNU\Payloads\kernel.macho cfgerr=[]
DB1 kernel read  Success size=53760000
DB2 kernel parse Success
DB3 adt read     Success size=13188
DB4 adt ok  win=120000000 keep=0 rd=ffffffffffffffff
DB arm64 va=0xfffffff007ac2000 pa=0x80070000 owned=0x120000000 window=0x30000000
video base=0x... width=2560 depth=32 bpp
DARWINBOOT: EL1 installed
DARWINBOOT: inputs validated; exiting boot services
still-there kernel entry code ran
DARWINBOOT: hand-off to the kernel
```

---

## III. Local Linux build (72 seconds per round)

The kernel can now be built on a local WSL Ubuntu 24.04 in **72 seconds** per round, versus 15-17 minutes on the GitHub macOS runner.

| Item | GitHub macOS runner | Local WSL Ubuntu |
|---|---|---|
| Build per round | 15-17 minutes | **72 seconds** |
| Output | 49.2 MB | **49 MB** |
| Reproducible | Only with CI | Can be run on the machine whenever you want |

**Output verification**

```
file            Mach-O 64-bit arm64 executable, flags:<NOUNDEFS|PIE>
__TEXT vmaddr   0xfffffff007004000      same as the original kernelcache
symbols         22708
nabu probes     nabu_mark / nabu_mark_map / nabu_mark_num / nabu_mark_putc
UFS probing     nabu_ufs_register_probe.cpp
sha256          c756ecdb88a9dd50156dc27d2cdf48a08ddf93fcf204040fa57804f814fc3c15
```

The toolchain comes from [`Allenwdk/xnu-linux-toolchain`](https://github.com/Allenwdk/xnu-linux-toolchain).

### 18 pitfalls getting it to work on Linux

| Category | Count | Examples |
|---|---|---|
| Missing tools | 8 | `libdispatch` has no Ubuntu package; `hostcompat.h` / `libc.h` / `copyfile.h` / `setmode` all had to be written |
| Hard-coded paths | 5 | `/usr/bin/xcrun`, `/usr/sbin/sysctl`, `compression_tool`, `dsymutil`, `lzfse` |
| BSD vs GNU | 3 | `sed -i ''`, `awk \(`, unknown `-Wno-*` |
| Logic conflicts | 2 | mockfs linked twice (23 duplicate symbols), duplicated `TargetConditionals.h` |

**The most valuable one**: in `makesyscalls.sh`, `printf("\t{ \(sy_call_t *\)...")` ——
**BSD awk treats `\(` as an escape, gawk keeps the backslash**: on Linux the generated `init_sysent.c` is all
`\(sy_call_t *\)`, and the compiler throws a pile of `expected expression`. A patch was made (`zzzz-nabu-awk-parens.patch`),
because `unixnu tree` rebuilds `.cache` every time and a manual change would be overwritten.

---

## IV. Root file system: 7-Zip extracts it directly, no hdiutil

`build userdata` gets stuck on Linux at `hdiutil`. There is no need to write an own UDIF parser ——
**7-Zip 23.01 natively supports DMG + LZFSE** and directly extracts the full iOS file system:

```bash
sudo apt-get install -y p7zip-full
7z x -y -o/tmp/dmgout 044-76040-038.dmg
```

Measured result:

```
/sbin/launchd   561,856 bytes   Mach-O 64-bit arm64 executable
                               flags:<NOUNDEFS|DYLDLINK|TWOLEVEL|PIE>

9.7 GB / 210,828 files
  8.1G  System
  713M  usr
  483M  private
  313M  Applications
  139M  Library
  960K  sbin
```

**Watch out**: `dmg2img 1.6.7` **does not support LZFSE**, it gives
`Unsupported or corrupted block found: -2147483641` and produces a garbage image. Use 7-Zip.

`7z l -slt` shows the compression method directly:

```
Method = Copy Zero2 LZFSE CRC
Path   = 3.apfs
Size   = 6077546496         5.66 GiB
Type   = APFS
Name   = DawnUpdate21H461.J120J121J207J208OS.apfs
num_files: 165509
```

---

## V. Six hard pitfalls and their fixes (hitting them in this order saves days)

### Pitfall 1: `fastboot boot` gives `Failed to load/authenticate boot image: Load Error`

It is **not** the modified ABL disabling boot, **it is the USB cable**.

- A bad charging cable loses data when transferring ~96 MB images -> the ABL fails verification
- With the original data cable and the rear motherboard USB port, the same image gives `Booting OKAY` right away

### Pitfall 2: the ramdisk size has lower and upper limits

| ramdisk | ABL | UEFI |
|---|---|---|
| 16 MB | Load Error | — |
| 32 MB | OK | normal menu |
| 64 MB | OK | normal menu |
| 96 MB | OK | black screen |

Usable range **32-64 MB**; `header_version = 1`, `page_size 2048`.

### Pitfall 3: reboot the device before `fastboot boot`

**The first boot after each reboot is the one that works most often**; back-to-back boots give Load Error (residual state is left in the download buffer).

### Pitfall 4: putting the kernel in the firmware volume does not work (PEI decompression budget)

| FVMAIN size | Result |
|---|---|
| 8 MB (original) | the firmware works |
| 62 MB (uncompressed kernel) | back to fastboot |
| 15 MB (LZMA-compressed kernel) | back to fastboot |

The FVMAIN limit is about 8-10 MB; the FD itself also has a limit. **The kernel cannot go in the boot.img kernel segment, only through storage.**

### Pitfall 5: there is no FAT disk at all (the most fundamental one)

The firmware actually ships a full storage stack (`UFSDxe` / `PartitionDxe` / `DiskIoDxe` / `Fat`),
but the Android partitions are all ext4/f2fs, so UniXNU finds no volume with `unixnu.toml`.

### Pitfall 6: the ADT DRAM has to be the measured value

```
dram-size               = 0x300000000   12 GiB (upgraded on this device)
darwinboot-memory-size  = 0x20000000    contiguous 512 MiB window
```

`darwinboot-memory-size` is a **contiguous** block of physical memory that DarwinBoot requests from the firmware.
512 MiB is enough; a larger value is harder to find as a contiguous range in `EfiConventionalMemory`.

---

## VI. Next step

**The only thing missing is turning the extracted root into a mountable volume.**

```bash
./unixnu ipsw fetch OS Cryptex1,SystemOS      # already downloaded: OS 4.80 GiB + SystemOS 3.08 GiB
7z x -y -o/tmp/dmgout out/ipsw/21H461/044-76040-038.dmg
./unixnu build userdata                       # SHNGROOT manifest + two windows
fastboot flash userdata out/nabu/userdata/userdata-root.img
```

`[userdata]` geometry (measured in TWRP):

```
first_lba = 0x288C40     2,654,272    (4 KiB LBA)
last_lba  = 0x77BF3FA    125,436,922
lba_bytes = 4096
windows   = [OS, SystemOS]
```

**It is no longer a build or driver problem: it is a data problem.**

---

## VII. References

- [`Allenwdk/xnu-linux-toolchain`](https://github.com/Allenwdk/xnu-linux-toolchain) —— cross toolchain for Linux
- [`1PJL/unixnu-nabu`](https://github.com/1PJL/unixnu-nabu) —— UFS volume diagnostic series (three steps `Recover GPT` / `Build Volume` / `Repack`, on `ubuntu-24.04`)
- `UniXNU` upstream —— kernel port and UEFI boot chain
