# UniXNU on Xiaomi Pad 5 (nabu / SM8150)

Registro completo del port que arranca el **kernel XNU de Apple** por UEFI en la **Xiaomi Pad 5 (nabu, Snapdragon 860 / SM8150)**.

> **Este equipo es la versión ampliada:** DRAM física de **12 GiB** (medido en TWRP: `MemTotal = 11766512 kB`,
> es decir, 12 GiB menos unos 816 MB para modem/hyp/rmtfs) y userdata de **unos 468 GiB**
> (`fastboot partition-size:userdata = 0x74167BB000`).
> Por eso `dram_size = 0x300000000` está **medido para esta máquina**; no es el valor de un modelo estándar de 6/8 GB.

> **Estado**: **el kernel ya ejecuta hasta `execve("/sbin/launchd")`**
> (`Process 1 exec of /sbin/launchd failed, errno 2`).
> Todo lo del lado del kernel pasa; lo que falta es un sistema de archivos raíz con los archivos del sistema.

---

## I. Hito: el kernel llegó a launchd

**Evidencia en pantalla**

```
Process 1 exec of /sbin/launchd failed, errno 2
/sbin/launchd
kern_exec.c

FAR=18446744042837921792
PC=18446744005117767160
LR=18446744005111703156
```

**Cadena completa**

```
bsd_autoconf()                            OK
  kminit()                                OK
    IOsurfaceRoot::installMemoryRegions() OK   <- se había creído que se atascaba aquí
bsd_init, segunda mitad                   OK
  vfs_mountroot()                         OK
  load_init_program()                     OK   <- resuelve /sbin/launchd
    execve("/sbin/launchd")               errno 2 (ENOENT)
```

**`errno 2` significa que el archivo no existe; no es un fallo del kernel.**

### Nos equivocamos durante tres días

La línea de `IOsurfaceRoot::installMemoryRegions()` **nunca fue el final, solo el último kprintf**.
Tras ella, `dtrace_postinit()`, `inittodr()` y la inicialización de red (compilación condicional) **no imprimen ningún log**,
así que "el log se paró" se leyó como "el kernel se paró".

Lo que faltaba siempre era un sistema de archivos raíz.

---

## II. Cadena de arranque (verificada en el teléfono)

```
fastboot boot -> Mu UEFI -> menú de UniXNU -> payload de la partición cust
-> DarwinBoot -> lee el kernel de 51 MB -> analiza el Mach-O -> comprueba el ADT
-> asigna la ventana -> mapea segmentos -> ExitBootServices -> salta a XNU -> el kernel se ejecuta
```

Logs clave:

```
UNIXNU: runxnu entry vol=A2142798 path=\EFI\UniXNU\Payloads\kernel.macho cfgerr=[]
DB1 kernel read  Success size=53760000
DB2 kernel parse Success
DB3 adt read     Success size=13188
DB4 adt ok  win=120000000 keep=0 rd=ffffffffffffffff
DB arm64 va=0xfffffff007ac2000 pa=0x80070000 owned=0x120000000 window=0x30000000
video base=0x... width=2560 depth=32 bpp
DARWINBOOT: EL1 installed
DARWINBOOT: inputs validated; exiting boot services
still-there kernel entry code ran
DARWINBOOT: hand-off to the kernel
```

---

## III. Compilación local en Linux (72 segundos por ronda)

El kernel ya se puede compilar en un WSL Ubuntu 24.04 local en **72 segundos** por ronda, frente a los 15-17 minutos del runner macOS de GitHub.

| Elemento | Runner macOS de GitHub | WSL Ubuntu local |
|---|---|---|
| Compilación por ronda | 15-17 minutos | **72 segundos** |
| Producto | 49,2 MB | **49 MB** |
| Reproducible | Solo con CI | Se puede ejecutar en la máquina cuando quieras |

**Verificación del producto**

```
file            Mach-O 64-bit arm64 executable, flags:<NOUNDEFS|PIE>
__TEXT vmaddr   0xfffffff007004000      igual que el kernelcache original
symbols         22708
Sondas nabu     nabu_mark / nabu_mark_map / nabu_mark_num / nabu_mark_putc
Sondeo de UFS   nabu_ufs_register_probe.cpp
sha256          c756ecdb88a9dd50156dc27d2cdf48a08ddf93fcf204040fa57804f814fc3c15
```

