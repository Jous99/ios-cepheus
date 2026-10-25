# TODO-MEASURE: lista de mediciones en el Xiaomi Mi 9 real

> Original en chino: `docs/original-zh/TODO-MEASURE.md`.
> Cada punto tiene un lugar de destino en `board.toml` o en un script. Herramientas: TWRP (o cualquier recovery que permita entrar al sistema)
> + fastboot + Mi 9 con el bootloader desbloqueado.
> Se distinguen los valores de referencia de plataforma (que se pueden reutilizar de raphael/nabu) de los que hay que medir.

## 1. DRAM (-> `board.toml` `[payload.adt]` `dram_size`)

```bash
# Shell de TWRP:
cat /proc/meminfo | head -3        # anota MemTotal
```
- Versión de 6 GB: MemTotal ~ 5.6-5.8x10^6 kB -> valor inicial `dram_size = 0x180000000`
- Versión de 8 GB: MemTotal ~ 7.6-7.8x10^6 kB -> valor inicial `dram_size = 0x200000000`
- Método de calibración en el STATUS.md de nabu: MemTotal + reservas (modem/hyp/rmtfs, unos 816 MB) ~ capacidad física
- La base es fija: `0x80000000` (común a SM8150)

## 2. Partición userdata (-> `board.toml` `[userdata]` `first_lba`/`last_lba`)

```bash
# Shell de TWRP (primero confirma qué número de sda es userdata):
ls -l /dev/block/by-name/userdata
cat /sys/block/sda/sdaXX/start     # sectores de 512 B
cat /sys/block/sda/sdaXX/size
```
Conversión: `first_lba = start / 8`, `last_lba = first_lba + size/8 - 1` (LBA de UFS = 4096 B)
Verificación cruzada: `fastboot partition-size:userdata` (los bytes deben ser = (last-first+1)*4096)

## 3. Dirección del framebuffer del panel (-> reg del nodo fbcon en `make-cepheus-adt.py`)

```bash
# Shell de TWRP:
cat /proc/device-tree/soc/qcom,mdss-sspp@0/... # o directamente
dmesg | grep -i "mdss\|framebuffer\|s6e3fc"
```
Panel del Mi 9: Samsung s6e3fc2x01, 1080x2340. Hay que encontrar en el device tree de cepheus la dirección física y la longitud
de MDSS/framebuffer (en nabu es `reg=<0x9C000000 0xC00000>`; en cepheus es distinta).
El método para extraer el device tree se copia de `docs/nabu-dts-extract.md` de nabu (para el dtb del boot.img).

## 4. UUID del volumen del OS (-> `board.toml` `root_match_volume_uuid`)

```bash
# En el PC, sobre el dmg del OS extraído del IPSW:
7z l -slt 044-76040-038.dmg | grep vol_uuid
```
Si se usa el mismo IPSW que nabu, se puede empezar directamente con el valor de nabu `04769d26-2ca0-4825-b443-e2e5f88300f2`.

## 5. Generador de ADT (hecho: `scripts/make-cepheus-adt.py`)

- Ya está adaptado a partir de `make-nabu-adt.py` del fork Lux12138/UniXNU, y se añadió el nodo `/cepheus-fbcon`
  (lo consume el parche 0003: reg=<dirección física tamaño> + width/height/stride).
- **Sigue por medir**: el reg/tamaño del fbcon (tras medir el punto 3, pásalo con `--fbcon-reg/--fbcon-size` o cambia los valores
  por defecto del script; ahora son los valores provisionales de nabu `0x9C000000/0xC00000`).

## 6. Dirección del fork en el CI

`.github/workflows/build-kernel.yml` clona ahora `Lux12138/UniXNU`. Al principio se puede usar tal cual (todo el trabajo de
kernel para SM8150 está ahí); a largo plazo conviene hacer un fork de `UniXNU` con tu propio remoto y añadirle allí `make-cepheus-adt.py`.

## 7. Contenido de los parches del kernel específico de dispositivo (tarea posterior, no bloquea la compilación)

Los 83 parches de `xnu-8796/patches/` son el trabajo acumulado de kernel de nabu para SM8150; los nombres de archivo se mantienen.
Lo que hay que tocar para cepheus (tras medir):
- `0004-nabu-machine-config.patch`: direcciones de plataforma / relacionado con DRAM
- `0010-nabu-early-framebuffer-debug.patch`: dirección del fbcon
- `0060~0063` (drivers táctiles): el IC táctil del Mi 9 es distinto al de nabu (¿NT36672?); hay que cambiarlo según el device tree de cepheus
- `0061-nabu-iphone-x-display-size.patch`: adaptación de resolución
- UFS/USB/PMIC probablemente son comunes; de momento no se tocan

## 6 (bis). Conclusiones de la última práctica con el fork de nabu (2026-10-24)

(El original repite la numeración "6".)

- El bloqueo actual de nabu es un panic tras `execve`, ya localizado: al ADT le falta `maxmem` (límite de memoria "owned"), lo que
  infla 116 veces el contador de páginas de VM (freepg=91.199.444 páginas ~ 373 GB), y la asignación de páginas revienta sí o sí.
  Arreglo = inyectar en el ADT `maxmem=4864` (igual a `owned_memory_size`).
  -> **Qué significa para cepheus: una vez medidos `dram_size` / `owned_memory_size`,
  `maxmem` debe ser igual a `owned_memory_size` (en una máquina de 6 GB, unos 6144 menos la zona reservada; vale lo que se mida).**
  El CI clona el último código del fork, así que ese arreglo ya está incluido; el `repos/UniXNU-nabu-fork` local estaba atrasado y,
  si hace falta, se sincroniza con `git -C repos/UniXNU-nabu-fork pull`.
- El fork se compila solo en un WSL local, y su workflow de CI no se ha mantenido con las nuevas imágenes de runner:
  la trampa de hostcompat que pisamos fue la primera; el arreglo está en el comentario `HOST_COMPAT_CFLAGS` de `build-kernel.yml`.

> **Nota del traductor (2026-10-25):** en este repo, `scripts/make-cepheus-adt.py` **no fija `maxmem`** (se comprobó con grep en
> scripts, kits, configs, board.toml y workflows; solo usa `darwinboot-memory-size`), y `board.toml` trae
> `owned_memory_size = "0x20000000"`. Revisa este punto al medir la DRAM: es el mismo tipo de fallo que describe esta sección.
