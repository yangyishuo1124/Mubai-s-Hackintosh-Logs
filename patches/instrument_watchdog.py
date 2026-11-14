from pathlib import Path
import sys
p=Path(sys.argv[1])/'shim/src/xnu/xg_kext.cpp'
s=p.read_text();s=s.replace('#include <kern/thread_call.h>','#include <kern/thread_call.h>\n#include <kern/thread.h>')
mark='static int\nxg_run_stage(int s)'
assert s.count(mark)==1
helper=r"""
static volatile UInt32 gDedicatedClaim, gDedicatedReady, gDedicatedActive;
static void
xg_dedicated_watchdog(void *, wait_result_t)
{
 uint64_t start = mach_absolute_time(), ns;
 OSCompareAndSwap(0, 1, &gDedicatedReady);
 while (gDedicatedActive) {
  IOSleep(100);
  absolutetime_to_nanoseconds(mach_absolute_time() - start, &ns);
  if (gDedicatedActive && ns > 60000000000ull)
   panic("XeGfx request watchdog: running_stage %d completed_stage %d progress %d irqs %u handled %u max_spin_us %llu long_spins %u",
     gRunning, gStage, xg_progress, xg_pci_irqs, xg_pci_handled, xg_spin_max_us, xg_spin_long);
 }
 OSCompareAndSwap(1, 0, &gDedicatedReady);
 OSCompareAndSwap(1, 0, &gDedicatedClaim);
 thread_terminate(current_thread());
 panic("XeGfx request watchdog termination returned");
}

static int
xg_request_watchdog_start(void)
{
 thread_t monitor = THREAD_NULL;
 if (!OSCompareAndSwap(0, 1, &gDedicatedClaim)) return EBUSY;
 gDedicatedReady = 0;
 gDedicatedActive = 1;
 if (kernel_thread_start(xg_dedicated_watchdog, nullptr, &monitor) != KERN_SUCCESS) {
  gDedicatedActive = 0;
  gDedicatedClaim = 0;
  return ENOMEM;
 }
 thread_deallocate(monitor);
 for (unsigned i = 0; i < 1000 && !gDedicatedReady; i++) IOSleep(1);
 if (!gDedicatedReady) {
  gDedicatedActive = 0;
  return ETIMEDOUT;
 }
 if (gResident) gResident->setProperty("XeGfxRequestWatchdogArmed", true);
 return 0;
}

"""
s=s.replace(mark,helper+mark)
a=s.index('static int\nxegfx_stage_sysctl(');b=s.index('static int\nxegfx_results_sysctl(',a);f=s[a:b]
anchor='\tIOLockLock(gStageLock);'
assert f.count(anchor)==1
f=f.replace(anchor,'\tif (v <= gStage) return 0;\n\terr = xg_request_watchdog_start();\n\tif (err) return err;\n'+anchor)
anchor='\tIOLockUnlock(gStageLock);'
f=f.replace(anchor,anchor+'\n\tgDedicatedActive = 0;\n\tif (gResident) gResident->setProperty("XeGfxRequestWatchdogArmed", false);')
s=s[:a]+f+s[b:]
s=s.replace('if (gStage > 0)\n\t\treturn KERN_FAILURE;', 'if (gStage > 0 || gDedicatedClaim)\n\t\treturn KERN_FAILURE;')
s=s.replace('ptl-stage4-trace-v10','ptl-deferred-boot-v21')
p.write_text(s)
print('Request watchdog covers stage-lock acquisition and stages 1-4, with readiness handshake.')
