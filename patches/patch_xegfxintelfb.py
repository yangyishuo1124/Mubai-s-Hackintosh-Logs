from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()

# 0. Replace fixed XIFB_AUX_CTL / XIFB_AUX_DATA with dynamic gAuxCtl / gAuxData so we can probe all AUX ports
aux_macros = """#define XIFB_AUX_CTL  0x64010
#define XIFB_AUX_DATA 0x64014"""
assert aux_macros in s, "aux_macros missing"

s = s.replace(
    aux_macros,
    "static uint32_t gAuxCtl = 0x64010;\n#define XIFB_AUX_CTL  gAuxCtl\n#define XIFB_AUX_DATA (gAuxCtl + 4)",
    1,
)

# 1. Include <IOKit/graphics/IODisplay.h>, add native AUX DPCD helpers right before xifbMeasureHz
anchor1 = "// pipe A's frame counter over about half a second: the refresh rate the firmware's mode runs at, in 16.16"
assert anchor1 in s, "anchor1 missing"

aux_dpcd_code = r"""#include <IOKit/graphics/IODisplay.h>
#include <IOKit/pwr_mgt/IOPM.h>
#include <IOKit/pwr_mgt/RootDomain.h>
#include <libkern/libkern.h>

// Native eDP AUX DPCD read/write (cmd 0x9 = read, 0x8 = write) for panel backlight (0x300..0x359, 0x700..0x737)
static int xifbAuxDpcd(uint8_t cmd, uint32_t addr, const uint8_t *wdata, uint8_t len, uint8_t *rdata)
{
    if (len == 0 || len > 16) return -1;
    uint8_t tx[20] = {
        (uint8_t)((cmd << 4) | ((addr >> 16) & 0xf)),
        (uint8_t)((addr >> 8) & 0xff),
        (uint8_t)(addr & 0xff),
        (uint8_t)(len - 1)
    };
    int ntx = 4;
    if (cmd == 0x8) {
        for (uint8_t i = 0; i < len; i++) tx[ntx++] = wdata[i];
    }
    uint8_t rx[17] = {};
    int nrx = (cmd == 0x9) ? (1 + len) : 1;
    for (int t = 0; t < 7; t++) {
        int n = xifbAux(tx, ntx, rx, nrx);
        if (n >= 1) {
            uint8_t reply = (rx[0] >> 4) & 0x3;
            if (reply == 0) { // AUX_ACK
                if (cmd == 0x9) {
                    if (n < 1 + len) return -1;
                    bcopy(rx + 1, rdata, len);
                }
                return 0;
            }
            if (reply == 1) return -1; // AUX_NACK
        }
        IODelay(500);
    }
    return -1;
}

static bool xifbProbeEdidAllAux(uint8_t *edid, int *len, uint32_t *foundCtl)
{
    static const uint32_t kAuxPorts[] = {
        0x16fa10u, 0x16fc10u, 0x16fe10u, 0x170010u,
        0x16f210u, 0x16f410u, 0x16f610u, 0x16f810u,
        0x64010u, 0x64110u, 0x64210u, 0x64310u, 0x64410u
    };
    for (unsigned i = 0; i < sizeof kAuxPorts / sizeof kAuxPorts[0]; i++) {
        gAuxCtl = kAuxPorts[i];
        uint32_t pre = xr(gAuxCtl);
        if (pre == 0xffffffffu) continue;
        if (xifbReadEdid(edid, len)) {
            if (foundCtl) *foundCtl = gAuxCtl;
            return true;
        }
        XIFBLOG("AUX %06x: pre=%08x post=%08x (no EDID)", gAuxCtl, pre, xr(gAuxCtl));
    }
    gAuxCtl = 0x64010u;
    return false;
}

"""
s = s.replace(anchor1, aux_dpcd_code + anchor1, 1)

# 1b. Declare XeGfxBacklightHandler (IODisplayParameterHandler subclass) right before XeGfxIntelFramebuffer
fb_cls_anchor = "class XeGfxIntelFramebuffer : public IONDRVFramebuffer {"
assert fb_cls_anchor in s, "fb_cls_anchor missing"
bl_handler_decl = r"""class XeGfxIntelFramebuffer;

static void xifbUpdateParamValue(IODisplay *display, const char *keyStr, SInt32 val);

class XeGfxBacklightHandler : public IODisplayParameterHandler {
    OSDeclareDefaultStructors(XeGfxBacklightHandler)
public:
    XeGfxIntelFramebuffer *fFb = nullptr;
    IODisplay *fDisplay = nullptr;
    uint32_t fUserLevel = 1024;
    uint32_t fFadeLevel = 0;
    static constexpr SInt32 kUiMax = 1024;

    static XeGfxBacklightHandler *withFramebuffer(XeGfxIntelFramebuffer *fb);
    bool setDisplay(IODisplay *display) override;
    bool doIntegerSet(OSDictionary *params, const OSSymbol *paramName, UInt32 value) override;
    bool doDataSet(const OSSymbol *paramName, OSData *value) override;
    bool doUpdate(void) override;
    void applyEffective();
};

class XeGfxIntelFramebuffer : public IONDRVFramebuffer {"""
s = s.replace(fb_cls_anchor, bl_handler_decl, 1)

# 2. Add VBL timer + interrupt state + backlight state (Intel HDR TCON + VESA DPCD + SoC PWM) inside XeGfxIntelFramebuffer
anchor2 = "    SInt32 fCurX = 0, fCurY = 0; bool fCurVis = false, fCurImg = false;"
assert anchor2 in s, "anchor2 missing"

