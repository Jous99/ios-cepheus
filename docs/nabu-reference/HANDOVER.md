# Port de XNU a nabu: documento de traspaso

**Fecha del traspaso**: 2026-10-23
**Motivo del traspaso**: una ventana nueva toma el relevo, avanzando en una sola línea
**Estado actual**: línea base reproducible, checkpoint 123

> El camino temprano (el método de inyección de sondas, el descubrimiento de `boot_args.Video`, el origen del método MARK) está en
> **`HANDOVER-legacy.md`**. Este documento es la entrada.

---

## I. El estado actual en treinta segundos

**Qué se puede hacer**: compilar el kernel en el CI (13 minutos) → empaquetar el payload → flashear → en el teléfono real llega a
`IOsurfaceRoot::installMemoryRegions()` y se detiene; en pantalla se ve el checkpoint `123` y 16 bloques de colores.

**Qué no se puede hacer**: no se monta el sistema de archivos raíz, `launchd` no arranca, no hay imagen.

**Siguiente paso**: primero confirmar si ese "se detiene" es un callejón sin salida real o solo un corte del log (sección V).

---

## II. Seis hechos duros que hay que conocer

### 1. Hay que desactivar los dos interruptores del log del kernel

```c
// pe_kprintf.c
SECURITY_READ_ONLY_LATE(bool) disable_serial_output  = false;  // hay que cambiarlo
SECURITY_READ_ONLY_LATE(bool) disable_kprintf_output = false;  // hay que cambiarlo
...
if (!disable_serial_output && !disable_kprintf_output) { ... }
```

**Los dos valen `true` por defecto**; cambiar solo uno no produce ninguna salida.

### 2. `PE_kputc` hay que asignarlo incondicionalmente

`PE_init_kprintf` corre en `STARTUP(KPRINTF)`, **antes** del mapeo del framebuffer. Por eso no se puede escribir
`if (nabu_console_fb_ready()) PE_kputc = nabu_mark_putc;` —— la condición es siempre falsa y el hook nunca se instala.

### 3. El mapeo del UART en `0x9000000` solo sirve en QEMU

Este es el **verdadero culpable del checkpoint 50**. `0x9000000` es un PL011 en QEMU virt, y en SM8150 es otro registro.
`ml_io_map_unmappable` **devuelve éxito en ambos**, y al escribir el primer carácter en el hardware real se cuelga.

Solución actual: decidir por el tamaño del panel (QEMU 800x600 / nabu 1600x2560) y mapear solo cuando `w <= 1024`.

### 4. El ADT debe tener el nodo `RAMDisk`

Si no, DarwinBoot da `boot refused: Compromised Data`:

```
/chosen/memory-map/RAMDisk   16 bytes, las dos mitades a 0
```

`make-nabu-adt.py --data-ramdisk` lo genera. El `[payload.adt]` de `board.toml` **solo tiene
`packed_data_ramdisk`, no el `data_ramdisk` normal** —— por el flujo oficial, esto es un hueco.

### 5. Los nuevos avisos de Xcode 26.0.1 hay que suprimirlos en tres sitios

`-Wunnecessary-virtual-specifier` se convierte en error con `-Weverything -Werror`; lo dispara `OSSymbol.h`.
Hay tres sitios independientes, cada uno con su propia lista de flags:

| Sitio | Tratamiento |
|---|---|
| `WARNFLAGS_STD` de `makedefs/MakeInc.def` | `build-xnu-4k-baseline.sh` lo inyecta directamente |
| la llamada a make de `installhdrs` | pasar `CFLAGS_EXTRA` |
| `build-arm-driver.py` / `audit-storage-interface.py` | cada uno añade sus `-Wno-*` |

### 6. La compilación en frío de `kernel.py` corre dos veces

La primera pasada solo genera el compile record y **vacía a propósito** 5 variables. Cualquier gate de "línea base válida" salta en la primera pasada.
Solución actual: al principio de `build-xnu-4k-baseline.sh`, si no existe `startup.o.json`, se degrada todo.

