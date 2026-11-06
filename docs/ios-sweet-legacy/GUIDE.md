# Guide: running ios-cepheus on the Mi 9 or from QEMU

This guide explains how to test the iOS port (ios-sweet adapted to cepheus, Xiaomi Mi 9) on the real phone and what can be done from QEMU.

> **Important note about QEMU:** QEMU does not emulate the Mi 9 SoC (Qualcomm SM8150). A kernel built for cepheus does not boot in QEMU, because it fails as soon as it touches the real hardware (UFS, PMIC, GPIO, display). QEMU is useful to check that the build is correct, to test tools and for arm64 smoke tests, but **it cannot validate drivers or the real boot**. Those tests can only be done on the phone.

---

## 1. Prerequisites

### Hardware
- Xiaomi Mi 9 (cepheus) with the battery charged to at least 60 %.
- USB data cable (not a charge-only one).
- A PC with Windows, Linux or macOS.

### Software on the PC
- Git.
- GitHub CLI (`gh`): `winget install GitHub.cli` on Windows.
- Android platform-tools (`fastboot` and `adb`).
- Xiaomi Mi Unlock Tool, if the bootloader is not unlocked yet.
- For QEMU: `qemu-system-aarch64` (Linux: `sudo apt install qemu-system-arm`; Windows: official QEMU installer).


---

## 2. Prepare the repository

```bash
git clone https://github.com/Jous99/ios-cepheus.git
cd ios-cepheus
git checkout cepheus-port
git pull origin cepheus-port
```

Check that both copies (Forgejo and GitHub) have the same commit:

```bash
git ls-remote origin cepheus-port
git ls-remote github cepheus-port
```

If the hashes do not match, wait for the mirror to sync or press "Synchronize" in the Forgejo mirror settings before building.

---

## 3. Build the kernel with the CI

The build runs on GitHub Actions (macOS runner), because xnu needs the Xcode toolchain.

1. Open `Jous99/ios-cepheus` on GitHub → **Actions** tab.
2. Choose the **xnu** workflow in the left column.
3. Press **Run workflow** and use these values:

| Field | Value |
|---|---|
| Branch | `cepheus-port` |
| `macos_version` | `13.5` |
| `kernel_config` | `DEVELOPMENT` |
| `machine_config` | `CEPHEUS` |
| `keep_going` | `true` |

4. Wait for it to finish. If it fails, download the log and look for the first error:

```bat
gh run list -R Jous99/ios-cepheus --limit 3
gh run view ID_DEL_RUN -R Jous99/ios-cepheus --log-failed > fallo.txt
findstr /n /i "error:" fallo.txt
```

Replace `ID_DEL_RUN` with the real ID from the first column of `gh run list`.

5. If it builds, download the run artifacts (kernel and, if applicable, the shim) from the run page, in the **Artifacts** section.

---

## 4. Running on the Mi 9

> **Warning:** unlocking the bootloader erases all data on the phone. Make a backup first.

### 4.1 Unlock the bootloader (if it is not unlocked)
1. On the phone: Settings → About phone → tap "MIUI version" 7 times. Enable "USB debugging" and "OEM unlocking".
2. Sign in to the Mi account on the phone.
3. Unlock the bootloader with Mi Unlock Tool. Wait for the queue period the tool indicates.

### 4.2 Boot the kernel without installing it
Always use the temporary boot, never `fastboot flash` on critical partitions, so you can go back:

```bat
adb reboot bootloader
fastboot devices
fastboot boot RUTA\AL\kernel_o_payload.img
```

The exact procedure (payload, ramdisk, boot order) depends on the ios-sweet method. See the repo README for that step, because it is not automated here.

### 4.3 What to look at on the first boot
- If the phone does not get past the fastboot screen, the problem is usually in the header or in the machine configuration.
- If it boots but reboots, check the serial log or the output the kernel leaves on the screen.
- The volume and power keys should respond if the `sweet_keys.c` driver is mapped correctly for cepheus. If volume does not respond, the PM8150 GPIO6 mapping is the first suspect.

### 4.4 Going back
Just reboot without the payload: `fastboot reboot`. Since nothing was flashed, the original Android is still intact.

---

## 5. Testing from QEMU

QEMU does not run the Mi 9 kernel. What you can do:

### 5.1 Check that the binary is valid arm64
```bash
file ruta/al/kernel
```

### 5.2 Smoke test with the virt machine
Useful to check that the toolchain, the scripts and the packaging work. It does not validate the port.

```bash
qemu-system-aarch64 -M virt -cpu cortex-a72 -m 2G -nographic -kernel ruta/a/Image
```

If you need a test image for `-kernel`, use an arm64 Linux Image from your distribution. The iOS kernel will not behave well here, and that is expected.

### 5.3 What to expect
- A cepheus kernel on `-M virt` will fail or hang on the first hardware access. That does **not** indicate a build failure.
- What QEMU is useful for is debugging the platform-independent part: header parsing, packaging scripts and build checks.

---

## 6. What is not tested yet

- Display, touch (SE17, FTS, protocol not implemented yet).
- USB and RPMh (sweet only).
- Battery and charging.
- DRAM memory probe (needs the phone in fastboot).

These parts are marked as pending in the repo README.

---

## 7. Quick checklist

- [ ] Repo on `cepheus-port`, same hashes on Forgejo and GitHub.
- [ ] `xnu` workflow built with `CEPHEUS` and `DEVELOPMENT`.
- [ ] Artifacts downloaded.
- [ ] Phone backup.
- [ ] Bootloader unlocked.
- [ ] Temporary boot with `fastboot boot`, no flash.
- [ ] First boot log saved to compare it in the next iteration.