members_code = r"""    friend class XeGfxBacklightHandler;
    SInt32 fCurX = 0, fCurY = 0; bool fCurVis = false, fCurImg = false;
    uint32_t fAuxCtl = 0x64010u;
    // High-refresh VBL timer & interrupt delivery (replaces 30 Hz IONDRVFramebuffer default)
    struct Irq { IOFBInterruptProc proc = nullptr; OSObject *target = nullptr; void *ref = nullptr; };
    Irq fVbl;
    bool fVblEnabled = true;
    thread_call_t fVblTimer = nullptr;
    uint64_t fFrameNs = 16666667ull;
    uint64_t fVblNext = 0, fVblLastTime = 0, fVblCalls = 0;
    volatile bool fStopping = false;
    static void vblFire(thread_call_param_t p0, thread_call_param_t) {
        XeGfxIntelFramebuffer *me = (XeGfxIntelFramebuffer *)p0;
        if (me->fStopping) return;
        uint64_t now = mach_absolute_time();
        me->fVblLastTime = now;
        if (!me->fDisplayAsleep && me->fVblEnabled && me->fVbl.proc) {
            me->fVbl.proc(me->fVbl.target, me->fVbl.ref);
            me->fVblCalls++;
        }
        uint64_t period = 0;
        nanoseconds_to_absolutetime(me->fFrameNs, &period);
        me->fVblNext = (me->fVblNext && me->fVblNext + period > now) ? me->fVblNext + period : now + period;
        thread_call_enter_delayed(me->fVblTimer, me->fVblNext);
    }
    void armVbl() {
        if (fVblTimer) return;
        if (fHz16 > (15u << 16)) {
            fFrameNs = (1000000000ull << 16) / (uint64_t)fHz16;
        }
        if (fFrameNs < 2000000ull || fFrameNs > 33333333ull) fFrameNs = 16666667ull;
        fVblTimer = thread_call_allocate(vblFire, this);
        if (fVblTimer) {
            uint64_t d = 0;
            clock_interval_to_deadline((uint32_t)(fFrameNs / 1000ull), kMicrosecondScale, &d);
            fVblNext = d;
            fVblLastTime = mach_absolute_time();
            thread_call_enter_delayed(fVblTimer, d);
        }
        XIFBLOG("vbl timer %s (period %llu us)", fVblTimer ? "armed" : "FAILED", (unsigned long long)(fFrameNs / 1000ull));
    }

    // Backlight control: Intel HDR TCON DPCD (0x340..0x359), VESA eDP DPCD (0x700..0x737), SoC PWM fallback
    IOPCIDevice *fPci = nullptr;
    bool fBlReady = false, fBlHdr = false, fBl16Bit = false, fBlPwm = false, fDisplayAsleep = false;
    bool fBlPanelWasOff = false;
    bool fClamshellClosed = false;
    int fBlReapplyLeft = 0;
    IONotifier *fPmNotifier = nullptr;
    uint32_t fBlLastFc = 0;
    uint32_t fBlLevel = 0x10000u, fBlSaveLevel = 0x10000u, fBlHwMax = 65535u, fBlPwmBase = 0, fBlPwmFreq = 0;
    uint32_t fBlHdrMin = 0, fBlHdrMax = 512;
    uint8_t fBlPwmBits = 0;
    XeGfxBacklightHandler *fBlHandler = nullptr;
    IOLock *fBlLock = nullptr;
    thread_call_t fBlSaveTimer = nullptr;
    thread_call_t fBlWatchTimer = nullptr;
    bool fHasSavedBl = false;
    uint64_t fBlInitNs = 0;
    static constexpr uint32_t kBlMax = 0x10000u;
    static constexpr uint32_t kBlMinFloor = 0x400u;

    static void nvramSetStr(const char *key, const char *str) {
        if (!key || !str) return;
        IORegistryEntry *o = IORegistryEntry::fromPath("/options", gIODTPlane);
        if (!o) return;
        if (OSData *d = OSData::withBytes(str, (unsigned)strlen(str))) {
            o->setProperty(key, d);
            d->release();
        }
        o->release();
    }
    static bool nvramReadU32(const char *key, uint32_t *out) {
        IORegistryEntry *o = IORegistryEntry::fromPath("/options", gIODTPlane);
        if (!o) return false;
        OSObject *v = o->copyProperty(key);
        OSData *d = OSDynamicCast(OSData, v);
        bool ok = false;
        if (d && d->getLength() == sizeof(uint32_t)) {
            bcopy(d->getBytesNoCopy(), out, sizeof(uint32_t));
            ok = true;
        }
        if (v) v->release();
        o->release();
        return ok;
    }
    static void nvramWriteU32(const char *key, uint32_t val) {
        IORegistryEntry *o = IORegistryEntry::fromPath("/options", gIODTPlane);
        if (!o) return;
        if (OSData *d = OSData::withBytes(&val, sizeof(val))) {
            o->setProperty(key, d);
            d->release();
        }
        o->release();
    }
    static void blSaveFire(thread_call_param_t p0, thread_call_param_t) {
        XeGfxIntelFramebuffer *me = (XeGfxIntelFramebuffer *)p0;
        if (me->fStopping) return;
        nvramWriteU32("xeintelfb-bl", me->fBlSaveLevel);
    }
    void scheduleBlSave(uint32_t level) {
        if (level > kBlMax) level = kBlMax;
        fBlSaveLevel = level;
        if (!fBlSaveTimer) fBlSaveTimer = thread_call_allocate(blSaveFire, this);
        if (fBlSaveTimer) {
            uint64_t dl = 0;
            clock_interval_to_deadline(1000, kMillisecondScale, &dl);
            thread_call_enter_delayed(fBlSaveTimer, dl);
        }
    }
    static bool readClamshellClosed() {
        IOService *pm = IOService::getPMRootDomain();
        if (!pm) return false;
        OSObject *cs = pm->copyProperty("AppleClamshellState");
        bool closed = (cs == kOSBooleanTrue);
        if (cs) cs->release();
        return closed;
    }
    static IOReturn pmInterestCb(void *target, void *, UInt32 messageType, IOService *provider, void *, vm_size_t) {
        XeGfxIntelFramebuffer *me = (XeGfxIntelFramebuffer *)target;
        if (!me || me->fStopping) return kIOReturnSuccess;
        OSObject *cs = provider ? provider->copyProperty("AppleClamshellState") : nullptr;
        bool closed = (cs == kOSBooleanTrue);
        if (cs) cs->release();
        if (closed) {
            if (!me->fClamshellClosed) {
                me->fClamshellClosed = true;
                me->fBlReapplyLeft = 0;
                XIFBLOG("clamshell closed (msg=%08x)", (unsigned)messageType);
            }
        } else if (me->fClamshellClosed) {
            me->fClamshellClosed = false;
            me->fBlReapplyLeft = 4;
            XIFBLOG("clamshell opened (msg=%08x) -> scheduling brightness restore %u/%u",
                    (unsigned)messageType, (unsigned)me->fBlLevel, (unsigned)kBlMax);
            if (me->fBlWatchTimer) {
                uint64_t dl = 0;
                clock_interval_to_deadline(50, kMillisecondScale, &dl);
                thread_call_enter_delayed(me->fBlWatchTimer, dl);
            }
        }
        return kIOReturnSuccess;
    }
    static void blWatchFire(thread_call_param_t p0, thread_call_param_t) {
        XeGfxIntelFramebuffer *me = (XeGfxIntelFramebuffer *)p0;
        if (me->fStopping) return;
        bool closed = readClamshellClosed();
        if (closed) {
            if (!me->fClamshellClosed) {
                me->fClamshellClosed = true;
                me->fBlReapplyLeft = 0;
                XIFBLOG("clamshell closed (polled)");
            }
        } else if (me->fClamshellClosed) {
            me->fClamshellClosed = false;
            me->fBlReapplyLeft = 4;
            XIFBLOG("clamshell opened (polled) -> scheduling brightness restore %u/%u",
                    (unsigned)me->fBlLevel, (unsigned)kBlMax);
        }
        if (!closed && !me->fDisplayAsleep && me->fBlReady && me->fBlHdr && me->fR && me->fPci &&
            (me->fPci->configRead16(kIOPCIConfigCommand) & kIOPCICommandMemorySpace)) {
            bool needRestore = false;
            uint32_t ppSt = me->rd(0xc7200);
            uint32_t ppCtl = me->rd(0xc7204);
            uint32_t fc = me->rd(0x70040);
            bool panelOff = ((ppSt & 0x80000000u) == 0) || ((ppCtl & 0x05u) != 0x05u) || (fc == me->fBlLastFc && me->fBlLastFc != 0);
            me->fBlLastFc = fc;
            if (me->fBlReapplyLeft > 0) {
                me->fBlReapplyLeft--;
                needRestore = true;
            }
            if (panelOff) {
                me->fBlPanelWasOff = true;
            } else {
                if (me->fBlPanelWasOff) {
                    me->fBlPanelWasOff = false;
                    needRestore = true;
                }
                if (me->fBlLock) IOLockLock(me->fBlLock);
                gRegs = me->fR;
                gAuxCtl = me->fAuxCtl;
                uint8_t oui[3] = {}, c0 = 0, ovr[4] = {}, rbN[4] = {};
                if (xifbAuxDpcd(0x9, 0x300, nullptr, 3, oui) != 0) {
                    me->fBlPanelWasOff = true;
                } else {
                    if (oui[0] != 0x00 || oui[1] != 0xaa || oui[2] != 0x01) {
                        needRestore = true;
                    }
                    if (xifbAuxDpcd(0x9, 0x344, nullptr, 1, &c0) != 0 ||
                        xifbAuxDpcd(0x9, 0x34a, nullptr, 4, ovr) != 0 ||
                        xifbAuxDpcd(0x9, 0x354, nullptr, 4, rbN) != 0) {
                        me->fBlPanelWasOff = true;
                    } else {
                        uint32_t hwMin = (uint32_t)ovr[0] | ((uint32_t)ovr[1] << 8);
                        uint32_t hwMax = (uint32_t)ovr[2] | ((uint32_t)ovr[3] << 8);
                        uint32_t hwNit = (uint32_t)rbN[0] | ((uint32_t)rbN[1] << 8);
                        uint32_t span = (me->fBlHdrMax > me->fBlHdrMin) ? (me->fBlHdrMax - me->fBlHdrMin) : 512u;
                        uint32_t wantNit = (me->fBlLevel == 0) ? 0 : (me->fBlHdrMin + (uint32_t)(((uint64_t)me->fBlLevel * span + kBlMax / 2) / kBlMax));
                        uint32_t diff = (hwNit > wantNit) ? (hwNit - wantNit) : (wantNit - hwNit);
                        if ((c0 & 0x10u) == 0 || hwMin != me->fBlHdrMin || hwMax != me->fBlHdrMax || diff > 4u) {
                            needRestore = true;
                        }
                    }
                }
                gRegs = nullptr;
                if (me->fBlLock) IOLockUnlock(me->fBlLock);
                if (needRestore) {
                    XIFBLOG("lid/panel restore (pp=%08x/%08x c0=%02x nit=%02x%02x rem=%d) -> bl=%u/%u",
                            (unsigned)ppSt, (unsigned)ppCtl, (unsigned)c0, rbN[1], rbN[0],
                            me->fBlReapplyLeft, (unsigned)me->fBlLevel, (unsigned)kBlMax);
                    (void)me->blWriteHw(me->fBlLevel);
                }
            }
        }
        uint64_t dl = 0;
        clock_interval_to_deadline(500, kMillisecondScale, &dl);
        thread_call_enter_delayed(me->fBlWatchTimer, dl);
    }
    void armBlWatch() {
        if (!fBlReady || !fBlHdr || fBlWatchTimer) return;
        IOService *pm = IOService::getPMRootDomain();
        if (pm && !fPmNotifier) {
            fPmNotifier = pm->registerInterest(gIOGeneralInterest, pmInterestCb, this, nullptr);
        }
        fBlWatchTimer = thread_call_allocate(blWatchFire, this);
        if (fBlWatchTimer) {
            uint64_t dl = 0;
            clock_interval_to_deadline(500, kMillisecondScale, &dl);
            thread_call_enter_delayed(fBlWatchTimer, dl);
            XIFBLOG("blWatchFire armed (500ms, pm=%d)", fPmNotifier != nullptr ? 1 : 0);
        }
    }
    void snapDeRegs(const char *tag, bool writeNvram) {
        uint16_t cmd = fPci ? fPci->configRead16(kIOPCIConfigCommand) : 0;
        uint32_t pipe = 0xffffffffu, pln = 0xffffffffu, surf = 0xffffffffu, ddi = 0xffffffffu;
        uint32_t pwr = 0xffffffffu, cd = 0xffffffffu, ppSt = 0xffffffffu, ppCtl = 0xffffffffu, aux = 0xffffffffu, fc = 0xffffffffu;
        if (fR && (cmd & kIOPCICommandMemorySpace)) {
            pipe = rd(0x70008);
            pln  = rd(0x70180);
            surf = rd(0x7019c);
            ddi  = rd(0x60400);
            pwr  = rd(0x45404);
            cd   = rd(0x46000);
            ppSt = rd(0xc7200);
            ppCtl = rd(0xc7204);
            aux  = rd(fAuxCtl);
            fc   = rd(0x70040);
        }
        char buf[220];
        snprintf(buf, sizeof(buf),
                 "%s:cmd=%04x pipe=%08x pln=%08x surf=%08x ddi=%08x pwr=%08x cd=%08x pp=%08x/%08x aux=%08x fc=%u bl=%u",
                 tag, (unsigned)cmd, (unsigned)pipe, (unsigned)pln, (unsigned)surf, (unsigned)ddi,
                 (unsigned)pwr, (unsigned)cd, (unsigned)ppSt, (unsigned)ppCtl, (unsigned)aux,
                 (unsigned)fc, (unsigned)fBlLevel);
        XIFBLOG("%s", buf);
        if (writeNvram) nvramSetStr("xeintelfb-wake", buf);
    }
    void blInit() {
        if (!fR) return;
        if (!fBlLock) fBlLock = IOLockAlloc();
        if (fBlLock) IOLockLock(fBlLock);
        gRegs = fR;
        gAuxCtl = fAuxCtl;

        uint8_t oui[4] = {}, hdrCap[6] = {}, hdrOvr[4] = {}, hdrNits[4] = {};
        bool ouiOk = (xifbAuxDpcd(0x9, 0x300, nullptr, 3, oui) == 0);
        bool hdrOk = (xifbAuxDpcd(0x9, 0x340, nullptr, 6, hdrCap) == 0);
        if ((!ouiOk || oui[0] != 0x00 || oui[1] != 0xaa || oui[2] != 0x01) && (!hdrOk || hdrCap[0] == 0)) {
            static const uint8_t kIntelOui[3] = { 0x00, 0xaa, 0x01 };
            (void)xifbAuxDpcd(0x8, 0x300, kIntelOui, 3, nullptr);
            IOSleep(10);
            hdrOk = (xifbAuxDpcd(0x9, 0x340, nullptr, 6, hdrCap) == 0);
        }
        (void)xifbAuxDpcd(0x9, 0x34a, nullptr, 4, hdrOvr);
        (void)xifbAuxDpcd(0x9, 0x354, nullptr, 4, hdrNits);
        XIFBLOG("eDP HDR DPCD (%06x): oui=%02x%02x%02x cap=[%02x %02x %02x %02x] ctrl=%02x ovr=[%02x%02x %02x%02x] nits=[%02x %02x %02x %02x]",
                fAuxCtl, oui[0], oui[1], oui[2],
                hdrCap[0], hdrCap[1], hdrCap[2], hdrCap[3], hdrCap[4],
                hdrOvr[1], hdrOvr[0], hdrOvr[3], hdrOvr[2],
                hdrNits[0], hdrNits[1], hdrNits[2], hdrNits[3]);

        uint8_t caps[8] = {}, ctrl[8] = {}, lum[8] = {};
        bool vesaOk = (xifbAuxDpcd(0x9, 0x700, nullptr, 8, caps) == 0 && xifbAuxDpcd(0x9, 0x720, nullptr, 8, ctrl) == 0);
        (void)xifbAuxDpcd(0x9, 0x730, nullptr, 8, lum);
        if (vesaOk) {
            XIFBLOG("eDP VESA DPCD: 700=[%02x %02x %02x %02x %02x %02x %02x %02x] 720=[%02x %02x %02x %02x %02x %02x %02x %02x] 730=[%02x %02x %02x %02x %02x %02x %02x %02x]",
                    caps[0], caps[1], caps[2], caps[3], caps[4], caps[5], caps[6], caps[7],
                    ctrl[0], ctrl[1], ctrl[2], ctrl[3], ctrl[4], ctrl[5], ctrl[6], ctrl[7],
                    lum[0], lum[1], lum[2], lum[3], lum[4], lum[5], lum[6], lum[7]);
        } else {
            XIFBLOG("eDP VESA DPCD (%06x): AUX read 0x700/0x720 failed", fAuxCtl);
        }

        // Prefer Intel HDR TCON DPCD if TCON advertises nits + SDR AUX control (i915 intel_dp_aux_backlight.c)
        if (hdrOk && hdrCap[0] >= 1 && (hdrCap[1] & 0x10u) && (hdrCap[2] & 0x01u)) {
            uint32_t ovrMin = (uint32_t)hdrOvr[0] | ((uint32_t)hdrOvr[1] << 8);
            uint32_t ovrMax = (uint32_t)hdrOvr[2] | ((uint32_t)hdrOvr[3] << 8);
            uint32_t curNits = (uint32_t)hdrNits[0] | ((uint32_t)hdrNits[1] << 8);
            if (ovrMax > ovrMin && ovrMax <= 2000u) {
                fBlHdrMin = ovrMin;
                fBlHdrMax = ovrMax;
            } else {
                fBlHdrMin = 0;
                fBlHdrMax = (curNits > 512u && curNits <= 1200u) ? curNits : 512u;
            }
            if ((hdrCap[4] & 0x10u) && curNits > 0 && fBlHdrMax > fBlHdrMin) {
                uint32_t span = fBlHdrMax - fBlHdrMin;
                uint32_t c = (curNits > fBlHdrMin) ? (curNits - fBlHdrMin) : 0;
                if (c > span) c = span;
                fBlLevel = (uint32_t)(((uint64_t)c * kBlMax + span / 2) / span);
            } else {
                fBlLevel = kBlMax;
            }
            fBlHdr = true;
            fBlReady = true;
            XIFBLOG("eDP backlight mode: Intel HDR TCON (%u..%u nits, cur=%u -> fBl=%u)",
                    (unsigned)fBlHdrMin, (unsigned)fBlHdrMax, (unsigned)curNits, (unsigned)fBlLevel);
        } else if (vesaOk && (caps[2] & 0x02u)) {
            // VESA: 0x702 bit 1 = aux_set, bit 2 = 16-bit LSB reg (0x722 MSB + 0x723 LSB)
            fBl16Bit = (caps[2] & 0x04u) != 0;
            uint8_t pn = ctrl[4] & 0x1fu;
            uint8_t pnMin = caps[6] & 0x1fu;
            uint8_t pnMax = caps[7] & 0x1fu;
            if (pnMax >= 8u && pnMax <= 16u && pnMin <= pnMax) {
                if (pn < pnMin || pn > pnMax) pn = pnMax;
                fBlPwmBits = pn;
                fBlHwMax = (1u << pn) - 1u;
            } else {
                fBlPwmBits = 0;
                fBlHwMax = fBl16Bit ? 65535u : 255u;
            }
            uint32_t cur = fBl16Bit ? (((uint32_t)ctrl[2] << 8) | ctrl[3]) : ctrl[2];
            if ((ctrl[1] & 0x03u) != 0x02u) {
                fBlLevel = kBlMax; // assume 100% until DPCD control mode is active
            } else {
                if (cur > fBlHwMax) cur = fBlHwMax;
                fBlLevel = fBlHwMax ? (uint32_t)(((uint64_t)cur * kBlMax + fBlHwMax / 2) / fBlHwMax) : kBlMax;
            }
            if (fBlLevel > kBlMax) fBlLevel = kBlMax;
            fBlReady = true;
            XIFBLOG("eDP backlight mode: VESA DPCD (%s, pn=%u, hwMax=%u, cur=%u -> fBl=%u)",
                    fBl16Bit ? "16b" : "8b", (unsigned)fBlPwmBits, (unsigned)fBlHwMax, (unsigned)cur, (unsigned)fBlLevel);
        }
        static const uint32_t kPwmBases[2] = { 0xc8250u, 0xc8350u };
        for (int i = 0; i < 2; i++) {
            uint32_t base = kPwmBases[i];
            uint32_t ctl = rd(base), freq = rd(base + 4), duty = rd(base + 8);
            XIFBLOG("SoC PWM%d (%06x): ctl=%08x freq=%u duty=%u", i, base, ctl, freq, duty);
            if (!fBlReady && (ctl & (1u << 31)) && freq > 0) {
                fBlPwm = true;
                fBlPwmBase = base;
                fBlPwmFreq = freq;
                fBlLevel = (duty <= freq) ? (uint32_t)(((uint64_t)duty * kBlMax + freq / 2) / freq) : kBlMax;
                if (fBlLevel > kBlMax) fBlLevel = kBlMax;
                fBlReady = true;
            }
        }
        gRegs = nullptr;
        if (fBlLock) IOLockUnlock(fBlLock);

        if (fBlReady) {
            absolutetime_to_nanoseconds(mach_absolute_time(), &fBlInitNs);
            uint32_t savedBl = 0;
            if (nvramReadU32("xeintelfb-bl", &savedBl) && savedBl <= kBlMax) {
                if (savedBl < kBlMinFloor) savedBl = kBlMinFloor;
                fBlLevel = savedBl;
                fBlSaveLevel = savedBl;
                fHasSavedBl = true;
                bool wOk = blWriteHw(fBlLevel);
                XIFBLOG("restored saved NVRAM brightness %u/%u (hw=%s)",
                        (unsigned)fBlLevel, (unsigned)kBlMax, wOk ? "ok" : "err");
            } else {
                fBlSaveLevel = fBlLevel;
            }
        }

        if (fBlReady && !fBlHandler) {
            fBlHandler = XeGfxBacklightHandler::withFramebuffer(this);
            if (fBlHandler) {
                if (!fBlHandler->attach(this)) {
                    fBlHandler->release();
                    fBlHandler = nullptr;
                } else {
                    fBlHandler->start(this);
                    fBlHandler->registerService();
                    XIFBLOG("XeGfxBacklightHandler attached (initLevel=%u)", (unsigned)fBlLevel);
                }
            }
        }
    }
    bool blSet(uint32_t level) {
        if (!fBlReady || !fR) return false;
        if (level > kBlMax) level = kBlMax;
        fBlLevel = level;
        if (fDisplayAsleep) return true;
        return blWriteHw(level);
    }
    bool blWriteHw(uint32_t level) {
        if (!fBlReady || !fR) return false;
        if (level > kBlMax) level = kBlMax;
        if (fBlLock) IOLockLock(fBlLock);
        if (fBlPwm) {
            uint32_t duty = (uint32_t)(((uint64_t)level * fBlPwmFreq + kBlMax / 2) / kBlMax);
            wr(fBlPwmBase + 8, duty);
            if (fBlLock) IOLockUnlock(fBlLock);
            return true;
        }
        gRegs = fR;
        gAuxCtl = fAuxCtl;
        static unsigned nSetLog = 0;
        bool doLog = (++nSetLog <= 12);
        if (fBlHdr) {
            static const uint8_t kIntelOui[3] = { 0x00, 0xaa, 0x01 };
            (void)xifbAuxDpcd(0x8, 0x300, kIntelOui, 3, nullptr);
            uint32_t span = (fBlHdrMax > fBlHdrMin) ? (fBlHdrMax - fBlHdrMin) : 512u;
            uint32_t nit = (level == 0) ? 0 : (fBlHdrMin + (uint32_t)(((uint64_t)level * span + kBlMax / 2) / kBlMax));
            uint8_t ovr[4] = {
                (uint8_t)(fBlHdrMin & 0xffu), (uint8_t)((fBlHdrMin >> 8) & 0xffu),
                (uint8_t)(fBlHdrMax & 0xffu), (uint8_t)((fBlHdrMax >> 8) & 0xffu)
            };
            (void)xifbAuxDpcd(0x8, 0x34a, ovr, 4, nullptr);
            uint8_t nb[4] = { (uint8_t)(nit & 0xffu), (uint8_t)((nit >> 8) & 0xffu), 0, 0 };
            int rc = xifbAuxDpcd(0x8, 0x354, nb, 4, nullptr);
            uint8_t c0 = 0;
            if (xifbAuxDpcd(0x9, 0x344, nullptr, 1, &c0) == 0) {
                uint8_t c1 = c0 | 0x10u; // INTEL_EDP_HDR_TCON_BRIGHTNESS_AUX_ENABLE
                if (c1 != c0) (void)xifbAuxDpcd(0x8, 0x344, &c1, 1, nullptr);
            }
            if (doLog) {
                uint8_t rbC = 0, rbN[4] = {};
                (void)xifbAuxDpcd(0x9, 0x344, nullptr, 1, &rbC);
                (void)xifbAuxDpcd(0x9, 0x354, nullptr, 4, rbN);
                XIFBLOG("blSet HDR lvl=%u -> nit=%u rc=%d rb[344=%02x 354=%02x%02x]",
                        (unsigned)level, (unsigned)nit, rc, rbC, rbN[1], rbN[0]);
            }
            gRegs = nullptr;
            if (fBlLock) IOLockUnlock(fBlLock);
            return rc == 0;
        }
        uint32_t v = (uint32_t)(((uint64_t)level * fBlHwMax + kBlMax / 2) / kBlMax);
        uint8_t curCtrl = 0;
        (void)xifbAuxDpcd(0x9, 0x720, nullptr, 1, &curCtrl);
        if (fBlPwmBits) {
            (void)xifbAuxDpcd(0x8, 0x724, &fBlPwmBits, 1, nullptr);
        }
        uint8_t mode = 0x02u; // DP_EDP_BACKLIGHT_CONTROL_MODE_DPCD
        (void)xifbAuxDpcd(0x8, 0x721, &mode, 1, nullptr);
        int rc = -1;
        if (fBl16Bit) {
            uint8_t val[2] = { (uint8_t)((v >> 8) & 0xffu), (uint8_t)(v & 0xffu) };
            rc = xifbAuxDpcd(0x8, 0x722, val, 2, nullptr);
        } else {
            uint8_t val[1] = { (uint8_t)(v & 0xffu) };
            rc = xifbAuxDpcd(0x8, 0x722, val, 1, nullptr);
        }
        uint8_t en = (curCtrl & ~0x01u) | (level > 0 ? 0x01u : 0x00u);
        (void)xifbAuxDpcd(0x8, 0x720, &en, 1, nullptr);
        if (doLog) {
            uint8_t rb[5] = {};
            (void)xifbAuxDpcd(0x9, 0x720, nullptr, 5, rb);
            XIFBLOG("blSet VESA lvl=%u -> hw=%u rc=%d rb[720..724=%02x %02x %02x %02x %02x]",
                    (unsigned)level, (unsigned)v, rc, rb[0], rb[1], rb[2], rb[3], rb[4]);
        }
        gRegs = nullptr;
        if (fBlLock) IOLockUnlock(fBlLock);
        return rc == 0;
    }"""
