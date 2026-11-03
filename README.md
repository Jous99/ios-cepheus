# ios-cepheus

**Port de iOS/XNU (xnu-8796, iOS 16) al Xiaomi Mi 9 (`cepheus`, Snapdragon 855 / SM8150).**

> **Estado (02/11/2026): iOS 16.7.16 arranca en el Mi 9 y llega al inicio con iconos.** Se abre Ajustes, los botones llegan a iOS y el
> táctil físico entrega toques (el primero se confirmó en el log). Sin GPU: iOS dibuja por CPU. Sin Wi-Fi, audio, batería ni sensores.
> Detalle del último tramo en `docs/progreso-2026-11-02.md`. La GPU (Adreno 640) vive en el repo aparte `ios-cepheus-gpu`.
> Lee `MIGRATION.md` antes de tocar nada. Para el estado detallado, mira `STATUS.md` y `TODO-MEASURE.md`.

## Cadena de arranque

```
Android boot image -> BootShim -> Mu-Silicium UEFI -> DarwinBoot -> XNU
```

Sustituye al shim propio de ios-sweet (guardado en `legacy/sweet-shim/`).

## Hardware de cepheus

| Componente | Cepheus |
| --- | --- |
| SoC | SM8150, 1+3+4 núcleos |
| PMIC | PM8150 / PM8150B / PM8150L |
| Pantalla | 1080x2340, panel `SS NOTCH FHD EA8074` (modo comando) |
| Táctil | STMicro FTS, I²C `0x49`, bus GENI SE17 (`i2c@c8c000`) |
| Botones | Volumen y encendido vía PM8150; volumen+ = GPIO6, SID 0 (parche `0084`, sin verificar en el teléfono) |
| UFS | `ufshc@1d84000` |
| GIC-v3 | GICD `0x17a00000`, GICR `0x17a60000` |

## Checklist

### Hecho
- [x] Hardware de cepheus identificado: SM8150, PM8150, táctil ST FTS (I²C `0x49`, SDA/SCL en gpio55/gpio56), panel 1080x2340
- [x] Direcciones de GIC y UFS confirmadas (coinciden con sweet)
- [x] dtb base SM8150 v2 extraído de `boot.img`; overlay CEPHEUS extraído de `dtbo.img`
- [x] Generador de ADT para cepheus (`scripts/make-cepheus-adt.py`) e identidad de iPhone X (`scripts/adt-edit.py`: `/product` real del D22AP)
- [x] Migración a la base UniXNU-cepheus (2026-10-25): la serie de parches aplica sobre xnu-8796.141.3
- [x] Los `.gitignore` excluyen imágenes, firmware y copias de seguridad

### Fase 0: Preparación del teléfono
- [x] Copia de seguridad de `boot`, `dtbo`, `vbmeta`, `persist`, `modemst1`, `modemst2`, `fsg` y `fsc`
- [x] Bootloader desbloqueado con Mi Unlock
- [x] Probar `fastboot boot` con un boot.img de Android sin modificar

### Fase 1: Arranque y consola
- [x] CI del kernel xnu-8796 compilando (`build-kernel-8796.yml`; artefacto `xnu-8796-kernel` con `out/kernel.development.cepheus`)
- [x] Imagen UEFI (`cepheus-xnu.img`) compilada y arrancando con `fastboot boot`
- [x] **Hito 1:** el kernel arranca desde la partición `cust`
- [x] Log en vivo por USB (CDC-ECM, UDP 5140) con `cepheususb=2`

### Fase 2: Almacenamiento y userland
- [x] Userland de iPhone X 16.7.16 (20H392), raíz HFS+ `iOSRoot` en `userdata`
- [x] Flasheo de `userdata` troceado con `simg2simg` (el `fastboot` de Windows corrompe a partir de 4 GiB): `scripts/flash-pieces.py` y `verify-simg2.py`
- [x] **Hito 2:** launchd y el userland arrancan; SpringBoard con identidad de iPhone X