---

## III. Línea base reproducible

| Elemento | Valor |
|---|---|
| Compilación | `39905065571` / 13 minutos / success |
| Kernel | `kernel.macho` 49,2 MB |
| runner | `macos-26` + Xcode 26.6 |
| defconfig | **9 interruptores** |
| `[kernel] archives` | **8** |
| prelink roots | 20 |
| Rama | `main` (siempre compilable y flasheable)|

**Comandos de recuperación**:
```bash
gh run list --repo Lux12138/unixnu-nabu --limit 1 --workflow build-kernel.yml
gh run download <id> --repo Lux12138/unixnu-nabu -n kernel-nabu -D C:\Temp\nabu-base
# gh run download falla a menudo; usa la API directamente:
#   curl.exe -sL -H "Authorization: token $(gh auth token)" -o out.zip \
#     https://api.github.com/repos/Lux12138/unixnu-nabu/actions/artifacts/<AID>/zip
wsl -e bash -c 'KM=/mnt/c/Temp/nabu-base/kernel/kernel.macho bash /mnt/c/Temp/payload2.sh'
cd C:\platform-tools
.\fastboot.exe flash cust C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\cust-payload.img
.\fastboot.exe boot C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs\nabu-xnu64-Z.img
```

---

## IV. La mayor lección de hoy

> **Tratar "activar todas las funciones oficiales" como pagar una deuda costó una docena de rondas de compilación.**

`CONFIG_XNU_BOOT_PROGRESS` / `NATIVE_UFS` / `NATIVE_AES` / `VIRTIO_BLOCK` / `OWNER_ROOT_AUDIT`
**No son interruptores**, sino un conjunto entero de líneas base válidas que dependen unas de otras:

- La implementación de `boot-progress` está en `UniXNU-sheng/kits/sheng/BootProgress.c` (82 KB) + 3 sondas ≈ **136 KB**
- Su builder (`build-boot-progress.py`) **no existe ni en el fork ni en el upstream de UniXNU**
- Al activarlo salta la cadena de gates: AES closure → CPU/pthread → owner crypto → virtio archive, **arreglas uno y sale otro**
- El bootstrap pass de `kernel.py` vacía a propósito estas variables → el gate **choca sí o sí** en la compilación en frío

**Reglas que se fijaron**:
1. **No cambiar defconfig a mitad del bring-up**
2. **Si depurar la cadena de compilación pasa de 2 rondas, retroceder**
3. **`main` siempre compilable**

---

## V. Siguientes pasos (en orden, sin saltarse ninguno)

### Paso 1: descartar la posibilidad de "corte del log" (medio día)

**La hipótesis actual puede ser errónea.** Siempre creímos que IOSurface era un callejón sin salida, pero **nunca verificamos si el kernel seguía corriendo**.

```c
bsd_autoconf();                              // ahora se atasca dentro de esto
kprintf("NABU: bsd_autoconf returned\n");    // añade esta línea
```

- **Sale algo** → el kernel sigue vivo, IOSurface solo era un corte del log → **pasar directamente al paso 2**
- **No sale nada** → se confirma el callejón sin salida → ir al paso 3

### Paso 2: sistema de archivos raíz (1-2 semanas)

Según `/guide/userdata` + `/concepts/userdata`:

```
1. añadir "OS" y "Cryptex1,SystemOS" al fetch de [ipsw] de board.toml   ← ya añadido, sin verificar
2. ./unixnu ipsw fetch          # baja dos componentes, varios GB
3. ./unixnu build userdata      # manifiesto SHNGROOT + dos ventanas
4. en [payload.adt] poner root_match_volume_uuid = <UUID del volumen OS>
5. fastboot flash userdata out/nabu/userdata/userdata-root.img
6. observar si se monta y si arranca launchd
```

