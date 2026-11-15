from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()

# 1. Add native AUX DPCD helpers + backlight init/set right after xifbI2c
anchor1 = "// pipe A's frame counter over about half a second: the refresh rate the firmware's mode runs at, in 16.16"
assert anchor1 in s, "anchor1 missing"

aux_dpcd_code = r"""// Native eDP AUX DPCD read/write (cmd 0x9 = read, 0x8 = write) for panel backlight (0x700..0x72f)
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

"""
s = s.replace(anchor1, aux_dpcd_code + anchor1, 1)

# 2. Add VBL timer + interrupt state + backlight state inside XeGfxIntelFramebuffer
anchor2 = "    SInt32 fCurX = 0, fCurY = 0; bool fCurVis = false, fCurImg = false;"
assert anchor2 in s, "anchor2 missing"

members_code = r"""    SInt32 fCurX = 0, fCurY = 0; bool fCurVis = false, fCurImg = false;
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
        if (me->fVblEnabled && me->fVbl.proc) {
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

    // eDP AUX DPCD backlight control
    bool fBlReady = false, fBl16Bit = false;
    uint32_t fBlLevel = 1024;
    static constexpr uint32_t kBlMax = 1024;
    void blInit() {
        if (!fR) return;
        gRegs = fR;
        uint8_t caps[4] = {}, ctrl[4] = {};
        if (xifbAuxDpcd(0x9, 0x700, nullptr, 4, caps) == 0 && xifbAuxDpcd(0x9, 0x720, nullptr, 4, ctrl) == 0) {
            bool auxSet = (caps[2] & 0x04) != 0;
            fBl16Bit = (caps[2] & 0x08) != 0;
            uint32_t cur = fBl16Bit ? (((uint32_t)ctrl[2] << 8) | ctrl[3]) : ctrl[2];
            uint32_t hwMax = fBl16Bit ? 65535u : 255u;
            fBlLevel = hwMax ? (cur * kBlMax + hwMax / 2) / hwMax : kBlMax;
            if (fBlLevel > kBlMax) fBlLevel = kBlMax;
            fBlReady = auxSet;
            XIFBLOG("eDP DPCD backlight: rev=%02x cap1=%02x cap2=%02x ctrl=%02x mode=%02x cur=%u (%s, aux=%d)",
                    caps[0], caps[1], caps[2], ctrl[0], ctrl[1], cur, fBl16Bit ? "16b" : "8b", auxSet ? 1 : 0);
        } else {
            XIFBLOG("eDP DPCD backlight: AUX read 0x700/0x720 failed");
        }
        gRegs = nullptr;
    }
    bool blSet(uint32_t level) {
        if (!fBlReady || !fR) return false;
        if (level > kBlMax) level = kBlMax;
        fBlLevel = level;
        gRegs = fR;
        uint8_t mode[2] = { 0x01, 0x02 }; // enable backlight, DPCD brightness mode
        (void)xifbAuxDpcd(0x8, 0x720, mode, 2, nullptr);
        uint8_t val[2];
        if (fBl16Bit) {
            uint32_t v = (level * 65535u + kBlMax / 2) / kBlMax;
            val[0] = (uint8_t)(v >> 8);
            val[1] = (uint8_t)(v & 0xff);
            int rc = xifbAuxDpcd(0x8, 0x722, val, 2, nullptr);
            gRegs = nullptr;
            return rc == 0;
        } else {
            val[0] = (uint8_t)((level * 255u + kBlMax / 2) / kBlMax);
            int rc = xifbAuxDpcd(0x8, 0x722, val, 1, nullptr);
            gRegs = nullptr;
            return rc == 0;
        }
    }"""
s = s.replace(anchor2, members_code, 1)

# 3. Call blInit() and armVbl() in start(), and add stop() + VBL overrides + 'bklt' attribute handling
anchor3 = "        if (!curSetup()) fCurReady = false;\n        return IONDRVFramebuffer::start(provider);"
assert anchor3 in s, "anchor3 missing"

start_hook = """        if (!curSetup()) fCurReady = false;
        blInit();
        bool ok = IONDRVFramebuffer::start(provider);
        if (ok) armVbl();
        return ok;
    }
    void stop(IOService *provider) override {
        fStopping = true;
        if (fVblTimer) {
            thread_call_cancel(fVblTimer);
            while (!thread_call_free(fVblTimer)) IOSleep(1);
            fVblTimer = nullptr;
        }
        IONDRVFramebuffer::stop(provider);
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

# 4. Handle 'bklt' in getAttributeForConnection and add setAttributeForConnection
anchor4 = """    IOReturn getAttributeForConnection(IOIndex ci, IOSelect attr, uintptr_t *value) override {
        if (fEdidLen && attr == kConnectionSupportsHLDDCSense) return kIOReturnSuccess;
        return IONDRVFramebuffer::getAttributeForConnection(ci, attr, value);
    }"""
assert anchor4 in s, "anchor4 missing"

attr_code = """    IOReturn getAttributeForConnection(IOIndex ci, IOSelect attr, uintptr_t *value) override {
        if (fEdidLen && attr == kConnectionSupportsHLDDCSense) return kIOReturnSuccess;
        if (fBlReady && attr == 0x626b6c74u /* 'bklt' */) {
            if (value) *value = fBlLevel;
            return kIOReturnSuccess;
        }
        return IONDRVFramebuffer::getAttributeForConnection(ci, attr, value);
    }
    IOReturn setAttributeForConnection(IOIndex ci, IOSelect attr, uintptr_t value) override {
        if (fBlReady && attr == 0x626b6c74u /* 'bklt' */) {
            return blSet((uint32_t)value) ? kIOReturnSuccess : kIOReturnIOError;
        }
        return IONDRVFramebuffer::setAttributeForConnection(ci, attr, value);
    }"""
s = s.replace(anchor4, attr_code, 1)

p.write_text(s)
print("Patched", p)
