#pragma once
#include <string>
#include <cstdint>
#include <memory>

namespace loom {

enum class TargetArchitecture {
    Native,
    Rp2040Baremetal,
    GenericBaremetal
};

class TargetProfile {
public:
    virtual ~TargetProfile() = default;

    virtual TargetArchitecture architecture() const = 0;
    virtual std::string name() const = 0;
    virtual std::string triple() const = 0;
    virtual std::string cpu() const = 0;
    virtual std::string features() const = 0;

    // Target Capabilities
    virtual bool supportsHeap() const = 0;
    virtual bool supportsThreads() const = 0;
    virtual bool supportsFileIO() const = 0;
    virtual bool supportsVectorSIMD() const = 0;
    virtual bool supportsVolatileIO() const = 0;

    virtual uint32_t pointerWidth() const = 0;
    virtual uint32_t defaultStackAlignment() const = 0;
};

class NativeTargetProfile : public TargetProfile {
public:
    TargetArchitecture architecture() const override { return TargetArchitecture::Native; }
    std::string name() const override { return "native"; }
    std::string triple() const override { return ""; /* System default */ }
    std::string cpu() const override { return "generic"; }
    std::string features() const override { return ""; }

    bool supportsHeap() const override { return true; }
    bool supportsThreads() const override { return true; }
    bool supportsFileIO() const override { return true; }
    bool supportsVectorSIMD() const override { return true; }
    bool supportsVolatileIO() const override { return true; }

    uint32_t pointerWidth() const override { return 64; }
    uint32_t defaultStackAlignment() const override { return 16; }
};

class Rp2040TargetProfile : public TargetProfile {
public:
    TargetArchitecture architecture() const override { return TargetArchitecture::Rp2040Baremetal; }
    std::string name() const override { return "rp2040"; }
    std::string triple() const override { return "thumbv6m-none-eabi"; }
    std::string cpu() const override { return "cortex-m0plus"; }
    std::string features() const override { return ""; }

    bool supportsHeap() const override { return false; }
    bool supportsThreads() const override { return false; }
    bool supportsFileIO() const override { return false; }
    bool supportsVectorSIMD() const override { return false; }
    bool supportsVolatileIO() const override { return true; }

    uint32_t pointerWidth() const override { return 32; }
    uint32_t defaultStackAlignment() const override { return 4; }
};

inline std::unique_ptr<TargetProfile> createTargetProfile(bool baremetal = false, const std::string& targetName = "") {
#ifdef LOOM_TOOLCHAIN_RP2040_ONLY
    (void)baremetal;
    (void)targetName;
    return std::make_unique<Rp2040TargetProfile>();
#else
    if (baremetal || targetName.find("thumb") != std::string::npos || targetName.find("rp2040") != std::string::npos) {
        return std::make_unique<Rp2040TargetProfile>();
    }
    return std::make_unique<NativeTargetProfile>();
#endif
}

} // namespace loom
