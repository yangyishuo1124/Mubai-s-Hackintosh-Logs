"""Experimental completion bridge; both endpoints must ship together."""
from pathlib import Path
import sys
r=Path(sys.argv[1]); k=r/'kexts/XeGfxAccel/accel/nvrm-accel.cpp'
s=k.read_text(); anchor='class IOAccelXeGfxDRMClient : public IOUserClient {'
s=s.replace(anchor,'static unsigned nvIntelCompletionMark(unsigned id, unsigned pending);\n'+anchor,1)
a='''        if (sel != 0 || a->scalarInputCount != 3 || a->scalarOutputCount != 1) return kIOReturnBadArgument;'''
b='''        if (sel == 1) {
            if (a->scalarInputCount != 2 || a->scalarOutputCount != 1 ||
                a->scalarInput[0] > 0xffffffffULL || a->scalarInput[1] > 1) return kIOReturnBadArgument;
            a->scalarOutput[0] = nvIntelCompletionMark((unsigned)a->scalarInput[0], (unsigned)a->scalarInput[1]);
            return kIOReturnSuccess;
        }
'''+a
assert a in s;s=s.replace(a,b,1)
a='static IOReturn nvAccelSurfVram(struct NVRMSurfShareEsc *p, task_t task, unsigned cmd)'
assert a in s;s=s.replace(a,'''static unsigned nvIntelCompletionMark(unsigned id, unsigned pending) {
    struct NVRMSurfShareEsc p = {};
    p.surfaceID = id; p.plane = pending;
    return nvSurfGpuEscape(&p);
}
'''+a,1);k.write_text(s)
p=r/'plugin/nvmtl_vk.c';s=p.read_text();a='''    if (!pnvk_surface_dirty || !g_dev) return 0x80000002u;'''
b='''    if (nvmtl_vk_vendor() == 0x8086) {
        static io_connect_t conn;
        static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
        pthread_mutex_lock(&lock);
        if (!conn) {
            io_service_t svc = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("NMXAccel"));
            if (!svc) { pthread_mutex_unlock(&lock); return 0x80000002u; }
            kern_return_t kr = IOServiceOpen(svc, mach_task_self(), 0x58474452u, &conn);
            IOObjectRelease(svc);
            if (kr != KERN_SUCCESS) { pthread_mutex_unlock(&lock); return 0x80000002u; }
        }
        pthread_mutex_unlock(&lock);
        uint64_t in[2] = { surfaceID, pending ? 1u : 0u }, out = 0;
        uint32_t count = 1;
        kern_return_t kr = IOConnectCallScalarMethod(conn, 1, in, 2, &out, &count);
        return kr == KERN_SUCCESS && count == 1 ? (uint32_t)out : 0x80000002u;
    }
'''+a
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s)

# Intel publishes the surface-wait capability on NMXAccel, not NVAccel.
p=r/"plugin/nvmtl_vk.c"
s=p.read_text()
a='int nvmtl_vk_accel_surface_wait(void)\n{\n    io_service_t s = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("NVAccel"));'
b='int nvmtl_vk_accel_surface_wait(void)\n{\n    io_service_t s = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching(nvmtl_vk_vendor() == 0x8086 ? "NMXAccel" : "NVAccel"));'
assert a in s
p.write_text(s.replace(a,b))