**Sabido**: los LBA de `[userdata]` ya se midieron hace tiempo (`first_lba = 0x288C40` /
`last_lba = 0x77BF3FA` / `lba_bytes = 4096`).

### Paso 3: pantalla (3-4 semanas, solo después del paso 2)

Siguiendo `UniXNU-sheng`: `IOCoreSurfaceRoot` + `AppleCLCD` propios, registrados en
`iokit/KernelConfigTables.cpp`, y en el platform expert crear nubs para los hijos de `arm-io`.

**No hacer este paso primero** —— resuelve "si se ve", no "si arranca".

---

## VI. Material de referencia

| Referencia | Uso |
|---|---|
| **`UniXNU-sheng`** | **La única referencia correcta**: ejemplo completo de roots / archives / defconfig |
| `UniXNU/UniXNU` | El framework en sí; nuestro fork va 163 commits por detrás y no se puede cambiar sin más (`-mach_msg2`)|
| `glebenekt/ios-nabu` | Mismo dispositivo, iPadOS 16.6.1, 83 parches hasta SpringBoard |
| `unixnu.com` | Documentación oficial |

**Dos puntos engañosos de la documentación** (ya pisados):
1. `/guide/debugging` presenta `boot-progress` como función general, pero en realidad es de sheng, de 136 KB
2. La imagen `macos-26` **no tiene** Xcode 26.6, solo 26.0 / 26.0.1

---

## VII. Lista de herramientas

| Herramienta | Uso |
|---|---|
| `C:\Temp\auto\watch.ps1` | sondeo de la compilación cada minuto |
| `C:\Temp\payload2.sh` | empaqueta el payload (**ojo**: llama a mano a `make-nabu-adt.py`, saltándose el `build payload` oficial)|
| `C:\Temp\auto\shot.ps1` | arranque de QEMU + captura de pantalla |
| `C:\Temp\findsym.py` | búsqueda inversa de símbolos del kernel |

**Parámetros de QEMU (no puede faltar ninguno)**:
```
-M virt -cpu max -m 8192 -smp 1
-drive if=pflash,...,file=edk2-aarch64-code.fd
-drive if=none,id=esp,...,file=fat:<directorio ESP>
-device virtio-blk-pci,drive=esp -device ramfb
-display none -serial file:<log>
```
`-cpu max` (cortex-a72 no reconoce `MSR S3_0_C4_C1_4`); `-m 8192` (con 4096 DarwinBoot da
`Out of Resources`).

---

## VIII. Mapa de archivos

| Archivo | Función |
|---|---|
| `board.toml` | Configuración de la placa: prelink roots / archives / userdata / payload |
| `configs/nabu_defconfig` | 9 interruptores (**no añadir por añadir**)|
| `patches/xnu/*.patch` | Parches del kernel, se aplican por orden de nombre |
| `.github/workflows/build-kernel.yml` | CI (17 pasos, incluido `build payload`)|
| `STATUS.md` | Resumen del estado actual |
| `FLOW.md` | Diagrama de flujo (siete etapas + dos rutas)|
| `HANDOVER-legacy.md` | Camino temprano (origen del método de sondas)|

**Dependencias externas**:
- `C:\Users\Administrator\Documents\UniXNU` — clon local del repo `UniXNU`; **el CI usa en realidad la versión que se sube (push) al fork** (esto es importante: cambiar lo local sin push, el CI no lo ve)
- `C:\Users\Administrator\Desktop\unixnu-nabu-kernel-ufs` — directorio de trabajo del payload y de la boot image

---

## IX. El primer comando de la ventana nueva

```powershell
cd C:\Users\Administrator\Documents\unixnu-nabu-gh
git log --oneline -10
Get-Content STATUS.md | Select-Object -First 60
gh run list --repo Lux12138/unixnu-nabu --limit 3 --workflow build-kernel.yml
```

**Luego, empezar por el primer paso de la sección V.**
