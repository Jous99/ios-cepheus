# Lista de cambios de firmware (Mu-Silicium para nabu)

> Documento de la Xiaomi Pad 5 (nabu), traducido al español. El original en chino está en `docs/original-zh/`.

Directorio de trabajo: WSL `/root/Mu-Silicium` (EDK2 / Mu UEFI)

## 1. El tamaño del FD no cambia

`Resources/Configs/nabu.toml`

```toml
[uefi_fd]
base = 0x9FC00000
size = 0x300000      # 3 MB; no lo agrandes (>32 MB hace que el firmware no arranque)
```

## 2. fdf: no incrustar unixnu.toml

En `[FV.FvMain]` de `Platforms/Xiaomi/nabuPkg/nabu.fdf`, quitar:

```
FILE RAW = 7D9C9E2A-3B4F-4C8E-9A11-2B3C4D5E6F70 {
  SECTION RAW = nabuPkg/unixnu.toml
}
```

Motivo: por la vía de incrustar la configuración en el FV, `Config->Volume` es siempre NULL y DarwinBoot da `NULL input`.
Ahora la configuración la aporta la partición FAT `cust`.

## 3. fdf: conservar DarwinBoot

En `[FV.FvMain]` tiene que estar:

```
INF UniXNUPkg/Application/UniXNU/UniXNU.inf
INF UniXNUPkg/Driver/UniXNUDxe/UniXNUDxe.inf
INF DarwinBootPkg/Driver/DarwinBoot.inf
```

## 4. APRIORI: forzar el despacho de DarwinBoot (¡clave!)

En `Platforms/Xiaomi/nabuPkg/Include/APRIORI.inc`, añadirlo al **primer** bloque `APRIORI DXE { ... }`:

```
APRIORI DXE {
  INF MdeModulePkg/Core/Dxe/DxeMain.inf
  ...
  INF DarwinBootPkg/Driver/DarwinBoot.inf      # <- línea nueva
}
```

Sin esa línea, `LocateProtocol(gUniXNULoaderProtocolGuid)` devuelve `Not Found` y el `Boot()` de DarwinBoot no se ejecuta.

No abras un bloque `APRIORI DXE {}` aparte (GenFv da `ERROR 2000: Invalid parameter`).

## 5. Si en el futuro hay que añadir un driver DXE propio

- Pon el módulo en `Silicium-ACPI/Platforms/Xiaomi/nabu/Drivers/<Nombre>/` (`nabu/` es la raíz del paquete).
- En `[LibraryClasses]` del dsc hay que añadir:
  ```
  FileExplorerLib|MdeModulePkg/Library/FileExplorerLib/FileExplorerLib.inf
  UefiDriverEntryPoint|MdePkg/Library/UefiDriverEntryPoint/UefiDriverEntryPoint.inf
  ```
  Si no, el enlazado da `undefined symbol: _ModuleEntryPoint`.

## 6. Intentos inútiles conocidos (no los repitas)

| Qué se hizo | Resultado |
|---|---|
| Meter el kernel en RAW dentro de FVMAIN | FVMAIN de 62 MB; falla la descompresión de PEI -> vuelve a fastboot |
| Kernel comprimido con LZMA dentro de FVMAIN | FVMAIN de 15 MB, aún fuera de presupuesto -> vuelve a fastboot |
| Blob dentro del FD pero fuera del FV (FD de 60 MB) | FD demasiado grande, BootShim no arranca |
| Registrar el ramdisk en `0x11000000` | ABL no lo pone ahí en realidad -> data abort |
| Registrar el ramdisk desde la entrada del driver DarwinBoot | La entrada del driver no se ejecuta (ver trampa 6) |
