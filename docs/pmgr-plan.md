# PMGR port plan (nabu / SM8150)

> Document from the Xiaomi Pad 5 (nabu), translated to English. The Chinese original is in `docs/original-zh/`.

The kernel already starts running on nabu (`DARWINBOOT: hand-off to the kernel`).
The next thing that will panic first, almost certainly, is **platform power management (PMGR)**:
XNU accesses the AON / PMGR registers through the `ApplePMGR` family before `bsd_init`.

## 0. First things first: a panic log

Without a log there is nowhere to start. There are two ways to get one (the first is better):

1. **Screen:** the kernel now drives the screen, so the panic will show up there -> record it on video or with burst photos.
2. **UART:** serial port at 115200 (on SM8150 it is usually `ttyMSM0`); the configuration carries `serial=3`.
   With a USB-TTL adapter on the board's test points you get the full log.

In the log, look above all for:
- The first line of the `panic(...)` and the call stack.
- Any kext name with `ApplePMGR` / `AppleARMIODevice` / `platform-power`.
- The last kext loaded successfully (it tells you which driver was the one that failed).

## 1. What SM8150 really looks like (completely different from Apple)

> Details in `docs/nabu-dts-extract.md`: this table comes from the public nabu DTS, with the addresses checked.

| Layer | Apple | SM8150 |
|---|---|---|
| Register access | MMIO + AON mailbox | **IPC (CmdDb)** messages, RPMh command TCS, SPMI |
| Power domains | PMGR, one huge block | RPMh (RSC + TCS), NPA, PDC |
| Clocks | PMGR clock gates | GCC (`0x100000`) |

Confirmed base addresses:

```
RPMh RSC  0x18200000  (0x10000) x3 banks   <-- the real RPMh entry point
IPCC/apss_shared 0x17c00000  (0x1000)  <-- only a mailbox, not RPMh
cmd-db    0x85f20000  (0x20000)
SPMI      0x0c440000
watchdog  0x17c10000
timer     0x17c20000
SMEM      0x86000000
GCC       0x100000    (see the offset table in scripts/GccUfs-nabu.h)
```

Key RPMh DRV registers (SM8150):

```
RSC_DRV_CTL_TCS_DATA_HI   0x38
RSC_DRV_CTL_TCS_DATA_LO   0x40
TCS_AMC_MODE_ENABLE       BIT(16)
```

## 2. The ApplePMGR surface (reverse-engineering result)

```
ApplePMGR sizeof = 0x4b8a8
vtable slot 177..340   (164 slots must be implemented)
slot 320  readAon()
slot 321  writeAon(uint64_t)
```

Strategy: **do not write all 164 at once.** First get `readAon/writeAon` and the initialization path working;
give the remaining slots a safe empty implementation (return 0 / do nothing) and fill them in one by one, guided by the panic log.
This is the same as what sheng does: `sheng-platform-power.patch` only adds a `sheng_pmgr_run()` in `bsd_init.c`.

## 2.5 Minimal RPMh read path (goal of the next code)

```
In cmd-db(0x85f20000), look up the TCS base by "active"/"wake"/"sleep"
        |
Build a 16-byte AMC command: { msg_id, addr, data, wait | cmd<<28 }
        |
Write the bank + RSC_DRV_CTL_TCS_DATA_HI(0x38) / LO(0x40), and set TCS_AMC_MODE_ENABLE(BIT16)
        |
Wait for the DRV to complete (or for the ack channel in SMEM)
        |
Read data back -> this is what XNU wants: "power domain / voltage / clock state"
```

Success is not "it does not hang", but **being able to print real voltage/clock values other than 0**.

## 3. Implementation order

1. Skeleton of `kits/nabu/NabuPlatformPower.cpp` (already included in this delivery).
2. `build-nabu-platform-power.py`: build the skeleton as a kit and inject it into UniXNU's driver list.
3. `nabu-platform-power.patch`: mirror of `sheng-platform-power.patch`, adding `nabu_pmgr_run()` in `bsd_init.c`.
4. The first time, implement only:
   - `init()`: detect IPCC / cmd-db / SMEM and print the bases and versions.
   - `readAon/writeAon`: first a minimal loop of **cmd-db lookup + RPMh TCS write**;
     if it fails, return 0 instead of hanging.
5. Capture the panic -> fill in the next slot -> repeat.

## 4. How to tell whether it "really works"

The criterion is not "there is no panic", but:
- Being able to print real voltage/clock values read from RPMh (not 0).
- The UFS driver enumerating partitions inside XNU (`NativeUfs` is already in the kernel).
- Reaching `bsd_init` and starting to load kexts.

## 5. Risks

- The RPMh TCSs are a **shared resource**: a wrong write can power off or hang the whole device (it recovers with a long press of the power button).
- Before each experiment, make sure the `cust` payload is intact and can be reflashed at any time.
- Do not touch `abl`/`xbl`/`bootloader`.
