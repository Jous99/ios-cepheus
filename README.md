# ios-cepheus

**Port de iOS/XNU (xnu-8796, iOS 16) al Xiaomi Mi 9 (`cepheus`, Snapdragon 855 / SM8150).**

> **Estado: experimental, sin arrancar.** Esta es la base migrada (2026-10-25). El kernel compila y
> los parches aplican, pero nada se ha probado todavía con esta cadena de arranque en tu Mi 9.
> Lee `MIGRATION.md` antes de tocar nada.

## Cadena de arranque

```
Android boot image -> BootShim -> Mu-Silicium UEFI -> DarwinBoot -> XNU
```

Sustituye al shim propio de ios-sweet (guardado en `legacy/sweet-shim/`).

## Hardware de cepheus (datos de tu repo anterior)

| Componente | Cepheus |
| --- | --- |
| SoC | SM8150, 1+3+4 núcleos |
| PMIC | PM8150 / PM8150B / PM8150L |
| Pantalla | 1080x2340, panel `SS NOTCH FHD EA8074` (modo comando) |
| Táctil | STMicro FTS, I²C `0x49`, bus GENI SE17 (`i2c@c8c000`) |
| Botones | Volumen y encendido vía PM8150; volumen+ = GPIO6, SID 0 (parche `0084`, sin verificar en el teléfono) |
| UFS | `ufshc@1d84000` |
| GIC-v3 | GICD `0x17a00000`, GICR `0x17a60000` |

## Estructura

| Ruta | Contenido |
| --- | --- |
| `board.toml` | Descripción de la placa (**ver aviso de medidas en `MIGRATION.md`**) |
| `xnu-8796/patches/` | Serie de parches que aplica el CI (0001-0082 y 0084) |
| `xnu-8796/patches-extra/` | Parches de debug tuyos, portados; **no** se aplican por defecto |
| `xnu-8796/patches-disabled/` | Parches desactivados a propósito (hardware que la Mi 9 no tiene) |
| `scripts/`, `kits/`, `configs/` | ADT, payload, plataforma y defconfig |
| `.github/workflows/` | CI (`build-kernel-8796.yml` es el que corresponde a xnu-8796) |
| `docs/` | Notas de UniXNU y `docs/ios-sweet-legacy/` (tu bitácora completa) |
| `legacy/` | Tu shim, tus herramientas y tus parches propios anteriores |
| `README.upstream.zh.md` | README original de UniXNU-cepheus (chino) |

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
