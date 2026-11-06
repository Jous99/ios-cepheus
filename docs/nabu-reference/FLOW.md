# nabu bring-up flow diagram

Generated: 2026-10-23

## I. Summary of the seven stages (following the official `/porting/bring-up` split)

```
                        ┌─────────────────────────────────────────────┐
                        │  Stage 1  UEFI firmware                     │
                        │  Mu UEFI boots and the framebuffer outputs  │
                        └────────────────────┬────────────────────────┘
                                             │ ✅ passed
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 2  UniXNU menu                       │
                        │  Reads unixnu.toml and lists the entries    │
                        └────────────────────┬────────────────────────┘
                                             │ ✅ passed
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 3  Payload                           │
                        │  kernel.macho + .adt in place               │
                        └────────────────────┬────────────────────────┘
                                             │ ✅ passed
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 4  DarwinBoot                        │
                        │ Checks kernel/ADT/trustcache → ExitBootServices│
                        └────────────────────┬────────────────────────┘
                                             │ ✅ passed (the RAMDisk node is the key)
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 5  Kernel entry → platform expert    │
                        │  Logs, probes, IOKit initialization         │
                        └────────────────────┬────────────────────────┘
                                             │ 🟡 in progress
                                             │ checkpoint 123
                                             │ stuck at IOSurface
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 6  Storage and root                  │
                        │  block driver → volume → root → launchd     │
                        └────────────────────┬────────────────────────┘
                                             │ ⬜ not started  ← Route A
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 7  User space                        │
                        │  launchd → SpringBoard → desktop            │
                        └─────────────────────────────────────────────┘
                                             ▲
                                             │ ⬜ long term  ← Route B is its prerequisite
```

## II. Inside Stage 5: where we are stopped

```
arm_init
   │
   ├── nabu_mark_map (fb mapping) ✅
   │      └── UART tee: works in QEMU / disabled on the phone (0x9000000 on SM8150 is another register) ✅
   │
   ├── STARTUP loop (checkpoint 50 is the loop entry)
   │      │
   │      ├── EARLY_BOOT / ulock_initialize        ✅ checkpoint 123
   │      ├── ml_processor_register                ✅
   │      ├── corecrypto POST (all PASSED)         ✅
   │      ├── 32 SKYWALK self-tests                ✅
   │      ├── bsd_autoconf → kminit                ✅
   │      └── IOsurfaceRoot::installMemoryRegions  🛑 stopped here
   │
   └── (should come next) setconf → vfs_mountroot → load_init_program
```

## III. The two interpretations of the current blocker

```
                     stopped at these two lines:
    IOsurfaceRoot::installMemoryRegions()
    IOSurface disallowing global lookups
                              │
              ┌───────────────┴───────────────┐
              │                               │
     ┌────────▼─────────┐          ┌──────────▼──────────┐
     │ A: dead end      │          │ B: log cut off      │
     │                  │          │                     │
     │ Closed IOSurface │          │ The kernel keeps    │
     │ kext does not run│          │ running, but there  │
     │ on non-Apple     │          │ is no kprintf to    │
     │ platforms: stops │          │ the fb afterwards   │
     └────────┬─────────┘          └──────────┬──────────┘
              │                               │
     it must be replaced               needs finer probes
     (own surface)                     or confirming with a serial log
              │                               │
        ← Route B work                     ← the first thing to rule out
```

**Important**: **interpretation B has not been ruled out yet.** We always assumed it was a dead end, but we never verified whether the kernel kept running.
How to verify it: add probes in the following steps, or a kprintf near `setconf`.

## IV. Relation between the two routes

```
                    Current baseline (checkpoint 123)
                              │
              ┌───────────────┴───────────────┐
              │                               │
    ┌─────────▼──────────┐        ┌───────────▼──────────┐
    │  Route A           │        │  Route B             │
    │  Root (files)      │        │  Display (IOSurface) │
    ├────────────────────┤        ├──────────────────────┤
    │ 1. userdata image  │        │ 1. Create IOCoreSurfaceRoot│
    │   (OS+SystemOS)    │        │ 2. Create AppleCLCD  │
    │ 2. Root UUID       │        │ 3. Reg. KernelConfig │
    │ 3. Flash userdata  │        │ 4. Bring up IOMFB    │
    │ 4. Mount root      │        │                      │
    │ 5. launchd starts  │        │                      │
    ├────────────────────┤        ├──────────────────────┤
    │ Time: 1-2 weeks    │        │ Time: 3-4 weeks      │
    │ Risk: low          │        │ Risk: high (board)   │
    └─────────┬──────────┘        └───────────┬──────────┘
              │                               │
              └───────────────┬───────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Stage 7 Userland  │
                    │  SpringBoard       │
                    └────────────────────┘
```

**The two routes do not contradict each other**: A answers "whether the system can boot", B answers "whether it can be seen".
A's prerequisite is ruling out "interpretation B" above: if the kernel is actually still running, A leads straight to Stage 6.

## V. How to develop in parallel

```
  main branch (current baseline, always buildable and flashable)
    │
    ├── feature/stage6-userdata      ← Route A
    │     · board.toml [userdata] and root_match_volume_uuid
    │     · the CI adds the build userdata step (OS/SystemOS must be downloaded, several GB)
    │     · do not touch the 9 defconfig switches
    │
    └── feature/stage5-iosurface     ← Route B
          · iokit/Kernel/arm/NabuSurface.cpp + NabuFramebuffer.cpp
          · register IOCoreSurfaceRoot / AppleCLCD in patches/xnu
          · entries must be added to [kernel] archives
          · do not touch board.toml [userdata]

  Rules:
    1. main always stays in the flashable checkpoint 123 state
    2. each branch has its own CI and its own flashing, without interfering
    3. if a branch fails 2 builds in a row → go back to main and reassess
    4. do not share defconfig changes (that is what burned a dozen rounds last time)
```