s = s.replace(anchor2, members_code, 1)

# 2b. Replace single AUX A EDID call in start() with xifbProbeEdidAllAux
old_edid_call = """                    if (xifbReadEdid(fEdid, &fEdidLen))
                        XIFBLOG("EDID %d B, maker %02x%02x product %02x%02x, %ux%u mm", fEdidLen, fEdid[8], fEdid[9], fEdid[11],
                                fEdid[10], fEdid[21] * 10, fEdid[22] * 10);
                    else { fEdidLen = 0; XIFBLOG("EDID: AUX A read failed, the display stays unnamed"); }"""
assert old_edid_call in s, "old_edid_call missing"

new_edid_call = """                    if (xifbProbeEdidAllAux(fEdid, &fEdidLen, &fAuxCtl))
                        XIFBLOG("EDID %d B via AUX %06x, maker %02x%02x product %02x%02x, %ux%u mm", fEdidLen, fAuxCtl,
                                fEdid[8], fEdid[9], fEdid[11], fEdid[10], fEdid[21] * 10, fEdid[22] * 10);
                    else { fEdidLen = 0; XIFBLOG("EDID: all AUX channels failed, the display stays unnamed"); }"""
s = s.replace(old_edid_call, new_edid_call, 1)

# 3. Call blInit() and armVbl() in start(), set AAPL panel/backlight properties, and add stop() + VBL overrides
anchor3 = "        if (!curSetup()) fCurReady = false;\n        return IONDRVFramebuffer::start(provider);"
assert anchor3 in s, "anchor3 missing"

