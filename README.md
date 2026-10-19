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

## Qué está hecho

- Identificación del hardware de cepheus (tabla de arriba).
- `tools/mkadt.py --board cepheus`: genera un ADT con el framebuffer 1080x2340, el `compatible` `xiaomi,cepheus` y las frecuencias de los tres clústeres. Sin `--board`, el comportamiento es el de sweet.
- Los `.gitignore` excluyen las imágenes del teléfono (`*.img`, `backup/`, `miui rom/`, `dtb/`), para que no se suban firmwares ni copias de seguridad.

## Qué falta

1. **Memoria DRAM real.** El dtb base deja el nodo `memory` vacío, porque lo rellena ABL en tiempo de ejecución. Hace falta una sonda de arranque que lea el FDT vivo para fijar `dram-base` y `dram-size`.
2. **Descriptor de iPhone X (`research/ipsw-x/d22ap.adt`).** Se extrae del IPSW de iOS 16.7.16 de Apple, igual que en ios-sweet. Sin él, MobileGestalt no tiene el nodo `/product`.
3. **Drivers de kernel para cepheus.** Los parches de sweet que tocan hardware (`sweet_touch.c` con Goodix en SE7, `sweet_keys.c`, `sweet_rpmh.c`, USB) son específicos de SM7150. Hay que escribir sus equivalentes para ST FTS en SE17 y para el PM8150. El `SweetPlatformExpert` todavía busca `xiaomi,sweet`, así que también hay que actualizarlo.
4. **Shim.** Las direcciones de `shim/` son las de sweet. Hay que revisarlas con el dtb de cepheus antes de generar la imagen de arranque.
5. **CI de kernel.** El kernel se compila en runners macOS de GitHub Actions, que no están disponibles en Forgejo.

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
