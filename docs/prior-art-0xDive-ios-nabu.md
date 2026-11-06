
# Comparison with prior work: 0xDive/ios-nabu

> Document from the Xiaomi Pad 5 (nabu), translated to English. The Chinese original is in `docs/original-zh/`.

Researched on 2026-10-21. Repository <https://github.com/0xDive/ios-nabu>
(created on 2026-10-19, Python, 12 open PRs/issues, the latest #34).

## They follow a completely different path

| Aspect | 0xDive/ios-nabu | This project (unixnu-nabu) |
|---|---|---|
| Boot layer | **U-Boot v2026.07** (Qualcomm phone U-Boot, pin `ece349ad...`) | **Mu-Silicium EDK2** + UniXNU |
| Current goal | Solve the **log channel** first (USB gadget ACM console / `fastboot oem console`) | Boot XNU directly |
| Measured progress | Stuck on the firmware / USB stack bring-up, **no XNU boot result at all** | **The XNU kernel already starts running** (`DARWINBOOT: hand-off to the kernel`) |

## Their specific blockers (PR #30-#34)

The goal is to get the Qualcomm USB stack working inside EDK2 so USB can be used as a serial port:

- With the `PciHostBridge` PE32, `LoadImage` succeeds, but
  `EFI_PCI_ROOT_BRIDGE_IO` / `EFI_PCI_IO` / `EFI_USB2_HC` / `EFI_USB_IO` **are all missing**.
- Based on the old open-source `XhciPciEmulation.c`, they believe `QCOM_USB_CONFIG_PROTOCOL` must be bound
  (GUID `E722B03F-B250-42CE-8EBD-5BD51812D037`, confirmed to exist in their pinned SM8150 binary),
  and `EFI_USB_INIT` with GUID `2DA15AC7-4909-4C4C-B8C3-A742195EA46E`.
- Changing the DXE order (`pci-first` / `usb-stack-first`) causes a **synchronous exception before the EFI Shell**:
  `ELR 0x13FE0C440`, `ESR 0x02000000` (EC=0), `FAR=0`
  -> symbolized offline to `ArmCpuDxe::UpdateRegionMappingRecursive()`,
  with `DxeCore::SetUefiImageMemoryAttributes()` / `ProtectUefiImage()` on the stack.
- They tried `PcdImageProtectionPolicy = 0` to disable image protection and locate the failure; it still does not work.
- Stages 8-11 are mostly "host-only audits" (building U-Boot, nabu DTS, PM8150B Type-C/PHY);
  all artifacts are marked `safe_to_boot = false`, and **they have never published a bootable image**.

## Three useful facts for us

### 1. The EDK2 image protection trap (write it down)

The `ArmCpuDxe::UpdateRegionMappingRecursive` + `PcdImageProtectionPolicy` combination
**has not affected us** when touching the fdf / APRIORI / FD size, but if the image layout or permissions
change, it could cause the same kind of early MMU failure. To investigate it:
`PcdImageProtectionPolicy = 0` as a single-variable comparison.

### 2. The public nabu DTS (ready-made material for the PMGR phase)

```
repo:   https://github.com/SeimoDev/linux-xiaomi-nabu
commit: 4e6d08bb1b467c721e19cd693e4ec7388d982d73
file:   arch/arm64/boot/dts/qcom/sm8150-xiaomi-nabu.dts
compat: "xiaomi,nabu", "qcom,sm8150"
```

The PMGR / UFS / clock / regulator nodes are **copied directly from this source**; it is much faster than
reverse-engineering ApplePMGR.
Note: it needs the accompanying `sm8150-wcd9340.dtsi`; it is not in the tree that ships with U-Boot.

### 3. USB / PHY hardware parameters (for writing the USB and charging drivers later)

| Item | Value |
|---|---|
| USB1 wrapper | `0x0A6F8800` (OTG, High-Speed) |
| USB1 HS PHY | `0x088E2000` |
| USB2 controller | `0x0A800000` (host, **SuperSpeed Plus**) |
| PHY supply | 0.880 V (PLL) / 1.800 V (digital) / 3.072 V (analog) |
| Type-C | `qcom,pm8150b-typec` + `qcom,pm8150b-vbus-reg` |
| Measured on Android | `/sys/class/udc/a600000.dwc3`: `state=configured`, `maximum_speed=high-speed`, `is_otg=1` |

## Conclusion

**We are not following their route.** To get logs they detoured to U-Boot and got stuck at the firmware layer;
this project already has usable log means (on-screen `Print` and, if needed, UART at 115200)
and has already passed a point they never reached (kernel execution).

Only the three **informative** facts above are reused, above all the public nabu DTS, which serves
PMGR directly.
