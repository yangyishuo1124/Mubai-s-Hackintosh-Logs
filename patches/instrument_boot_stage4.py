from pathlib import Path
import sys
p=Path(sys.argv[1])/'shim/src/xnu/xg_kext.cpp';s=p.read_text()
assert '#include <pexpert/pexpert.h>' not in s
s=s.replace('#include <mach/kmod.h>','#include <mach/kmod.h>\n#include <pexpert/pexpert.h>')
s=s.replace('bool\nXeGfxResident::start', 'static void xg_boot_initialize(void);\n\nbool\nXeGfxResident::start',1)
anchor='\tgResident = this;'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'\n\txg_boot_initialize();',1)
helper=r'''
/* Opt-in boot initialization, called after IOService start, never from _start. */
static void
xg_boot_initialize(void)
{
 int target = 0;
 if (!PE_parse_boot_argn("xegfx_bootstage", &target, sizeof(target)) || target != 4)
  return;
 strlcpy(xg_env, "compat.linuxkpi.xe_probe_display=0 compat.linuxkpi.xe_probe_skip_pc_start=1", sizeof(xg_env));
 xg_printf("XeGfx BOOT V20: automatic stages 1-4; display=0 PC bypass=1 NVRAM trace=0\n");
 int err = xg_request_watchdog_start();
 if (err) {
  xg_printf("XeGfx BOOT watchdog unavailable: %d; initialization stopped\n", err);
  return;
 }
 IOLockLock(gStageLock);
 while (gStage < target) {
  int stage = gStage + 1;
  xg_printf("XeGfx BOOT stage %d BEGIN\n", stage);
  int rc = xg_run_stage(stage);
  gResult[stage] = rc;
  xg_printf("XeGfx BOOT stage %d RETURN rc=%d progress=%d\n", stage, rc, xg_progress);
  if (rc < 0) break;
  gStage = stage;
 }
 IOLockUnlock(gStageLock);
 gDedicatedActive = 0;
 xg_printf("XeGfx BOOT initialization returned; completed stage=%d\n", gStage);
}

'''
mark='static int\nxegfx_stage_sysctl('
assert s.count(mark)==1
s=s.replace(mark,helper+mark)
p.write_text(s)
print('Opt-in boot stage 4 initialization installed at IOService start.')
