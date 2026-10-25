# Receta: imagen UEFI + DarwinBoot para el Mi 9 (cepheus)

> **Estado: el firmware compiló en WSL (2026-10-25); la imagen de arranque y el arranque en el teléfono siguen sin probar.**
> (Nota anterior: Lo verificado: el parche `uefi/cepheusPkg-unixnu.patch` aplica limpio sobre
> Mu-Silicium (2026-10-25) y `unixnu status` lee este `board.toml`. )
> Modelo seguido: UniXNU-sheng + uefi-sheng, y las notas de nabu en `docs/firmware-patches.md`.

## Notas de la primera ejecución (2026-10-25)
- El firmware (`build firmware`) compiló bien en WSL.
- `unixnu bootimg` falló con *the ARM64 image header does not describe the shim plus the firmware volume*: el `BootShim.S` de Mu-Silicium
  declara en la cabecera solo `FD_SIZE`, y UniXNU espera `FD_SIZE + tamaño del shim`. Reproducido compilando el shim: `0x300000` frente a `0x300070`.
  Con el `BootShim.S` de uefi-sheng (`uefi/BootShim-unixnu.patch`) la comprobación pasa (`0x3000c0`). Ese shim además limpia la caché antes de saltar al firmware copiado.
  El shim se compila dentro de `bootimg`, así que **no hace falta recompilar el firmware**.
- `bootimg` también necesita `--uefi` y `--dtb ~/Mu-Silicium/Resources/DTBs/cepheus.dtb`.

## Qué hay y qué falta
- Mu-Silicium **ya trae `cepheusPkg`** (Xiaomi Mi 9). Su estado declarado es *Inactive*; en UEFI figuran pantalla,
  almacenamiento y botones como funcionando, y USB host no.
- Mu-Silicium **no trae UniXNU ni DarwinBoot**. El parche `uefi/cepheusPkg-unixnu.patch` los añade a `cepheus.dsc`,
  `cepheus.fdf`, `Include/DXE.inc` y `Include/APRIORI.inc` (DarwinBoot en el firmware y despachado, como en nabu).
- El almacenamiento (UFSDxe, Fat, DiskIo, Partition) ya está en el firmware de cepheus.
- No se usa `UniXNURamDiskDxe`: el payload va en la partición `cust`, como en nabu (el ramdisk de la imagen de arranque es pequeño).

## Pasos (Linux o WSL Ubuntu; Mu-Silicium pesa unos 5 GB)
```bash
sudo apt update && sudo apt install -y git python3 python3-pip clang lld llvm dosfstools mtools device-tree-compiler
cd ~
git clone --recurse-submodules https://github.com/UniXNU/UniXNU.git
git clone --recursive https://github.com/Project-Silicium/Mu-Silicium.git
git clone https://github.com/Jous99/ios-cepheus.git
mkdir -p ~/ios-cepheus/out

cd ~/Mu-Silicium && ./setup_env.sh -p apt && python3 -m pip install -r pip-requirements.txt
git apply ~/ios-cepheus/uefi/cepheusPkg-unixnu.patch        # añade UniXNU/DarwinBoot a cepheusPkg
git apply ~/ios-cepheus/uefi/BootShim-unixnu.patch          # shim de uefi-sheng: cabecera ARM64 con el tamaño total (shim+FD) y limpieza de caché

cd ~/UniXNU
./unixnu build firmware --uefi ~/Mu-Silicium -D ~/ios-cepheus     # firmware UEFI (.fd)
./unixnu bootimg --uefi ~/Mu-Silicium -D ~/ios-cepheus             # imagen de arranque Android (BootShim + FD + dtb)
# si pide el árbol de dispositivo: añade  --dtb ~/Mu-Silicium/Resources/DTBs/cepheus.dtb
```
Si `build firmware` falla, pega el primer `error` y la línea anterior.

## Payload de la partición `cust` (kernel + ADT)
```bash
cd ~/ios-cepheus
cp /mnt/c/Users/Jous/Desktop/ios-cepheus/out/kernel/out/kernel.development.cepheus out/kernel.macho
# MemTotal de TU móvil -> dram-size. 6 GB: 0x180000000; 8 GB: 0x200000000 (confirma con /proc/meminfo)
python3 scripts/make-cepheus-adt.py --dram-size 0x180000000 --output out/kernel.macho.adt
bash scripts/make-cepheus-cust-payload.sh out/kernel.macho out/kernel.macho.adt out/cust-payload.img
```
Revisa antes `TODO-MEASURE.md`: el `fbcon` y el `maxmem` del ADT siguen por confirmar.

## Antes de tocar el móvil
1. Copia de seguridad de `cust` desde TWRP (`dd if=/dev/block/by-name/cust`), y comprueba que pesa ~1 GB.
2. Un cable de datos bueno (los cables malos dan `Load Error` con imágenes de ~96 MB).
3. Reinicia el móvil antes de cada `fastboot boot`.

## Probar (solo escribe en `cust`; `fastboot boot` no escribe en disco)
```bash
fastboot flash cust out/cust-payload.img
fastboot boot ~/UniXNU/out/cepheus/<la-imagen-de-arranque>.img     # la ruta exacta la imprime `unixnu bootimg`
```
Si se cuelga: pulsación larga del botón de encendido (10 s).

## Lo que NO está garantizado
- Que el kernel xnu-8796 arranque a través de DarwinBoot (no hay evidencia previa).
- Que el firmware de cepheus de Mu-Silicium (estado *Inactive*) funcione tal cual en tu unidad.
- Que la versión de DarwinBoot de UniXNU upstream encaje con este kernel (puede que haga falta la del fork de nabu).
- `board.toml` `[firmware]`: la lista de parches de Mu y los `defines` son los de Mu-Silicium, no probados con `unixnu build`.
