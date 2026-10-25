# UniXNU on Xiaomi Pad 5 (nabu / SM8150) — Documento de traspaso completo

> Estado: **el kernel XNU ya entra en ejecución en el teléfono real** (DarwinBoot `exiting boot services` → `hand-off to the kernel`).
> Trabajo actual: instalar en el kernel "sondas de visibilidad" (convertir la caja negra en caja blanca).
> ✅ La cadena de inyección está arreglada y **el CI pasa** (UniXNU `0c4e9a1` / unixnu-nabu `b7642cf`, run `39612555624` success,
> los marcadores de bloques MARK1–4 ya están enlazados en `kernel.macho`).
> ✅ También se comprobó la **causa real** de "el kernel no da salida": el `boot_args.Video` de DarwinBoot se había cambiado al orden de array antiguo,
> desalineado con los campos de `struct Boot_Video` del kernel (ver **Trampa 8, corrección**).
> ⬜ Siguiente paso: **recompilar el firmware + flashear y contar los bloques** (sección 7, paso 5; hace falta conectar el dispositivo).

---

## 0. Ubicación del repositorio y de los productos

| Elemento | Ruta |
|---|---|
| Este repositorio (documentos/scripts/kits) | `C:\Users\Administrator\Documents\unixnu-nabu-gh` → https://github.com/Lux12138/unixnu-nabu |
| Fork de UniXNU (scripts de compilación del kernel) | `C:\Users\Administrator\Documents\UniXNU` → https://github.com/Lux12138/UniXNU |
| Productos de kernel/payload/imágenes | `C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs` (**todos los nabu-xnu64-*.img están aquí**)|
| WSL (compilación del firmware) | `/root/Mu-Silicium` (EDK2/Mu UEFI), `/root/UniXNU` (upstream), `/root/xnu` (clon parcial de xnu como referencia)|
| fastboot/adb | `C:\platform-tools` |
| git | `C:\Users\Administrator\.dsh-tools\PortableGit\cmd\git.exe` |
| gh | `C:\Program Files\GitHub CLI\gh.exe` |

> ⚠️ Fuente de errores: existen tanto `Documents\unixnu-nabu-kernel-ufs` como `Desktop\unixnu-nabu-kernel-ufs`,
> **la imagen de boot está en la de Desktop**; varias veces hubo `No such file` por escribir mal la ruta.

---

## 1. Cadena ya funcionando (verificada paso a paso en el teléfono)

```
fastboot boot → BootShim → Mu UEFI → menú de UniXNU → payload FAT de la partición cust
→ DarwinBoot → lee el kernel de 51 MB → analiza el Mach-O → lee el ADT → comprueba el ADT
→ asigna la ventana → mapea segmentos → ExitBootServices → salta al kernel XNU ✅
```

Log del teléfono real (foto):
```
UNIXNU: runxnu entry vol=A2142798 path=\EFI\UniXNU\Payloads\kernel.macho cfgerr=
DB1 kernel read  Success size=0x3345000      (≈51,2 MB; ojo, se imprime en hexadecimal)
DB2 kernel parse Success
DB3 adt read     Success size=0x330C
DB4 adt ok  win=0x130000000 keep=0 rd=ffffffffffffffff
DB6 va=0xFFFFFFF00427C000 pa=0x8007C000 args=0xC4364000
DARWINBOOT: inputs validated; exiting boot services
still-there kernel entry code ran
```

---

## 2. Trampas duras y soluciones (en el orden en que se pisaron)

### Trampa 1: Load Error
- Se creyó que "el ABL modificado desactivaba boot"; **la causa real era el cable USB**
- Un cable malo pierde datos al transferir imágenes grandes → el ABL falla al verificar
- ✅ Cambiar al cable de datos original + puerto USB trasero de la placa base

### Trampa 2: rango del tamaño del ramdisk
| ramdisk | ABL | UEFI |
|---|---|---|
| 16 MB | ❌ Load Error | — |
| 32 MB | ✅ | ✅ |
| 64 MB | ✅ | ✅ |
| 96 MB | ✅ | ❌ pantalla negra |

→ **rango utilizable 32–64 MB**; `header_version=1`, `page_size=2048`

### Trampa 3: hay que reiniciar el dispositivo antes de cada boot
El **primer boot tras un reinicio es el que más veces funciona**; boots seguidos dan Load Error (restos en el download buffer).

### Trampa 4: el kernel no puede ir en el volumen de firmware (presupuesto de descompresión de PEI)
| FVMAIN | Resultado |
|---|---|
| 8 MB (original) | ✅ |
| 62 MB (kernel sin comprimir) | ❌ |
| 15 MB (kernel LZMA) | ❌ |

Límite del propio FD: **3 MB utilizables; con 32 MB/60 MB no arranca nada** (`[uefi_fd] size` se queda en `0x300000`).

### Trampa 5: no hay ningún volumen FAT (la más fundamental)
El firmware trae su pila de almacenamiento (`UFSDxe`/`PartitionDxe`/`DiskIoDxe`/`Fat`), pero las particiones de Android son todas ext4/f2fs →
`Config->Volume=NULL` → DarwinBoot da `NULL input`.

✅ **El payload se flashea en la partición `cust`** (1 GB, partición de recursos de fábrica, no afecta al arranque del sistema):
```
\EFI\UniXNU\unixnu.toml
\EFI\UniXNU\Payloads\kernel.macho        (51MB)
\EFI\UniXNU\Payloads\kernel.macho.adt    (13KB)
```
⚠️ Antes de flashear, comprueba que está completo: `Sending 'cust' (65536 KB)`; una vez se truncó a 1,2 MB y se manifestó como `config error: unixnu.toml line 1: expected '='`

### Trampa 6: DarwinBoot no se despacha (dispatch)
✅ Se incorpora al **primer** bloque `APRIORI DXE { }` de `Include/APRIORI.inc` (un bloque nuevo da `GenFv ERROR 2000`)

### Trampa 7: el marcador de RAMDisk del ADT debe coincidir con la realidad
```c
else if (RamdiskOffset != MAX_UINTN) { Status = EFI_UNSUPPORTED; goto Fail; }
```
✅ Al generar el ADT **no uses** `--data-ramdisk` / `--packed-data-ramdisk`, de modo que quede `rd=ffffffffffffffff keep=0`

### Trampa 8: disposición de `boot_args.Video` (⚠️ la conclusión anterior era errónea, ver abajo)
`BootVideo.h` escribía originalmente `[base, 1, rowBytes, width, height, 32]`, y entonces se creyó que XNU esperaba
`[base, rowBytes, width, height, depth, display]`
→ el kernel leía `rowBytes=1 / depth=2560` → `initialize_screen()` falla → **vuelve en silencio al puerto serie**
✅ Se reescribió una vez (y se cambiaron a la vez los índices con que DarwinBoot dibuja); DarwinBoot informa `base=0x50000000 row=6400 1600x2560 depth=32`

