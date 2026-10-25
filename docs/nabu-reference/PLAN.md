# Port de XNU a nabu: la ruta de los proyectos de referencia y nuestro plan de viabilidad

Generado: 2026-10-22

---

## I. El tamaño real de los proyectos de referencia

| Proyecto | Versión del kernel | Tamaño de parches | Estado alcanzado |
|---|---|---|---|
| **glebenekt/ios-nabu** | xnu-8796 | **83 parches / 1,58 MB** | XNU en teléfono real, raíz UFS de lectura/escritura, **launchd / SpringBoard / backboardd arrancan**, servicios de pantalla registrados |
| **oosexgang/hackios** | xnu-8796 | **un solo archivo de 119 KB** | pantalla de bloqueo/escritorio/ajustes/Safari funcionan (GPU Adreno)|
| **IssacL04/Pagani** | reutiliza la config BCM2837 | varios | supera las aserciones del asignador, llega a setconf de BSD |
| **Nosotros (Lux12138)** | **xnu-10063** | unos 20 parches propios | **kernel hasta después de bsd_autoconf, atascado en IOSurface** |

**Diferencia clave**: los dos proyectos maduros usan **xnu-8796**; nosotros insistimos en **10063**.
Los parches **no se pueden portar directamente**, pero **la división en etapas y la metodología sí se pueden copiar tal cual**.

---

## II. Los 83 parches de ios-nabu son en realidad un camino de cinco etapas

### Etapa 1: Que el kernel pueda arrancar (0001–0020, 20 parches)

| Parche | Función |
|---|---|
| 0001/0002/0005 | Arreglos de compilación para el clang nuevo |
| **0003/0010/0012** | **consola serie por framebuffer, depuración temprana del fb, conservar la consola tras ttbr0** |
| 0004/0006–0009 | machine config, asm pmap de código abierto, stubs de headers internos de Apple, rellenar huecos de bibliotecas cerradas |
| 0011 | Relleno de alineación del physmap |
| **0013/0014** | **RNG sin depender de corecrypto** (`vm_kern.c`, 97 líneas)|
| **0015** | **trust cache no disponible en tiempo de ejecución** |
| **0016/0017/0018** | **platform expert por device tree, IRQ del timer virtual, driver de la CPU de arranque** |
| **0019** | **pthread integrado** (¡no por prelink!)|
| 0020 | portable AES-CBC |

**Lo que ya tenemos**: el equivalente de 0003/0010/0012 (fb + UART + kprintf, resuelto esta noche).
**Lo que nos falta**: 0013/0014 (RNG), 0015 (trust cache), 0016–0018 (platform expert por DT), **0019 (pthread integrado; nosotros usamos mal el prelink)**.

### Etapa 2: Sistema de archivos raíz (0021–0037, 17 parches)

| Parche | Función |
|---|---|
| **0021** | **mockfs + RAM disk como raíz** (54 líneas)|
| 0022/0024 | raíz ramdisk sin IOMedia, E/S virtual de ramdisk en mockfs |
| 0023/0026/0027/0032/0033 | sha256 / HFS / BearSSL integrados (md5/sha1/sha384/sha512)|
| **0025** | **AMFI propio, sin comprobación de entitlements** (`bsd/kern/nabu_amfi.c`, 192 líneas)|
| **0028/0030/0031/0034** | dispositivo raíz UFS, soporte de escritura, raíz de lectura/escritura, DMA por encima de 4G |
| **0029** | **unsealed root** (24 líneas, cambia el panic por un printf)|
| 0035/0036 | entitlements de AMFI, firma de binarios de plataforma |
| 0037 | bindfs |

**Clave**: ellos **empezaron con mockfs + RAM disk** (0021) y **UFS se añadió después** (0028).
Como nosotros desactivamos NativeUfs, necesitamos justo el camino de 0021.

### Etapa 3: Estabilidad en ejecución (0038–0045, 8 parches)

AppleKeyStore, coredump desactivado, **iowatchdog (0040/0045)**, notas de enlaces HFS,
log corto de exec, **log de crash en consola (0043/0044)**.

**iowatchdog es clave**: sin él, el sistema que no arranca es reiniciado por el watchdog, y parece un "reinicio aleatorio".

### Etapa 4: Pantalla (0046–0049, 4 parches)

| Parche | Función |
|---|---|
| **0046** | **IOSurface + IOMobileFramebuffer propios** (`NabuSurface.cpp` / `NabuFramebuffer.cpp`)|
| **0047** | **log de consola persistente** (anillo de 4 MiB al final de userdata, legible con TWRP)|
| 0048/0049 | devnull tee, traza de IOKit |

