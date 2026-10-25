# Consola temprana del kernel por framebuffer (sacar el panic sin desmontar el móvil)

> Documento de la Xiaomi Pad 5 (nabu), traducido al español para referencia. El original en chino está en `docs/original-zh/`.

## El problema

El kernel ya entra en ejecución (`DARWINBOOT: hand-off to the kernel` / `still-there kernel entry code ran`),
pero **no aparece ningún texto de panic en pantalla**, y el control vuelve a UniXNU (se redibuja el menú).

Causa: el `kprintf` temprano de XNU saca por defecto por el **puerto serie**; sin UART es una caja negra.
Y el UART exige desmontar y soldar cables, y en este punto no existen ni `fastboot` ni ADB.

## Condiciones favorables que ya existen

DarwinBoot ya entrega al kernel la información de la memoria de vídeo (`Video[6]` de los boot args):

```
video base=0x50000000   1600x2560   row 6400 bytes   32 bpp
```

Es decir, `PE_state.video` ya tiene `v_baseAddr / v_rowBytes / v_width / v_height / v_depth`.
El framebuffer es memoria normal mapeada, escribible desde EL1: **no hace falta hardware adicional**.

## Plan: llevar una consola de framebuffer mínima

No depende de `video_console` de Apple (ese subsistema sirve sobre todo a la pantalla de arranque en x86 y no está
activo en ARM). Escribir un backend `putc` autocontenido es lo de menor riesgo.

```
scripts/nabu-early-fb-console/
├── nabu_fb_console.c    ~150 líneas
│     - fuente de puntos 8x16 (ASCII 32..126; se puede empezar solo con 0x20..0x7E)
│     - nabu_fb_putc(c): gestiona \n / \r / desplazamiento
│     - escritura de píxeles: base + rowBytes*y + 4*x, 32 bpp, escribe 0x00FFFFFF
│     - todo se basa en PE_state.video; sin MMIO ni registros
└── inject.py            inyección en tiempo de compilación
```

### Puntos de inyección

1. `PE_init_kprintf()` (`pexpert/gen/pe_gen.c` o la implementación de arm)
   → añadir tras la inicialización:
   ```c
   if (PE_state.video.v_baseAddr != 0) { nabu_fb_init(); }
   ```
2. `vputchar()` (`osfmk/console/printf.c` o el equivalente en pexpert)
   → añadir tras la salida serie: `nabu_fb_putc(c);`

### Restricciones de seguridad

- `v_baseAddr == 0`, o `v_depth != 32`, o ancho/alto anómalos → **no activar nada** (return directo).
- Solo escrituras de memoria normal; no se lee ni se escribe ningún registro del SoC.
- Sin asignación de memoria (al principio no hay malloc): arrays estáticos para cursor y color.
- Un fallo nunca hace panic; en el peor caso, "no aparece nada más en pantalla".

## Orden de implementación

1. Obtener el código de xnu (en el CI o clonado en `~/xnu`) y confirmar:
   - la ruta real y el cuerpo de `PE_init_kprintf`
   - la ruta real y la firma de `vputchar`
   - nombre y tipo de los campos de `PE_state.video` (`video_info_t`)
2. Escribir `nabu_fb_console.c` con los nombres reales; pasarle antes `clang -fsyntax-only` en local.
3. `inject.py`: insertar con cadenas ancla; tras insertar, **comprobar que el ancla es única y que la inserción
   tuvo éxito**; si falla, hacer fallar la compilación.
4. Subir al CI para compilar el kernel → rehacer boot.img (mismo flujo que `nabu-xnu64-*.img`) → arrancar en el móvil.
5. Criterio:
   - Aparece texto temprano del kernel / `panic(...)` en pantalla → la consola funciona ✅
   - Sigue viéndose solo el menú de UniXNU → el kernel muere antes de `PE_init_kprintf`
     → adelantar la inicialización del fb (antes de `arm_init` / `machine_startup`), o ponerla en la primera línea
       de la entrada en C tras `Entry.S`.

## Relación con PMGR

Es un **requisito previo**: sin salida temprana, cada paso de PMGR es un cambio a ciegas.
Con la consola funcionando, el ciclo de depuración de PMGR pasa a ser:
editar `NabuPlatformPower.cpp` → compilar → arrancar → ver en pantalla los valores de voltaje/reloj leídos.

---

## Avance medido (2026-10-21 19:49)

### Corregido: array de vídeo desplazado (una de las causas reales)

`DarwinBootPkg/Driver/BootVideo.h` escribía `boot_args.Video[6]` como

```
[0]=base  [1]=1  [2]=rowBytes  [3]=width  [4]=height  [5]=32
```

mientras que XNU (`pexpert/arm/pe_init.c:425`) espera

```
[0]=base  [1]=rowBytes  [2]=width  [3]=height  [4]=depth  [5]=display
```