> **⚠️ Corrección (verificada en esta sesión)**: el `boot_args.Video` de xnu-10063.141.1 **no es un array**, sino
> `struct Boot_Video`, definido en `pexpert/pexpert/arm64/boot.h:31-38`:
> ```c
> struct Boot_Video {
>     unsigned long v_baseAddr;  // [0]
>     unsigned long v_display;   // [1]  ← ¡el 2.º! no el último
>     unsigned long v_rowBytes;  // [2]
>     unsigned long v_width;     // [3]
>     unsigned long v_height;    // [4]
>     unsigned long v_depth;     // [5]
> };
> ```
> y `pexpert/arm/pe_init.c:419-429` toma los valores uno a uno **por nombre de campo**:
> ```c
> PE_state.video.v_baseAddr = boot_args_ptr->Video.v_baseAddr;
> PE_state.video.v_display  = boot_args_ptr->Video.v_display;
> PE_state.video.v_rowBytes = boot_args_ptr->Video.v_rowBytes;
> PE_state.video.v_width    = ...->Video.v_width;
> PE_state.video.v_height   = ...->Video.v_height;
> PE_state.video.v_depth    = (...->Video.v_depth >> 0) & 0xFF;   // la profundidad son solo los 8 bits bajos
> PE_state.video.v_rotate   = (v_depth>>8 & 0xFF) + (v_depth>>24 & 0xFF);
> PE_state.video.v_scale    = ((v_depth>>16) & 0xFF) + 1;
> ```
> Es decir: **si DarwinBoot escribiera de verdad `[base, rowBytes, width, height, depth, display]`**,
> el kernel leería `v_display=rowBytes (distinto de 0, así que va por gráficos), v_rowBytes=width,
> v_width=height, v_height=depth, v_depth=bits de display todos 0` ——
> **todos los parámetros de vídeo desalineados**; `vcattach` recibe mal el ancho de fila y el ancho/alto, y el resultado es "no hay salida".
>
> ⇒ **Esta es** la causa real de "el kernel muere en silencio antes de `PE_create_console`" (verificado, no es una suposición):
> `vcattach` recibe `v_rowBytes=1600` (real 6400), `v_width=2560` (real 1600),
> `v_height=32` (real 2560), `v_depth=0` —— los parámetros de pantalla están todos mal y la consola gráfica no arranca.
>
> **Cadena de evidencias**:
> 1. `pexpert/arm/pe_init.c:419-429` lee **por nombre de campo** (no por índice de array)
> 2. `pexpert/pexpert/arm64/boot.h:31-38` el orden de la estructura = base, display, rowBytes, width, height, depth
> 3. El `git diff` de `drivers/DarwinBoot/DarwinBootPkg/Driver/BootVideo.h` muestra:
>    **la versión upstream original ya tenía el orden correcto de la estructura**
>    ```c
>    Video[0] = FrameBufferBase;              Video[1] = 1;      // v_display
>    Video[2] = RowBytes;                     Video[3] = HorizontalResolution;
>    Video[4] = VerticalResolution;           Video[5] = 32;
>    ```
>    y la "corrección de la trampa 8" lo cambió a `Video[1]=RowBytes … Video[5]=0` —— **se cambió en el sentido contrario**.
> 4. El `DiagDraw` de `DarwinBoot.c` se cambió a la vez para usar `Video[1]` como rowBytes (también al revés),
>    mientras que `Video[2]*Video[4]` (tamaño del FB), `Video[3]/Video[4]` (ancho/alto) y otros puntos de llamada
>    **siempre tuvieron la semántica de estructura y no se tocaron** —— lo que prueba que el código original era correcto.
>
> ✅ **Revertido (WSL `/root/UniXNU/drivers/DarwinBoot`)**:
> - `git checkout -- DarwinBootPkg/Driver/BootVideo.h` → se restaura el orden de estructura de upstream
> - Los 5 índices de `DiagDraw` vuelven a `Video[2]`=rowBytes / `Video[3]`=width / `Video[4]`=height
> - Los demás puntos de llamada (`Video[2]*Video[4]`=tamaño del FB, `Video[3]`/`Video[4]`=ancho/alto,
>   base/width/height/row/depth del log) **ya tenían semántica de estructura y no hay que cambiarlos**
>
> ⇒ **Conclusión: el DarwinBoot del HEAD de upstream es correcto. No hacen falta parches ni fork.**
> Lo único que hay que hacer es "no volver a cambiarlo al orden de array". Tras recompilar el firmware, la disposición de `Video` coincide con la del kernel.

### Trampa 11: el kernel **no puede** escribir en el framebuffer al principio (la sonda llegó a matar al kernel)
Tras `ExitBootServices`, el framebuffer **sigue siendo escribible y visible** (demostrado con la sonda bicolor de DarwinBoot, ver abajo),
pero eso es **bajo las tablas de páginas de UEFI**. Después de `start.s`, el kernel usa sus propias tablas, y la **dirección física** `0x50000000`
no está mapeada en ellas → la escritura en `arm_init` **provoca un fault directamente**,
el kernel muere ahí mismo y la pantalla se queda igual, igual que si "el kernel no se hubiera ejecutado".

**Síntomas característicos**: hay log, hay pantalla, no hay bloques, y el comportamiento no cambia antes y después de añadir la marca (porque la propia marca es la causa de la muerte).

✅ **Solución (UniXNU `9ad570c`)**:
- `nabu_mark_init()` solo limpia el estado y **no toca el fb**
- `NABU_MARK(n)` solo anota el acierto en un mapa de bits en RAM `g_hits` (la RAM siempre es escribible)
- `nabu_mark_rebind()` se engancha **al final de `vcattach()`** y repone en pantalla de una vez los aciertos

> ⚠️ **¡El punto de mapeo no es `PE_create_console()`!** (la primera versión erró aquí y se flashearon dos rondas en balde)
> - `vcattach()` lo invoca **`PE_init_printf(TRUE)`** (`pexpert/gen/pe_gen.c:135-140`)
> - y en `arm_init` solo hay `PE_init_printf(FALSE)` → **durante `arm_init` el fb nunca está mapeado**
> - El mapeo real está en `vcattach` → `initialize_screen(NULL, kPEAcquireScreen)`
>   → `ml_io_map_unmappable(...)` (`osfmk/console/video_console.c:2880`)
>
> Por eso el punto de inyección está antes del `}` final de `vcattach`, con una **guarda de VA de kernel**:
> ```c
> if ((unsigned long)PE_state.video.v_baseAddr >= 0xFFFFFFF000000000UL) {
>     nabu_mark_rebind((const unsigned long *)&PE_state.video);
> }
> ```
> Si la dirección aún no parece una VA de kernel, **se omite**; aunque se adivine mal, no hay fault.
>
> **Conclusión colateral**: como el rebind (después de la consola) llegó a matar al kernel, se demuestra que **el kernel sí llega
> hasta después de `PE_create_console`**, mucho más lejos de lo que anotaba el HANDOVER anterior ("muere antes de `PE_create_console`").