start_hook = """        fPci = OSDynamicCast(IOPCIDevice, provider);
        if (!curSetup()) fCurReady = false;
        blInit();
        snapDeRegs("DE boot", false);
        if (fBlReady) {
            uint32_t one = 1;
            uint8_t zero = 0;
            provider->setProperty("AAPL,HasPanel", &one, 4);
            provider->setProperty("AAPL,backlight-control", &one, 4);
            provider->setProperty("built-in", &zero, 1);
            setProperty("AAPL,HasPanel", &one, 4);
            setProperty("AAPL,backlight-control", &one, 4);
            setProperty("built-in", &zero, 1);
        }
        bool ok = IONDRVFramebuffer::start(provider);
        if (ok) { armVbl(); armBlWatch(); }
        return ok;
    }
    void stop(IOService *provider) override {
        fStopping = true;
        if (fPmNotifier) {
            fPmNotifier->remove();
            fPmNotifier = nullptr;
        }
        if (fVblTimer) {
            thread_call_cancel(fVblTimer);
            while (!thread_call_free(fVblTimer)) IOSleep(1);
            fVblTimer = nullptr;
        }
        if (fBlSaveTimer) {
            thread_call_cancel(fBlSaveTimer);
            while (!thread_call_free(fBlSaveTimer)) IOSleep(1);
            fBlSaveTimer = nullptr;
        }
        if (fBlWatchTimer) {
            thread_call_cancel(fBlWatchTimer);
            while (!thread_call_free(fBlWatchTimer)) IOSleep(1);
            fBlWatchTimer = nullptr;
        }
        if (fBlHandler) {
            fBlHandler->stop(this);
            fBlHandler->detach(this);
            fBlHandler->release();
            fBlHandler = nullptr;
        }
        IONDRVFramebuffer::stop(provider);
    }
    using IONDRVFramebuffer::setProperty;
    bool setProperty(const OSSymbol *key, OSObject *value) override {
        bool ok = IONDRVFramebuffer::setProperty(key, value);
        if (ok && fBlHandler && key && strcmp(key->getCStringNoCopy(), "IOFBBuiltIn") == 0) {
            XIFBLOG("IOFBBuiltIn set -> re-syncing backlight IODisplayParameters");
            fBlHandler->doUpdate();
        }
        return ok;
    }
    IOReturn getAppleSense(IOIndex ci, UInt32 *senseType, UInt32 *primary, UInt32 *extended, UInt32 *displayType) override {
        if (ci == 0) {
            if (senseType) *senseType = 0;
            if (primary) *primary = 0;
            if (extended) *extended = 0;
            if (displayType) *displayType = kPanelTFTConnect;
            return kIOReturnSuccess;
        }
        return IONDRVFramebuffer::getAppleSense(ci, senseType, primary, extended, displayType);
    }
    IOReturn registerForInterruptType(IOSelect type, IOFBInterruptProc proc, OSObject *target, void *ref, void **iref) override {
        if (type == kIOFBVBLInterruptType) {
            fVbl = { proc, target, ref };
            if (iref) *iref = &fVbl;
            return kIOReturnSuccess;
        }
        return IONDRVFramebuffer::registerForInterruptType(type, proc, target, ref, iref);
    }
    IOReturn unregisterInterrupt(void *iref) override {
        if (iref == &fVbl) { fVbl = {}; return kIOReturnSuccess; }
        return IONDRVFramebuffer::unregisterInterrupt(iref);
    }
    IOReturn setInterruptState(void *iref, UInt32 state) override {
        if (iref == &fVbl) { fVblEnabled = (state != 0); return kIOReturnSuccess; }
        return IONDRVFramebuffer::setInterruptState(iref, state);
    }
    void getVBLTime(AbsoluteTime *time, AbsoluteTime *delta) override {
        if (time) *(uint64_t *)time = fVblLastTime ? fVblLastTime : mach_absolute_time();
        if (delta) {
            uint64_t period = 0;
            nanoseconds_to_absolutetime(fFrameNs, &period);
            *(uint64_t *)delta = period;
        }"""
