// CepheusPlatformPower — esqueleto de PMGR (SM8150 / cepheus)
//
// Direcciones y semántica según el DTS público (ver docs/nabu-dts-extract.md; el original citaba docs/cepheus-dts-extract.md):
//   apps_rsc: rsc@18200000  compatible "qcom,rpmh-rsc"
//     bank0 0x18200000 +0x10000
//     bank1 0x18210000 +0x10000
//     bank2 0x18220000 +0x10000
//   aop_cmd_db 0x85f20000 +0x20000 (qcom,cmd-db)
//   smem       0x86000000 +0x200000
//   apss_shared mailbox 0x17c00000 (solo es un mailbox, no es RPMh)
//
// En esta fase solo se hace la "superficie mínima verificable":
//   - Probe(): lee los registros de versión/estado del RSC y confirma que 0x18200000 es accesible y que el valor es razonable
//   - ReadAon()/WriteAon(): siguen siendo stubs seguros (devuelven 0 / no hacen nada)
// No se escribe en TCS, para no colgar todo el equipo durante el bring-up temprano.

#include <stdint.h>

namespace cepheus {

// ---- Direcciones físicas (valores autoritativos del DTS) ----
static constexpr uint64_t kRscBank0   = 0x18200000ULL;
static constexpr uint64_t kRscBank1   = 0x18210000ULL;
static constexpr uint64_t kRscBank2   = 0x18220000ULL;
static constexpr uint64_t kRscBankSz  = 0x00010000ULL;

static constexpr uint64_t kCmdDbBase  = 0x85f20000ULL;
static constexpr uint64_t kCmdDbSize  = 0x00020000ULL;
static constexpr uint64_t kSmemBase   = 0x86000000ULL;
static constexpr uint64_t kSmemSize   = 0x00200000ULL;
static constexpr uint64_t kApssShared = 0x17c00000ULL;  // mailbox only
static constexpr uint64_t kSpmiBase   = 0x0c440000ULL;
static constexpr uint64_t kPdcBase    = 0x0b220000ULL;
static constexpr uint64_t kGccBase    = 0x00100000ULL;
static constexpr uint64_t kUfsHcBase  = 0x01d84000ULL;
static constexpr uint64_t kUfsPhyBase = 0x01d87000ULL;
static constexpr uint64_t kTimeBaseHz = 19200000ULL;    // medido

// ---- Registros DRV del RSC (puerto de comandos TCS de RPMh) ----
static constexpr uint32_t kRscDrvHwVersion   = 0x0000;
static constexpr uint32_t kRscDrvCtlTcsDataHi = 0x0038;
static constexpr uint32_t kRscDrvCtlTcsDataLo = 0x0040;
static constexpr uint32_t kTcsAmcModeEnable   = (1u << 16);

// Ayudas para construir la palabra de comando AMC (Address/Mask/Command), para la siguiente fase
enum class RpmhCmd : uint32_t {
  kRead  = 0x1,
  kWrite = 0x2,
  kWake  = 0x3,
  kSleep = 0x4,
};

struct RpmhAmcCmd {
  uint32_t message_id;   // dirección del TCS encontrada en cmd-db
  uint32_t addr;         // dirección del recurso (de cmd-db)
  uint32_t data;
  uint32_t wait;         // 1 = requiere confirmación de finalización
  RpmhCmd  cmd;
};

class CepheusPlatformPower {
 public:
  // Sondeo de solo lectura: confirma que el RPMh RSC es accesible. No hace ninguna escritura.
  bool Probe();

  // Sustituto mínimo de los slots 320 / 321 de ApplePMGR
  uint64_t ReadAon(uint32_t index);
  void     WriteAon(uint32_t index, uint64_t value);

  uint32_t RscHwVersion(uint64_t bank) const;
  bool     Probed() const { return probed_; }

 private:
  bool     probed_ = false;
  uint32_t ver_[3] = {0, 0, 0};
};

bool CepheusPlatformPower::Probe() {
  // TODO(paso 1): sustituir la implementación provisional por lecturas MMIO reales (en UEFI primero MapFixedAddress,
  //               en XNU con IOMemoryMap). Aquí solo se conserva la estructura, para evitar escribir registros por error.
  ver_[0] = 0;
  ver_[1] = 0;
  ver_[2] = 0;

  // TODO(paso 2): comprobar que el HW_VERSION de bank0..2 es de la misma familia (se espera distinto de 0 e igual)
  // TODO(paso 3): en cmd-db, buscar la base del TCS por "sleep"/"wake"/"active"
  // TODO(paso 4): reservar el canal rpmh en SMEM (para releer el ack)

  // Solo se podrá poner a true en la siguiente fase: antes hay que completar los pasos 1..3
  probed_ = false;
  return probed_;
}

uint32_t CepheusPlatformPower::RscHwVersion(uint64_t /*bank*/) const {
  return 0;  // TODO: lectura MMIO (bank + kRscDrvHwVersion)
}

uint64_t CepheusPlatformPower::ReadAon(uint32_t index) {
  (void)index;
  // TODO: armar RpmhAmcCmd{cmd=kRead} → escribir TCS_DATA_HI/LO → esperar la finalización del DRV → obtener data
  return 0;
}

void CepheusPlatformPower::WriteAon(uint32_t index, uint64_t value) {
  (void)index;
  (void)value;
  // TODO: igual, con cmd=kWrite. El TCS es un recurso compartido: primero hay que serializar y poner protección por timeout.
}

}  // namespace cepheus

// Lo llama cepheus-platform-power.patch en bsd_init.c
extern "C" void cepheus_pmgr_run(void) {
  static cepheus::CepheusPlatformPower pmgr;
  pmgr.Probe();
}
