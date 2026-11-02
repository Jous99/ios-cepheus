#!/usr/bin/env python3
"""Toca el iOS del Mi 9 desde el PC por la red USB (UDP 5141). Coordenadas en pixeles del panel (1080 x 2340).

uso:
  python phone-touch.py tap X Y                  un toque
  python phone-touch.py hold X Y [MS]            pulsacion larga (por defecto 800 ms)
  python phone-touch.py swipe X1 Y1 X2 Y2 [MS]   arrastrar (por defecto 300 ms)
  python phone-touch.py home                     desliza desde el borde inferior hacia arriba (desbloquear / inicio)
  python phone-touch.py repl                     modo interactivo (los mismos comandos, uno por linea)
Opcion: --host IP (por defecto 192.168.7.2, el movil por la red USB).
El kernel del movil recibe lineas "d DEDO X Y" (abajo o moviendose) y "u DEDO" (arriba).
"""
import socket
import sys
import time

PORT = 5141
W, H = 1080, 2340


class Phone:
    def __init__(self, host):
        self.addr = (host, PORT)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, text):
        self.sock.sendto(text.encode(), self.addr)

    def down(self, x, y, finger=0):
        self.send('d %d %d %d\n' % (finger, x, y))

    def up(self, finger=0):
        self.send('u %d\n' % finger)

    def tap(self, x, y, ms=80):
        self.down(x, y)
        time.sleep(ms / 1000.0)
        self.up()

    def hold(self, x, y, ms=800):
        self.tap(x, y, ms)

    def swipe(self, x1, y1, x2, y2, ms=300):
        steps = max(4, int(ms / 16))
        self.down(x1, y1)
        for i in range(1, steps + 1):
            time.sleep(ms / 1000.0 / steps)
            self.down(x1 + (x2 - x1) * i // steps, y1 + (y2 - y1) * i // steps)
        self.up()

    def home(self):
        self.swipe(W // 2, H - 8, W // 2, H // 2, 250)


def run(phone, words):
    cmd, args = words[0], [int(a) for a in words[1:]]
    if cmd == 'tap' and len(args) == 2:
        phone.tap(*args)
    elif cmd == 'hold' and len(args) in (2, 3):
        phone.hold(*args)
    elif cmd == 'swipe' and len(args) in (4, 5):
        phone.swipe(*args)
    elif cmd == 'home' and not args:
        phone.home()
    else:
        print('comando no valido:', ' '.join(words))
        return False
    return True


def main():
    argv = sys.argv[1:]
    host = '192.168.7.2'
    if '--host' in argv:
        i = argv.index('--host')
        host = argv[i + 1]
        del argv[i:i + 2]
    if not argv:
        sys.exit(__doc__)
    phone = Phone(host)
    if argv[0] == 'repl':
        print('comandos: tap X Y | hold X Y [MS] | swipe X1 Y1 X2 Y2 [MS] | home | salir')
        while True:
            try:
                line = input('> ').split()
            except EOFError:
                break
            if not line:
                continue
            if line[0] in ('salir', 'exit', 'quit'):
                break
            try:
                run(phone, line)
            except ValueError:
                print('las coordenadas deben ser numeros')
    else:
        try:
            run(phone, argv)
        except ValueError:
            sys.exit('las coordenadas deben ser numeros')


main()
