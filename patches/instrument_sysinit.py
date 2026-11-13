from pathlib import Path
import sys
root=Path(sys.argv[1]);bsd=Path(sys.argv[2])
p=root/'shim/src/xnu/xg_kext.cpp';s=p.read_text();mark='static void\nxg_trace_fire('
assert s.count(mark)==1
helper='''
/* Debug checkpoints persist synchronously, without holding the log lock over NVRAM I/O. */
extern "C" void
xg_init_checkpoint(int progress, const char *label)
{
 xg_progress = progress;
 if (!gTraceOn) return;
 char line[160];
 snprintf(line, sizeof(line), "checkpoint %d %s", progress, label);
 IOInterruptState flags = IOSimpleLockLockDisableInterrupt(gLogLock);
 strlcpy(gLast, line, sizeof(gLast));
 gLastSeq++;
 IOSimpleLockUnlockEnableInterrupt(gLogLock, flags);
 xg_trace_write();
}

'''
s=s.replace(mark,helper+mark).replace('ptl-stage4-guc-v4','ptl-stage4-uc-v8');p.write_text(s)
p=root/'shim/src/fbsd/xg_init.c';s=p.read_text();s=s.replace('extern int xg_progress;', 'extern int xg_progress;\nvoid xg_init_checkpoint(int, const char *);')
needle='			si->func(si->udata);';assert s.count(needle)==1
s=s.replace(needle,'			if (!reverse) xg_init_checkpoint(10000 + pass * 1000 + i * 2, "SYSINIT enter");\n'+needle+'\n			if (!reverse) xg_init_checkpoint(10001 + pass * 1000 + i * 2, "SYSINIT returned");');p.write_text(s)
p=bsd/'sys/compat/linuxkpi/common/src/linux_current.c';s=p.read_text();needle='static void\nlinux_current_init(void *arg __unused)\n{';assert s.count(needle)==1
s=s.replace(needle,'extern void xg_init_checkpoint(int, const char *);\n\n'+needle+'\n	xg_init_checkpoint(20001, "linux_current entered");')
replacements=[
 ('	linux_current_zone = uma_zcreate', '	xg_init_checkpoint(20002, "current zone create begin");\n	linux_current_zone = uma_zcreate'),
 ('	uma_zone_reserve(linux_current_zone', '	xg_init_checkpoint(20003, "current zone created");\n	uma_zone_reserve(linux_current_zone'),
 ('	linux_mm_zone = uma_zcreate', '	xg_init_checkpoint(20004, "mm zone create begin");\n	linux_mm_zone = uma_zcreate'),
 ('	uma_zone_reserve(linux_mm_zone', '	xg_init_checkpoint(20005, "mm zone created");\n	uma_zone_reserve(linux_mm_zone'),
 ('	linuxkpi_thread_dtor_tag = EVENTHANDLER_REGISTER', '	xg_init_checkpoint(20006, "thread destructor registration begin");\n	linuxkpi_thread_dtor_tag = EVENTHANDLER_REGISTER'),
 ('	lkpi_alloc_current = linux_alloc_current;', '	xg_init_checkpoint(20007, "thread destructor registered");\n	lkpi_alloc_current = linux_alloc_current;\n	xg_init_checkpoint(20008, "current allocator installed");')]
for old,new in replacements:
 assert s.count(old)==1,old
 s=s.replace(old,new)
p.write_text(s)
print('Synchronous SYSINIT entry/exit and linux_current checkpoints installed; no init steps skipped.')
