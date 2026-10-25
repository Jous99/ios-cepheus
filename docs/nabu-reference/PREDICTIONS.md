# Lista de previsiones (actualizada el 2026-10-22 21:58)

Ordenadas según el orden de ejecución de `bsd_init.c` / `bsdinit_task()`. Cuando se choque con una, se identifica directamente.

| # | Punto de bloqueo | Condición de disparo | Estado |
|---|---|---|---|
| 1 | `panic("rootvp not authenticated after mounting")` | En no-macOS se fuerza `require_rootauth = TRUE`; la raíz mockfs/ramdisk no tiene firma sealed | ✅ ya corregido de antemano (`zzzz-nabu-unsealed-root.patch`)|
| 2 | `cannot mount root, errno = N` | No hay dispositivo raíz utilizable (NativeUfs desactivado, sin ramdisk)| **pendiente de encontrarlo, el primer hueso duro** |
| 3 | `imageboot_setup` | `CONFIG_IMAGEBOOT` busca una imagen de disco del sistema | por observar |
| 4 | `devfs_kernel_mount("/dev")` | devfs sin inicializar | por observar |
| 5 | `load_init_program` no encuentra init | ver abajo | **el segundo hueso duro** |
| 6 | carrera de loopattach con 8 núcleos | teléfono real multinúcleo; en QEMU se evita con `-smp 1` | conocido |

## Detalle del punto 5 (confirmado)

`kern_exec.c`:

```c
static const char * init_programs[] = ('/usr/appleinternal/sbin/launchd.debug', '/usr/appleinternal/sbin/launchd.development', '/sbin/launchd');
```

Es una compilación DEVELOPMENT, así que el orden es
`launchd.development` → `/sbin/launchd`.
`appleinternal` no existirá, así que **hay que depender de `/sbin/launchd` en el sistema de archivos raíz**.

**Esto significa: una vez que el kernel llega hasta aquí, todo lo demás depende del sistema de archivos raíz.**
No es un problema de lógica del kernel, sino de "si el userland de iOS está instalado o no".

## Prácticas correctas conocidas (para no repetir errores)

- **Los boot-args van en el `[[entry]] args` de `unixnu.toml`**, no en el ADT ni en `make-nabu-adt.py`
- **kprintf necesita desactivar dos interruptores a la vez**: `disable_serial_output` y `disable_kprintf_output`
  (la condición es `if (!disable_serial_output && !disable_kprintf_output)`)
- **`PE_kputc` hay que asignarlo incondicionalmente**: `PE_init_kprintf` corre en `STARTUP(KPRINTF)`, antes del mapeo del fb
- **La instrumentación nueva, siempre con archivos patch**: el script de inyección ha fallado en silencio 5 veces
- **Proteger los headers con `extern "C"`** (cuando los incluye un archivo C++)
- **Includes relativos**: fuera de `osfmk/`, siempre `"../../osfmk/arm/nabu_early_mark.h"`
- **El límite de numeración de sondas** se amplió a 128 (con 64, las de 65+ se descartaban en silencio)

## Hechos verificados en QEMU

- La entrada del kernel funciona (barra verde arriba)
- El trace de excepciones solo tiene IRQ, **ningún abort** → el kernel está vivo en QEMU
- `disable_serial_output=0 / disable_kprintf_output=0 / nabu_mark_putc` están verificados en el binario
- El serie sigue sin texto → se está usando un "tag UART fijo" para distinguir "el UART no escribe" de "no se llegó al kprintf"
- **QEMU no puede reproducir el bloqueo de IOSurface** (eso es IOKit contra hardware real)


## La esencia del bloqueo de IOSurface en el teléfono real (importante)

El `0046-nabu-iosurface-iomfb.patch` de ios-nabu revela la causa: **no usaron el kext de
IOSurface cerrado de Apple**, sino que implementaron por su cuenta:

    iokit/Kernel/arm/NabuSurface.cpp       -> IOCoreSurfaceRoot
    iokit/Kernel/arm/NabuFramebuffer.cpp   -> AppleCLCD

y registran esas dos clases en `iokit/KernelConfigTables.cpp`; además, en `NabuPlatformExpert` crean nubs para
los hijos de `arm-io`, para que los drivers integrados puedan emparejarse.

**Conclusión: el bloqueo tras `IOsurfaceRoot:installMemoryRegions()` no es una aserción ni falta de memoria,
sino que el kext cerrado de IOSurface no funciona en plataformas que no son de Apple.** Superarlo exige reescribir
el driver de surface / framebuffer, un trabajo de semanas, que no se resuelve con una o dos rondas de parches.

Esto también explica por qué ios-nabu tiene 83 parches y tardó varios meses en llegar a SpringBoard.