→ el kernel leía `rowBytes=1 / width=6400 / height=1600 / depth=2560`,
`initialize_screen()` lo daba por fallido → **volvía en silencio al puerto serie** → nunca había salida del kernel en pantalla.

Se corrigió al formato correcto (y los índices que usa DarwinBoot para dibujar su propio texto).
Medido después: `base=0x50000000 row=6400 width=1600 height=2560 depth=32 display=0` ✅

### Pero sigue sin salida del kernel → el kernel muere antes de `PE_create_console`

`PE_create_console()` en `osfmk/arm/arm_init.c:616` es el primer punto donde podría salir texto.
Con los parámetros de vídeo ya correctos y aun así sin salida, significa que **no llega hasta ahí**.

## Primera sospecha actual: el nivel de excepción (EL) de partida no coincide

| Hecho | Explicación |
|---|---|
| La sonda de DarwinBoot mide `EL=4` (= EL1) | Ahora entregamos el kernel **en EL1** |
| El código de DarwinBoot exige `DarwinCurrentEl() == 4` | Fuerza EL1 |
| Cadena real de Apple | **iBoot entrega en EL2 y XNU baja a EL1 por sí mismo** |

Al principio, `arm_init` / `arm_start` de XNU acceden a registros de sistema de EL2
(`HCR_EL2`, `VTCR_EL2`, `VHE`, etc.). **Si el kernel cree estar en EL2 pero está en EL1, la primera instrucción
relacionada provoca una excepción, y todavía no hay ninguna consola inicializada → muerte silenciosa.**
Coincide exactamente con lo observado: parámetros de vídeo correctos, el código de entrada del kernel se ejecutó,
y ni una sola letra.

### Cómo comprobarlo (siguiente paso, una de dos)

**A. Que el kernel hable por sí mismo** (lo más directo)
En la primera línea de `arm_init()` de `osfmk/arm/arm_init.c`, inyectar un `putc` de framebuffer autocontenido
(que solo escriba en la memoria de vídeo a la que apunta `boot_args_ptr->Video`, sin depender de ninguna consola):

```c
nabu_fb_early_init(boot_args_ptr->Video);
nabu_fb_early_puts("arm_init enter\n");
```
Y poner un marcador antes y después de `machine_startup`, `PE_init_platform` y `PE_create_console`:
así se ve con precisión hasta qué línea llega el kernel.

**B. Cambiar DarwinBoot para entregar en EL2**
Cambiar la comprobación `DarwinCurrentEl() != 4` para admitir EL2 (o quitarla), de modo que el kernel arranque
desde EL2 como en la cadena real de Apple. Riesgo: DarwinBoot corre ahora en EL1; para que entregue el control en EL2
hay que hacer un cambio de EL extra (`eret` a EL2), un cambio mayor.

> Se recomienda empezar por A (da más información y tiene menos riesgo) y, una vez localizado el punto de muerte,
> decidir si hace falta B.

---

## Ajuste del plan: primero "bloques de control", sin fuente de texto

Escribir una fuente 8×16 exige ~1500 bytes de datos de puntos, es fácil dibujarla mal y difícil de verificar;
y **localizar el punto de muerte no necesita texto**: basta saber en qué punto de control se llega.

### Mecanismo

`kits/nabu/nabu_early_mark.c`: dibuja **bloques de color de 48×48** en la memoria de vídeo a la que apunta
`boot_args.Video`; no depende de la consola, no asigna memoria, no toca registros, y si los parámetros no son válidos
se rinde en silencio (`depth!=32` / `base==0`).

### Cómo se lee (una fila de bloques arriba a la izquierda)

| Bloques que se ven | Significado |
|---|---|
| **0** | Ni siquiera entró en `arm_init`: muere en la entrada en ensamblador / al montar la MMU |
| **1 (blanco)** | Entró en `arm_init` |
| **2 (amarillo)** | Pasó `PE_init_platform` |
| **3 (cian)** | Pasó `PE_create_console` |
| **4 (verde)** | Pasó `machine_startup` |
| **N en rojo** | Parámetros no válidos (abandonó con seguridad, sin corromper memoria) |

### Puntos de inyección (siguiente ronda, modificando el código fuente de XNU)

```c
// osfmk/arm/arm_init.c : primera línea de arm_init()
nabu_mark_init(boot_args_ptr->Video);
NABU_MARK(1);

// después, uno tras cada paso clave
PE_init_platform(...);   NABU_MARK(2);
PE_create_console();     NABU_MARK(3);
// dentro de machine_startup
```

### Por qué este método es mejor

- ~110 líneas de código, sin datos de puntos: casi imposible "dibujarlo mal".
- Para interpretarlo basta contar bloques; se ve bien en foto o vídeo.
- Un fallo es totalmente seguro (solo escrituras de memoria de vídeo tras comprobar límites).
- Una vez localizada la fase concreta, se decide si hace falta la fuente de texto (para entonces quizá ya no).