**0046 es justo el tramo en el que estamos atascados**; su respuesta fue **no usar el kext cerrado de Apple y escribirlo ellos**.

### Etapa 5: Periféricos de userland (0050–0083, 34 parches)

política de sandbox, muestreo de crashes, rename de HFS, process sampler, AKS, limitación del fb,
**servicios de eventos HID (0058)**, identidad de iPhone (0059),
**drivers de táctil/teclas (0060/0062/0063/0071/0083)**, tamaño de pantalla del iPhone X (0061),
**SMP PSCI (0065/0078)**, console mute, caché de búsqueda de surfaces, aceleración de UFS,
**USB (0072–0077/0081)**, energía de la pantalla, net trace, UFS AES.

---

## III. Nuestra brecha real (corregida tras inventariar los parches reales)

La primera versión exageró la brecha. Tras contar `patches/xnu/`, la situación es:

| Capacidad | Parche nuestro existente | Equivalente en ios-nabu | Estado |
|---|---|---|---|
| Arreglos de compilación de mockfs | `mockfs-typed-allocation` / `mockfs-statfs` / `mockfs-intermediate-lookup` / `mockfs-memory-device-width` / `mockfs-test-file` | 0021/0024 | ✅ **hecho** |
| Tolerancia a la ausencia de block storage | `null-root-media` | 0021 | ✅ **hecho** |
| trust cache en ejecución | `native-trust-cache-runtime` | 0015 | ✅ **hecho** |
| **pthread** | `source-pthread-bootstrap` (añade `bsd/kern/source_pthread_bootstrap.c`)| 0019 | ✅ **ya hay solución** |
| SMP | `native-smp-secondary` | 0065/0078 | ✅ ya está |
| zona de panic | `native-dt-panic-region` | 0066 | ✅ ya está |
| work interval | `native-priv-work-interval` / `native-work-interval-soft-fail` | 0064 | ✅ ya está |
| platform expert / DT | `armvirt-platform-personality` / `source-machine-layer` / `sheng-platform-power` | 0016–0018 | 🟡 parcial |
| **mockfs compilado en el kernel** | `zzzz-nabu-mockfs-root` (añadido en esta ronda)| 0021 | 🟡 **verificándose en esta ronda** |
| **RNG sin depender de corecrypto** | — | 0013/0014 | ❌ falta |
| **iowatchdog** | — | 0040/0045 | ❌ falta |
| **AMFI sin entitlements** | — | 0025 | ❌ falta (o ya cubierto en parte por `public-entitlements-header`)|
| **surface / framebuffer propios** | — | 0046 | ❌ falta, **sigue siendo la mayor brecha** |
| táctil / USB / energía de pantalla | — | 0058–0083 | ❌ falta, a largo plazo |

**Conclusión: la gran mayoría de las etapas 1 y 2 ya la tenemos**; el vacío real está en
**RNG (0013), iowatchdog (0040), AMFI (0025) y surface/framebuffer (0046)**.

---

## IV. Plan de viabilidad

### Opción A: Seguir con 10063 siguiendo las etapas de ios-nabu (recomendada para el objetivo de "ser autónomo")

**Premisa**: aceptar que 10063 es un kernel de iOS 17 y que el riesgo de ABI del userland corre por nuestra cuenta.

**Paso 1: completar lo que queda de la etapa 1 (1-2 días)**

| Acción | Referencia | Explicación |
|---|---|---|
| **Pasar pthread de prelink a integrado** | 0019 | Ahora metemos `com.apple.kec.pthread` en los roots de prelink, y no es la forma correcta |
| RNG sin depender de corecrypto | 0013 | Cambiar `osfmk/vm/vm_kern.c` |
| tolerancia del trust cache en ejecución | 0015 | Sin Image4, no hacer panic |
| platform expert por DT | 0016–0018 | Es el requisito para que los hijos de `arm-io` puedan emparejar drivers |

**Paso 2: conseguir el sistema de archivos raíz (2-3 días)**