s = s.replace(anchor3, start_hook, 1)

# 4. Handle 'flgs' (kConnectionFlags -> kIOConnectionBuiltIn) and 'bklt' fallback in getAttributeForConnection / setAttributeForConnection
anchor4 = """    IOReturn getAttributeForConnection(IOIndex ci, IOSelect attr, uintptr_t *value) override {
        if (fEdidLen && attr == kConnectionSupportsHLDDCSense) return kIOReturnSuccess;
        return IONDRVFramebuffer::getAttributeForConnection(ci, attr, value);
    }"""
assert anchor4 in s, "anchor4 missing"

attr_code = """    IOReturn getAttributeForConnection(IOIndex ci, IOSelect attr, uintptr_t *value) override {
        if (fEdidLen && attr == kConnectionSupportsHLDDCSense) return kIOReturnSuccess;
        if (ci == 0 && attr == 0x666c6773u /* 'flgs' kConnectionFlags */) {
            uintptr_t base = 0;
            IONDRVFramebuffer::getAttributeForConnection(ci, attr, &base);
            if (value) *value = base | (1u << 11); // kIOConnectionBuiltIn (0x800)
            return kIOReturnSuccess;
        }
        if (fBlReady && attr == 0x626b6c74u /* 'bklt' */) {
            if (value) *value = fBlLevel;
            return kIOReturnSuccess;
        }
        IOReturn r = IONDRVFramebuffer::getAttributeForConnection(ci, attr, value);
        static unsigned nConnLog = 0;
        if (nConnLog < 40) {
            nConnLog++;
            auto p4 = [](uint32_t v, int s) -> char { char c = (char)((v >> s) & 0xff); return (c >= 0x20 && c < 0x7f) ? c : '.'; };
            XIFBLOG("getAttrConn(%d, %08x/'%c%c%c%c') -> %08x val=%lx", (int)ci,
                    (unsigned)attr, p4(attr, 24), p4(attr, 16), p4(attr, 8), p4(attr, 0),
                    (unsigned)r, value ? (unsigned long)*value : 0ul);
        }
        return r;
    }
    IOReturn setAttributeForConnection(IOIndex ci, IOSelect attr, uintptr_t value) override {
        if (fBlReady && attr == 0x626b6c74u /* 'bklt' */) {
            XIFBLOG("setAttrConn(%d, 'bklt', %lu)", (int)ci, (unsigned long)value);
            bool ok = blSet((uint32_t)value);
            if (ok) scheduleBlSave((uint32_t)value);
            return ok ? kIOReturnSuccess : kIOReturnIOError;
        }
        return IONDRVFramebuffer::setAttributeForConnection(ci, attr, value);
    }"""