### Trampa 12: la barra verde en la parte superior de la pantalla **no** significa "kernel entry code ran"
El mensaje de `DarwinBoot.c` es incorrecto. Evidencias:
1. `BootShim.S` no tiene en todo su texto código que dibuje una barra verde; tampoco aparece en Mu-Silicium / UniXNU
2. En las cuatro fotos, la altura de la barra verde y el tamaño de fuente guardan una **proporción constante**; solo cambia la distancia de la foto
3. El experimento de sondas A/B confirmó que los bloques rojo/verde dibujados **debajo** de la barra verde se muestran con normalidad

⇒ La barra verde es solo un banner fijo del lado UEFI y **no sirve** como progreso del kernel. Para interpretar, mira solo los bloques.

#### Experimento de sondas A/B (decisivo)
En DarwinBoot, en un mismo arranque se dibujan dos bloques (ambos bajo la barra verde, y=800):
| Sonda | Momento | Resultado |
|---|---|---|
| Bloque verde (700,800) | **antes** de `ExitBootServices` | ✅ aparece |
| Bloque rojo (32,800) | **después** de `ExitBootServices` | ✅ aparece |

⇒ Tras el traspaso, el fb es escribible y visible; **se descarta** la vía de "framebuffer inválido".

### Trampa 10: `nabu_mark_init(args->Video)` no compila (corregido)
```
error: passing 'Boot_Video' (aka 'struct Boot_Video') to parameter of
       incompatible type 'const unsigned long long *'
```
✅ Se cambia a pasar como "flujo de `unsigned long`": `nabu_mark_init((const unsigned long *)&args->Video);`
La implementación de las marcas admite las dos interpretaciones (prioridad al orden de estructura, con retroceso automático al orden de array antiguo),
y **dibuja un bloque rojo** cuando `depth&0xFF != 32` o se usó el retroceso, para que el problema de disposición se vea directamente en pantalla.

### Trampa 9: el EL no es el problema, no lo investigues más
- Rama `EL1_OR_EL2` de `ModuleEntryPoint.S`: si empieza en EL2 se queda en EL2, si empieza en EL1 se queda en EL1
- Medido `EL=4` (EL1) → **el ABL entrega en EL1**, **subir de EL es imposible**
- El propio código de DarwinBoot exige EL1, coherente con el diseño de UniXNU ✅

---

## 3. El único bloqueo actual (en curso)

El kernel ya salta y se ejecuta, pero **muere en silencio antes de `PE_create_console()` (arm_init.c:616)** y en pantalla no hay ninguna salida del kernel.

### Solución: dibujar "bloques de control" en la entrada más temprana del kernel
Principio: `boot_args.Video` ya da el framebuffer; el kernel dibuja bloques de color de 48×48 al principio de `arm_init()`, **sin necesitar consola ni fuente de texto**.

| Nº de bloques | Color | Significado |
|---|---|---|
| 0 | — | muere en la entrada en ensamblador/MMU, o el framebuffer no está mapeado |
| 1 | blanco | entró en `arm_init` |
| 2 | amarillo | pasó `PE_init_platform` |
| 3 | cian | pasó `PE_create_console` ← **la consola funciona** |
| 4 | verde | pasó el segundo `PE_init_platform` |

Los bloques empiezan en `(32,32)`, con 64 px de separación y una franja negra de fondo encima.

### Ya implementado
- `kits/nabu/nabu_early_mark.{c,h}` (C puro, pasa `gcc -fsyntax-only`)
- `scripts/inject-early-marks.sh` (**solo de referencia**: inyecta en cualquier árbol xnu dado; el CI ya no lo llama)
- ✅ **La implementación autorizada está en** `UniXNU/scripts/build-xnu-4k-baseline.sh` (commit `18ca785`):
  se inyecta en `.cache/xnu-work` tras el bucle de parches, con pre-clean reentrante, anclas independientes de la indentación y MARK1–MARK4 completos

> El paso "inyectar en `refer/xnu`" de `.github/workflows/build-kernel.yml` se eliminó: ese árbol no participa en la compilación
> y dejarlo solo confunde; ahora hay un paso nuevo tras la compilación, `Verify early checkpoint marks`, que imprime automáticamente
> tres pruebas: `marks inserted` / `WARN: mark? anchor` / comprobación de símbolos con `llvm-nm`.

### Historia de las trampas de la inyección (¡importante!)
1. Paso independiente del CI → `refer/xnu` no existe (**la fuente refer se descarga de forma diferida**, comentario de `tree.py`: `fetched when a step needs it`)
2. Dentro del paso Build kernel → `ls refer/` muestra `total 0`
3. En el script de compilación, pero **dentro del bloque `if [ ! -d refer/xnu/.git ]; then`** → el CI ya lo había descargado, el bloque se salta
4. Sacado del bloque if → `Set-Content -Encoding UTF8` de PowerShell escribe **BOM+CRLF** → bash no lo analiza (se normalizó a LF con Python)
5. Inyectado en `refer/xnu` → no surte efecto, **el directorio de compilación real es `.cache/xnu-work`** ✅ ya cambiado
6. Cambiado a `.cache/xnu-work` → el CI **falla**: la inyección modificó `arm_init.c` y **choca** con los parches oficiales de `git apply` posteriores
   → ✅ **corregido**: el bloque de inyección se movió **después** del `done` del bucle de parches (línea 113), con limpieza inversa pre-clean
   (`native-4k-user-abi.patch` y `zzz-boot-progress.patch` modifican `osfmk/arm/arm_init.c`;
   `source-machine-layer.patch` modifica `osfmk/conf/files.arm64`)
7. El ancla era un `assert`, y se comprobó que es **sensible a la indentación** (`\t` vs espacios) y daba falsos resultados
   → ✅ cambiado a una **expresión regular independiente de la indentación** + si no hay coincidencia solo `print WARN` sin interrumpir; si falta el ancla de `#include`, retrocede a la última línea `#include`
8. La compilación del kernel ejecuta el script **dos veces** (bootstrap pass genera los compile records → pasada real), sobre el mismo `.cache/xnu-work`
   → ✅ el pre-clean hace la inyección reentrante (`MKU` primero deshace, `MKP` luego inyecta), así que aunque el CI reutilice el árbol de trabajo no se contamina el contexto de los parches

### Comprobar que la inyección ha surtido efecto
- ❌ No mires solo la consola del CI (el stdout del script se redirige al producto)
- ✅ Mira `kernel.log` del producto: `marks inserted` / `nabu_early_mark`
- ✅ Comprueba que el binario `kernel.macho` contiene `nabu_mark`

---

## 4. Anclas clave del código fuente (xnu-10063.141.1 / commit d8b80295, verificadas)

