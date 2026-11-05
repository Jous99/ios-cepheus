# Checklist del proyecto ios-cepheus (iOS en el Xiaomi Mi 9)

Estado a 04/11/2026. Para marcar una casilla: en Forgejo, botón del lápiz (editar), cambia `[ ]` por `[x]` y guarda.

Dificultad entre paréntesis: **fácil**, **medio**, **difícil**, **incierto** (no sé si es posible).

**Orden recomendado:** la parte 1 completa (decide si la GPU es viable), después lo fácil que mejora el uso diario (hora, apps visibles, reducir movimiento, red por USB) y, con datos, seguir con las puertas de la GPU o invertir en otras partes.

## Índice

- [1. Inmediato: consola de la GPU y decisión](#1-inmediato-consola-de-la-gpu-y-decisión)
- [2. GPU: puertas del arranque](#2-gpu-puertas-del-arranque)
- [3. Fluidez sin esperar a la GPU](#3-fluidez-sin-esperar-a-la-gpu)
- [4. iOS completo: software](#4-ios-completo-software)
- [5. Hardware sin portar](#5-hardware-sin-portar)
- [6. Entrada: táctil y botones](#6-entrada-táctil-y-botones)
- [7. Arranque sin PC (instalación permanente)](#7-arranque-sin-pc-instalación-permanente)
- [8. Repositorio, documentación y seguridad](#8-repositorio-documentación-y-seguridad)

## 1. Inmediato: consola de la GPU y decisión

Dificultad entre paréntesis. Lo de esta parte decide si la GPU es viable.

- [x] Montar y subir el `0117` (consola de lectura y escritura acotada + buffer de RAM) (fácil)
- [x] Esperar al CI en verde, bajar el artefacto y flashear (pasos 1 a 4) (fácil)
- [x] Comprobar que el móvil tiene la consola nueva: `python3 $P zzz` debe terminar en `| rw` (fácil)
- [x] Experimento del `S2CR`: solo acepta `TYPE = traducir` (`fallo` se ignora y `bypass` se vuelve `fallo`); `sCR0` es de solo lectura (fácil)
- [x] Comprobar si el bit 18 de `sCR0` sigue al reloj `gcc_ddrss_gpu_axi_clk`: no lo sigue (fácil)
- [ ] Registrar los resultados de G2b en `docs/05-m1-puertas.md` y subir (fácil)
- [ ] Verificar que `backup-mi9` conserva las 8 copias de seguridad tras el formateo (fácil)

## 2. GPU: puertas del arranque

- [x] G0: inventario de relojes y dominios
- [x] G1: dominio CX y relojes del GMU, registros del GMU legibles (`g g1`)
- [x] G2a: inventario de la SMMU (`g smmu`)
- [x] G2b: SMMU del GMU: stream 5 -> grupo 5 -> banco 1, activado (el `S2CR` se escribe antes que el `SMR`)
  - [x] Banco de contexto 1 (`TTBR0`, `TCR`, `MAIR0`, `SCTLR`) y tablas de páginas en el buffer de RAM
  - [x] Mapear `0x4000` (caché de instrucciones), `0x44000` (de datos), `0x60000000` (ficticia), log y HFI
  - [x] Validar: la SMMU no ofrece traducción por hardware (`ATOSNS = 1`); lo valida que el GMU ejecute el firmware
- [x] G2c: cargar los 7 bloques del firmware del GMU (ITCM y DTCM por registros, los otros dos en RAM)
- [x] G2d: soltar el reset del procesador del GMU: `FW_INIT_RESULT = 0xbabeface` (exigía `RPMH_CTRL & 0xf11`)
- [ ] G3a: leer la base de datos de comandos de RPMh y programar el RSC y el PDC (necesita un parche de kernel: lectura de RAM física y ventanas del PDC) (difícil)
- [ ] G3b: HFI: `HFI_CTRL_INIT`, tablas de rendimiento y de ancho de banda por la cola de comandos (difícil)
- [ ] G3c: PLL1 a 500 MHz y dominio GX (difícil)
- [ ] G4: SQE y zap shader (llamadas a TrustZone) (incierto, quizá imposible desde nuestro kernel)
- [ ] G5: una orden mínima y leer el resultado (difícil)
- [ ] Integración con iOS: controlador que haga que iOS use ese Adreno (difícil, no garantizado)

## 3. Fluidez sin esperar a la GPU

- [ ] Ajustes > Accesibilidad > Movimiento > **Reducir movimiento**; Pantalla y tamaño de texto > **Reducir transparencia** (fácil, sin probar en este port)
- [ ] Comprobar cuántos núcleos arranca XNU y a qué frecuencia (`docs/pmgr-plan.md`) (medio, incierto)
- [ ] Medir dónde se va el tiempo al dibujar: CPU, memoria, composición (medio)

## 4. iOS completo: software

- [ ] Apps que no aparecen: mirar la Biblioteca de apps y la búsqueda; si existen pero están ocultas, ajustar las capacidades del árbol de dispositivo (`mkadt.py`) o el diseño del inicio (fácil a medio)
- [ ] Decidir sobre el asistente Hello: saltado a propósito porque sin módem se bloquea esperando a CoreTelephony (difícil)
- [ ] Activación y estado "activado" sin servidor de Apple (hoy sembrado a mano) (incierto)
- [ ] Telefonía: `CommCenter` está eliminado; decidir si Teléfono y Mensajes se ocultan o se simulan (medio)
- [ ] Reactivar las vigilancias de `SpringBoard` cuando el rendimiento lo permita (fácil)

## 5. Hardware sin portar

- [ ] Fecha y hora: arranca el 31 de diciembre (sin RTC); orden por UDP que la ponga desde el PC (fácil)
- [ ] Red de iOS por el cable USB con salida a internet a través del PC (medio)
- [ ] Pantalla: modo comando sin DSC y control de brillo (medio)
- [ ] Batería y carga visibles en iOS (medio)
- [ ] Audio (el plug-in virtual está desactivado) (difícil)
- [ ] Wi-Fi y Bluetooth (difícil)
- [ ] Sensores: giro, proximidad, luz (difícil)
- [ ] Vibración, huella bajo la pantalla, NFC, GPS, cámara (difícil o fuera de alcance por ahora)

## 6. Entrada: táctil y botones

- [x] Botones y táctil físico llegando a iOS; entrada desde el PC por UDP
- [ ] Validar el uso prolongado con el dedo: escala de coordenadas y evento de levantar (`33`, supuesto) (fácil)
- [ ] Varios dedos y gestos: zoom, deslizar desde el borde (medio)

## 7. Arranque sin PC (instalación permanente)

Riesgo real: un error deja el móvil sin arrancar nada hasta restaurar con `fastboot`.

- [ ] Verificar las copias de `boot`, `dtbo`, `vbmeta`, `persist`, `modemst1`, `modemst2`, `fsg` y `fsc` (fácil)
- [ ] Comprobar el estado de `vbmeta` (verificación) con el bootloader desbloqueado (fácil)
- [ ] Grabar `cepheus-xnu.img` en `boot` (riesgo, reversible solo con las copias)
- [ ] Camino de vuelta a Android: restaurar `boot` y reinstalar `userdata` (medio)
- [ ] Si Android arranca por error, puede ofrecer **formatear** `userdata` y borrar iOS: decidir cómo evitarlo (medio)
- [ ] Doble arranque (aparcado)

## 8. Repositorio, documentación y seguridad

- [ ] Regenerar el documento de traspaso general (el del 28/10 está obsoleto) (fácil)
- [ ] Actualizar README y diario con cada puerta de la GPU (fácil)
- [ ] Licencia del repo de la GPU (el público ya tiene `LICENSE`) (fácil)
- [ ] Pasar `limpiar-privado.py` al repo público antes de cada subida (fácil)
- [ ] Guardar en el repo los modelos de simulación con los que se prueba el código de la GPU (fácil)
- [ ] Un script de una línea para los pasos 1 y 3 del flasheo (fácil)
