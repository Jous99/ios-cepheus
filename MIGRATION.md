# Migración ios-cepheus (ios-sweet) -> base UniXNU-cepheus

Fecha: 2026-10-25. Origen: tu repo `ios-cepheus` (fork de ios-sweet, shim propio). Destino: UniXNU-cepheus (UEFI + DarwinBoot).

## Qué se encontró al comparar
- De los 81 primeros parches de XNU, 79 son idénticos tras normalizar sweet/nabu/cepheus. Los otros dos (0046, 0070) solo cambian en guardas `#if`.
- UniXNU-cepheus es en gran parte la serie de sweet renombrada. Por eso arrastra constantes de sweet en sitios de hardware
  (p. ej. los botones: PM6150L SID 4). Tu repo tenía los valores correctos del PM8150 de la Mi 9 -> parche `0084`.

## Qué cambió
| Cambio | Detalle |
| --- | --- |
| Base | Árbol completo de UniXNU-cepheus |
| **Añadido** `0084-cepheus-keys-pm8150` | Volumen+ en GPIO6 del PM8150 (SID 0), portado de tu `0082`. **Sin verificar en el teléfono** |
| **Desactivado** `0083` (NT36523 SPI) | Táctil de la Pad 5, no existe en la Mi 9. En `patches-disabled/` |
| **Extras** E01-E09 | Tus marcadores de debug, renombrados a `cepheus_*`. No se aplican por defecto |
| **Excluido** 0093 | Prueba que desactivaba `procinit`; queda en `legacy/` |
| **No portado** tu `0082`/`0083` | Eran las guardas `|| CEPHEUS` y la config de máquina sobre sweet; en esta serie ya es CEPHEUS puro |
| Legado | `legacy/` (shim, tools, parches propios) y `docs/ios-sweet-legacy/` (NOTES, GUIDE, README, AGENTS) |

## Verificación hecha
Sobre `xnu-8796.141.3` limpio (macOS 13.5): la serie 0001-0082 + 0084 aplica sin fallos con `git apply`, y E01-E09 también, en ese orden.
**Límites:** no se ha compilado (el CI es macOS) y los scripts `stage-*` no pudieron ejecutarse del todo aquí
(sin `xcrun`, y bearssl.org no es accesible), así que los parches que dependen de esos archivos preparados no se comprobaron.

## Documentación
Se tradujeron al español `STATUS.md`, `TODO-MEASURE.md` y los documentos de `docs/` (los originales en chino están en `docs/original-zh/`).
`docs/nabu-reference/` (notas históricas de la Pad 5) no se tradujo.

## Qué NO se hizo (decisiones tuyas)
1. **IPSW:** `board.toml` apunta al iPad 17.7.11 (xnu-10063); tu proyecto usaba el iPhone X 16.7.16 con xnu-8796.
   El workflow `build-kernel-8796.yml` no usa esa sección, pero el empaquetado del root sí. Hay que decidir cuál.
2. **Tu root actual:** `userdata` contiene tu root de iOS 16. Esta cadena lo sobrescribiría con el del IPSW elegido.
3. **`maxmem` en el ADT:** `make-cepheus-adt.py` no lo fija y `board.toml` trae `owned_memory_size = 0x20000000`; revísalo al medir la DRAM (ver `TODO-MEASURE.md`).
4. **Ramdisk/logs:** tus pruebas de RAM para logs (0x9d000000, 0x1f0000000) no sobrevivían al reinicio; sigue valiendo la pantalla.

## Medir en tu Mi 9 (obligatorio antes de flashear)
Desde TWRP (`adb shell`):
```
cat /proc/meminfo | head -3
ls -l /dev/block/by-name/userdata
cat /sys/block/sda/sdaXX/start /sys/block/sda/sdaXX/size    # XX = número que salga arriba
fastboot getvar partition-size:userdata
```
`first_lba = start/8`, `last_lba = first_lba + size/8 - 1`. Si no coinciden con `board.toml`, corrígelos.
Los valores actuales (6 GB, userdata ~111 GiB) vienen del repo original y no se han confirmado en tu unidad.

## Cómo subirlo (desde un PC, cuando puedas)
No sobrescribas `main`. Crea una rama:
```
git clone https://git.joustech.space/Jous/ios-cepheus.git && cd ios-cepheus
git checkout -b unixnu-migration
git rm -rq . && cp -a /RUTA/ios-cepheus-migrado/ios-cepheus/. .
git add -A && git commit -m "Migración a base UniXNU-cepheus" && git push -u origin unixnu-migration
```
El CI (`build-kernel-8796.yml`) se dispara al hacer push a `main` con cambios en `xnu-8796/patches/`; en una rama no corre solo.
Cuando lo lances, vigila los minutos de macOS.