s = s.replace(anchor4, attr_code, 1)

# 5. Drop kDisplayModeValidForHiResFlag and physical imageWidth/imageHeight so macOS uses native 1x (2560x1600) instead of 2x (1280x800)
img_size_line = "        if (fEdidLen && fEdid[21] && fEdid[22]) { info->imageWidth = fEdid[21] * 10; info->imageHeight = fEdid[22] * 10; }"
assert img_size_line in s, "img_size_line missing"
s = s.replace(img_size_line, "        // leave imageWidth/imageHeight unset so WindowServer stays at 1x native 2560x1600", 1)

hires_line = "        info->flags |= kDisplayModeValidForHiResFlag;"
assert hires_line in s, "hires_line missing"
s = s.replace(hires_line, "        info->flags &= ~kDisplayModeValidForHiResFlag;", 1)

# 6. Strip kIOPMPreventSystemSleep from registerPowerDriver, handle kIOPowerStateAttribute, and log getAttribute() queries
get_attr_anchor = """    IOReturn getAttribute(IOSelect attr, uintptr_t *value) override {
        if (attr == kIOHardwareCursorAttribute) { if (value) *value = fCurReady; return kIOReturnSuccess; }
        return IONDRVFramebuffer::getAttribute(attr, value);
    }"""
assert get_attr_anchor in s, "get_attr_anchor missing"

