#!/usr/bin/env python3
"""Compara una particion del movil (adb/TWRP) con una imagen sparse de Android y clasifica las diferencias.

uso: python verify-simg2.py IMAGEN.simg [--from-gib X] [--part by-name/userdata] [--raw ARCHIVO_LOCAL]
  --from-gib X  empieza a comparar en el GiB X (rapido para mirar solo el final)
"""
import struct, subprocess, sys, time

RAW, FILL, DONT_CARE = 0xCAC1, 0xCAC2, 0xCAC3
PIECE = 8 * 1024 * 1024

def read_exact(stream, n):
    buf = bytearray()
    while len(buf) < n:
        part = stream.read(n - len(buf))
        if not part: break
        buf += part
    return bytes(buf)

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    path = a[0]; part = 'by-name/userdata'; raw = None; start = 0
    if '--part' in a: part = a[a.index('--part') + 1]
    if '--raw' in a: raw = a[a.index('--raw') + 1]
    f = open(path, 'rb')
    magic, maj, mi, fh, ch, bs, tb, tc, crc = struct.unpack('<IHHHHIIII', f.read(28))
    assert magic == 0xED26FF3A, 'no es sparse'
    total = tb * bs
    if '--from-gib' in a:
        start = (int(float(a[a.index('--from-gib') + 1]) * 2**30) // bs) * bs
    print('imagen: %.2f GiB, %d trozos; se compara desde %.2f GiB' % (total / 2**30, tc, start / 2**30), flush=True)

    if raw:
        src = open(raw, 'rb'); src.seek(start); proc = None
    else:
        cmd = 'dd if=/dev/block/%s bs=%d skip=%d' % (part, bs, start // bs) if start else 'cat /dev/block/%s' % part
        proc = subprocess.Popen(['adb', 'exec-out', cmd], stdout=subprocess.PIPE)
        src = proc.stdout

    pos = 0; ok = 0; bad = {'datos': 0, 'relleno': 0}; runs = []
    actual_zero = 0; expected_zero = 0; samples = []
    short = False; t0 = time.time(); nextp = start + 512 * 2**20
    f.seek(fh)

    def mark(off, n):
        if runs and runs[-1][1] == off: runs[-1][1] = off + n
        else: runs.append([off, off + n])

    def compare(kind, exp, act, base):
        nonlocal ok, actual_zero, expected_zero
        if exp == act:
            ok += len(exp) // bs; return
        for o in range(0, len(exp), bs):
            e = exp[o:o+bs]; x = act[o:o+bs]
            if e == x: ok += 1; continue
            bad[kind] += 1; mark(base + o, bs)
            if x == b'\0' * bs: actual_zero += 1
            if e == b'\0' * bs: expected_zero += 1
            if len(samples) < 8:
                samples.append((kind, base + o, e[:16].hex(), x[:16].hex()))

    for i in range(tc):
        ctype, _, csz, tsz = struct.unpack('<HHII', f.read(12))
        n = csz * bs; body = tsz - ch
        if ctype == FILL: pat = f.read(4)
        elif ctype == RAW: bodypos = f.tell()
        elif body: f.read(body)
        # saltar lo que queda antes del punto de inicio
        skip = 0
        if pos + n <= start:
            if ctype == RAW: f.seek(bodypos + n)
            pos += n; continue
        if pos < start:
            skip = start - pos
            if ctype == RAW: f.seek(bodypos + skip)
            pos += skip; n -= skip
        left = n
        while left:
            m = min(left, PIECE)
            if ctype == RAW:
                exp = f.read(m); act = read_exact(src, m)
                if len(act) < m: short = True; break
                compare('datos', exp, act, pos)
            elif ctype == FILL:
                exp = pat * (m // 4); act = read_exact(src, m)
                if len(act) < m: short = True; break
                compare('relleno', exp, act, pos)
            else:
                act = read_exact(src, m)
                if len(act) < m: short = True; break
            pos += m; left -= m
        if short: break
        if pos >= nextp:
            print('  %.1f GiB  (distintos: datos %d, relleno %d)  %.0f s' % (pos / 2**30, bad['datos'], bad['relleno'], time.time() - t0), flush=True)
            nextp += 512 * 2**20
    if proc: proc.kill()

    print()
    print('RESULTADO: %d iguales | DISTINTOS: %d en bloques de DATOS, %d en bloques de RELLENO' % (ok, bad['datos'], bad['relleno']))
    if short: print('AVISO: lectura cortada en 0x%x' % pos)
    tb_bad = bad['datos'] + bad['relleno']
    if tb_bad:
        print('de los distintos: el disco tiene todo ceros en %d, y la imagen esperaba ceros en %d' % (actual_zero, expected_zero))
        print('ejemplos (tipo, offset, esperado[16B], disco[16B]):')
        for s in samples: print('  %-8s 0x%x  esp=%s  disco=%s' % s)
        print('tramos: %d; el primero en %.2f MiB, el ultimo en %.2f MiB' % (len(runs), runs[0][0] / 2**20, runs[-1][0] / 2**20))
    elif not short:
        print('Coincide por completo en la zona comparada.')

main()
