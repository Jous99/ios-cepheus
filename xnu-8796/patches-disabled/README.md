# Parches desactivados

- `0083-nabu-nt36523-spi-probe.patch`: sondea el táctil Novatek NT36523 por SPI (Xiaomi Pad 5).
  La Mi 9 usa un ST FTS por I²C (SE17), así que ese probe no sirve y podría tocar un bus que no corresponde.
  Era el último parche de la serie, así que quitarlo no rompe ningún otro. Para restaurarlo, muévelo de nuevo a `patches/`.