| Acción | Referencia | Nuestro cambio concreto |
|---|---|---|
| **Añadir `mockfs` a `FILESYS_BASE`** | 0021 | Nuestro `config/MASTER.arm64.bcm2837` es ahora `[devfs fifo fs_compression config_protect config_mnt_rootsnap config_fse routefs namedstreams bindfs]`, **sin mockfs** |
| **Tolerar la ausencia de `IOBlockStorageDriver`** | 0021 | Hay que quitar el `assert(ioblockstoragedriverClass)` de `iokit/Kernel/IOService.cpp:5261` (al desactivar NativeUfs, esa clase no existe)|
| **unsealed root** | 0029 | ✅ **completado** (`zzzz-nabu-unsealed-root.patch`)|
| RAM disk como raíz | 0021/0022 | algo como `rd=md0`, o usar mockfs directamente como raíz |

**Paso 3: pantalla (1-4 semanas, este es el verdadero obstáculo)**

| Opción | Esfuerzo | Resultado |
|---|---|---|
| **`IOCoreSurfaceRoot` + `AppleCLCD` propios** | 2-4 semanas | Se puede dibujar, abre camino a SpringBoard |
| Renunciar a los gráficos | 0 | El kernel llega a launchd, pero no se ve la imagen |

**Paso 4: runtime + periféricos** (etapas 3/5, varias semanas)

### Opción B: Pasar a 8796, basándose en ios-nabu (recomendada para el objetivo de "ver la imagen")

| Elemento | Explicación |
|---|---|
| Beneficio | **los 83 parches se pueden usar directamente**, mismo dispositivo, mismo iPadOS 16.6.1, ya llega a SpringBoard |
| Coste | Rehacer la cadena de compilación (aunque tenemos la base de `build-kernel-8796.yml` y 87 parches)|
| Riesgo | Hay que entender y mantener 1,58 MB de parches ajenos |
| Tiempo | **en una semana se podría ver lo que ellos tienen**, en vez de varios meses |

### Opción C: Dos líneas en paralelo (la más segura)

- **Línea principal 10063**: seguir validando nuestro propio kernel (QEMU ya llegó al límite, el teléfono llega a IOSurface)
- **Línea secundaria 8796**: usar los parches de ios-nabu para conseguir rápido un sistema **con imagen visible**
- Las dos líneas comparten: entorno QEMU, cadena de CI, herramientas de sondeo

---

## V. Mi recomendación

**Primero los pasos 1 y 2 de la Opción A (3-5 días), porque hay que hacerlos vayamos por el camino que vayamos y su coste es controlable:**

1. **pthread a integrado** (ahora está mal)
2. **añadir mockfs a `FILESYS_BASE`**
3. **quitar `assert(ioblockstoragedriverClass)`**
4. **RAM disk como raíz**

Hechas esas cuatro cosas, hay muchas probabilidades de que el kernel avance hasta **`load_init_program`** (buscar `/sbin/launchd`).
Llegados ahí, se decide entre el **paso 3 de la Opción A (surface propio, varias semanas) y la Opción B (pasar a 8796, una semana)**.

**Razón**: las cuatro primeras cosas son **la parte común de los dos caminos**, y hacerlas no es trabajo perdido; en cambio el tramo de IOSurface es **la bifurcación**,
y conviene decidir después de ver el resultado real de `load_init_program`.

---

## VI. Lista ejecutable de inmediato (ordenada por relación coste-beneficio)

| # | Acción | Referencia | Estimación |
|---|---|---|---|
| 1 | Añadir `mockfs` a `FILESYS_BASE` de `config/MASTER.arm64.bcm2837` | 0021 | 10 minutos |
| 2 | Hacer que el assert de block storage de `IOService.cpp` tolere NULL | 0021 | 10 minutos |
| 3 | Quitar pthread de los roots de prelink y usar la implementación integrada | 0019 | medio día |
| 4 | RNG de `vm_kern.c` sin depender de corecrypto | 0013 | medio día |
| 5 | Que un trust cache no disponible en ejecución no haga panic | 0015 | 2 horas |
| 6 | RAM disk como raíz, verificar que se llega a `load_init_program` | 0021/0022 | 1 día |
| 7 | Decisión: surface propio o pasar a 8796 | — | — |

---

## VII. Valoración honesta

- **Con 1-6 hechos, el kernel probablemente llega a launchd**, pero **no se ve imagen**
- **Ver imagen** exige el tramo de IOSurface, que **no se puede esquivar**
- **ios-nabu lo logró con 83 parches y varios meses**; hacer nosotros el mismo trabajo **no será más rápido**
- Lo único que acelera de forma notable es la **Opción B (pasar a 8796 + tomar prestados los parches)**

**Recomendación final**: primero 1-6 (la parte común, 3-5 días), obtener el resultado real de `load_init_program`,
y después decidir si el tramo de IOSurface lo escribimos nosotros o cambiamos de versión.