### Fase 3: Entrada
- [x] Botones: encendido, volumen− y volumen+ llegan a iOS (parche `0095`)
- [x] Táctil ST FTS: I²C por GPIO (el SE17 es solo GPI-DMA); protocolo de la generación nueva: cola con `0x86`, eventos `13/23/33`, escaneo `A0 00 FF` (parches `0097` a `0108`)
- [x] Entrada desde el PC por UDP, puerto 5141 (`0106`; `scripts/phone-touch.py`)
- [x] Consola de depuración del chip táctil por UDP (`0107`; `scripts/ts-console.py` y `scripts/ts-poll.py`)
- [x] **Hito 3 (parcial):** SpringBoard llega al inicio, abre Ajustes y los toques físicos llegan a iOS (`CEPHEUS HID: touch` en el log)
- [ ] Validar el uso prolongado con el dedo: escala de coordenadas y evento de «levantar» (`33`, supuesto por el patrón)

### Fase 4: Extras
- [x] USB ECM para leer logs por red
- [x] `0110` verificado (02/11): tras `usbipd detach`/`attach` el dispositivo reenumera y la red vuelve (hay que volver a poner la IP si no la pone `sweet-usbnet.sh`)
- [ ] Fecha y hora (iOS arranca el 31 de diciembre: no hay RTC)
- [ ] Red de iOS por el cable USB (hoy solo la usa el log)
- [ ] Panel en modo comando (sin DSC)
- [ ] Wi-Fi, audio, batería y sensores

### Fase 5: GPU (Adreno 640), en `ios-cepheus-gpu`
- [x] Firmware identificado: `a630_sqe.fw`, `a640_gmu.bin` y `sm8150/a640_zap.mbn` (linux-firmware, redistribuibles; no se suben a git)
- [x] Mapa de relojes y dominios: gpucc `0x2c90000`, GDSC CX `0x106c`, GX `0x100c`
- [x] Consola de registros de solo lectura por UDP (`0109`)
- [x] `0111` verificado (02/11): el `survey` completo ya no hace panic; la GPU está apagada (inventario G0 en `ios-cepheus-gpu`)
- [x] G1 (03/11): dominio CX y relojes del GMU encendidos; registros del GMU legibles (parche `0112`)
- [ ] G2 SMMU del GMU y su firmware; G3 HFI y GX; G4 SQE y zap (TrustZone); G5 orden mínima
- [ ] Que iOS use esa GPU: sin garantía (AdrenoMetal está atado al ABI de iPadOS 17.7.11)

### Decisiones pendientes
- [x] iOS puede ocupar `userdata` (aprobado el 2026-10-15); confirmar cada paso destructivo antes de ejecutarlo
- [ ] Dual boot: aparcado, se retoma más adelante
- [ ] Licencia del repo de la GPU

## Estructura

| Ruta | Contenido |
| --- | --- |
| `board.toml` | Descripción de la placa (**ver aviso de medidas en `MIGRATION.md`**) |
| `xnu-8796/patches/` | Serie de parches que aplica el CI (0001-0082 y 0084-0112) |
| `xnu-8796/patches-extra/` | Parches de debug tuyos, portados; **no** se aplican por defecto |
| `uefi/`, `docs/uefi-cepheus.md` | Parche de Mu-Silicium (`cepheusPkg` + UniXNU/DarwinBoot) y receta de construcción |
| `xnu-8796/patches-disabled/` | Parches desactivados a propósito (hardware que la Mi 9 no tiene) |
| `scripts/`, `kits/`, `configs/` | ADT, payload, plataforma y defconfig |
| `scripts/phone-touch.py`, `ts-console.py`, `ts-poll.py` | Herramientas del PC: tocar iOS y depurar el chip táctil por UDP |
| `docs/progreso-*.md` | Diario de progreso por tramos |
| `.github/workflows/` | CI (`build-kernel-8796.yml` es el que corresponde a xnu-8796) |
| `STATUS.md`, `TODO-MEASURE.md` | Estado y lista de mediciones (traducidos) |
| `docs/` | Notas técnicas en español; `docs/original-zh/` guarda los originales en chino |
| `docs/ios-sweet-legacy/` | Tu bitácora completa del port anterior |
| `legacy/` | Tu shim, tus herramientas y tus parches propios anteriores |

