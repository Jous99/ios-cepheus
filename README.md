# ios-cepheus

**Port de iOS/XNU (xnu-8796, iOS 16) al Xiaomi Mi 9 (`cepheus`, Snapdragon 855 / SM8150).**

> **Estado: experimental, sin arrancar.** Esta es la base migrada (2026-10-25). Los parches aplican sobre xnu-8796.141.3,
> pero el CI del kernel aún no se ha comprobado y nada se ha probado todavía con esta cadena de arranque en tu Mi 9.
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
- [x] Hardware de cepheus identificado: SM8150, PM8150, táctil ST FTS en SE17, panel 1080x2340
- [x] Direcciones de GIC y UFS confirmadas (coinciden con sweet)
- [x] dtb base SM8150 v2 extraído de `boot.img`
- [x] Overlay CEPHEUS extraído de `dtbo.img`
- [x] Generador de ADT para cepheus (`scripts/make-cepheus-adt.py`)
- [x] Migración a la base UniXNU-cepheus (2026-10-25): la serie de parches aplica sobre xnu-8796.141.3
- [x] Configuración de máquina CEPHEUS en el kernel (parches `0004` / `0006`)
- [x] Parche `0084`: botones del PM8150 (volumen+ en GPIO6, SID 0)
- [x] Los `.gitignore` excluyen imágenes, firmware y copias de seguridad

### Fase 0: Preparación del teléfono
- [ ] Copia de seguridad de `boot`, `dtbo`, `vbmeta`, `persist`, `modemst1`, `modemst2`, `fsg` y `fsc`
- [ ] Bootloader desbloqueado con Mi Unlock (revisar el estado de la cuenta)
- [ ] Probar `fastboot boot` con un boot.img de Android sin modificar

### Fase 1: Arranque y consola en pantalla
- [ ] Medir en tu Mi 9: DRAM, `userdata` (first/last LBA) y dirección del framebuffer (`TODO-MEASURE.md`)
- [ ] Comprobar `maxmem` / `owned_memory_size` en el ADT (ver nota en `TODO-MEASURE.md`)
- [ ] Primer CI del kernel xnu-8796 compilando (`build-kernel-8796.yml`; vigilar los minutos de macOS)
- [ ] Imagen UEFI: receta y parche listos en `docs/uefi-cepheus.md` + `uefi/` (sin compilar ni probar)
- [ ] **Hito 1:** el kernel escribe texto en pantalla con `fastboot boot`

### Fase 2: Almacenamiento y userland
- [ ] Decidir el IPSW (iPad 17.7.11 de `board.toml` o iPhone X 16.7.16; el kernel xnu-8796 es de la línea iOS 16)
- [ ] Imagen root en `userdata` (borra Android; confirmar antes)
- [ ] **Hito 2:** launchd y el userland arrancan

### Fase 3: Entrada
- [ ] Verificar la lectura de botones en el teléfono (diagnóstico `CEPHEUS KEYS:` en el log)
- [ ] Driver nuevo para el táctil ST FTS en SE17, con `st_fts_f1.ftb` (los drivers táctiles de la serie son de otras placas)
- [ ] Touch, USB, RPMh y batería siguen siendo de sweet/nabu: hay que portarlos para cepheus
- [ ] **Hito 3:** SpringBoard y Setup se pueden usar con el táctil

### Fase 4: Extras (no prioritarios)
- [ ] USB ECM para leer logs por red
- [ ] Panel en modo comando (sin DSC)
- [ ] Sensores y audio

### Decisiones pendientes
- [x] iOS puede ocupar `userdata` (aprobado el 2026-10-15); confirmar cada paso destructivo antes de ejecutarlo
- [ ] Dual boot: aparcado, se retoma más adelante
- [ ] IPSW definitivo (ver Fase 2)

## Estructura

| Ruta | Contenido |
| --- | --- |
| `board.toml` | Descripción de la placa (**ver aviso de medidas en `MIGRATION.md`**) |
| `xnu-8796/patches/` | Serie de parches que aplica el CI (0001-0082 y 0084) |
| `xnu-8796/patches-extra/` | Parches de debug tuyos, portados; **no** se aplican por defecto |
| `uefi/`, `docs/uefi-cepheus.md` | Parche de Mu-Silicium (`cepheusPkg` + UniXNU/DarwinBoot) y receta de construcción |
| `xnu-8796/patches-disabled/` | Parches desactivados a propósito (hardware que la Mi 9 no tiene) |
| `scripts/`, `kits/`, `configs/` | ADT, payload, plataforma y defconfig |
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

## Flasheo (cuando haya artefactos)

```
fastboot flash cust cust-payload.img   # única escritura: partición cust
fastboot boot cepheus-xnu.img          # arranque temporal, no escribe en disco
```

Si se cuelga, mantén el botón de encendido 10 s para volver a Android.

## Créditos

- UniXNU-cepheus (sxl47) y unixnu-nabu (Lux12138): estructura, kits y la serie de parches.
- ios-sweet (dipa-studio): origen de los parches de XNU.
- blacktop/darwin-xnu-build: sistema de compilación del kernel.
- Capa de hardware de cepheus y parche `0084`: tu repo anterior.

Nota: UniXNU-cepheus no incluye archivo de licencia. Antes de publicar este repo, comprueba la licencia de cada origen.
