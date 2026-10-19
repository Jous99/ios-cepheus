# Guía: ejecutar ios-cepheus en el Mi 9 o desde QEMU

Esta guía explica cómo probar el port de iOS (ios-sweet adaptado a cepheus, Xiaomi Mi 9) en el teléfono real y qué se puede hacer desde QEMU.

> **Aviso importante sobre QEMU:** QEMU no emula el SoC del Mi 9 (Qualcomm SM8150). Un kernel compilado para cepheus no arranca en QEMU, porque en cuanto toca el hardware real (UFS, PMIC, GPIO, pantalla) falla. QEMU sirve para comprobar que el build es correcto, probar herramientas y pruebas de humo en arm64, pero **no sirve para validar drivers ni el arranque real**. Esas pruebas solo se pueden hacer en el teléfono.

---

## 1. Requisitos previos

### Hardware
- Xiaomi Mi 9 (cepheus) con batería cargada al menos al 60 %.
- Cable USB de datos (no de solo carga).
- Un PC con Windows, Linux o macOS.

### Software en el PC
- Git.
- GitHub CLI (`gh`): `winget install GitHub.cli` en Windows.
- Android platform-tools (`fastboot` y `adb`).
- Xiaomi Mi Unlock Tool, si el bootloader aún no está desbloqueado.
- Para QEMU: `qemu-system-aarch64` (Linux: `sudo apt install qemu-system-arm`; Windows: instalador oficial de QEMU).


---

## 2. Preparar el repositorio

```bash
git clone https://git.joustech.space/Jous/ios-cepheus.git
cd ios-cepheus
git checkout cepheus-port
git pull origin cepheus-port
```

Comprueba que las dos copias (Forgejo y GitHub) tienen el mismo commit:

```bash
git ls-remote origin cepheus-port
git ls-remote github cepheus-port
```

Si los hashes no coinciden, espera a que el mirror sincronice o pulsa "Synchronize" en la configuración del mirror de Forgejo antes de compilar.

---

## 3. Compilar el kernel con el CI

El build se hace en GitHub Actions (runner macOS), porque xnu necesita el toolchain de Xcode.

1. Abre `Jous99/ios-cepheus` en GitHub → pestaña **Actions**.
2. Elige el workflow **xnu** en la columna izquierda.
3. Pulsa **Run workflow** y usa estos valores:

| Campo | Valor |
|---|---|
| Branch | `cepheus-port` |
| `macos_version` | `13.5` |
| `kernel_config` | `DEVELOPMENT` |
| `machine_config` | `CEPHEUS` |
| `keep_going` | `true` |

4. Espera a que termine. Si falla, descarga el log y busca el primer error:

```bat
gh run list -R Jous99/ios-cepheus --limit 3
gh run view ID_DEL_RUN -R Jous99/ios-cepheus --log-failed > fallo.txt
findstr /n /i "error:" fallo.txt
```

Sustituye `ID_DEL_RUN` por el ID real de la primera columna de `gh run list`.

5. Si compila, descarga los artefactos del run (kernel y, si aplica, el shim) desde la página del run, en la sección **Artifacts**.

---

## 4. Ejecutar en el Mi 9

> **Atención:** desbloquear el bootloader borra todos los datos del teléfono. Haz copia de seguridad antes.

### 4.1 Desbloquear el bootloader (si no lo está)
1. En el teléfono: Ajustes → Acerca del teléfono → pulsa 7 veces en "Versión de MIUI". Activa "Depuración USB" y "Desbloqueo de OEM".
2. Inicia sesión en la cuenta Mi en el teléfono.
3. Con Mi Unlock Tool, desbloquea el bootloader. Espera el periodo de cola que indique la herramienta.

### 4.2 Arrancar el kernel sin instalarlo
Usa siempre el arranque temporal, nunca `fastboot flash` sobre particiones críticas, para poder volver atrás:

```bat
adb reboot bootloader
fastboot devices
fastboot boot RUTA\AL\kernel_o_payload.img
```

El procedimiento exacto (payload, ramdisk, orden de arranque) depende del método de ios-sweet. Consulta el README del repo para ese paso, porque no está automatizado aquí.

### 4.3 Qué mirar en el primer arranque
- Si el teléfono no pasa de la pantalla de fastboot, el problema suele estar en la cabecera o en la configuración de máquina.
- Si arranca pero se reinicia, revisa el log serie o la salida que el kernel deja en la pantalla.
- Las teclas de volumen y encendido deben responder si el driver de `sweet_keys.c` está bien mapeado para cepheus. Si el volumen no responde, el mapeo de GPIO6 del PM8150 es la primera sospecha.

### 4.4 Volver atrás
Basta con reiniciar sin el payload: `fastboot reboot`. Al no haber flasheado nada, el Android original sigue intacto.

---

## 5. Probar desde QEMU

QEMU no ejecuta el kernel del Mi 9. Lo que sí puedes hacer:

### 5.1 Comprobar que el binario es arm64 válido
```bash
file ruta/al/kernel
```

### 5.2 Prueba de humo con la máquina virt
Útil para comprobar que el toolchain, los scripts y el empaquetado funcionan. No valida el port.

```bash
qemu-system-aarch64 -M virt -cpu cortex-a72 -m 2G -nographic -kernel ruta/a/Image
```

Si necesitas una imagen de prueba para `-kernel`, usa un Image de Linux arm64 de tu distribución. El kernel de iOS no se va a comportar bien aquí, y eso es esperado.

### 5.3 Qué esperar
- Un kernel de cepheus en `-M virt` fallará o se quedará colgado en el primer acceso a hardware. Eso **no** indica un fallo del build.
- Lo útil de QEMU es depurar la parte independiente de la plataforma: parsing de cabeceras, scripts de empaquetado y comprobaciones de compilación.

---

## 6. Qué no está probado todavía

- Pantalla, táctil (SE17, FTS, aún sin protocolo implementado).
- USB y RPMh (solo para sweet).
- Batería y carga.
- Sonda de memoria DRAM (necesita el teléfono en fastboot).

Estas partes están marcadas como pendientes en el README del repo.

---

## 7. Checklist rápida

- [ ] Repo en `cepheus-port`, hashes iguales en Forgejo y GitHub.
- [ ] Workflow `xnu` compilado con `CEPHEUS` y `DEVELOPMENT`.
- [ ] Artefactos descargados.
- [ ] Copia de seguridad del teléfono.
- [ ] Bootloader desbloqueado.
- [ ] Arranque temporal con `fastboot boot`, no flash.
- [ ] Log del primer arranque guardado para compararlo en la siguiente iteración.
