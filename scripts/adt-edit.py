#!/usr/bin/env python3
"""Retoca un ADT ya generado (idempotente): pantalla, display-scale, wdt e identidad iPhone X completa.

uso: adt-edit.py ENTRADA SALIDA [--iphone-x]
"""
import struct, sys

# /product del DeviceTree real del iPhone X (D22AP, iOS 16.7.16 20H392), sin los marcadores syscfg que iBoot rellena.
# MobileGestalt/CoreUI sacan de aqui artwork-device-subtype (2436), idioma, gamut, clase grafica...
D22AP_PRODUCT = [
    ('sandman-support', bytes.fromhex('01000000')),
    ('display-mirroring', bytes.fromhex('01000000')),
    ('car-integration', bytes.fromhex('01000000')),
    ('assistant', bytes.fromhex('01000000')),
    ('lockdown-certtype', bytes.fromhex('01000000')),
    ('ui-pip', bytes.fromhex('01000000')),
    ('wifi-chipset', bytes.fromhex('3433353700')),
    ('product-name', bytes.fromhex('6950686f6e65205800')),
    ('hearingaid-audio-equalization', bytes.fromhex('01000000')),
    ('RF-exposure-separation-distance', bytes.fromhex('05000000')),
    ('mobiledevice-min-ver', bytes.fromhex('3134303000')),
    ('product-id', bytes.fromhex('fd079b298144a7deb4d7c87fef3eb474d8f0e7eb')),
    ('gps-capable', bytes.fromhex('01000000')),
    ('product-description', bytes.fromhex('6950686f6e65205800')),
    ('allow-32bit-apps', bytes.fromhex('01000000')),
    ('low-power-wallet-mode', bytes.fromhex('01000000')),
    ('builtin-mics', bytes.fromhex('04000000')),
    ('has-boot-chime', bytes.fromhex('00000000')),
    ('supports-burnin-mitigation', bytes.fromhex('01000000')),
    ('compatible-device-fallback', bytes.fromhex('6950686f6e65392c3200')),
    ('device-perf-memory-class', bytes.fromhex('04000000')),
    ('artwork-scale-factor', bytes.fromhex('03000000')),
    ('baseband-chipset', bytes.fromhex('6d6176313700')),
    ('hearingaid-low-energy-audio', bytes.fromhex('01000000')),
    ('ui-background-quality', bytes.fromhex('64000000')),
    ('supports-avatars', bytes.fromhex('')),
    ('public-key-accelerator', bytes.fromhex('01000000')),
    ('disable-globe-map', bytes.fromhex('')),
    ('artwork-device-idiom', bytes.fromhex('70686f6e6500')),
    ('device-color-policy', bytes.fromhex('00000000')),
    ('graphics-featureset-class', bytes.fromhex('4150504c453400')),
    ('siri-gesture', bytes.fromhex('01000000')),
    ('supports-maps-optical-heading', bytes.fromhex('')),
    ('compatible-app-variant', bytes.fromhex('3000')),
    ('artwork-dynamic-displaymode', bytes.fromhex('3000')),
    ('bluetooth-le', bytes.fromhex('01000000')),
    ('watch-companion', bytes.fromhex('01000000')),
    ('has-applelpm', bytes.fromhex('00000000')),
    ('iap2-protocol-supported', bytes.fromhex('01000000')),
    ('ephemeral-data-mode', bytes.fromhex('00000000')),
    ('activation-protocol-version', bytes.fromhex('02000000')),
    ('volume-up-button-location', bytes.fromhex('78b00900ff96140030e00300ca9d010010270000')),
    ('ptp-large-files', bytes.fromhex('01000000')),
    ('udid-version', bytes.fromhex('01000000')),
    ('offline-dictation', bytes.fromhex('01000000')),
    ('location-reminders', bytes.fromhex('01000000')),
    ('ui-weather-quality', bytes.fromhex('64000000')),
    ('graphics-featureset-fallbacks', bytes.fromhex('4150504c45333a4150504c453376313a4150504c45323a4150504c45313a474c4553322c3000')),
    ('dictation', bytes.fromhex('01000000')),
    ('itunes-min-ver', bytes.fromhex('03070c00')),
    ('artwork-display-gamut', bytes.fromhex('503300')),
    ('front-cam-offset-from-center', bytes.fromhex('d00101009e1d0000e803000000000000')),
    ('ui-reachability', bytes.fromhex('01000000')),
    ('volume-down-button-location', bytes.fromhex('78b00900ff96140048d00500ca9d010010270000')),
    ('personal-hotspot', bytes.fromhex('01000000')),
    ('single-stage-boot', bytes.fromhex('01000000')),
    ('mobiledevice-beta-min-ver', bytes.fromhex('313139302e3130302e3200')),
    ('oled-display', bytes.fromhex('01000000')),
    ('thin-bezel', bytes.fromhex('01000000')),
    ('artwork-device-subtype', bytes.fromhex('84090000')),
    ('side-button-location', bytes.fromhex('75f300002a0f020000710000ea3f0000e8030000')),
]

