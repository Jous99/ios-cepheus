#!/bin/bash
# Build the iOS 16.7.16 (20H392) root image for cepheus/sweet from WSL2 Ubuntu.
# Reads the IPSW you already have on Windows; nothing Apple-owned is committed or uploaded.
#
#   bash tools/build-root-wsl.sh /mnt/c/Users/Jous/Desktop/ios-cepheus/research/ipsw-x/iPhone10,3_16.7.16_20H392_Restore.ipsw
#
# Needs sudo, ~20 GB free in WSL and ~13 GB free where OUT lives.
# Output: research/ipsw-x/ios16-root.simg (gitignored), flashed with:
#   fastboot flash -S 512M userdata research/ipsw-x/ios16-root.simg
set -euo pipefail

IPSW="${1:?usage: $0 /path/to/iPhone10,3_16.7.16_20H392_Restore.ipsw}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/research/ipsw-x/ios16-root.simg}"
WORK="${WORK:-$HOME/iosroot-build}"
DMG="$WORK/dmg"

[[ -f "$IPSW" ]] || { echo "No encuentro el IPSW: $IPSW" >&2; exit 1; }
[[ ! -e "$OUT" ]] || { echo "Ya existe $OUT: bórralo o define OUT=..." >&2; exit 1; }

echo "==> Dependencias"
sudo apt-get update -qq
sudo apt-get install -y -qq apfs-fuse hfsprogs android-sdk-libsparse-utils rsync python3 >/dev/null

mkdir -p "$DMG"

echo "==> Extrayendo OS, SystemOS y AppOS del IPSW (según BuildManifest.plist)"
python3 - "$IPSW" "$DMG" <<'PY'
import plistlib, sys, zipfile
from pathlib import Path
ipsw, dest = sys.argv[1], Path(sys.argv[2])
z = zipfile.ZipFile(ipsw)
man = plistlib.loads(z.read('BuildManifest.plist'))
bi = next(b for b in man['BuildIdentities'] if 'OS' in b['Manifest'])
wanted = {'OS': 'os.dmg', 'Cryptex1,SystemOS': 'systemos.dmg', 'Cryptex1,AppOS': 'appos.dmg'}
for key, local in wanted.items():
    member = bi['Manifest'][key]['Info']['Path']
    print(f'  {key} -> {member}')
    with z.open(member) as src, open(dest / local, 'wb') as dst:
        while chunk := src.read(16 << 20):
            dst.write(chunk)
PY

IMG="$WORK/ios16-root.img"
echo "==> mkiosroot.sh -> $IMG"
bash "$ROOT/tools/mkiosroot.sh" "$DMG/os.dmg" "$DMG/systemos.dmg" "$DMG/appos.dmg" "$IMG" 16G

echo "==> fsck y tweaks de bring-up"
sudo fsck.hfsplus -fy "$IMG" || true
MNT=/mnt/iosroot
sudo mkdir -p "$MNT"
sudo mount -t hfsplus -o loop,force "$IMG" "$MNT"
trap 'sudo umount "$MNT" 2>/dev/null || true' EXIT
sudo python3 "$ROOT/tools/sweet-root-tweaks.py" "$MNT"
sudo umount "$MNT"
trap - EXIT

echo "==> Convirtiendo a sparse para fastboot -> $OUT"
img2simg "$IMG" "$OUT"
sha256sum "$OUT" | tee "$OUT.sha256"
echo "==> OK. Ahora: fastboot flash -S 512M userdata $OUT"
