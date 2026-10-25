# Resumen de estado (cepheus)

> Este repo se adaptó a partir del esqueleto de port de nabu (2026-10-23). El registro de estado original de nabu está en
> `docs/nabu-reference/STATUS.md`. El original en chino de este archivo está en `docs/original-zh/STATUS.md`.

## Estado actual: esqueleto completo, falta medir en el teléfono real

- [x] Copiado y renombrado desde nabu: configs / kits / scripts / workflow de CI
- [x] El contenido de los 83 parches de XNU renombrado de forma uniforme (la cadena de símbolos cepheus-fbcon / cepheus_early es coherente)
- [x] `scripts/make-cepheus-adt.py` terminado (incluye el nodo /cepheus-fbcon, verificado en local)
- [x] `MACHINE_CONFIG` del workflow cambiado a CEPHEUS (coincide con `MASTER.arm64.cepheus` del parche 0006)
- [x] `board.toml` cambiado a cepheus (con marcadores TODO_MEASURE)
- [x] `TODO-MEASURE.md`: lista de mediciones
- [ ] Clonar el fork Lux12138/UniXNU y tomar `make-nabu-adt.py` como base -> `make-cepheus-adt.py`
      (nota del traductor: el script ya existe en `scripts/`; este punto parece haber quedado sin marcar)
- [ ] Mediciones en el teléfono real: DRAM / userdata / dirección del fbcon (ver `TODO-MEASURE.md`)
- [ ] Que pase el primer CI de compilación del kernel (¡no hace falta el teléfono! Tras el push, lanzar `workflow_dispatch` a mano)
      - Progreso de los arreglos del CI: pin del ipsw -> entorno hostcompat -> declaración de iig v1 (ambigua) -> v2 (refirmada,
        símbolos duplicados al enlazar) -> **v3 (actual)**: el iig de Xcode 26.6 (DriverKit-440) compila
        `IOService.iig.cpo` / `IOUserClient.iig.cpo` dentro del kernel, que ya trae tres definiciones de reenvío;
        se eliminan las definiciones escritas a mano de `iig-method-forwarders.patch` del fork (hunk inverso exacto),
        conservando el typedef de `OSContainer` en `IOService.h`. Parche =
        `patches/macos-iig-forwarder-decls.patch`.
- [ ] Repo UEFI `uefi-cepheus` (tomando como referencia uefi-sheng + `firmware-patches.md` de nabu)
- [ ] Bring-up en las fases 1-7 (ver `../notes/cepheus-plan.md` §5; ese archivo no está en este repo)

## 2026-10-25 - Migración
Base cambiada a UniXNU-cepheus. Ver `MIGRATION.md`. Pendiente: medir en tu Mi 9, decidir el IPSW, primer CI, `uefi-cepheus`.
