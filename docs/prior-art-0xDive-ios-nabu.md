# Comparación con trabajos previos: 0xDive/ios-nabu

> Documento de la Xiaomi Pad 5 (nabu), traducido al español. El original en chino está en `docs/original-zh/`.

Investigado el 2026-10-21. Repositorio <https://github.com/0xDive/ios-nabu>
(creado el 2026-10-19, Python, 12 PR/issues abiertos, el último #34).

## Siguen un camino totalmente distinto

| Aspecto | 0xDive/ios-nabu | Este proyecto (unixnu-nabu) |
|---|---|---|
| Capa de arranque | **U-Boot v2026.07** (U-Boot de teléfono Qualcomm, pin `ece349ad...`) | **Mu-Silicium EDK2** + UniXNU |
| Objetivo actual | Resolver primero el **canal de logs** (consola USB gadget ACM / `fastboot oem console`) | Arrancar XNU directamente |
| Avance medido | Atascados en el bring-up del firmware / pila USB, **sin ningún resultado de arranque de XNU** | **El kernel XNU ya entra en ejecución** (`DARWINBOOT: hand-off to the kernel`) |

## Sus puntos de bloqueo concretos (PR #30-#34)

El objetivo es que la pila USB de Qualcomm funcione dentro de EDK2 para usar USB como puerto serie:

- Con el PE32 de `PciHostBridge`, `LoadImage` tiene éxito, pero
  `EFI_PCI_ROOT_BRIDGE_IO` / `EFI_PCI_IO` / `EFI_USB2_HC` / `EFI_USB_IO` **faltan todos**.
- Según el antiguo `XhciPciEmulation.c` de código abierto, creen que hay que enlazar `QCOM_USB_CONFIG_PROTOCOL`
  (GUID `E722B03F-B250-42CE-8EBD-5BD51812D037`, comprobado que existe en su binario SM8150 fijado),
  y `EFI_USB_INIT` con GUID `2DA15AC7-4909-4C4C-B8C3-A742195EA46E`.
- Cambiar el orden de DXE (`pci-first` / `usb-stack-first`) provoca una **excepción síncrona antes de la EFI Shell**:
  `ELR 0x13FE0C440`, `ESR 0x02000000` (EC=0), `FAR=0`
  -> simbolizado sin conexión en `ArmCpuDxe::UpdateRegionMappingRecursive()`,
  con `DxeCore::SetUefiImageMemoryAttributes()` / `ProtectUefiImage()` en la pila.
- Probaron `PcdImageProtectionPolicy = 0` para desactivar la protección de imágenes y localizar el fallo; sigue sin funcionar.
- Las etapas 8-11 son sobre todo "auditorías solo en host" (compilar U-Boot, DTS de nabu, Type-C/PHY del PM8150B);
  todos los productos están marcados `safe_to_boot = false`, y **nunca han publicado una imagen arrancable**.

## Tres datos útiles para nosotros

### 1. La trampa de la protección de imágenes de EDK2 (anótala)

La combinación `ArmCpuDxe::UpdateRegionMappingRecursive` + `PcdImageProtectionPolicy`
**no nos ha afectado** al tocar fdf / APRIORI / tamaño del FD, pero si se cambia la disposición o los permisos
de la imagen, podría provocar el mismo tipo de fallo temprano de la MMU. Para investigarlo:
`PcdImageProtectionPolicy = 0` como comparación de una sola variable.

### 2. El DTS público de nabu (material ya hecho para la fase PMGR)

```
repo:   https://github.com/SeimoDev/linux-xiaomi-nabu
commit: 4e6d08bb1b467c721e19cd693e4ec7388d982d73
file:   arch/arm64/boot/dts/qcom/sm8150-xiaomi-nabu.dts
compat: "xiaomi,nabu", "qcom,sm8150"
```

Los nodos de PMGR / UFS / relojes / reguladores se **copian directamente de esta fuente**; es mucho más rápido que
hacer ingeniería inversa de ApplePMGR.
Ojo: hace falta el `sm8150-wcd9340.dtsi` que lo acompaña; no está en el árbol que trae U-Boot.

### 3. Parámetros de hardware de USB / PHY (para escribir después los drivers de USB y carga)

| Elemento | Valor |
|---|---|
| Wrapper USB1 | `0x0A6F8800` (OTG, High-Speed) |
| PHY HS de USB1 | `0x088E2000` |
| Controlador USB2 | `0x0A800000` (host, **SuperSpeed Plus**) |
| Alimentación del PHY | 0.880 V (PLL) / 1.800 V (digital) / 3.072 V (analógico) |
| Type-C | `qcom,pm8150b-typec` + `qcom,pm8150b-vbus-reg` |
| Medido en Android | `/sys/class/udc/a600000.dwc3`: `state=configured`, `maximum_speed=high-speed`, `is_otg=1` |

## Conclusión

**No seguimos su ruta.** Para conseguir logs se desviaron a U-Boot y se atascaron en la capa de firmware;
este proyecto ya tiene medios de log utilizables (`Print` en pantalla y, si hace falta, UART a 115200)
y ya ha pasado de un punto al que ellos no llegaron (ejecución del kernel).

Solo se aprovechan los tres datos **informativos** de arriba, sobre todo el DTS público de nabu, que sirve
directamente para PMGR.