| Archivo | Línea | Contenido |
|---|---|---|
| `osfmk/arm/arm_init.c` | 199 | `void arm_init(boot_args * args);` |
| | 370 | `PE_init_platform(FALSE, args);` ← ancla de MARK1 |
| | 616 | `PE_create_console();` ← ancla de MARK2/3 |
| | 619 | `PE_init_printf(FALSE);` |
| `pexpert/arm/pe_init.c` | 425-436 | rellena `PE_state.video` desde `boot_args.Video` (arm64 genérico)|
| `pexpert/gen/pe_gen.c` | 135 | `PE_init_printf(boolean)` (`TRUE`→vcattach)|
| `osfmk/conf/files.arm64` | 51 | `osfmk/arm/arm_init.c	optional config_pmap_ppl`(para archivos nuevos, añadir con este formato)|

Script de compilación `UniXNU/scripts/build-xnu-4k-baseline.sh` (números de línea según el commit `18ca785`):

| Línea | Contenido |
|---|---|
| 13 | `if [ ! -d refer/xnu/.git ]; then git clone ...; fi` (fuente refer, **no participa en la compilación**)|
| 21 | `if [ ! -d .cache/xnu-work/.git ]; then git clone --shared refer/xnu .cache/xnu-work; fi` |
| 40-66 | **pre-clean de nabu (MKU)**: deshace la inyección anterior, para que el contexto de `apply --check` de los parches esté limpio |
| 76-81 | **bucle de aplicación de parches** (el `done` está en la línea 81)|
| 82-169 | **bloque de inyección de nabu (MKP)**: escribe `nabu_early_mark.{c,h}` + `files.arm64` + los cuatro MARK de `arm_init.c` |
| 992 | `make -C .cache/xnu-work "${XNU_BUILD_TARGET:-build}" ...` (la compilación real)|

> ⚠️ La inyección **debe** ir después del bucle de parches: `native-4k-user-abi.patch` y `zzz-boot-progress.patch` modifican ambos
> `osfmk/arm/arm_init.c`, y `source-machine-layer.patch` modifica `osfmk/conf/files.arm64`.
> Además, la compilación del kernel ejecuta el script **dos veces** (bootstrap pass + pasada formal), así que el pre-clean es imprescindible, no opcional.

---

## 5. Datos de hardware medidos

| Elemento | Valor |
|---|---|
| DRAM | 12 GiB |
| **RPMh RSC** | **`0x18200000` ×3 bank** |
| IPCC/apss_shared | `0x17c00000` (**solo es un mailbox, no es RPMh**)|
| cmd-db / SMEM | `0x85f20000` / `0x86000000` |
| SPMI / PDC | `0xc440000` / `0xb220000` |
| GCC | `0x100000 +0x1f0000` (`#clock-cells=1`)|
| UFS HC / PHY | `0x1d84000` (ice `0x1d90000`) / `0x1d87000` |
| Base de tiempos | 19200000 Hz |
| Partición cust | `0x40000000` (1 GB)|
| CPU | `reg 0x0..0x700`, psci, kryo485 (coincide con `--cpu-regs` del ADT)|
| Alimentación del UFS | vcc 2.504–2.95V(L10A), vccq 1.2V(L9A), vccq2 1.8V(S4A), vdda-phy 0.88V(L5A), vdda-pll 1.2V(L3C) |
| PMIC | pm8150=0, pm8150b=2, pm8150l=4 (**sin pm8009**)|

---

## 6. Referencia rápida de comandos

```bash
# ADT (sin marcador de RAMDisk, por favor)
python3 UniXNU/scripts/make-nabu-adt.py --dram-size 0x300000000 \
  --owned-memory-size 0x130000000 --cpu-regs "0,0x100,0x200,0x300,0x400,0x500,0x600,0x700" \
  --ipad-identity --chip-id 0x207 --unique-chip-id 0x0000000000000001 --output kernel.macho.adt

# cust payload
bash unixnu-nabu-gh/scripts/make-cust-payload.sh kernel.macho kernel.macho.adt cust-payload.img

# Flashear + arrancar (hace falta fastboot)
fastboot flash cust cust-payload.img
fastboot boot C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\nabu-xnu64-T.img

# Firmware (WSL)
cd /root/Mu-Silicium && python3 build_uefi.py -d nabu -r DEBUG
```

**Recuperación**: mantener pulsado el botón de encendido 10 s; en todo el proceso **solo se ha escrito `cust`**, `abl`/`xbl`/`bootloader` nunca se han flasheado.

---

## 7. Lo primero de la próxima sesión (en orden)

> ✅ 1–3 completados (commit `18ca785` @ UniXNU main). **Continuar desde el paso 4.**

| # | Tarea | Estado |
|---|---|---|
| 1 | Mover el bloque de inyección después del `done` del bucle de parches | ✅ hecho |
| 2 | Hacer el `assert` tolerante (y pasarlo a regex independiente de la indentación) | ✅ hecho |
| 3 | Validar con `bash -n` → commit/push de UniXNU → lanzar el CI | ✅ hecho (`18ca785`)|
| 3.5 | Primer CI: arreglar el conflicto de inyección → sale un error de compilación → arreglar de nuevo | ✅ hecho (ver abajo)|
| 4 | Descargar los productos → revisar logs/símbolos | ✅ hecho (run `39612555624` success)|
| 4.5 | Buscar la causa real: desalineación de la disposición de `boot_args.Video` | ✅ confirmado (ver corrección de la trampa 8)|
| 5 | Recompilar el firmware (arreglar Video) → rehacer el cust payload → flashear + arrancar → contar bloques | 🔄 primera ronda flasheada: bloques **0** (ver abajo), MARK1 etc. bajados a la tercera ronda del kernel |
| 6 | Si hay 0 bloques: cambiar a "escribir RAM escribible + relectura por DarwinBoot" | ⬜ se dispara por condición |

### Paso 5, medido en el teléfono (ronda a ronda)

| Ronda | Cambio en el kernel | Resultado en pantalla | Conclusión |
|---|---|---|---|
| 1 | MARK1–4, escribiendo directamente en el fb físico | **0 bloques** | la propia sonda hace fault (fb sin mapear) |
| 2 | MARK1 bajado a la entrada de `arm_init` | 0 bloques | igual que antes |
| 3 | Al principio solo se anota en RAM, rebind tras `PE_create_console` | 0 bloques | el fb sigue sin mapear en ese momento |
| 4 | rebind enganchado al final de `vcattach` | 0 bloques | el kernel no llegó a `vcattach` |
| 5 | **`nabu_mark_map()` crea su propio mapeo con `ml_io_map_unmappable`** | **5 bloques** ✅ | el tronco de `arm_init` funciona |
| 6 | redibujado en tiempo real + MARK7 (antes de `machine_startup`) + MARK8/9 (`kernel_bootstrap`)| **8 bloques** ✅✅ | **supera `machine_startup` y entra en `kernel_bootstrap()`** |

**Lectura clave de la ronda 6**: 8 bloques = MARK1–8 todos acertados, es decir
`arm_init` termina completo → `machine_startup(args)` → entra en `kernel_bootstrap()`.
Pero el bloque 9 (después de `PE_init_iokit()`) no aparece, y **en pantalla no hay texto del kernel** ——
⇒ el punto de muerte queda acotado **dentro de `PE_init_iokit()`**, es decir, en la cadena `PE_init_printf(TRUE)` → `vcattach`
→ `initialize_screen(NULL, kPEAcquireScreen)`, la ruta de inicialización de la consola.