get_attr_log = """    IOReturn registerPowerDriver(IOService *controllingDriver, IOPMPowerState *powerStates, unsigned long numberOfStates) override {
        if (controllingDriver == this && powerStates && numberOfStates > 0 && numberOfStates <= 8) {
            IOPMPowerState patched[8];
            bcopy(powerStates, patched, numberOfStates * sizeof(IOPMPowerState));
            for (unsigned long i = 0; i < numberOfStates; i++)
                patched[i].capabilityFlags &= ~kIOPMPreventSystemSleep;
            XIFBLOG("registerPowerDriver: stripped kIOPMPreventSystemSleep (%lu states)", numberOfStates);
            return IONDRVFramebuffer::registerPowerDriver(controllingDriver, patched, numberOfStates);
        }
        return IONDRVFramebuffer::registerPowerDriver(controllingDriver, powerStates, numberOfStates);
    }
    IOReturn setAttribute(IOSelect attr, uintptr_t value) override {
        if ((attr == kIOPowerStateAttribute || attr == kIODriverPowerAttribute) && value == 0) {
            fDisplayAsleep = true;
            fCurDdb = false;
            nvramSetStr("xeintelfb-wake", "sleep");
            if (fBlReady) (void)blWriteHw(0);
        }
        IOReturn r = IONDRVFramebuffer::setAttribute(attr, value);
        if (attr == kIOPowerStateAttribute || attr == kIODriverPowerAttribute) {
            static unsigned nPwrLog = 0;
            if (++nPwrLog <= 20)
                XIFBLOG("setAttr(%08x, %lu) -> %08x (bl=%u)", (unsigned)attr, (unsigned long)value, (unsigned)r, (unsigned)fBlLevel);
            if (value == 1 && fDisplayAsleep) {
                snapDeRegs("w1", true);
            } else if (value >= 2) {
                bool wasAsleep = fDisplayAsleep;
                fDisplayAsleep = false;
                if (wasAsleep) {
                    if (fBlHandler) {
                        fBlHandler->fFadeLevel = 0;
                        xifbUpdateParamValue(fBlHandler->fDisplay, "brightness-fade", 0);
                    }
                    if (fBlSaveLevel > 0 && fBlLevel < kBlMinFloor) {
                        fBlLevel = (fBlSaveLevel >= kBlMinFloor) ? fBlSaveLevel : kBlMinFloor;
                    }
                    if (fBlReady) (void)blWriteHw(fBlLevel);
                    if (fCurReady && fR && fPci &&
                        (fPci->configRead16(kIOPCIConfigCommand) & kIOPCICommandMemorySpace) &&
                        rd(XIFB_P1_SURF) == 0xff000000u) {
                        curDdb();
                        IOInterruptState is = IOSimpleLockLockDisableInterrupt(fCurLock);
                        curPtes();
                        if (fCurDdb) curRegs(fCurX, fCurY, fCurVis && fCurImg);
                        IOSimpleLockUnlockEnableInterrupt(fCurLock, is);
                    }
                    snapDeRegs("w2", true);
                } else if (fBlReady) {
                    (void)blWriteHw(fBlLevel);
                }
            }
        }
        return r;
    }
    IOReturn getAttribute(IOSelect attr, uintptr_t *value) override {
        if (attr == kIOHardwareCursorAttribute) { if (value) *value = fCurReady; return kIOReturnSuccess; }
        IOReturn r = IONDRVFramebuffer::getAttribute(attr, value);
        static unsigned nAttrLog = 0;
        if (nAttrLog < 40) {
            nAttrLog++;
            auto p4 = [](uint32_t v, int s) -> char { char c = (char)((v >> s) & 0xff); return (c >= 0x20 && c < 0x7f) ? c : '.'; };
            XIFBLOG("getAttr(%08x/'%c%c%c%c') -> %08x val=%lx",
                    (unsigned)attr, p4(attr, 24), p4(attr, 16), p4(attr, 8), p4(attr, 0),
                    (unsigned)r, value ? (unsigned long)*value : 0ul);
        }
        return r;
    }"""
s = s.replace(get_attr_anchor, get_attr_log, 1)