La cadena de herramientas viene de [`Allenwdk/xnu-linux-toolchain`](https://github.com/Allenwdk/xnu-linux-toolchain).

### 18 trampas al hacerlo funcionar en Linux

| Categoría | Cantidad | Ejemplos |
|---|---|---|
| Herramientas ausentes | 8 | `libdispatch` no tiene paquete en Ubuntu; `hostcompat.h` / `libc.h` / `copyfile.h` / `setmode` hubo que escribirlos todos |
| Rutas escritas a mano | 5 | `/usr/bin/xcrun`, `/usr/sbin/sysctl`, `compression_tool`, `dsymutil`, `lzfse` |
| BSD vs GNU | 3 | `sed -i ''`, `awk \(`, `-Wno-*` desconocidos |
| Conflictos de lógica | 2 | doble enlazado de mockfs (23 símbolos duplicados), `TargetConditionals.h` duplicado |

**El más valioso**: en `makesyscalls.sh`, `printf("\t{ \(sy_call_t *\)...")` ——
**el awk de BSD trata `\(` como escape, gawk conserva la barra invertida**: en Linux el `init_sysent.c` generado es todo
`\(sy_call_t *\)`, y el compilador da un montón de `expected expression`. Se hizo un parche (`zzzz-nabu-awk-parens.patch`),
porque `unixnu tree` reconstruye `.cache` cada vez y un cambio manual se sobrescribiría.

---

## IV. Sistema de archivos raíz: 7-Zip lo extrae directamente, sin hdiutil

`build userdata` se atasca en Linux con `hdiutil`. No hace falta escribir un analizador UDIF propio ——
**7-Zip 23.01 soporta de forma nativa DMG + LZFSE** y extrae directamente el sistema de archivos completo de iOS:

```bash
sudo apt-get install -y p7zip-full
7z x -y -o/tmp/dmgout 044-76040-038.dmg
```

Resultado medido:

```
/sbin/launchd   561,856 bytes   Mach-O 64-bit arm64 executable
                               flags:<NOUNDEFS|DYLDLINK|TWOLEVEL|PIE>

9.7 GB / 210,828 archivos
  8.1G  System
  713M  usr
  483M  private
  313M  Applications
  139M  Library
  960K  sbin
```

**Ojo**: `dmg2img 1.6.7` **no soporta LZFSE**, da
`Unsupported or corrupted block found: -2147483641` y produce una imagen basura. Usa 7-Zip.

`7z l -slt` muestra directamente el método de compresión:

```
Method = Copy Zero2 LZFSE CRC
Path   = 3.apfs
Size   = 6077546496         5.66 GiB
Type   = APFS
Name   = DawnUpdate21H461.J120J121J207J208OS.apfs
num_files: 165509
```

---

## V. Seis trampas duras y sus soluciones (pisándolas en este orden se ahorran días)

### Trampa 1: `fastboot boot` da `Failed to load/authenticate boot image: Load Error`

**No es** que el ABL modificado desactive boot, **es el cable USB**.

- Un cable de carga malo pierde datos al transferir imágenes de ~96 MB -> el ABL falla al verificar
- Con el cable de datos original y el puerto USB trasero de la placa base, la misma imagen da `Booting OKAY` de inmediato

### Trampa 2: el tamaño del ramdisk tiene límites inferior y superior

| ramdisk | ABL | UEFI |
|---|---|---|
| 16 MB | Load Error | — |
| 32 MB | OK | menú normal |
| 64 MB | OK | menú normal |
| 96 MB | OK | pantalla negra |

Rango utilizable **32-64 MB**; `header_version = 1`, `page_size 2048`.

### Trampa 3: reinicia el dispositivo antes de `fastboot boot`

**El primer boot tras cada reinicio es el que más veces funciona**; boots seguidos dan Load Error (queda estado residual en el download buffer).

### Trampa 4: meter el kernel en el volumen de firmware no funciona (presupuesto de descompresión de PEI)

| Tamaño de FVMAIN | Resultado |
|---|---|
| 8 MB (original) | el firmware funciona |
| 62 MB (kernel sin comprimir) | vuelve a fastboot |
| 15 MB (kernel comprimido con LZMA) | vuelve a fastboot |

El límite de FVMAIN es de unos 8-10 MB; el propio FD también tiene límite. **El kernel no puede ir en el segmento de kernel del boot.img, solo por almacenamiento.**

### Trampa 5: no hay ningún disco FAT (la más fundamental)

En realidad el firmware trae una pila de almacenamiento completa (`UFSDxe` / `PartitionDxe` / `DiskIoDxe` / `Fat`),
pero las particiones de Android son todas ext4/f2fs, así que UniXNU no encuentra ningún volumen con `unixnu.toml`.

### Trampa 6: la DRAM del ADT tiene que ser el valor medido

```
dram-size               = 0x300000000   12 GiB (ampliada en este equipo)
darwinboot-memory-size  = 0x20000000    ventana contigua de 512 MiB
```

`darwinboot-memory-size` es un bloque **contiguo** de memoria física que DarwinBoot pide al firmware.
512 MiB bastan; un valor mayor es más difícil de encontrar como intervalo contiguo en `EfiConventionalMemory`.

---

## VI. Siguiente paso

**Lo único que falta es convertir la raíz extraída en un volumen montable.**

```bash
./unixnu ipsw fetch OS Cryptex1,SystemOS      # ya descargado: OS 4,80 GiB + SystemOS 3,08 GiB
7z x -y -o/tmp/dmgout out/ipsw/21H461/044-76040-038.dmg
./unixnu build userdata                       # manifiesto SHNGROOT + dos ventanas
fastboot flash userdata out/nabu/userdata/userdata-root.img
```

Geometría de `[userdata]` (medida en TWRP):

```
first_lba = 0x288C40     2,654,272    (4 KiB LBA)
last_lba  = 0x77BF3FA    125,436,922
lba_bytes = 4096
windows   = [OS, SystemOS]
```

**Ya no es un problema de compilación ni de drivers: es un problema de datos.**

---

## VII. Referencias

- [`Allenwdk/xnu-linux-toolchain`](https://github.com/Allenwdk/xnu-linux-toolchain) —— cadena de herramientas cruzada para Linux
- [`1PJL/unixnu-nabu`](https://github.com/1PJL/unixnu-nabu) —— serie de diagnóstico de volúmenes UFS (tres pasos `Recover GPT` / `Build Volume` / `Repack`, sobre `ubuntu-24.04`)
- `UniXNU` upstream —— port del kernel y cadena de arranque UEFI
