# Trabajar en ios-cepheus (base UniXNU)

- Lee `MIGRATION.md` y `STATUS.md` antes de empezar. Actualiza `STATUS.md` tras cada hito: commits, IDs de CI, resultados exactos de compilación/arranque y trabajo pendiente. Distingue observaciones de suposiciones.
- El arranque de pruebas es siempre temporal (`fastboot boot`). Conserva Android y las copias de seguridad de particiones.
  Aprobado el 2026-10-15: iOS puede ocupar `userdata`; confirma con el usuario cada paso destructivo.
- Nombres: código nuevo `cepheus_*` / `CEPHEUS`, comentarios de debug "CEPHEUS debug", guardas `#if CEPHEUS`.
- Parches nuevos: desde `0085` en `xnu-8796/patches/`. Los de debug van en `patches-extra/`.
- No subas a git volcados del dispositivo, números de serie ni artefactos de Apple.
- Historia previa (sweet): `docs/ios-sweet-legacy/`.
