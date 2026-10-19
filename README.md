# ios-cepheus

**Port de iOS 16 a Xiaomi Mi 9 (`cepheus`, Qualcomm SM8150 / Snapdragon 855).**

> **Estado: experimental, todavía no arranca.** Este repositorio es el punto de partida del port. Nada de lo que hay aquí se ha probado en un Mi 9 todavía. Para el estado real del trabajo, mira la sección "Estado" y `NOTES.md`.

Este repo es una bifurcación de [ios-sweet](https://github.com/dipa-studio/ios-sweet), que lleva iOS 16 a un Redmi Note 10 Pro (`sweet`, SM7150). Se mantiene el mismo enfoque: el kernel XNU de iOS 16 (xnu-8796) con parches propios, y encima el userland sin modificar del iPhone X (`iPhone10,3`, `D22AP`), 16.7.16 (20H392). Lo que cambia es la capa de hardware, que aquí es propia de cepheus.

## Hardware de cepheus

Datos extraídos del paquete oficial de MIUI 12.5.1 global para cepheus (`boot.img` y `firmware-update/dtbo.img`) y del dtb base SM8150 v2 del propio `boot.img`:

| Componente | Cepheus | Notas |
| --- | --- | --- |
| SoC | Qualcomm SM8150 (Snapdragon 855), 1+3+4 núcleos | En sweet: SM7150 (732G) |
| PMIC | PM8150, PM8150B, PM8150L | En sweet: PM6150 / PM6150L |
| Pantalla | 1080x2340, panel `SS NOTCH FHD EA8074` en modo comando | En sweet: 1080x2400, vídeo DSC |
| Táctil | STMicro FTS, I²C `0x49`, en el bus GENI SE17 (`i2c@c8c000`) | En sweet: Goodix GT9896 en SE7 |
| Botones | Volumen y encendido vía PM8150 (`gpio-keys`) | |
| Almacenamiento | UFS en `ufshc@1d84000` | La misma dirección que en sweet |
| Interrupciones | GIC-v3, `GICD 0x17a00000`, `GICR 0x17a60000` | Igual que en sweet |

## Checklist

### Hecho
- [x] Hardware de cepheus identificado: SM8150, PM8150, táctil ST FTS en SE17, panel 1080x2340
- [x] Direcciones de GIC y UFS confirmadas (coinciden con sweet)
- [x] dtb base SM8150 v2 extraído de `boot.img`
- [x] Overlay CEPHEUS extraído de `dtbo.img`
- [x] `tools/mkadt.py --board cepheus` creado
- [x] `d22ap.adt` del iPhone X extraído del IPSW 16.7.16 (20H392)
- [x] Los `.gitignore` excluyen imágenes, firmware y copias de seguridad

### Fase 0: Preparación del teléfono
- [ ] Copia de seguridad de `boot`, `dtbo`, `vbmeta`, `persist`, `modemst1`, `modemst2`, `fsg` y `fsc`
- [ ] Bootloader desbloqueado con Mi Unlock (revisar el estado de la cuenta)
- [ ] Probar `fastboot boot` con un boot.img de Android sin modificar

### Fase 1: Arranque y consola en pantalla
- [ ] Sonda de arranque que lea el FDT vivo de ABL: DRAM real (`dram-base`, `dram-size`) y framebuffer
- [ ] Ajustar `mkadt.py` con la memoria real
- [x] Revisar `shim/`: framebuffer de 2340 con `BOARD=cepheus` (`-DBOARD_CEPHEUS`), dtb configurable con `DTB=`. Compila para sweet y cepheus. UFS y framebuffer coinciden con el dtb
- [ ] Configuración de máquina CEPHEUS en el kernel: equivalente a `0004`, `0016`-`0019` y `SWEET.h` (GIC, timer, pthread, identidad del SoC)
- [ ] Parche del kernel: que `SweetPlatformExpert` reconozca `xiaomi,cepheus`
- [ ] Commit y CI de kernel en GitHub Actions (vigilar los minutos de macOS en repos privados)
- [ ] **Hito 1:** el kernel escribe texto en pantalla con `fastboot boot`

### Fase 2: Almacenamiento y userland
- [ ] El shim lee el ramdisk desde UFS en cepheus
- [ ] Imagen root de iOS con `tools/mkiosroot.sh` a partir del IPSW
- [ ] Escribir `userdata` (borra Android; confirmar antes)
- [ ] **Hito 2:** launchd y el userland arrancan

### Fase 3: Entrada
- [ ] Botones de volumen y encendido desde el PM8150 (`gpio-keys`)
- [ ] Driver nuevo para el táctil ST FTS en SE17, con `st_fts_f1.ftb`
- [ ] **Hito 3:** SpringBoard y Setup se pueden usar con el táctil

### Fase 4: Extras (no prioritarios)
- [ ] USB ECM para leer logs por red
- [ ] Panel en modo comando (sin DSC)
- [ ] Sensores y audio

### Decisiones pendientes
- [ ] Dual boot: aparcado, se retoma más adelante
- [ ] Confirmar que iOS puede ocupar `userdata` antes de la Fase 2

## Cómo se compila (cuando esté listo)

El procedimiento es el de ios-sweet, con estas diferencias:

```sh
# 1. Kernel: se compila en GitHub Actions (workflow xnu.yml)
gh workflow run xnu.yml -R TU_USUARIO/ios-cepheus
gh run download RUN_ID -R TU_USUARIO/ios-cepheus -n xnu-kernel -D xnu/out

# 2. ADT para cepheus
python3 tools/mkadt.py shim/out/cepheus.adt --board cepheus --highmem

# 3. Imagen de arranque (el cmdline es el de sweet, pendiente de revisar)
python3 tools/mkpayload.py xnu/out/kernel.development.cepheus shim/out/cepheus.adt shim/out/payload.bin --cmdline '...'
shim/build.sh ../shim/out/payload.bin
```

El root de iOS (`tools/mkiosroot.sh`) es el mismo que en sweet, a partir del IPSW del iPhone X 16.7.16 (20H392).

**Aviso:** el arranque requiere el bootloader desbloqueado y usa `fastboot boot`, sin flashear las particiones de arranque. Aun así, la instalación de iOS sobrescribe `userdata` y borra los datos de Android. Haz copia de seguridad antes de cualquier prueba (`boot`, `dtbo`, `vbmeta`, `persist`, `modemst1`, `modemst2`, `fsg`, `fsc`).

## Estructura

| Ruta | Contenido |
| --- | --- |
| `shim/` | Shim de arranque en C y ensamblador (de sweet, pendiente de adaptar) |
| `xnu/patches/` | Parches de XNU (de sweet, pendientes de adaptar a cepheus) |
| `tools/mkadt.py` | Generador del ADT, con `--board cepheus` |
| `tools/mkiosroot.sh` | Construye el root de iOS desde el IPSW |
| `NOTES.md` | Bitácora de ingeniería |

## Créditos

El enfoque y la mayoría del código vienen de ios-sweet (dipa-studio). Este repositorio solo añade la capa de cepheus encima.
