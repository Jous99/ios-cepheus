# Parches extra (no se aplican por defecto)

El CI copia solo `xnu-8796/patches/*.patch`. Estos son tuyos, portados de ios-cepheus (sweet):
`sweet_early_mark` -> `cepheus_early_mark`, `arm64/sweet_early.h` -> `arm64/cepheus_early.h`.
Se aplican **en orden E01..E09** sobre la serie completa (verificado sobre xnu-8796.141.3 limpio).

- E01: quita la guarda `TARGET_OS_OSX` de `iBoot_Stage_2_version` (solo si el kernel falla por ese símbolo).
- E02-E09: marcadores de arranque en pantalla (startup, bsd_init, procinit).

Se dejó fuera `0093-cepheus-test-procinit-off` (desactivaba `procinit` para una prueba de cuelgue;
está en `legacy/sweet-unique-patches/`).
Para usarlos, cópialos a `xnu-8796/patches/` con números libres (0085 en adelante).
