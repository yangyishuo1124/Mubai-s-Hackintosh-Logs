from pathlib import Path
import sys
p=Path(sys.argv[1])/'shim/src/xnu/xg_kext.cpp';s=p.read_text()
assert '#include <pexpert/pexpert.h>' not in s
s=s.replace('#include <mach/kmod.h>','#include <mach/kmod.h>\n#include <pexpert/pexpert.h>')
s=s.replace('bool\nXeGfxResident::start', 'extern "C" int xg_printf(const char *, ...);\nstatic thread_call_t gBootInitCall;\nstatic void xg_boot_fire(thread_call_param_t, thread_call_param_t);\n\nbool\nXeGfxResident::start',1)
anchor='\tgResident = this;'
assert s.count(anchor)==1
queue=r'''
	int target = 0;
	if (PE_parse_boot_argn("xegfx_bootstage", &target, sizeof(target)) && target == 4) {
		gBootInitCall = thread_call_allocate(xg_boot_fire, nullptr);
		if (gBootInitCall) {
			uint64_t deadline;
			clock_interval_to_deadline(250, NSEC_PER_MSEC, &deadline);
			thread_call_enter_delayed(gBootInitCall, deadline);
		} else xg_printf("XeGfx BOOT: failed to allocate deferred initializer\n");
	}
'''.replace('\n+', '\n')
start=s.index('bool\nXeGfxResident::start')
end=s.index('OSDefineMetaClassAndStructors', start)
part=s[start:end]
assert part.count('\tregisterService();') == 1
part=part.replace('\tregisterService();', '\tregisterService();\n'+queue)
s=s[:start]+part+s[end:]
s=s.replace('if (gStage > 0 || gDedicatedClaim)', 'if (gStage > 0 || gDedicatedClaim || gBootInitCall)')
helper=r'''
/* Deferred boot initialization; wait outside the matching/start callback. */
static void
xg_boot_initialize(void)
{
 int target = 0;
 if (!PE_parse_boot_argn("xegfx_bootstage", &target, sizeof(target)) || target != 4)
  return;
 IOPCIDevice *gpu = nullptr;
 xg_printf("XeGfx BOOT: waiting up to 60s for enumerated Intel GPU\n");
 for (unsigned attempt = 0; attempt < 600; ++attempt) {
  gpu = xg_find_igpu();
  if (gpu) break;
  if (!(attempt % 50)) xg_printf("XeGfx BOOT: GPU not visible yet, elapsed=%u ms\n", attempt * 100);
  IOSleep(100);
 }
 if (!gpu) {
  xg_printf("XeGfx BOOT: GPU discovery timed out; no stages executed\n");
  return;
 }
 gpu->release();
 xg_printf("XeGfx BOOT: GPU discovered; starting stages\n");
 strlcpy(xg_env, "compat.linuxkpi.xe_probe_display=0 compat.linuxkpi.xe_probe_skip_pc_start=1 compat.linuxkpi.xe_probe_skip_lrc_cleanup=1", sizeof(xg_env));
 xg_printf("XeGfx BOOT V25: automatic stages 1-4; display=0 PC bypass=1 LRC cleanup bypass=1 NVRAM trace=0\n");
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
callback=r'''
static void
xg_boot_worker(void *, wait_result_t)
{
 xg_printf("XeGfx BOOT: dedicated initializer thread entered\n");
 xg_boot_initialize();
 xg_printf("XeGfx BOOT: dedicated initializer thread exiting\n");
 thread_terminate(current_thread());
 panic("XeGfx boot worker termination returned");
}

static void
xg_boot_fire(thread_call_param_t, thread_call_param_t)
{
 thread_t worker = THREAD_NULL;
 kern_return_t kr = kernel_thread_start(xg_boot_worker, nullptr, &worker);
 if (kr != KERN_SUCCESS) {
  xg_printf("XeGfx BOOT: initializer thread creation failed kr=%d; no stages executed\n", kr);
  return;
 }
 thread_deallocate(worker);
}

'''.replace('\n+', '\n')
helper += callback
mark='static int\nxegfx_stage_sysctl('
assert s.count(mark)==1
s=s.replace(mark,helper+mark)
p.write_text(s)
print('Opt-in boot stage 4 initialization installed at IOService start.')
