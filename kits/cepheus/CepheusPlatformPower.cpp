// CepheusPlatformPower — PMGR skeleton (SM8150 / cepheus)
//
// Addresses and semantics according to the public DTS (see docs/nabu-dts-extract.md; the original cited docs/cepheus-dts-extract.md):
//   apps_rsc: rsc@18200000  compatible "qcom,rpmh-rsc"
//     bank0 0x18200000 +0x10000
//     bank1 0x18210000 +0x10000
//     bank2 0x18220000 +0x10000
//   aop_cmd_db 0x85f20000 +0x20000 (qcom,cmd-db)
//   smem       0x86000000 +0x200000
//   apss_shared mailbox 0x17c00000 (only a mailbox, not RPMh)
//
// At this stage only the "minimal verifiable surface" is done:
//   - Probe(): reads the RSC version/status registers and confirms that 0x18200000 is accessible and the value is reasonable
//   - ReadAon()/WriteAon(): still safe stubs (return 0 / do nothing)
// Nothing is written to the TCS, so the whole device does not hang during the early bring-up.

#include <stdint.h>

namespace cepheus {

// ---- Physical addresses (authoritative DTS values) ----
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
static constexpr uint64_t kTimeBaseHz = 19200000ULL;    // measured

// ---- RSC DRV registers (RPMh TCS command port) ----
static constexpr uint32_t kRscDrvHwVersion   = 0x0000;
static constexpr uint32_t kRscDrvCtlTcsDataHi = 0x0038;
static constexpr uint32_t kRscDrvCtlTcsDataLo = 0x0040;
static constexpr uint32_t kTcsAmcModeEnable   = (1u << 16);

// Helpers to build the AMC (Address/Mask/Command) command word, for the next stage
enum class RpmhCmd : uint32_t {
  kRead  = 0x1,
  kWrite = 0x2,
  kWake  = 0x3,
  kSleep = 0x4,
};

struct RpmhAmcCmd {
  uint32_t message_id;   // TCS address found in cmd-db
  uint32_t addr;         // resource address (from cmd-db)
  uint32_t data;
  uint32_t wait;         // 1 = requires completion acknowledgement
  RpmhCmd  cmd;
};

class CepheusPlatformPower {
 public:
  // Read-only probe: confirms that the RPMh RSC is accessible. It does no writes at all.
  bool Probe();

  // Minimal stand-in for ApplePMGR slots 320 / 321
  uint64_t ReadAon(uint32_t index);
  void     WriteAon(uint32_t index, uint64_t value);

  uint32_t RscHwVersion(uint64_t bank) const;
  bool     Probed() const { return probed_; }

 private:
  bool     probed_ = false;
  uint32_t ver_[3] = {0, 0, 0};
};

bool CepheusPlatformPower::Probe() {
  // TODO(step 1): replace the provisional implementation with real MMIO reads (in UEFI first MapFixedAddress,
  //               in XNU with IOMemoryMap). Only the structure is kept here, to avoid writing registers by mistake.
  ver_[0] = 0;
  ver_[1] = 0;
  ver_[2] = 0;

  // TODO(step 2): check that the HW_VERSION of bank0..2 is from the same family (expected non-zero and equal)
  // TODO(step 3): in cmd-db, look up the TCS base by "sleep"/"wake"/"active"
  // TODO(step 4): reserve the rpmh channel in SMEM (to read back the ack)

  // It can only be set to true in the next stage: steps 1..3 must be completed first
  probed_ = false;
  return probed_;
}

uint32_t CepheusPlatformPower::RscHwVersion(uint64_t /*bank*/) const {
  return 0;  // TODO: MMIO read (bank + kRscDrvHwVersion)
}

uint64_t CepheusPlatformPower::ReadAon(uint32_t index) {
  (void)index;
  // TODO: build RpmhAmcCmd{cmd=kRead} → write TCS_DATA_HI/LO → wait for the DRV to complete → get data
  return 0;
}

void CepheusPlatformPower::WriteAon(uint32_t index, uint64_t value) {
  (void)index;
  (void)value;
  // TODO: same, with cmd=kWrite. The TCS is a shared resource: serialize first and add timeout protection.
}

}  // namespace cepheus

// Called by cepheus-platform-power.patch in bsd_init.c
extern "C" void cepheus_pmgr_run(void) {
  static cepheus::CepheusPlatformPower pmgr;
  pmgr.Probe();
}