# 7. Append XeGfxBacklightHandler method definitions at end of intelfb.cpp
s += r"""

OSDefineMetaClassAndStructors(XeGfxBacklightHandler, IODisplayParameterHandler)

static void xifbSetParamEntry(OSDictionary *params, const char *keyStr, SInt32 minVal, SInt32 maxVal, SInt32 curVal)
{
    if (!params) return;
    OSDictionary *pd = OSDictionary::withCapacity(3);
    if (!pd) return;
    OSNumber *nMin = OSNumber::withNumber((unsigned long long)(uint32_t)minVal, 32);
    OSNumber *nMax = OSNumber::withNumber((unsigned long long)(uint32_t)maxVal, 32);
    OSNumber *nVal = OSNumber::withNumber((unsigned long long)(uint32_t)curVal, 32);
    if (nMin && nMax && nVal) {
        pd->setObject("min", nMin);
        pd->setObject("max", nMax);
        pd->setObject("value", nVal);
        params->setObject(keyStr, pd);
    }
    if (nMin) nMin->release();
    if (nMax) nMax->release();
    if (nVal) nVal->release();
    pd->release();
}

static void xifbUpdateParamValue(IODisplay *display, const char *keyStr, SInt32 val)
{
    if (!display) return;
    OSObject *p = display->copyProperty("IODisplayParameters");
    OSDictionary *dp = OSDynamicCast(OSDictionary, p);
    OSDictionary *sub = dp ? OSDynamicCast(OSDictionary, dp->getObject(keyStr)) : nullptr;
    OSNumber *num = sub ? OSDynamicCast(OSNumber, sub->getObject("value")) : nullptr;
    if (num) num->setValue((unsigned long long)(uint32_t)val);
    if (p) p->release();
}

XeGfxBacklightHandler *XeGfxBacklightHandler::withFramebuffer(XeGfxIntelFramebuffer *fb)
{
    XeGfxBacklightHandler *h = new XeGfxBacklightHandler;
    if (h && !h->init()) {
        h->release();
        return nullptr;
    }
    if (h) h->fFb = fb;
    return h;
}

bool XeGfxBacklightHandler::setDisplay(IODisplay *display)
{
    fDisplay = display;
    if (!display || !fFb) return false;
    fUserLevel = (uint32_t)(((uint64_t)fFb->fBlLevel * kUiMax + XeGfxIntelFramebuffer::kBlMax / 2) / XeGfxIntelFramebuffer::kBlMax);
    if (fUserLevel > (uint32_t)kUiMax) fUserLevel = (uint32_t)kUiMax;
    fFadeLevel = 0;
    XIFBLOG("BlHandler::setDisplay(%s) initUi=%u", display->getName(), (unsigned)fUserLevel);
    return true;
}

bool XeGfxBacklightHandler::doUpdate(void)
{
    if (!fDisplay || !fFb) return false;
    OSObject *p = fDisplay->copyProperty("IODisplayParameters");
    OSDictionary *cur = OSDynamicCast(OSDictionary, p);
    OSDictionary *nd = cur ? OSDictionary::withDictionary(cur) : OSDictionary::withCapacity(8);
    if (p) {
        if (cur) {
            OSDictionary *existingBr = OSDynamicCast(OSDictionary, cur->getObject("brightness"));
            if (existingBr) {
                OSNumber *mx = OSDynamicCast(OSNumber, existingBr->getObject("max"));
                OSNumber *vl = OSDynamicCast(OSNumber, existingBr->getObject("value"));
                XIFBLOG("BlHandler::doUpdate existing brightness max=%u val=%u -> setting %u/%d",
                        mx ? (unsigned)mx->unsigned32BitValue() : 0u,
                        vl ? (unsigned)vl->unsigned32BitValue() : 0u,
                        (unsigned)fUserLevel, (int)kUiMax);
            }
        }
        p->release();
    }
    if (!nd) return false;
    xifbSetParamEntry(nd, "brightness", 0, kUiMax, (SInt32)fUserLevel);
    xifbSetParamEntry(nd, "linear-brightness", 0, kUiMax, (SInt32)fUserLevel);
    xifbSetParamEntry(nd, "brightness-fade", 0, kUiMax, (SInt32)fFadeLevel);
    xifbSetParamEntry(nd, "commit", 0, 0, 0);
    fDisplay->setProperty("IODisplayParameters", nd);
    nd->release();
    return true;
}

void XeGfxBacklightHandler::applyEffective()
{
    if (!fFb) return;
    uint32_t effUi = fUserLevel;
    if (fFadeLevel > 0) {
        uint32_t cap = (fFadeLevel >= (uint32_t)kUiMax) ? 0u : ((uint32_t)kUiMax - fFadeLevel);
        if (cap < effUi) effUi = cap;
    }
    uint32_t hw = (uint32_t)(((uint64_t)effUi * XeGfxIntelFramebuffer::kBlMax + kUiMax / 2) / kUiMax);
    fFb->blSet(hw);
}

bool XeGfxBacklightHandler::doIntegerSet(OSDictionary *params, const OSSymbol *paramName, UInt32 value)
{
    const char *name = paramName ? paramName->getCStringNoCopy() : "";
    static unsigned nLog = 0;
    if (++nLog <= 30) XIFBLOG("BlHandler::doIntegerSet('%s', %u)", name, (unsigned)value);

    if (strcmp(name, "brightness") == 0) {
        if (value > (UInt32)kUiMax) value = (UInt32)kUiMax;
        if (fFb->fHasSavedBl) {
            uint64_t nowNs = 0;
            absolutetime_to_nanoseconds(mach_absolute_time(), &nowNs);
            if (nowNs >= fFb->fBlInitNs && (nowNs - fFb->fBlInitNs) < 25000000000ull) {
                if (value == 255 || value == fUserLevel) {
                    if (value == 255 && fUserLevel != 255) {
                        XIFBLOG("ignoring early boot 255 brightness override; keeping saved %u", (unsigned)fUserLevel);
                    }
                    xifbUpdateParamValue(fDisplay, "brightness", (SInt32)fUserLevel);
                    xifbUpdateParamValue(fDisplay, "linear-brightness", (SInt32)fUserLevel);
                    applyEffective();
                    return true;
                }
                if ((nowNs - fFb->fBlInitNs) < 5000000000ull) {
                    XIFBLOG("ignoring early boot brightness %u; keeping saved %u", (unsigned)value, (unsigned)fUserLevel);
                    xifbUpdateParamValue(fDisplay, "brightness", (SInt32)fUserLevel);
                    xifbUpdateParamValue(fDisplay, "linear-brightness", (SInt32)fUserLevel);
                    applyEffective();
                    return true;
                }
            }
        }
        fFb->fHasSavedBl = false;
        fUserLevel = value;
        xifbUpdateParamValue(fDisplay, "linear-brightness", (SInt32)fUserLevel);
        applyEffective();
        uint32_t hwUser = (uint32_t)(((uint64_t)fUserLevel * XeGfxIntelFramebuffer::kBlMax + kUiMax / 2) / kUiMax);
        fFb->scheduleBlSave(hwUser);
        return true;
    }
    if (strcmp(name, "linear-brightness") == 0) {
        if (value > (UInt32)kUiMax) value = (UInt32)kUiMax;
        if (fFb->fHasSavedBl) {
            uint64_t nowNs = 0;
            absolutetime_to_nanoseconds(mach_absolute_time(), &nowNs);
            if (nowNs >= fFb->fBlInitNs && (nowNs - fFb->fBlInitNs) < 25000000000ull) {
                if (value == 255 || value == fUserLevel) {
                    if (value == 255 && fUserLevel != 255) {
                        XIFBLOG("ignoring early boot 255 override; keeping saved brightness %u", (unsigned)fUserLevel);
                    }
                    xifbUpdateParamValue(fDisplay, "brightness", (SInt32)fUserLevel);
                    xifbUpdateParamValue(fDisplay, "linear-brightness", (SInt32)fUserLevel);
                    applyEffective();
                    return true;
                }
                if ((nowNs - fFb->fBlInitNs) < 5000000000ull) {
                    XIFBLOG("ignoring early boot linear-brightness %u; keeping saved %u", (unsigned)value, (unsigned)fUserLevel);
                    xifbUpdateParamValue(fDisplay, "brightness", (SInt32)fUserLevel);
                    xifbUpdateParamValue(fDisplay, "linear-brightness", (SInt32)fUserLevel);
                    applyEffective();
                    return true;
                }
            }
        }
        fFb->fHasSavedBl = false;
        fUserLevel = value;
        xifbUpdateParamValue(fDisplay, "brightness", (SInt32)fUserLevel);
        applyEffective();
        uint32_t hwUser = (uint32_t)(((uint64_t)fUserLevel * XeGfxIntelFramebuffer::kBlMax + kUiMax / 2) / kUiMax);
        fFb->scheduleBlSave(hwUser);
        return true;
    }
    if (strcmp(name, "brightness-fade") == 0) {
        if (value > (UInt32)kUiMax) value = (UInt32)kUiMax;
        fFadeLevel = value;
        applyEffective();
        return true;
    }
    if (strcmp(name, "commit") == 0) {
        return true;
    }
    return false;
}

bool XeGfxBacklightHandler::doDataSet(const OSSymbol *paramName, OSData *value)
{
    return false;
}
"""

p.write_text(s)
print("Patched", p)
