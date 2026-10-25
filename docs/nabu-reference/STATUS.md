# Resumen de estado

> Este equipo es una **nabu ampliada**: DRAM física de **12 GiB**, medida en el `/proc/meminfo` de TWRP
> (`MemTotal = 11766512 kB`, es decir, 12 GiB menos unos 816 MB para modem/hyp/rmtfs).
> Por eso `dram_size = 0x300000000` y `owned_memory_size = 0x130000000` son **valores medidos para esta máquina**,
> no los de un modelo estándar de 6/8 GB. Copiar el `0x180000000` (6 GiB) de otros proyectos haría que la memoria física por encima de 6 GiB
> fuera invisible para Darwin.

## Hito: el kernel llegó a launchd

**Evidencia en pantalla (noche del 2026-10-23)**

```
Process 1 exec of /sbin/launchd failed, errno 2
/sbin/launchd
kern_exec.c

FAR=18446744042837921792
PC=18446744005117767160
LR=18446744005111703156
```

**El kernel recorrió completa esta cadena:**

```
bsd_autoconf()        ✅
  kminit()            ✅
    IOsurfaceRoot::installMemoryRegions()   ✅   ← antes se creía que se atascaba aquí, pero no
bsd_init, segunda mitad       ✅
  vfs_mountroot()     ✅
  load_init_program() ✅   ← resuelve /sbin/launchd
    execve("/sbin/launchd")   ❌  errno 2 (ENOENT)
```

**`errno 2` significa que el archivo no existe: no es un problema del kernel, sino que el sistema de archivos raíz no tiene ese archivo.**

### Esto desmonta el diagnóstico de tres días

La línea de `IOsurfaceRoot::installMemoryRegions()` **nunca fue el final**, solo era el último kprintf.
Lo que viene justo después (`dtrace_postinit()`, `inittodr()` y la inicialización de red de compilación condicional) no imprime logs, así que
"el log se paró" se tomó por "el kernel se paró".

Lo que siempre faltó es **una raíz de verdad**, no un surface propio.

## Compilación local en Linux funcionando (12 veces más rápida)

| Elemento | Runner macOS de GitHub | WSL Ubuntu local |
|---|---|---|
| Compilación por ronda | 15-17 minutos | **72 segundos** |
| Producto | 49,2 MB | **49 MB** |
| Reproducible | Solo con CI | Se puede ejecutar en la máquina cuando quieras |

Verificación:

```
file            Mach-O 64-bit arm64 executable, flags:<NOUNDEFS|PIE>
__TEXT vmaddr   0xfffffff007004000      ← igual que el kernelcache original
symbols         22708
Sondas nabu     nabu_mark / nabu_mark_map / nabu_mark_num / nabu_mark_putc
Sondeo de UFS   nabu_ufs_register_probe.cpp
sha256          c756ecdb88a9dd50156dc27d2cdf48a08ddf93fcf204040fa57804f814fc3c15
```

**Cadena de herramientas**: `Allenwdk/xnu-linux-toolchain` (Ubuntu 24.04 / clang 18 / 12 núcleos)

## 18 problemas resueltos por el camino

```
 1  libdispatch no tiene paquete en Ubuntu → compilar desde fuente + .pc escrito a mano
 2  toolchain/csh es un enlace simbólico   → cp -L
 3  xcrun con /usr/bin/xcrun fijo          → enlace simbólico
 4  sysctl con /usr/sbin/sysctl fijo       → sustituido por un shim de Darwin
 5  /bin/sh es dash                        → apuntar a bash
 6  bison/flex/m4 están en /usr/sbin       → enlace simbólico
 7  hostcompat.h no existe                 → escrito a mano
 8  libc.h no existe                       → escrito a mano (OSAtomic / alineación de página)
 9  copyfile.h / fcopyfile                 → escrito a mano
10  setmode/getmode                        → escrito a mano (desplazamiento de who + corrección de mask)
11  TargetConditionals.h                   → escrito a mano, y solo en dos sitios
12  sys/_types/_os_inline.h                → escrito a mano y replicado en el árbol compat
13  mach/mach_init.h                       → escrito a mano
14  -Wno-* no reconocidos                  → -Wno-unknown-warning-option
15  nombres de diagnóstico de macOS clang 26 → CCC_OVERRIDE_OPTIONS, rebajando uno a uno
16  sed -i '' es sintaxis BSD              → tratamiento por ramas, y solo se ejecuta en Darwin
17  awk \( en GNU conserva la barra invertida → hecho parche (zzzz-nabu-awk-parens)
18  doble enlazado de mockfs (23 símbolos duplicados) → se quita force_load
```

## Siguiente paso

**Lo único que falta es un sistema de archivos raíz de verdad.**

```
./unixnu ipsw fetch                          # OS + Cryptex1,SystemOS
./unixnu build userdata                      # manifiesto SHNGROOT + dos ventanas
fastboot flash userdata out/nabu/userdata/userdata-root.img
```

Sabido: los LBA de `[userdata]` ya se midieron hace tiempo (`first_lba = 0x288C40` / `last_lba = 0x77BF3FA` /
`lba_bytes = 4096`).

**Ya no es un problema de compilación ni de drivers: es un problema de datos.**
