# Porting XNU to nabu: the route of the reference projects and our feasibility plan

Generated: 2026-10-22

---

## I. The real size of the reference projects

| Project | Kernel version | Patch size | State reached |
|---|---|---|---|
| **glebenekt/ios-nabu** | xnu-8796 | **83 patches / 1.58 MB** | XNU on a real phone, read/write UFS root, **launchd / SpringBoard / backboardd start**, display services registered |
| **oosexgang/hackios** | xnu-8796 | **a single 119 KB file** | lock screen/home screen/settings/Safari work (Adreno GPU)|
| **IssacL04/Pagani** | reuses the BCM2837 config | several | gets past the allocator assertions, reaches BSD setconf |
| **Us (Lux12138)** | **xnu-10063** | about 20 own patches | **kernel up to after bsd_autoconf, stuck at IOSurface** |

**Key difference**: both mature projects use **xnu-8796**; we insist on **10063**.
The patches **cannot be ported directly**, but **the stage split and the methodology can be copied as they are**.

---

## II. The 83 ios-nabu patches are really a five-stage path

### Stage 1: Getting the kernel to boot (0001–0020, 20 patches)

| Patch | Function |
|---|---|
| 0001/0002/0005 | Build fixes for the new clang |
| **0003/0010/0012** | **serial console over the framebuffer, early fb debugging, keeping the console after ttbr0** |
| 0004/0006–0009 | machine config, open-source asm pmap, stubs for Apple internal headers, filling gaps left by closed libraries |
| 0011 | physmap alignment padding |
| **0013/0014** | **RNG without depending on corecrypto** (`vm_kern.c`, 97 lines)|
| **0015** | **trust cache unavailable at runtime** |
| **0016/0017/0018** | **device tree platform expert, virtual timer IRQ, boot CPU driver** |
| **0019** | **built-in pthread** (not through prelink!)|
| 0020 | portable AES-CBC |

**What we already have**: the equivalent of 0003/0010/0012 (fb + UART + kprintf, solved tonight).
**What we are missing**: 0013/0014 (RNG), 0015 (trust cache), 0016–0018 (DT platform expert), **0019 (built-in pthread; we misuse prelink)**.

### Stage 2: Root file system (0021–0037, 17 patches)

| Patch | Function |
|---|---|
| **0021** | **mockfs + RAM disk as root** (54 lines)|
| 0022/0024 | ramdisk root without IOMedia, virtual ramdisk I/O in mockfs |
| 0023/0026/0027/0032/0033 | built-in sha256 / HFS / BearSSL (md5/sha1/sha384/sha512)|
| **0025** | **own AMFI, no entitlement checks** (`bsd/kern/nabu_amfi.c`, 192 lines)|
| **0028/0030/0031/0034** | UFS root device, write support, read/write root, DMA above 4G |
| **0029** | **unsealed root** (24 lines, turns the panic into a printf)|
| 0035/0036 | AMFI entitlements, platform binary signing |
| 0037 | bindfs |

**Key**: they **started with mockfs + RAM disk** (0021) and **UFS was added later** (0028).
Since we disabled NativeUfs, we need exactly the 0021 path.

### Stage 3: Runtime stability (0038–0045, 8 patches)

AppleKeyStore, coredump disabled, **iowatchdog (0040/0045)**, HFS link notes,
short exec log, **crash log on the console (0043/0044)**.

**iowatchdog is key**: without it, a system that does not boot is rebooted by the watchdog, and it looks like a "random reboot".

### Stage 4: Display (0046–0049, 4 patches)

| Patch | Function |
|---|---|
| **0046** | **own IOSurface + IOMobileFramebuffer** (`NabuSurface.cpp` / `NabuFramebuffer.cpp`)|
| **0047** | **persistent console log** (4 MiB ring at the end of userdata, readable from TWRP)|
| 0048/0049 | devnull tee, IOKit trace |

**0046 is exactly the stretch where we are stuck**; their answer was **not to use Apple's closed kext and write it themselves**.

### Stage 5: Userland peripherals (0050–0083, 34 patches)

sandbox policy, crash sampling, HFS rename, process sampler, AKS, fb throttling,
**HID event services (0058)**, iPhone identity (0059),
**touch/key drivers (0060/0062/0063/0071/0083)**, iPhone X screen size (0061),
**PSCI SMP (0065/0078)**, console mute, surface lookup cache, UFS acceleration,
**USB (0072–0077/0081)**, display power, net trace, UFS AES.

---

## III. Our real gap (corrected after taking stock of the actual patches)

The first version exaggerated the gap. After counting `patches/xnu/`, the situation is:

| Capability | Our existing patch | ios-nabu equivalent | Status |
|---|---|---|---|
| mockfs build fixes | `mockfs-typed-allocation` / `mockfs-statfs` / `mockfs-intermediate-lookup` / `mockfs-memory-device-width` / `mockfs-test-file` | 0021/0024 | ✅ **done** |
| Tolerating missing block storage | `null-root-media` | 0021 | ✅ **done** |
| runtime trust cache | `native-trust-cache-runtime` | 0015 | ✅ **done** |
| **pthread** | `source-pthread-bootstrap` (adds `bsd/kern/source_pthread_bootstrap.c`)| 0019 | ✅ **solution already exists** |
| SMP | `native-smp-secondary` | 0065/0078 | ✅ already there |
| panic region | `native-dt-panic-region` | 0066 | ✅ already there |
| work interval | `native-priv-work-interval` / `native-work-interval-soft-fail` | 0064 | ✅ already there |
| platform expert / DT | `armvirt-platform-personality` / `source-machine-layer` / `sheng-platform-power` | 0016–0018 | 🟡 partial |
| **mockfs built into the kernel** | `zzzz-nabu-mockfs-root` (added this round)| 0021 | 🟡 **being verified this round** |
| **RNG without depending on corecrypto** | — | 0013/0014 | ❌ missing |
| **iowatchdog** | — | 0040/0045 | ❌ missing |
| **AMFI without entitlements** | — | 0025 | ❌ missing (or already partly covered by `public-entitlements-header`)|
| **own surface / framebuffer** | — | 0046 | ❌ missing, **still the biggest gap** |
| touch / USB / display power | — | 0058–0083 | ❌ missing, long term |

