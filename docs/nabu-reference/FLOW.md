# Diagrama de flujo del bring-up de nabu

Generado: 2026-10-23

## I. Resumen de las siete etapas (según la división oficial `/porting/bring-up`)

```
                        ┌─────────────────────────────────────────────┐
                        │  Stage 1  Firmware UEFI                     │
                        │  Mu UEFI arranca y el framebuffer da salida  │
                        └────────────────────┬────────────────────────┘
                                             │ ✅ superada
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 2  Menú de UniXNU                    │
                        │  Lee unixnu.toml y lista las entradas        │
                        └────────────────────┬────────────────────────┘
                                             │ ✅ superada
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 3  Payload                           │
                        │  kernel.macho + .adt en su sitio             │
                        └────────────────────┬────────────────────────┘
                                             │ ✅ superada
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 4  DarwinBoot                        │
                        │ Valida kernel/ADT/trustcache → ExitBootServices│
                        └────────────────────┬────────────────────────┘
                                             │ ✅ superada (el nodo RAMDisk es la clave)
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 5  Entrada kernel → platform expert  │
                        │  Logs, sondas, inicialización de IOKit       │
                        └────────────────────┬────────────────────────┘
                                             │ 🟡 en curso
                                             │ checkpoint 123
                                             │ atascado en IOSurface
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 6  Almacenamiento y raíz              │
                        │  block driver → volumen → raíz → launchd     │
                        └────────────────────┬────────────────────────┘
                                             │ ⬜ sin empezar  ← Ruta A
                        ┌────────────────────▼────────────────────────┐
                        │  Stage 7  Espacio de usuario                 │
                        │  launchd → SpringBoard → escritorio          │
                        └─────────────────────────────────────────────┘
                                             ▲
                                             │ ⬜ a largo plazo  ← la Ruta B es su requisito previo
```

## II. Dentro de la Stage 5: dónde estamos parados

```
arm_init
   │
   ├── nabu_mark_map (mapeo del fb) ✅
   │      └── UART tee: en QEMU sirve / en el teléfono está desactivado (0x9000000 en SM8150 es otro registro) ✅
   │
   ├── bucle STARTUP (el checkpoint 50 es la entrada del bucle)
   │      │
   │      ├── EARLY_BOOT / ulock_initialize        ✅ checkpoint 123
   │      ├── ml_processor_register                ✅
   │      ├── corecrypto POST (todo PASSED)        ✅
   │      ├── 32 autopruebas de SKYWALK            ✅
   │      ├── bsd_autoconf → kminit                ✅
   │      └── IOsurfaceRoot::installMemoryRegions  🛑 parado aquí
   │
   └── (después debería venir) setconf → vfs_mountroot → load_init_program
```

## III. Las dos interpretaciones del bloqueo actual

```
                     parado en estas dos líneas:
    IOsurfaceRoot::installMemoryRegions()
    IOSurface disallowing global lookups
                              │
              ┌───────────────┴───────────────┐
              │                               │
     ┌────────▼─────────┐          ┌──────────▼──────────┐
     │ A: sin salida     │          │ B: log cortado       │
     │                  │          │                     │
     │ IOSurface cerrado│          │ El kernel sigue     │
     │ el kext no corre │          │ corriendo, pero     │
     │ en plataformas no│          │ después no hay      │
     │ Apple: se detiene│          │ kprintf al fb       │
     └────────┬─────────┘          └──────────┬──────────┘
              │                               │
     hay que sustituirlo                necesita sondas más finas
     (surface propio)                   o confirmar con log serie
              │                               │
        ← trabajo de la Ruta B             ← lo primero a descartar
```

**Importante**: **la interpretación B aún no se ha descartado.** Siempre asumimos que era un callejón sin salida, pero no verificamos si el kernel seguía corriendo.
Cómo verificarlo: añadir sondas en los pasos siguientes, o un kprintf cerca de `setconf`.

## IV. Relación entre las dos rutas

```
                    Línea base actual (checkpoint 123)
                              │
              ┌───────────────┴───────────────┐
              │                               │
    ┌─────────▼──────────┐        ┌───────────▼──────────┐
    │  Ruta A            │        │  Ruta B              │
    │  Raíz (archivos)    │        │  Pantalla (IOSurface) │
    ├────────────────────┤        ├──────────────────────┤
    │ 1. Imagen userdata  │        │ 1. Crear IOCoreSurfaceRoot│
    │   (OS+SystemOS)     │        │ 2. Crear AppleCLCD   │
    │ 2. Root UUID        │        │ 3. Reg. KernelConfig │
    │ 3. Flash userdata   │        │ 4. Levantar IOMFB     │
    │ 4. Montar raíz       │        │                      │
    │ 5. Arranca launchd   │        │                      │
    ├────────────────────┤        ├──────────────────────┤
    │ Plazo: 1-2 semanas  │        │ Plazo: 3-4 semanas   │
    │ Riesgo: bajo         │        │ Riesgo: alto (placa)  │
    └─────────┬──────────┘        └───────────┬──────────┘
              │                               │
              └───────────────┬───────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Stage 7 Userland   │
                    │  SpringBoard       │
                    └────────────────────┘
```

**Las dos rutas no se contradicen**: A resuelve "si el sistema puede arrancar", B resuelve "si se puede ver".
El requisito previo de A es descartar la "interpretación B" de arriba: si el kernel en realidad sigue corriendo, A lleva directo a la Stage 6.

## V. Cómo desarrollar en paralelo

```
  rama main (línea base actual, siempre compilable y flasheable)
    │
    ├── feature/stage6-userdata      ← Ruta A
    │     · [userdata] de board.toml y root_match_volume_uuid
    │     · el CI añade el paso build userdata (hay que bajar OS/SystemOS, varios GB)
    │     · no tocar los 9 interruptores de defconfig
    │
    └── feature/stage5-iosurface     ← Ruta B
          · iokit/Kernel/arm/NabuSurface.cpp + NabuFramebuffer.cpp
          · registrar IOCoreSurfaceRoot / AppleCLCD en patches/xnu
          · hay que añadir entradas en [kernel] archives
          · no tocar [userdata] de board.toml

  Reglas:
    1. main se mantiene siempre en el estado flasheable del checkpoint 123
    2. cada rama tiene su propio CI y su propio flasheo, sin interferir
    3. si una rama falla 2 compilaciones seguidas → volver a main y reevaluar
    4. no compartir cambios de defconfig (fue lo que quemó una docena de rondas la última vez)
```
