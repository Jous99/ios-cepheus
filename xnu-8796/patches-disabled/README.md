# Disabled patches

- `0083-nabu-nt36523-spi-probe.patch`: probes the Novatek NT36523 touch controller over SPI (Xiaomi Pad 5).
  The Mi 9 uses an ST FTS over I²C (SE17), so that probe is useless and could touch a bus it does not belong to.
  It was the last patch in the series, so removing it does not break any other. To restore it, move it back to `patches/`.
