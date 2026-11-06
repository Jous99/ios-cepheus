# Distilled from the public nabu device tree (PMGR / storage / clocks / PMIC)

> Document from the Xiaomi Pad 5 (nabu), translated to English. The Chinese original is in `docs/original-zh/`.
> It serves as a reference for SM8150; the Mi 9 (cepheus) values must be checked separately.

Source (pinned):
```
https://github.com/SeimoDev/linux-xiaomi-nabu
commit 4e6d08bb1b467c721e19cd693e4ec7388d982d73
file   arch/arm64/boot/dts/qcom/sm8150-xiaomi-nabu.dts
```
> The board dts is overlay-style; the `gcc` / `ufs*` / `cpus` / `pmic` / RPMh nodes are in
> `sm8150.dtsi` and `pm8150{,b,l}.dtsi` from the same commit.

Board identification: `compatible = "xiaomi,nabu", "qcom,sm8150"`, `model = "Xiaomi Pad 5"`,
`chassis-type = "tablet"`.

---

## 1. RPMh / power management (**the most important part**)

| Node | compatible | Address | Explanation |
|---|---|---|---|
| `apps_rsc: rsc@18200000` | `qcom,rpmh-rsc` | **`0x18200000 +0x10000`**<br>**`0x18210000 +0x10000`**<br>**`0x18220000 +0x10000`** | **The RPMh RSC entity, three banks** |
| `rpmhpd: power-controller` | `qcom,sm8150-rpmhpd` | no reg (child of `apps_rsc`) | Power domains |
| `rpmhcc: clock-controller` | `qcom,sm8150-rpmh-clk` | no reg (child of `apps_rsc`) | RPMh clocks |
| `aop_cmd_db: memory@85f20000` | `qcom,cmd-db` | `0x85f20000 +0x20000` | cmd-db |
| `smem` | `qcom,smem` | `memory-region = <&smem_mem>` -> `0x86000000 +0x200000` | SMEM |
| `apss_shared: mailbox@17c00000` | `qcom,sm8150-apss-shared` | `0x17c00000 +0x1000` | **apss_shared mailbox (not RPMh)** |
| `spmi_bus: spmi@c440000` | `qcom,spmi-pmic-arb` | `0xc440000 +0x1100`, `0xc600000 +0x2000000`, `0xe600000 +0x100000`, `0xe700000 +0xa0000`, `0xc40a000 +0x26000` | SPMI arbiter |
| `pdc: interrupt-controller@b220000` | `qcom,sm8150-pdc` | `0xb220000 +0x30000` | PDC |
| `osm_l3: interconnect@18321000` | `qcom,sm8150-osm-l3` | `0x18321000 +0x1400` | OSM L3 |

> **Correction:** SM8150 has neither a `qcom,ipcc` node nor the legacy `qcom,rpm`.
> `0x17c00000` used to be taken for RPMh, and that was a mistake: it is the apss_shared mailbox.
> **RPMh must be accessed in the `0x18200000` area.**

List of interconnect nodes (they may be useful when touching bandwidths/clocks):

| Node | compatible | Address |
|---|---|---|
| config_noc | `qcom,sm8150-config-noc` | `0x1500000 +0x7400` |
| system_noc | `qcom,sm8150-system-noc` | `0x1620000 +0x19400` |
| mc_virt | `qcom,sm8150-mc-virt` | `0x163a000 +0x1000` |
| aggre1_noc | `qcom,sm8150-aggre1-noc` | `0x16e0000 +0xd080` |
| aggre2_noc | `qcom,sm8150-aggre2-noc` | `0x1700000 +0x20000` |
| compute_noc | `qcom,sm8150-compute-noc` | `0x1720000 +0x7000` |
| mmss_noc | `qcom,sm8150-mmss-noc` | `0x1740000 +0x1c100` |
| dc_noc | `qcom,sm8150-dc-noc` | `0x9160000 +0x3200` |
| gem_noc | `qcom,sm8150-gem-noc` | `0x9680000 +0x3e200` |
| camnoc_virt | `qcom,sm8150-camnoc-virt` | `0xac00000 +0x1000` |

## 2. GCC (clocks / reset / GDSC)

| Node | compatible | reg | cells |
|---|---|---|---|
| `gcc: clock-controller@100000` | `qcom,gcc-sm8150` | `0x100000 +0x1f0000` | `#clock-cells = <1>`, `#reset-cells = <1>`, `#power-domain-cells = <1>` |

## 3. UFS (corresponds to `NativeUfs`)

| Node | compatible | reg |
|---|---|---|
| `ufs_mem_hc: ufshc@1d84000` | `qcom,sm8150-ufshc`, `qcom,ufshc`, `jedec,ufs-2.0` | `0x1d84000 +0x2500` (std), `0x1d90000 +0x8000` (ice) |
| `ufs_mem_phy: phy@1d87000` | `qcom,sm8150-qmp-ufs-phy` | `0x1d87000 +0x1000` |

`status = "okay"`; `lanes-per-direction = <2>`; boot device `soc@0/1d84000.ufshc`.

## 4. UFS power supplies (the power driver must follow this)

| supply | Regulator | PMIC rail | Voltage | Current limit |
|---|---|---|---|---|
| `vcc-supply` | `vreg_l10a_2p5` | pm8150 ldo10 | 2504-2950 mV | 750 mA |
| `vccq-supply` | `vreg_l9a_1p2` | pm8150 ldo9 | 1200 mV | 700 mA |
| `vccq2-supply` | `vreg_s4a_1p8` | pm8150 S4 (fixed) | 1800 mV | 750 mA |
| `vdda-phy-supply` | `vreg_l5a_0p8` | pm8150 ldo5 | 880 mV | 90.2 mA |
| `vdda-pll-supply` | `vreg_l3c_1p2` | pm8150l ldo3 | 1200 mV | 19 mA |

PMIC nodes (SPMI USID):

| PMIC | Node | compatible | reg |
|---|---|---|---|
| pm8150 | `pmic@0` | `qcom,pm8150`, `qcom,spmi-pmic` | `0x0` |
| pm8150b | `pmic@2` | `qcom,pm8150b`, `qcom,spmi-pmic` | `0x2` |
| pm8150l | `pmic@4` | `qcom,pm8150l`, `qcom,spmi-pmic` | `0x4` |
| pm8009 | **does not exist** (board comment: not present) | - | - |

RPMh regulator groups (under `apps_rsc`): `pm8150-rpmh-regulators` (`pmic-id = "a"`),
`pm8150l-rpmh-regulators` (`pmic-id = "c"`).

## 5. CPU (matches the ADT `cpu-regs`)

`cpu@0/100/200/300/400/500/600/700`, `reg = <0x0 0xN00>`,
`compatible = "qcom,kryo485"`, `enable-method = "psci"`,
idle uses `domain-idle-states` (`/cpus/idle-states`, `entry-method = "psci"`).
The board adds `cpu7_opp21 = 2956800000 Hz`.

> It matches our ADT's `--cpu-regs "0,0x100,...,0x700"` **exactly**; nothing needs to change.

---

## Direct conclusions for PMGR

1. **The RPMh access target moves to `0x18200000`** (3 banks), not `0x17c00000`.
2. cmd-db `0x85f20000` and SMEM `0x86000000` stay as they were.
3. Do not guess voltages or clocks: the five UFS supplies and the PMIC USIDs are taken from this table.
4. `rpmhpd` / `rpmhcc` are **child nodes** of `apps_rsc`: power domains and clocks are
   controlled through the RPMh command channel (very different from Apple's MMIO PMGR).