> ⚠️ **Esto desmonta por completo la antigua conclusión de que "el kernel muere en silencio antes de `PE_create_console`".**
> El kernel en realidad llega a `kernel_bootstrap`; que antes no se viera ninguna salida se debía simplemente a que
> **nadie mapeaba la memoria de vídeo al principio del kernel** (ver trampa 11).

**Medida tomada**: se añaden 4 sondas nuevas para trocear el interior de `PE_init_iokit` (UniXNU `cb2a921`):
```
10 = entrada de PE_init_iokit
11 = entrada de vcattach
12 = después de initialize_screen(NULL, kPEAcquireScreen)
13 = después de PE_init_printf(TRUE)
```

Semántica de los bloques (v4: redibujado en tiempo real, 13 ranuras):

> ⚠️ La barra verde no es señal de progreso (ver trampa 12). Cuenta solo los bloques.
> Los bloques se **refrescan al instante** en cada acierto, así que lo que muestra la pantalla es la posición más reciente del kernel.

| Nº de bloques | Hasta dónde llegó |
|---|---|
| 0 | principio de `arm_init` (o antes de `nabu_mark_map`)|
| 5 | después del segundo `PE_init_platform` |
| 6 | `arm_vm_init` + automapeo correcto |
| 7 | antes de `machine_startup(args)` → **`arm_init` terminó** |
| 8 | entra en `kernel_bootstrap()` |
| 9 | pasó `PE_init_iokit()` |
| 10 | entra en `PE_init_iokit()` |
| 11 | entra en `vcattach()` |
| 12 | después de `initialize_screen(kPEAcquireScreen)` |
| 13 | después de `PE_init_printf(TRUE)` → **consola totalmente lista** |
| bloque rojo extra | un bloque rojo independiente arriba a la derecha = disposición/profundidad de Video sospechosa (el firmware no surtió efecto)|

### Resultado de la verificación del paso 4 (run `39612555624`, success)
```
① Conflicto de parches: ningún patch failed / does not apply
② Registro de la inyección:
   kernel-bootstrap.log : marks inserted: MARK1=True MARK2=True MARK3=True MARK4=True
   kernel.log           : nabu pre-clean: reverted .cache/xnu-work/osfmk/arm/arm_init.c
                          nabu pre-clean: reverted .cache/xnu-work/osfmk/conf/files.arm64
                          marks inserted: MARK1=True MARK2=True MARK3=True MARK4=True
   ← dos pasadas del script, el pre-clean funciona y la segunda pasada reinyecta correctamente: validación del diseño superada
③ Símbolos (kernel.macho 53.760.000 B): _nabu_mark ×6, _nabu_mark_init ×2
```

### Paso 3.5: resultado del primer CI (queda registrado)
- run `39611266428` **failure**, pero **ya no por conflicto de parches**: el conflicto está arreglado.
  Evidencia: en todo el `apply --check` de `zzz-boot-progress.patch` no hay ningún `patch failed`.
- El nuevo error es de compilación:
  `arm_init.c:373: passing 'Boot_Video' to parameter of incompatible type 'const unsigned long long *'`
  → ver la **trampa 10**: `args->Video` es una `struct Boot_Video`, no un array.
- A la vez, mirando `pexpert/arm/pe_init.c:419-429`, se vio que **la conclusión de la trampa 8 era errónea** (display está en la 2.ª posición),
  y ya se anotó la corrección y los puntos por verificar en esa sección.
- Solución: pasar `(const unsigned long *)&args->Video`; la implementación se adapta a las dos disposiciones y dibuja un bloque rojo si la disposición es sospechosa.

### Paso 4: confirmar que la inyección de verdad entró en el binario

Cómo lanzarlo (workflow_dispatch, `build-kernel.yml`):
```bash
gh workflow run build-kernel.yml --repo Lux12138/unixnu-nabu
gh run watch --repo Lux12138/unixnu-nabu
gh run download --repo Lux12138/unixnu-nabu -n kernel-nabu -D /tmp/nabu-kernel
```

Tres pruebas (**el paso nuevo `Verify early checkpoint marks` ya imprime estas tres**):

```bash
# ① Los parches incrementales se aplican limpios (sin apply failed = la inyección no choca con los parches)
grep -a 'error: patch failed' /tmp/nabu-kernel/logs/kernel.log || echo clean
# ② Registro de la inyección: deben verse MARK1..MARK4 todos True
grep -a 'marks inserted' /tmp/nabu-kernel/logs/kernel.log
# Esperado: marks inserted: MARK1=True MARK2=True MARK3=True MARK4=True
# Si sale WARN: mark? anchor missing → deriva de las anclas del código fuente upstream; revisar de nuevo con los números de línea de la sección 4
# ③ Los símbolos realmente enlazados en el kernel
xcrun llvm-nm --defined-only /tmp/nabu-kernel/kernel/kernel.macho | grep nabu_mark
# Esperado: dos líneas _nabu_mark / _nabu_mark_init (T)
```
⚠️ **No mires solo la consola del CI** (el stdout del script se redirige a `out/nabu/logs/kernel.log`);
`kernel-bootstrap.log` es el log del bootstrap pass; la inyección corre en las dos pasadas y en las dos debería aparecer `marks inserted`.

### Paso 5: flashear + contar bloques

**5a. Recompilar el firmware (¡hay que hacerlo primero! si no, Video sigue mal)**
DarwinBoot ya se revirtió a la versión correcta de upstream; recompilar basta para que surta efecto:
```bash
wsl -e bash
cd /root/Mu-Silicium && python3 build_uefi.py -d nabu -r DEBUG
cd /root/UniXNU && ./unixnu bootimg        # empaqueta como imagen de boot de Android (UEFI FD + dtb + ramdisk)
```
El producto se numera con el nombre ya existente, incrementando (el último actual es `nabu-xnu64-T.img`, el siguiente sugerido `-U`), y se deja en
`C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\`.

**5b. Rehacer el cust payload (lado del kernel)**
```bash
# ADT (sin marcador de RAMDisk, por favor)
python3 UniXNU/scripts/make-nabu-adt.py --dram-size 0x300000000 \
  --owned-memory-size 0x130000000 --cpu-regs "0,0x100,0x200,0x300,0x400,0x500,0x600,0x700" \
  --ipad-identity --chip-id 0x207 --unique-chip-id 0x0000000000000001 --output kernel.macho.adt
