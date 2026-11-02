#!/usr/bin/env python3
"""Lee la cola de eventos del chip tactil sin parar (UDP 5141 + log en vivo) y decodifica los toques.

uso:  python3 ts-poll.py [SEGUNDOS] [--log RUTA] [--host IP]     (por defecto 15 s)
Toca la pantalla del movil mientras corre. Necesita el kernel con la consola (parche 0107) y cepheusts=1.
Cada evento son 8 bytes. Ids de la generacion nueva: 03 listo, 13 entra, 23 mueve, 33 sale, 43 eco, f3 error.
Se decodifican las coordenadas de dos formas (A y B): la correcta sigue tu dedo (panel 1080 x 2340).
"""
import glob
import os
import re
import socket
import sys
import time

HOST, PORT = '192.168.7.2', 5141
LOGS = '/mnt/c/Users/Jous/Documents/git/ios-cepheus/logs/live*.txt'
NAMES = {0x03: 'LISTO?', 0x13: 'ENTRA', 0x23: 'MUEVE', 0x33: 'SALE', 0x43: 'ECO', 0xf3: 'ERROR', 0x04: 'SALE?', 0x05: 'MUEVE?'}


def decode(ev):
    kind = NAMES.get(ev[0], 'id %02x' % ev[0])
    if ev[0] in (0x13, 0x23, 0x33):
        # empaquetado nuevo (A) y antiguo (B): compara con donde pusiste el dedo
        xa = ((ev[3] & 15) << 8) | ev[2]
        ya = (ev[4] << 4) | (ev[3] >> 4)
        xb = (ev[2] << 4) | (ev[4] >> 4)
        yb = (ev[3] << 4) | (ev[4] & 15)
        return '%-5s dedo %d  A x=%4d y=%4d | B x=%4d y=%4d' % (kind, ev[1] & 15, xa, ya, xb, yb)
    if ev[0] == 0x43:
        return 'ECO de comando %s' % ' '.join('%02x' % b for b in ev[2:6])
    return kind


def main():
    argv = sys.argv[1:]
    host, path, secs = HOST, None, 15.0
    for opt in ('--host', '--log'):
        if opt in argv:
            i = argv.index(opt)
            val = argv[i + 1]
            del argv[i:i + 2]
            if opt == '--host':
                host = val
            else:
                path = val
    if argv:
        secs = float(argv[0])
    if not path:
        files = glob.glob(LOGS)
        path = max(files, key=os.path.getmtime) if files else None
    if not path:
        sys.exit('no hay log en vivo')
    start = os.path.getsize(path)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print('log:', path)
    print('>>> TOCA LA PANTALLA Y ARRASTRA EL DEDO durante %.0f s <<<' % secs)
    n, end = 0, time.time() + secs
    while time.time() < end:
        sock.sendto(b't x 86 32\n', (host, PORT))
        n += 1
        time.sleep(0.04)
    time.sleep(3.0)
    with open(path, 'rb') as f:
        f.seek(start)
        text = f.read().decode('latin-1')
    reads = [m for m in re.finditer(r'CEPHEUS TSC: x tx=86 n=32 err=(\d+) irq=(\d) rx:([0-9a-f ]*)', text)]
    shown, low, errs = 0, 0, 0
    for m in reads:
        err, irq, data = int(m.group(1)), int(m.group(2)), m.group(3).split()
        low += irq == 0
        errs += err != 0
        raw = bytes(int(b, 16) for b in data)
        for i in range(0, len(raw) - 7, 8):
            ev = raw[i:i + 8]
            if any(ev):
                shown += 1
                if shown <= 60:
                    print('%-34s  %s  irq=%d' % (decode(ev), ' '.join('%02x' % b for b in ev), irq))
    print('enviadas %d, respuestas %d en el log, con error %d, interrupcion baja en %d, eventos %d' % (n, len(reads), errs, low, shown))


main()