**Conclusion: we already have the vast majority of stages 1 and 2**; the real gap is in
**RNG (0013), iowatchdog (0040), AMFI (0025) and surface/framebuffer (0046)**.

---

## IV. Feasibility plan

### Option A: Stay on 10063 following the ios-nabu stages (recommended for the "be self-sufficient" goal)

**Premise**: accept that 10063 is an iOS 17 kernel and that the userland ABI risk is on us.

**Step 1: complete what is left of stage 1 (1-2 days)**

| Action | Reference | Explanation |
|---|---|---|
| **Move pthread from prelink to built-in** | 0019 | We now put `com.apple.kec.pthread` in the prelink roots, and that is not the right way |
| RNG without depending on corecrypto | 0013 | Change `osfmk/vm/vm_kern.c` |
| runtime trust cache tolerance | 0015 | Without Image4, do not panic |
| DT platform expert | 0016–0018 | It is the prerequisite for the `arm-io` children to match drivers |

**Step 2: get the root file system (2-3 days)**

| Action | Reference | Our concrete change |
|---|---|---|
| **Add `mockfs` to `FILESYS_BASE`** | 0021 | Our `config/MASTER.arm64.bcm2837` is now `[devfs fifo fs_compression config_protect config_mnt_rootsnap config_fse routefs namedstreams bindfs]`, **without mockfs** |
| **Tolerate a missing `IOBlockStorageDriver`** | 0021 | The `assert(ioblockstoragedriverClass)` in `iokit/Kernel/IOService.cpp:5261` must be removed (with NativeUfs disabled, that class does not exist)|
| **unsealed root** | 0029 | ✅ **completed** (`zzzz-nabu-unsealed-root.patch`)|
| RAM disk as root | 0021/0022 | something like `rd=md0`, or use mockfs directly as root |

**Step 3: display (1-4 weeks, this is the real obstacle)**

| Option | Effort | Result |
|---|---|---|
| **Own `IOCoreSurfaceRoot` + `AppleCLCD`** | 2-4 weeks | Can draw, opens the way to SpringBoard |
| Give up on graphics | 0 | The kernel reaches launchd, but no image is shown |

**Step 4: runtime + peripherals** (stages 3/5, several weeks)

### Option B: Move to 8796, building on ios-nabu (recommended for the "see the image" goal)

| Item | Explanation |
|---|---|
| Benefit | **the 83 patches can be used directly**, same device, same iPadOS 16.6.1, already reaches SpringBoard |
| Cost | Rebuild the build chain (although we have the basis of `build-kernel-8796.yml` and 87 patches)|
| Risk | 1.58 MB of someone else's patches must be understood and maintained |
| Time | **within a week we could see what they have**, instead of several months |

### Option C: Two lines in parallel (the safest)

- **Main line 10063**: keep validating our own kernel (QEMU has reached its limit, the phone reaches IOSurface)
- **Secondary line 8796**: use the ios-nabu patches to quickly get a system **with a visible image**
- Both lines share: the QEMU environment, the CI chain, the probing tools

---

## V. My recommendation

**First steps 1 and 2 of Option A (3-5 days), because they have to be done whichever path we take and their cost is controllable:**

1. **pthread to built-in** (it is wrong now)
2. **add mockfs to `FILESYS_BASE`**
3. **remove `assert(ioblockstoragedriverClass)`**
4. **RAM disk as root**

Once those four things are done, there is a good chance the kernel advances to **`load_init_program`** (looking for `/sbin/launchd`).
At that point, decide between **Option A step 3 (own surface, several weeks) and Option B (move to 8796, one week)**.

**Reason**: the first four things are **the part common to both paths**, and doing them is not wasted work; the IOSurface stretch, on the other hand, is **the fork in the road**,
and it is better to decide after seeing the real result of `load_init_program`.

---

## VI. List that can be executed right away (sorted by cost-benefit)

| # | Action | Reference | Estimate |
|---|---|---|---|
| 1 | Add `mockfs` to `FILESYS_BASE` in `config/MASTER.arm64.bcm2837` | 0021 | 10 minutes |
| 2 | Make the block storage assert in `IOService.cpp` tolerate NULL | 0021 | 10 minutes |
| 3 | Remove pthread from the prelink roots and use the built-in implementation | 0019 | half a day |
| 4 | `vm_kern.c` RNG without depending on corecrypto | 0013 | half a day |
| 5 | Make an unavailable runtime trust cache not panic | 0015 | 2 hours |
| 6 | RAM disk as root, verify that `load_init_program` is reached | 0021/0022 | 1 day |
| 7 | Decision: own surface or move to 8796 | — | — |

---

## VII. Honest assessment

- **With 1-6 done, the kernel probably reaches launchd**, but **no image is shown**
- **Seeing an image** requires the IOSurface stretch, which **cannot be avoided**
- **ios-nabu achieved it with 83 patches and several months**; doing the same work ourselves **will not be faster**
- The only thing that speeds things up noticeably is **Option B (move to 8796 + borrow the patches)**

**Final recommendation**: first 1-6 (the common part, 3-5 days), get the real result of `load_init_program`,
and then decide whether we write the IOSurface stretch ourselves or change versions.
