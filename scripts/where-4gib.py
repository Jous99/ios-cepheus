#!/usr/bin/env python3
"""Localiza en un .simg la posicion en el ARCHIVO de los datos de un offset de la particion.

uso: python where-4gib.py IMAGEN.simg OFFSET_PARTICION [LIMITE_BYTES]
  OFFSET_PARTICION acepta 0x...; LIMITE_BYTES por defecto 4294967296 (4 GiB).
"""
import struct, sys

path = sys.argv[1]; target = int(sys.argv[2], 0)
limit = int(sys.argv[3], 0) if len(sys.argv) > 3 else 2**32
f = open(path, 'rb')
magic, maj, mi, fh, ch, bs, tb, tc, crc = struct.unpack('<IHHHHIIII', f.read(28))
assert magic == 0xED26FF3A, 'no es sparse'
names = {0xCAC1: 'DATOS', 0xCAC2: 'RELLENO', 0xCAC3: 'DONT_CARE', 0xCAC4: 'CRC'}
img = 0; fpos = fh; hit = None; cross = None; raw_before = 0
f.seek(fh)
for i in range(tc):
    ctype, _, csz, tsz = struct.unpack('<HHII', f.read(12))
    n = csz * bs; dstart = fpos + 12
    if ctype == 0xCAC1:
        if cross is None and dstart <= limit < dstart + n:
            cross = (i, img + (limit - dstart), dstart, n)
        if img <= target < img + n:
            hit = (i, 'DATOS', img, n, dstart + (target - img))
    elif img <= target < img + n:
        hit = (i, names.get(ctype, hex(ctype)), img, n, None)
    img += n; fpos += tsz; f.seek(fpos)

print('imagen: %.2f GiB, %d trozos, archivo %.3f GiB' % (img / 2**30, tc, fpos / 2**30))
if hit:
    i, t, a, n, fp = hit
    print('offset 0x%x (%.2f MiB) -> trozo %d (%s), cubre %.2f..%.2f MiB' % (target, target / 2**20, i, t, a / 2**20, (a + n) / 2**20))
    if fp is not None:
        print('   sus datos estan en la posicion %d del archivo (%.4f GiB; limite = %.4f GiB)' % (fp, fp / 2**30, limit / 2**30))
if cross:
    i, off, dstart, n = cross
    print('el archivo cruza el limite en el trozo %d, que corresponde a la particion 0x%x (%.2f MiB)' % (i, off, off / 2**20))
    print('   diferencia con el offset del primer bloque malo: %.2f MiB' % ((target - off) / 2**20))
else:
    print('el archivo no cruza el limite dentro de un trozo de datos')
