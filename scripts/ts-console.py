#!/usr/bin/env python3
"""Consola del chip tactil del Mi 9, por UDP (puerto 5141) con la respuesta del log en vivo.

uso:
  python3 ts-console.py "scan"            un comando y su respuesta
  python3 ts-console.py repl              modo interactivo
  Opciones: --host IP (192.168.7.2)  --log RUTA (por defecto el logs/live*.txt mas reciente)
Comandos (el kernel necesita arrancar con cepheusts=1):
  scan | x HEX [N] | rst BAJO ALTO | irq | us N | dir 0|1 | fifo MS
  ejemplos:  x b60004 3   (leer el ID del chip)    x 85 8   (leer un evento)    rst 20 300   (reset)
"""
import glob
import os
import socket
import sys
import time

HOST = '192.168.7.2'
PORT = 5141
LOGS = '/mnt/c/Users/Jous/Documents/git/ios-cepheus/logs/live*.txt'


def newest_log():
    files = glob.glob(LOGS)
    return max(files, key=os.path.getmtime) if files else None


def log_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def send(sock, host, text):
    sock.sendto(('t ' + text + '\n').encode(), (host, PORT))


def answers(path, start, wait):
    """Devuelve las lineas CEPHEUS TSC (y TS) nuevas del log, esperando hasta `wait` s a que se calle."""
    out, last_new = [], time.time()
    deadline = time.time() + wait
    pos = start
    while time.time() < deadline:
        time.sleep(0.15)
        try:
            with open(path, 'rb') as f:
                f.seek(pos)
                data = f.read()
        except OSError:
            continue
        if data:
            pos += len(data)
            for line in data.decode('latin-1').splitlines():
                if 'CEPHEUS TSC' in line or 'CEPHEUS TS:' in line:
                    out.append(line.strip())
                    last_new = time.time()
        if out and time.time() - last_new > 1.2:
            break
    return out


def run(sock, host, path, text):
    start = log_size(path) if path else 0
    send(sock, host, text)
    if not path:
        print('(sin log: mira la ventana del log en vivo)')
        return
    wait = 3.0
    words = text.split()
    if words and words[0] == 'fifo' and len(words) > 1 and words[1].isdigit():
        wait += int(words[1]) / 1000.0 * 2.5
    if words and words[0] == 'rst':
        wait += 1.0
    lines = answers(path, start, wait)
    print('\n'.join(lines) if lines else '(sin respuesta en %.0f s: el kernel arranco con cepheusts=1 y ya paso la etapa 1?)' % wait)


def main():
    argv = sys.argv[1:]
    host, path = HOST, None
    for opt in ('--host', '--log'):
        if opt in argv:
            i = argv.index(opt)
            val = argv[i + 1]
            del argv[i:i + 2]
            if opt == '--host':
                host = val
            else:
                path = val
    path = path or newest_log()
    if not argv:
        sys.exit(__doc__)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print('log:', path)
    if argv[0] == 'repl':
        print('escribe un comando (scan, x HEX N, rst BAJO ALTO, irq, us N, dir 0|1, fifo MS) o salir')
        while True:
            try:
                line = input('ts> ').strip()
            except EOFError:
                break
            if line in ('salir', 'exit', 'quit'):
                break
            if line:
                run(sock, host, path, line)
    else:
        run(sock, host, path, ' '.join(argv))


main()
