# Plan de port de PMGR (nabu / SM8150)

> Documento de la Xiaomi Pad 5 (nabu), traducido al español. El original en chino está en `docs/original-zh/`.

El kernel ya entra en ejecución en nabu (`DARWINBOOT: hand-off to the kernel`).
Lo siguiente que hará panic antes, casi seguro, es la **gestión de energía de la plataforma (PMGR)**:
XNU accede a los registros AON / PMGR a través de la familia `ApplePMGR` antes de `bsd_init`.

## 0. Lo primero: un log de panic

Sin log no hay por dónde empezar. Hay dos formas de obtenerlo (mejor la primera):

1. **Pantalla:** ahora el kernel ya controla la pantalla, así que el panic saldrá ahí -> grábalo en vídeo o con ráfaga de fotos.
2. **UART:** puerto serie a 115200 (en SM8150 suele ser `ttyMSM0`); la configuración lleva `serial=3`.
   Con un USB-TTL a los puntos de test de la placa se obtiene el log completo.

En el log busca sobre todo:
- La primera línea del `panic(...)` y la pila de llamadas.
- Cualquier nombre de kext con `ApplePMGR` / `AppleARMIODevice` / `platform-power`.
- El último kext cargado con éxito (sirve para saber qué driver fue el que falló).

## 1. Cómo es realmente SM8150 (totalmente distinto de Apple)

> Detalles en `docs/nabu-dts-extract.md`: esta tabla sale del DTS público de nabu, con las direcciones comprobadas.

| Capa | Apple | SM8150 |
|---|---|---|
| Acceso a registros | MMIO + mailbox AON | Mensajes **IPC (CmdDb)**, TCS de comandos RPMh, SPMI |
| Dominios de energía | PMGR, un bloque enorme | RPMh (RSC + TCS), NPA, PDC |
| Relojes | Puertas de reloj de PMGR | GCC (`0x100000`) |

Direcciones base confirmadas:

```
RPMh RSC  0x18200000  (0x10000) x3 bancos   <-- la entrada real de RPMh
IPCC/apss_shared 0x17c00000  (0x1000)  <-- solo es un mailbox, no es RPMh
cmd-db    0x85f20000  (0x20000)
SPMI      0x0c440000
watchdog  0x17c10000
timer     0x17c20000
SMEM      0x86000000
GCC       0x100000    (ver la tabla de offsets en scripts/GccUfs-nabu.h)
```

Registros clave del DRV de RPMh (SM8150):

```
RSC_DRV_CTL_TCS_DATA_HI   0x38
RSC_DRV_CTL_TCS_DATA_LO   0x40
TCS_AMC_MODE_ENABLE       BIT(16)
```

## 2. La superficie de ApplePMGR (resultado de ingeniería inversa)

```
ApplePMGR sizeof = 0x4b8a8
vtable slot 177..340   (hay que implementar 164 slots)
slot 320  readAon()
slot 321  writeAon(uint64_t)
```

Estrategia: **no escribir 164 de golpe.** Primero hacer funcionar `readAon/writeAon` y el camino de inicialización;
al resto de slots darles una implementación vacía segura (devolver 0 / no hacer nada) y completarlos uno a uno guiándose por el log de panic.
Es lo mismo que hace sheng: `sheng-platform-power.patch` solo añade un `sheng_pmgr_run()` en `bsd_init.c`.

## 2.5 Camino mínimo de lectura de RPMh (objetivo del siguiente código)

```
En cmd-db(0x85f20000), buscar por "active"/"wake"/"sleep" la base del TCS
        |
Armar un comando AMC de 16 bytes: { msg_id, addr, data, wait | cmd<<28 }
        |
Escribir el banco + RSC_DRV_CTL_TCS_DATA_HI(0x38) / LO(0x40), y poner TCS_AMC_MODE_ENABLE(BIT16)
        |
Esperar la finalización del DRV (o el canal de ack en SMEM)
        |
Releer data -> es lo que XNU quiere: "estado del dominio de energía / voltaje / reloj"
```

El éxito no es "no se cuelga", sino **poder imprimir valores reales de voltaje/reloj distintos de 0**.

## 3. Orden de implementación

1. Esqueleto de `kits/nabu/NabuPlatformPower.cpp` (ya incluido en esta entrega).
2. `build-nabu-platform-power.py`: compilar el esqueleto como kit e inyectarlo en la lista de drivers de UniXNU.
3. `nabu-platform-power.patch`: espejo de `sheng-platform-power.patch`, añadiendo `nabu_pmgr_run()` en `bsd_init.c`.
4. La primera vez, implementar solo:
   - `init()`: detectar IPCC / cmd-db / SMEM e imprimir bases y versiones.
   - `readAon/writeAon`: primero un circuito mínimo de **consulta a cmd-db + escritura de TCS de RPMh**;
     si falla, devolver 0 en vez de colgarse.
5. Capturar el panic -> completar el siguiente slot -> repetir.

## 4. Cómo saber si "de verdad funciona"

El criterio no es "no hay panic", sino:
- Poder imprimir valores reales de voltaje/reloj leídos de RPMh (no 0).
- Que el driver UFS enumere particiones dentro de XNU (`NativeUfs` ya está en el núcleo).
- Llegar a `bsd_init` y empezar a cargar kexts.

## 5. Riesgos

- Los TCS de RPMh son un **recurso compartido**: escribir mal puede apagar o colgar todo el equipo (se recupera con pulsación larga del botón de encendido).
- Conviene asegurarse antes de cada experimento de que el payload de `cust` está intacto y se puede reflashear en cualquier momento.
- No tocar `abl`/`xbl`/`bootloader`.
