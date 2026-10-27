#!/usr/bin/env python3
"""Flashea en orden las piezas p.0, p.1, ... de una carpeta con fastboot (userdata). Se para si una falla.

uso: python flash-pieces.py CARPETA [EMPEZAR_EN]
"""
import glob, os, subprocess, sys

folder = sys.argv[1]
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
files = sorted(glob.glob(os.path.join(folder, 'p.*')), key=lambda p: int(p.rsplit('.', 1)[1]))
print(len(files), 'piezas en', folder, flush=True)
if not files:
    sys.exit('no hay piezas (p.0, p.1, ...)')
for i, p in enumerate(files):
    if i < start:
        continue
    print('[%d/%d] %s (%d MB)' % (i + 1, len(files), os.path.basename(p), os.path.getsize(p) // 10**6), flush=True)
    r = subprocess.run(['fastboot', 'flash', 'userdata', p])
    if r.returncode != 0:
        print('FALLO en la pieza %d. Reinicia a fastboot a mano y repite con: python flash-pieces.py "%s" %d' % (i, folder, i))
        sys.exit(1)
print('TODAS LAS PIEZAS OK', flush=True)