`docs/nabu-reference/` son notas históricas de la Pad 5, también traducidas (el texto que ya estaba en inglés y los comandos se dejaron tal cual).

## Trampas conocidas de SM8150 (de UniXNU/nabu)

- ramdisk utilizable entre 32 y 64 MB; cabecera de boot `header_version=1`, `page_size=2048`.
- El volumen de firmware (FVMAIN) admite 8-10 MB: el kernel va por la partición `cust`.
- `DarwinBoot` debe ser el primer DXE de `APRIORI.inc`.
- El ADT no lleva marcador de RAMDisk salvo que se dé un initrd.
- `build-libpthread-kernel.py` debe estar en `archives`, o hay panic de pthread.
- "El log se para" no significa "el kernel se paró": usa `boot-progress=2` para ver puntos de control.
- Cable USB malo: la imagen de 96 MB da `Load Error`.
- `fastboot` de Windows corrompe imágenes sparse a partir de 4 GiB: trocear con `simg2simg` y flashear con `scripts/flash-pieces.py`.
- El log en vivo solo recoge lo que se imprime con el PC ya con IP: arranca `sweet-usbnet.sh` antes de `fastboot boot`.
- El driver USB heredado perdía la red al reenumerar el dispositivo (cualquier `usbipd detach`/`attach`); arreglo `0110`, verificado.
- El SE17 del táctil es solo GPI-DMA (`GENI_IF_DISABLE_RO` queda en 1): el I²C va por GPIO.
- Una lectura de registro fuera de la ventana mapeada es un fallo de acceso del kernel (panic): comprueba el offset contra el tamaño.

## Flasheo y arranque

Solo se escribe en `cust` (kernel y configuración); `userdata`, con iOS, no se toca. Tres ventanas: **A** WSL, **C** CMD, **B** CMD de administrador.

1. **WSL:** kernel del CI en `out/kernel.macho` y payload con el táctil activo (`cepheusts=4`):
   `bash scripts/make-cepheus-cust-payload.sh out/kernel.macho out/kernel.macho.adt.fixed out/cust-payload.img`, y copiarlo a `out\` en Windows.
2. **Ventana A (WSL), antes de arrancar:** `sudo modprobe cdc_ether`, `sudo -v` y
   `bash legacy/sweet-tools/sweet-usbnet.sh logs/liveN.txt`. Lo que el kernel imprime antes de que el PC tenga IP se pierde.
3. **Ventana C (CMD), móvil en fastboot (Vol− + Encendido), dentro de `out\`:**
   ```
   fastboot flash cust cust-payload.img   # única escritura: partición cust
   fastboot boot cepheus-xnu.img          # arranque temporal, no escribe en disco
   ```
4. **Ventana B (CMD de administrador), al salir `Booting OKAY`:** `usbipd list` (fila `1209:0001`) y
   `usbipd bind --busid BUSID` (solo la primera vez) y `usbipd attach --wsl --busid BUSID --auto-attach`.
5. Si la red se cae, `usbipd detach` y `attach` la recuperan (parche `0110`); tras reenumerar, pon la IP: `sudo ip addr add 192.168.7.1/24 dev enx02005e77ee01`.

Herramientas del PC, ya con red (`ping 192.168.7.2`): `scripts/phone-touch.py` (tocar iOS), `scripts/ts-console.py` y `scripts/ts-poll.py` (chip táctil).
Si se cuelga, mantén el botón de encendido 10-15 s para apagarlo.

## Créditos

- UniXNU-cepheus (sxl47) y unixnu-nabu (Lux12138): estructura, kits y la serie de parches.
- ios-sweet (dipa-studio): origen de los parches de XNU.
- blacktop/darwin-xnu-build: sistema de compilación del kernel.
- Capa de hardware de cepheus y parche `0084`: tu repo anterior.

Nota: UniXNU-cepheus no incluye archivo de licencia. Antes de publicar este repo, comprueba la licencia de cada origen.
