# Reference project: mytiantian001/iPadOS-nabu

> Document from the Xiaomi Pad 5 (nabu), translated to English. The Chinese original is in `docs/original-zh/`.

> Source: https://github.com/mytiantian001/iPadOS-nabu
> Noted on 2026-10-22 (during bring-up rounds 6-7 of this repo)
> Purpose: **comparison with a project of the same kind**. It is not a dependency of this repo; it is a list of differences.

## 1. What they achieved (according to their own README)

On the same **Xiaomi Pad 5 / nabu / SM8150-AC**:

| Part | State |
|---|---|
| Boot | Unlocked stock ABL -> `fastboot boot` of their own shim -> XNU |
| CPU | 1 core stable; 8 cores reach userspace |
| Storage | Their own UFS host driver; the iPadOS root is HFS+ on `userdata`, read and write |
| **Userland** | **Real iPad7,3 / iPadOS 16.6.1 (20G81) root and shared cache; launchd and the system daemons work** |
| **SpringBoard** | **SpringBoard, backboardd and AKS start** |
| Display services | `AppleCLCD`, `IOMobileFramebuffer`, `IOSurface` registered; 1600x2560 panel on |
| Buttons / AKS | PMIC PON and GPIO fine; AKS selector fine, keybag completed |
| Logs | 4 MiB **persistent ring** at the end of `userdata`, readable from TWRP |

Unfinished: getting the iPad UI to actually display (backboardd only sends one `SwapEnd` and then `RequestPowerChange(0)` turns the screen off),
GPU acceleration, touch (Novatek NT36523 over SPI).

## 2. Key fact: **they also build their own XNU**

- Kernel base: **xnu-8796 (iOS 16 generation)**, from Apple's open-source distribution.
- It is not "the original iPadOS kernel"; the userland, however, is real iPadOS 16.6.1 binaries.
- Number of patches: **83** (`xnu/patches/0001...0083`).

> This repo's earlier conclusion ("they use the original kernel") was **wrong**; what this section says stands.

## 3. Differences from this repo (UniXNU / xnu-10063.141.1)

| Item | This repo | Them |
|---|---|---|
| Kernel base | **xnu-10063.141.1** (iOS 17 / macOS 14 generation) | **xnu-8796** (iOS 16 generation) |
| Compatible userland | None (10063 is not ABI-compatible with iPadOS 16.6.1) | iPadOS 16.6.1 (20G81) |
| Current progress | The kernel gets inside `kernel_bootstrap()` | SpringBoard / backboardd / AKS |
| Visibility means | Own block + number probe (`nabu_mark`) | `nabu_early` text console + persistent log ring |

**Conclusion:** like it or not, **to run the real iPadOS userland the kernel base has to be from the 8796 generation**.
Even if 10063 worked completely, it could not load the iPadOS 16.6.1 userland.

## 4. Three patches that can be reused directly

### 4.1 `0010-nabu-early-framebuffer-debug.patch`: early text console on the fb

Core mechanism (original comment):
```c
/* start.s maps the splash framebuffer VA=PA as Normal Non-Cacheable memory.
 * Stop using that mapping before arm_vm_init tears down bootstrap TTBR0. */
```

- Already in **`start.s`** the splash framebuffer is mapped as **VA=PA, Normal Non-Cacheable**
  -> writes take effect immediately, **with no cache flush**.
- `nabu_early_putc()` uses `iso_font[256*16]` (8x16 bitmap) to **print text directly**, with
  line scrolling and `\r`/`\n` handling; all state is static, so it can be used inside `panic()`.
- In `arm_vm_init()`, **before** `set_mmu_ttb(invalid_ttep & TTBR_BADDR_MASK)`, `nabu_early_disable()` is called.
- Marker points: `arm_init` entry / after `PE_init_platform` / after `ml_parse_cpu_topology` /
  after `cpu_bootstrap` / after `kernel_startup_bootstrap` / after `cpu_init` / before entering `arm_vm_init`.

**What it means for this repo:** our block probe only conveys "number N";
with text it prints directly "which function it gets stuck in", an order of magnitude more information.

### 4.2 `0012-nabu-keep-debug-console-after-ttbr0.patch`: keep the console after TTBR0

It shows that "the console disappears after switching page tables" is a **common trap** on this route,
not a problem unique to us.

### 4.3 `0047-nabu-persistent-console-log.patch`: persistent ring log

Writes the console output to a 4 MiB ring at the end of `userdata`,
which **is read from TWRP after rebooting**; it completely sidesteps the "nothing visible on screen" problem.

**It is the first thing this repo should copy:** it is more reliable than any on-screen probe.

## 5. Other patches worth comparing (sorted by how likely we are missing them)

| patch | What it is for | Why it matters |
|---|---|---|
| `0004-nabu-machine-config` | Machine configuration | Platform constants |
| `0006-nabu-master-config-open-source-asm-pmap` | Adaptation of the open-source asm/pmap | We also have the 4K pmap series; it must be compared |
| `0011-nabu-physmap-alignment-padding` | physmap alignment padding | Related to VM initialization |
| `0016-nabu-device-tree-platform-expert` | DT -> platform expert | Behavior after `PE_init_platform` |
| `0017-nabu-device-tree-virtual-timer-irq` | Virtual timer IRQ from the DT | **Clock initialization inside `kernel_bootstrap`** |
| `0018-nabu-boot-cpu-driver` | Boot CPU driver | **Same as the previous one** |
| `0013/0014` kmem rng / hmac prng | Remove the corecrypto dependency | Early random numbers |
| `0025/0035/0038` AMFI / entitlements / AKS | Userland signature chain | Essential to reach SpringBoard |
| `0028/0030/0034/0069/0082` UFS series | Own UFS driver | Root mount |
| `0046-nabu-iosurface-iomfb` | IOSurface + IOMobileFramebuffer | Display services |
| `0058/0060/0062/0083` HID / keys / touch / NT36523 | Input | Touch bring-up |

## 6. Recommended actions (by cost-benefit)

1. **First copy `0047`, the persistent ring log:** a one-time investment, and from then on every "cannot see it" problem becomes "read the log".
2. **Then copy the `0010` text console:** in `start.s` create VA=PA Non-Cacheable + `iso_font`.
3. **Seriously consider changing base:** moving the kernel from 10063 to **8796**, lining up directly with the context of their 83 patches,
   is the only realistic path to the userland. Patching further on top of 10063 will never give the iPadOS 16.6.1 userland.