bash unixnu-nabu-gh/scripts/make-cust-payload.sh kernel.macho kernel.macho.adt cust-payload.img
```
`kernel.macho` usa el producto del CI `C:\Temp\nabu-ok\kernel\kernel.macho` (run `39612555624`).

**5c. Flashear + arrancar** (antes de flashear, comprobar `Sending 'cust' (65536 KB)`, que no se trunque)
```bash
fastboot flash cust cust-payload.img
fastboot boot C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\nabu-xnu64-U.img
```
**Antes de cada boot, reiniciar con pulsación larga de encendido de 10 s** (trampa 3).

**Cómo leer la nueva señal del "bloque rojo"**: si arriba a la derecha (ranura 8) aparece un bloque rojo, significa que el kernel cree que
`Video` sigue sin cuadrar —— eso implicaría que el firmware no se recompiló bien, no un problema del framebuffer.

Semántica de los bloques (v3: al principio solo se anota en RAM y se reproduce de una vez tras `PE_create_console`; desde `(32,32)`, separación de 64 px):

> ⚠️ **La barra verde no es señal de progreso** (ver trampa 12). Cuenta solo los bloques.
> Como antes de `PE_create_console` no se puede escribir en pantalla, **"0 bloques" solo indica "muere antes de la consola" y
> no se puede afinar más** —— es un límite duro del medio de observación actual.

| Nº de bloques | Color | Significado |
|---|---|---|
| **0** | — | muere antes de `PE_create_console()` (principio de `arm_init` / firma JOP / `arm_vm_init`)|
| 4 | blanco amarillo cian verde | llegó a `PE_create_console()`, y pasaron 1/2/3 (caso normal)|
| 5 | +magenta | todo pasó, incluido el segundo `PE_init_platform` |
| bloque rojo extra | rojo | un bloque rojo independiente arriba a la derecha = disposición/profundidad de Video sospechosa (el firmware no surtió efecto, o actuó el fallback)|
| solo 1~3 bloques | — | no debería ocurrir: la reproducción dibuja todos los aciertos; que falten números indica un problema de mapa de bits/geometría |

### Paso 6 (solo con 0 bloques)
La dirección base de `Video` no está mapeada en las tablas de páginas tempranas del kernel (el `start.s` del kernel reutiliza las tablas de UEFI, pero solo garantiza las zonas de RAM),
así que la escritura de `nabu_mark_init` hace fault. Dos direcciones:
1. **Primero confirmar si el fb de verdad no es escribible**: que DarwinBoot, tras `ExitBootServices` y antes de `DarwinEnter`,
   dibuje un "bloque de relevo" con el fb que ya tiene verificado. Si el bloque de relevo aparece en pantalla pero **no** hay MARK1 ⇒ el fb no es escribible desde el lado del kernel (diagnóstico confirmado).
2. **Pasar por RAM**: al principio de `arm_init` escribir solo variables estáticas (bss siempre es escribible),
   y tras `arm_vm_init` mapear el fb con pmap y volcar de una vez todos los puntos de control a la pantalla.

### Alternativas (si la vía de las marcas se bloquea)
- B: DarwinBoot entrega en EL2 (requiere cambio de EL, cambio grande)
- C: UART a 115200 (requiere desmontar; **el usuario no lo acepta**)
- D: consola temprana del kernel por GOP (`vcattach` solo surte efecto después de `PE_create_console`, no salva muertes más tempranas)

---

## 8. Índice de documentos

| Archivo | Contenido |
|---|---|
| `README.md` | Parte de guerra: cadena + trampas + reproducción |
| `HANDOVER.md` | Este documento |
| `docs/firmware-patches.md` | Lista de cambios de firmware + intentos inútiles conocidos |
| `docs/nabu-dts-extract.md` | Destilado del DTS (corrección de direcciones RPMh + UFS/PMIC/relojes)|
| `docs/pmgr-plan.md` | Plan de PMGR + camino mínimo de lectura de RPMh |
| `docs/early-console-plan.md` | Consola temprana + mecanismo de bloques de control |
| `docs/prior-art-0xDive-ios-nabu.md` | Comparación con proyectos similares |
| `kits/nabu/NabuPlatformPower.cpp` | Esqueleto de PMGR |
| `kits/nabu/nabu_early_mark.{c,h}` | Bloques de control (C puro)|
| `scripts/make-cust-payload.sh` | Generación del cust payload |
| `scripts/inject-early-marks.sh` | Inyector de marcas |

---

## 13. El arranque de xnu-10063 se detiene en mig_init (conclusión de localización de esta ronda)

### Cadena de hechos (todos con evidencia de hardware)

| Punto de control | Lectura | Significado |
|---|---|---|
| `NABU_MARK(8)` | 8 | entra en `kernel_bootstrap` |
| numeración automática 18..44 | 26 | llegó a `mac_policy_init` |
| 45 / 46 | **45** | `mac_policy_init()` devolvió; cae dentro de `kernel_startup_initialize_upto(STARTUP_SUB_MACH_IPC)` |
| subsistema + entrada | 13 / 27 | la entrada 28 de la ronda MACH_IPC |
| hash de `cur->func` | 56 → 50 | con las dos versiones de toolchain se asigna de forma única a **`_mig_init`** |
| índice `mig_e[i]` | **0** | `_mach_vm_subsystem` |
| índice de rutina j | **0** | `mach_vm_allocate` (msgid 4800) |
| hash del puntero stub | 19 | `0x...153c >> 4 & 0x3F`, coincide con el volcado estático → kstub **distinto de cero** |

`mig_init()` tiene cinco ramas de panic; la que se dispara es:

```c
panic("kroutine must have precise size %d %d", mig_e[i]->start, j);
```

es decir, `max_reply_msg == 0` de `mach_vm_allocate`. Pero en `mach_vm.defs` tiene parámetros `out`,
y el descriptor **debería** traer el tamaño de la respuesta —— así que es que **el paso de generación de mig en la compilación perdió ese campo**; no es un problema de la definición.

### Ya descartado

- Registro duplicado: 31 ops, 31 `iko_op_type` únicos
- Desbordamiento de array: `__init_entry_set` 95856 B = 3994×24; `ipc_kobject_ops_array` 1728 B = 54×32
- Versión de toolchain: tras `picked: /Applications/Xcode_15.0.app` sigue parándose en el mismo panic
- Nuestros parches: el conjunto de parches no tiene ningún cambio de `IKOT` / `mig`
- Paso de RAM entre boots: `keep probe` en el segundo arranque sigue siendo `fresh RAM`, la DRAM no se conserva

### Tratamiento adoptado

Cambiar el panic por un retroceso:

```c
} else {
    mig_buckets[pos].kreply_size = mig_e[i]->maxsize;   /* valor conservador */
    mig_buckets[pos].kreply_desc_cnt =
        mig_e[i]->kroutine[j].reply_descr_count;
}
```

Es un **rodeo pragmático** (un tamaño demasiado grande solo malgasta memoria, mientras que el panic pierde todo el arranque). Efectos secundarios y riesgos:
el búfer de respuesta se asigna con el máximo del subsistema (4140 B en mach_vm); si más adelante hay presión de kalloc o
un fallo al analizar replies, hay que sospechar primero de aquí.

### Experiencia con las sondas (para no volver a pisarla)

- El framebuffer está **sin mapear** durante todo `arm_init`; solo se puede escribir después de crear el mapeo propio con `ml_io_map_unmappable`
- La barra de bloques tiene como máximo 24 casillas y se dibuja **de menor a mayor** número, así que los tardíos 45/46/50/60 se desplazan (ya se cambió a dibujar los 24 últimos)
- `draw_number` debe borrar la casilla antes de dibujar, o quedan restos de las decenas (50 se leería como 54/58)
- Un solo número no da información suficiente: la tabla de arranque de mach tiene 1736 entradas (`subsystem <= 14`), y ZALLOC ocupa 767 por sí solo,
  se cambió a doble casilla "subsistema + nº de entrada", y luego se subió a cuatro casillas `nabu_mark_quad`
---

## 14. Superado mach IPC: el kernel entra en la carga de kexts de IOKit

### Hito

Hoy, por primera vez, se pasa `kernel_startup_initialize_upto(STARTUP_SUB_MACH_IPC)`.
La conclusión anterior ("se detiene en el panic de kroutine de mig_init") era correcta, pero **solo era la primera capa**.

### Cadena completa de causas de la muerte (cada capa respaldada por lecturas de pantalla)

| Capa | Fenómeno | Evidencia | Tratamiento |
|---|---|---|---|
| 1 | `panic("kroutine must have precise size")` | i=0/j=0 → `mach_vm_allocate`, `max_reply_msg=0` | retroceso al `maxsize` del subsistema |
| 2 | el `printf` final dispara kprintf | tras quitarlo sigue parándose | borrar ese printf de diagnóstico |
| 3 | falso positivo de `assert3u(grp,<,TASK_GRP_COUNT)` | panel `line=283 x=120675180 y=32` | en realidad era la capa siguiente |
| 4 | **`reply_descr_count <= IPC_KOBJECT_RDESC_MAX`** | texto original de la aserción + `x=120675180` (bits bajos de un puntero), `y=32` | **desactivar las dos aserciones de recuento de descriptores** |
| 5 | **`OSMetaClass: Kext %s class %s is a duplicate`** | texto original en verde | problema actual (capa de prelink)|

La capa 4 es la culpable real: el offset de los campos de `kern_routine_descriptor` no coincide con esta compilación,
`reply_descr_count` lee los bits bajos de un puntero (0x731_4xxx), y la aserción falla sí o sí.
Esto también explica por qué antes todos los volcados estáticos "por más que se calculara el layout no cuadraba".

### Evolución de los medios de observación (aprendizaje clave de ingeniería)

1. **Automapeo del framebuffer físico**: `nabu_mark_map()`, utilizable después de `arm_vm_init`
2. **Sondas de bloques / números**: al principio sirvieron para localizar `mig_init`
3. **Fuente 5x7 + `nabu_mark_text()`**: dibuja directamente en pantalla la cadena de formato del panic
4. **El hook de panic analiza varargs**: dibuja la expresión de la aserción, el nº de línea y los valores reales de x/y
5. Todas las sondas se bajaron a la mitad inferior de la pantalla (`y≈1000+`), dejando la superior para consola/texto

> Lección: **no vuelvas a adivinar valores con casillas de dos dígitos**. `x=5180/y=32` fue una lectura errónea,
> en realidad era `x=120675180/y=32`, y la conclusión es totalmente distinta. Usa `nabu_mark_num()` para imprimir texto decimal.

### Caminos probados que no sirvieron

- **Consola temprana** (llamar a `PE_init_printf(TRUE)` en `arm_init`):
  `vcattach` queda semiinicializado y luego `gc_update_color` choca con `assert(gc_ops.update_color)`
  (`video_console.c:1226`) —— autolesión, ya eliminado
- **Paso de RAM entre boots**: la DRAM no se conserva al reiniciar, `keep probe` en la segunda vez sigue siendo `fresh RAM`
- **Puerto serie UART**: xnu tiene el framework `serial_console`, pero falta la dirección base del UART de la plataforma + hace falta cablear hardware
- **Log por USB** (lo que hacen Pagani/giulia): solo existe tras entrar al userspace, inútil al principio

### Trampas de la cadena de compilación (se perdieron más de una docena de rondas)

- `unixnu tree` ya aplicó los patch y el script de compilación los vuelve a aplicar → `patch does not apply`,
  y el error se lo traga `|| true`. **Solución: antes de aplicar los parches, `git reset --hard` + `clean -fdq`**
- `source-machine-layer.patch` añade 4 `amcc_rorgn_*.c` a `files.arm64`,
  archivos que no existen en 10063 → `Error 2` en la fase de lista de archivos, sin diagnóstico
- `pexpert/arm/` no tiene la raíz de include de osfmk, y `<arm/nabu_early_mark.h>` no se resuelve;
  hay que usar `"../../osfmk/arm/nabu_early_mark.h"`
- El kernel **no tiene `strstr`**, y el enlazado fallaría; se sustituye por comparación de prefijos literales
- El código inyectado que hace referencia a variables `static` de `nabu_early_mark.c` (como `g_h`) no compila,
  solo se pueden usar coordenadas fijas

### Problema actual

`OSMetaClass: Kext %s class %s is a duplicate; kext %s already has a class with this name`

IOKit informa durante la inicialización de nombres de clase de kext duplicados. Es un problema de la capa de **empaquetado prelink** (submódulo `kits/NativePrelink`),
no de la lógica del kernel. Siguiente paso: leer los nombres de kext duplicados y cotejar con la lista de prelink.

---

## 15. Entorno de iteración rápida con QEMU (montado hoy)

### Por qué

Una compilación del kernel en el CI tarda **8,1 minutos** (el 87 % de los 9,3 minutos totales es compilación),
y cada ronda de flasheo añade 2 minutos más + fotografiar e interpretar a mano. Sin un host macOS no se puede compilar en local,
así que solo se puede llevar a local la mitad de **validación**: **QEMU, 45 segundos por ronda, con log serie directamente legible**.

### Componentes (todos ya en su sitio)

| Pieza | Ubicación | Explicación |
|---|---|---|
| QEMU | `C:\Program Files\qemu` | 11.1.0, con `edk2-aarch64-code.fd` |
| Mu_Basecore | `UniXNU/package/Mu_Basecore` | rama de EDK2 `release/202608`, 8,3k archivos |
| UniXNU.efi | `package/Build/Out/AARCH64-DEBUG/UniXNU.efi` | 94 KB, `./build.sh -b DEBUG -t GCC` |
| DarwinBoot.efi | `package/Build/UniXNU/DEBUG_GCC/AARCH64/DarwinBoot.efi` | 36 KB, aporta el XNU loader protocol |
| ESP | `C:\Temp\qemu-test\esp` | `EFI/BOOT/BOOTAA64.EFI` + `EFI/UniXNU/{Drivers,Payloads,unixnu.toml}` |

### Trampas clave

- En `build.sh`, `PACKAGES_PATH` solo tenía originalmente `package` + `edk2`;
  `DarwinBootPkg` está bajo `drivers/DarwinBoot/`, así que hace falta
  `$ROOT/../drivers/DarwinBoot:$ROOT/../drivers:$ROOT:$EDK2`
- La ruta de `Test/Validation.inf` en `DarwinBoot.dsc` está escrita relativa a `DarwinBootPkg/`,
  pero el archivo real está en `drivers/DarwinBoot/Test/`, no se resuelve y se eliminó
- Cuando el `build` de EDK2 falla solo imprime `- Failed -`; hace falta `-d 9` para ver la causa
- **Al llamar desde WSL al QEMU de Windows, las rutas en la línea de comandos de QEMU deben tener forma de Windows**
  (`C:/...`); solo el archivo de log se queda en el lado WSL
- Con `-m 4096` DarwinBoot da `boot refused: Out of Resources`; **con 8 GB basta**

### Hechos ya verificados en QEMU

```
UNIXNU: UniXNU 0.1.0 starting as application, firmware EDK II
UNIXNU: driver \EFI\UniXNU\Drivers\DarwinBoot.efi (config): started
DARWINBOOT: loader v2 installed EL1
DARWINBOOT: ARM64 va=0xFFFFFFF00427C000 pa=0x4807C000 entry=0x4B1EB488
DARWINBOOT: hand-off to the kernel
```

**El código de entrada del kernel corrió (barra verde arriba), y el trace de excepciones muestra que el kernel se ejecuta con normalidad:**
852 excepciones, todas las del final son `Taking exception 5 [IRQ]`, `SPSR 0x205` (EL1h),
**ningún abort**. Así que el kernel está vivo en QEMU; solo que no saca nada por el puerto serie.

### Pendiente

- Tras añadir a `nabu_mark_putc` un **tee a PL011** (`0x9000000`), QEMU podrá capturar el texto del kernel;
  en el teléfono real esa dirección no está mapeada, la escritura se la traga el manejo de fallos de página y no afecta a la vía del fb
- Una vez funcione el serie, el trace de `-d int` ya no será necesario

### Totalmente automático

- `C:\Temp\auto\run.ps1` —— una pasada: espera la última compilación → descarga → flashea ESP → QEMU → resumen
- `C:\Temp\auto\loop.ps1` —— bucle: lanza compilación → espera → descarga → QEMU → análisis → siguiente ronda,
  el log de cada ronda se guarda en `C:\Temp\auto\rounds\<n>\`
- El CI ya tiene `actions/cache` (`xnu-work/build`); desde la próxima vez la compilación debería ser incremental


---

## 16. Log del kernel por QEMU funcionando (logro de esta noche)

### Resultado

El QEMU local ya puede imprimir **logs reales del kernel**:

```
NABU                                                          <- marca de que el mapeo del UART funcionó
kprintf initialized
Serial mode specified: 00000003
initialize_screen: b=23C7A0000, w=320, h=258, r=0xC80
pe_arm_init_interrupts: args: 0xfffffff007a62860
corecrypto_kext_start (tracing disabled)
FIPSPOST_KEXT ... all tests PASSED (1690 ms)
corecrypto_kext_start completed successfully
ulock_initialize>thread_max=1536, ull_hash_buckets=512        <- se detiene aquí
```

Una ronda de verificación dura **40 segundos** (CI 8,5 minutos + flasheo 2 minutos + foto).

### Cuatro obstáculos (cada uno con una causa raíz clara)

| # | Síntoma | Causa raíz |
|---|---|---|
| 1 | ningún log | la condición de `kprintf` es `if (!disable_serial_output && !disable_kprintf_output)`, **los dos son true por defecto**; limpiar solo uno no sirve |
| 2 | tras limpiarlos sigue sin log | `PE_init_kprintf` corre en `STARTUP(KPRINTF)`, **antes del mapeo del fb**; decidir por "fb listo" hace que el hook nunca se instale |
| 3 | el tag UART tampoco aparece | `0x9000000` es una **dirección física**, la VM del kernel no la tiene mapeada y el fault de la escritura se traga; hay que mapearla antes con `ml_io_map_unmappable` |
| 4 | Undefined Instruction | el `-cpu cortex-a72` de QEMU no reconoce `MSR S3_0_C4_C1_4` (0xd500419f); **solo sirve `-cpu max`** |

### El límite de QEMU

Se atasca en `zalloc_permanent` de `ulock_initialize()` (`STARTUP(EARLY_BOOT, STARTUP_RANK_FIRST)`).
**El teléfono real supera este paso** (el real ya llegó a IOKit), así que se debe a que a QEMU le falta hardware o a diferencias de
disposición de memoria, no a un defecto del kernel. **La profundidad de validación de QEMU termina aquí**.

### Qué se puede reutilizar

| Pieza | Ubicación |
|---|---|
| Mu_Basecore | `UniXNU/package/Mu_Basecore` (`release/202608`)|
| UniXNU.efi | `package/Build/Out/AARCH64-DEBUG/UniXNU.efi` |
| DarwinBoot.efi | `package/Build/UniXNU/DEBUG_GCC/AARCH64/DarwinBoot.efi` |
| ESP | `C:\Temp\auto\esp` |
| Device tree de QEMU | `C:\Temp\auto\qemu.adt` |
| Captura de pantalla | `C:\Temp\auto\shot.ps1` |
| Automatización total | `C:\Temp\auto\loop.ps1` |

**Línea de comandos de QEMU (no puede faltar ninguna opción)**

```
-M virt -cpu max -m 8192 -smp 1
-drive if=pflash,format=raw,readonly=on,file=edk2-aarch64-code.fd
-drive if=none,id=esp,format=raw,readonly=on,file=fat:<directorio ESP>
-device virtio-blk-pci,drive=esp -device ramfb
-display none -serial file:<log>
```

- `-cpu max`: cortex-a72 choca con una instrucción indefinida
- `-m 8192`: con 4096 DarwinBoot da `boot refused: Out of Resources`
- La ESP se usa como **directorio** (`fat:`), no hace falta crear una imagen con dd/mkfs.vfat
- Al llamar desde WSL al QEMU de Windows, **las rutas de la línea de comandos deben tener la forma `C:/...`**

### El device tree tiene que ser el de QEMU, no el de nabu

Se genera con `make-dt.py --armvirt --armcpu --smp 1`. Con el `.adt` de nabu se obtiene:

```
*** CPU id 256 from CPU ordinal 1 'reg' property is out of range [0..7]
*** Missing 'interrupts' property for CPU 0
*** Missing 'function-ipi_dispatch' property for CPU 0
```

### La esencia de IOSurface en el teléfono real (ya aclarada)

Atascarse tras `IOsurfaceRoot:installMemoryRegions()` **no es una aserción ni falta de memoria**, sino que
**el kext cerrado de IOSurface de Apple no funciona en plataformas que no son de Apple**.

La solución de ios-nabu es **reescribir**: `NabuSurface.cpp` (IOCoreSurfaceRoot) +
`NabuFramebuffer.cpp` (AppleCLCD), registrados en `iokit/KernelConfigTables.cpp`,
y en `NabuPlatformExpert` se crean nubs para los hijos de `arm-io`. **Trabajo de semanas**.
