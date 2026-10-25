# Proyecto de referencia: mytiantian001/iPadOS-nabu

> Documento de la Xiaomi Pad 5 (nabu), traducido al español. El original en chino está en `docs/original-zh/`.

> Fuente: https://github.com/mytiantian001/iPadOS-nabu
> Anotado el 2026-10-22 (durante las rondas 6-7 de bring-up de este repo)
> Uso: **comparación con un proyecto del mismo tipo**. No es una dependencia de este repo; es una lista de diferencias.

## 1. Lo que consiguieron (según su propio README)

En la misma **Xiaomi Pad 5 / nabu / SM8150-AC**:

| Parte | Estado |
|---|---|
| Arranque | ABL de stock desbloqueado -> `fastboot boot` de su propio shim -> XNU |
| CPU | 1 núcleo estable; 8 núcleos llegan al userspace |
| Almacenamiento | Driver host UFS propio; el root de iPadOS está en HFS+ en `userdata`, lectura y escritura |
| **Userland** | **Root y shared cache reales de iPad7,3 / iPadOS 16.6.1 (20G81); launchd y los daemons del sistema funcionan** |
| **SpringBoard** | **SpringBoard, backboardd y AKS arrancan** |
| Servicios de pantalla | `AppleCLCD`, `IOMobileFramebuffer`, `IOSurface` registrados; panel de 1600x2560 encendido |
| Botones / AKS | PON y GPIO del PMIC bien; el selector de AKS bien, keybag completado |
| Logs | **Ring persistente** de 4 MiB al final de `userdata`, legible con TWRP |

Sin terminar: que la UI del iPad se muestre de verdad (backboardd solo envía un `SwapEnd` y luego `RequestPowerChange(0)` apaga la pantalla),
acelerador GPU, táctil (Novatek NT36523 por SPI).

## 2. Hecho clave: **ellos también compilan su propio XNU**

- Base del kernel: **xnu-8796 (generación iOS 16)**, de la distribución de código abierto de Apple.
- No es "el kernel original de iPadOS"; el userland sí son binarios reales de iPadOS 16.6.1.
- Número de parches: **83** (`xnu/patches/0001...0083`).

> La conclusión anterior de este repo ("ellos usan el kernel original") era **errónea**; vale lo que dice esta sección.

## 3. Diferencias con este repo (UniXNU / xnu-10063.141.1)

| Elemento | Este repo | Ellos |
|---|---|---|
| Base del kernel | **xnu-10063.141.1** (generación iOS 17 / macOS 14) | **xnu-8796** (generación iOS 16) |
| Userland compatible | Ninguno (10063 no es compatible en ABI con iPadOS 16.6.1) | iPadOS 16.6.1 (20G81) |
| Avance actual | El kernel llega al interior de `kernel_bootstrap()` | SpringBoard / backboardd / AKS |
| Medios de visibilidad | Sonda propia de bloques + números (`nabu_mark`) | Consola de texto `nabu_early` + ring de log persistente |

**Conclusión:** se quiera o no, **para ejecutar el userland real de iPadOS la base del kernel tiene que ser de la generación 8796**.
Aunque 10063 funcionara del todo, no podría cargar el userland de iPadOS 16.6.1.

## 4. Tres parches que se pueden aprovechar directamente

### 4.1 `0010-nabu-early-framebuffer-debug.patch`: consola de texto temprana en el fb

Mecanismo central (comentario original):
```c
/* start.s maps the splash framebuffer VA=PA as Normal Non-Cacheable memory.
 * Stop using that mapping before arm_vm_init tears down bootstrap TTBR0. */
```

- Ya en **`start.s`** se mapea el framebuffer de splash como **VA=PA, Normal Non-Cacheable**
  -> las escrituras surten efecto de inmediato, **sin flush de caché**.
- `nabu_early_putc()` usa `iso_font[256*16]` (mapa de bits 8x16) para **imprimir texto directamente**, con
  desplazamiento de líneas y manejo de `\r`/`\n`; todo el estado es estático, así que se puede usar dentro de `panic()`.
- En `arm_vm_init()`, **antes** de `set_mmu_ttb(invalid_ttep & TTBR_BADDR_MASK)`, se llama a `nabu_early_disable()`.
- Puntos de marca: entrada de `arm_init` / tras `PE_init_platform` / tras `ml_parse_cpu_topology` /
  tras `cpu_bootstrap` / tras `kernel_startup_bootstrap` / tras `cpu_init` / antes de entrar en `arm_vm_init`.

**Qué significa para este repo:** nuestra sonda de bloques solo transmite "el número N";
con texto se imprime directamente "en qué función se atasca", un orden de magnitud más de información.

### 4.2 `0012-nabu-keep-debug-console-after-ttbr0.patch`: conservar la consola tras TTBR0

Indica que "tras cambiar de tablas de páginas desaparece la consola" es una **trampa común** de esta ruta,
no un problema exclusivo nuestro.

### 4.3 `0047-nabu-persistent-console-log.patch`: log en ring persistente

Escribe la salida de la consola en un ring de 4 MiB al final de `userdata`,
que **se lee con TWRP tras reiniciar**; esquiva del todo el problema de "no se ve nada en pantalla".

**Es lo primero que este repo debería copiar:** es más fiable que cualquier sonda en pantalla.

## 5. Otros parches que merece la pena comparar (ordenados por probabilidad de que nos falten)

| parche | Para qué sirve | Por qué importa |
|---|---|---|
| `0004-nabu-machine-config` | Configuración de máquina | Constantes de plataforma |
| `0006-nabu-master-config-open-source-asm-pmap` | Adaptación de asm/pmap de código abierto | También tenemos la serie de pmap de 4K; hay que compararla |
| `0011-nabu-physmap-alignment-padding` | Relleno de alineación del physmap | Relacionado con la inicialización de VM |
| `0016-nabu-device-tree-platform-expert` | DT -> platform expert | Comportamiento tras `PE_init_platform` |
| `0017-nabu-device-tree-virtual-timer-irq` | IRQ del temporizador virtual por DT | **Inicialización del reloj dentro de `kernel_bootstrap`** |
| `0018-nabu-boot-cpu-driver` | Driver de la CPU de arranque | **Igual que el anterior** |
| `0013/0014` kmem rng / hmac prng | Quitan la dependencia de corecrypto | Números aleatorios tempranos |
| `0025/0035/0038` AMFI / entitlements / AKS | Cadena de firmas del userland | Imprescindibles para llegar a SpringBoard |
| `0028/0030/0034/0069/0082` serie UFS | Driver UFS propio | Montaje del root |
| `0046-nabu-iosurface-iomfb` | IOSurface + IOMobileFramebuffer | Servicios de pantalla |
| `0058/0060/0062/0083` HID / keys / touch / NT36523 | Entrada | Bring-up del táctil |

## 6. Recomendaciones de acción (por relación coste-beneficio)

1. **Primero copiar `0047`, el log en ring persistente:** una inversión y, a partir de ahí, todos los problemas de "no se ve" pasan a ser "leer el log".
2. **Después copiar la consola de texto de `0010`:** en `start.s` crear VA=PA Non-Cacheable + `iso_font`.
3. **Evaluar en serio cambiar de base:** pasar el kernel de 10063 a **8796**, alineándose directamente con el contexto de sus 83 parches,
   es el único camino realista al userland. Seguir parcheando sobre 10063 nunca dará el userland de iPadOS 16.6.1.