class Node:
    def __init__(self):
        self.props = []      # [nombre, longitud_con_flags, valor]
        self.children = []
    def get(self, name):
        for p in self.props:
            if p[0] == name:
                return p
        return None
    def set(self, name, value):
        p = self.get(name)
        if p:
            p[1] = (p[1] & 0x80000000) | len(value); p[2] = value
        else:
            self.props.append([name, len(value), value])
    def delete_prefix(self, prefixes):
        self.props = [p for p in self.props if not any(p[0].startswith(x) for x in prefixes)]
    def name(self):
        p = self.get('name')
        return p[2].split(b'\0')[0].decode() if p else ''
    def child(self, name):
        for c in self.children:
            if c.name() == name:
                return c
        return None

def parse(b, pos=0):
    n = Node()
    nprops, nchild = struct.unpack_from('<II', b, pos); pos += 8
    for _ in range(nprops):
        name = b[pos:pos+32].split(b'\0')[0].decode(); ln = struct.unpack_from('<I', b, pos+32)[0]; pos += 36
        real = ln & 0x7fffffff
        n.props.append([name, ln, b[pos:pos+real]]); pos += (real + 3) & ~3
    for _ in range(nchild):
        c, pos = parse(b, pos); n.children.append(c)
    return n, pos

def dump(n):
    out = bytearray(struct.pack('<II', len(n.props), len(n.children)))
    for name, ln, val in n.props:
        out += name.encode().ljust(32, b'\0') + struct.pack('<I', ln) + val + b'\0' * (-len(val) % 4)
    for c in n.children:
        out += dump(c)
    return bytes(out)

def mk(name, props):
    n = Node(); n.set('name', name.encode() + b'\0')
    for k, v in props: n.set(k, v)
    return n

u32 = lambda v: struct.pack('<I', v)
cs = lambda s: s.encode() + b'\0'

def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, dst, iphone = sys.argv[1], sys.argv[2], '--iphone-x' in sys.argv[3:]
    data = open(src, 'rb').read()
    root, end = parse(data)
    assert end == len(data), 'ADT con basura al final'
    log = []

    chosen = root.child('chosen'); armio = root.child('arm-io')
    assert chosen and armio, 'faltan /chosen o /arm-io'
    chosen.set('display-scale', u32(3)); log.append('/chosen display-scale = 3')
    if not armio.child('wdt'):
        armio.children.append(mk('wdt', [('no-pmu', u32(1))])); log.append('+ /arm-io/wdt')
    if not armio.child('disp0'):
        armio.children.append(mk('disp0', [('device_type', cs('display-subsystem')), ('compatible', cs('cepheus,display')),
                                           ('canvas-width', u32(1125)), ('canvas-height', u32(2436))]))
        log.append('+ /arm-io/disp0 (1125x2436)')

    if iphone:
        root.set('model', cs('iPhone10,3')); root.set('target-type', cs('D22')); root.set('target-sub-type', cs('D22AP'))
        root.set('manufacturer', cs('Apple Inc.'))
        root.set('compatible', cs('D22AP') + cs('iPhone10,3') + cs('xiaomi,cepheus') + cs('qcom,sm8150') + cs('AppleARM'))
        prod = root.child('product')
        assert prod, 'falta /product'
        prod.props = [p for p in prod.props if p[0] in ('name', 'AAPL,phandle')]
        for k, v in D22AP_PRODUCT: prod.set(k, v)
        if not root.child('buttons'):
            root.children.append(mk('buttons', [('compatible', cs('buttons')), ('device_type', cs('buttons')),
                                                ('button-names', b'hold\0voldown\0volup\0'), ('home-button-type', u32(2))]))
            log.append('+ /buttons')
        log.append('identidad iPhone X: raiz iPhone10,3/D22AP/AppleARM + /product real (%d propiedades)' % len(D22AP_PRODUCT))

    open(dst, 'wb').write(dump(root))
    print('adt-edit: %d bytes -> %d bytes' % (len(data), len(dump(root))))
    for l in log: print('  ' + l)

main()
