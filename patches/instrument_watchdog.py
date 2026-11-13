from pathlib import Path
import sys
p=Path(sys.argv[1])/'shim/src/xnu/xg_kext.cpp'
s=p.read_text();s=s.replace('#include <kern/thread_call.h>','#include <kern/thread_call.h>\n#include <kern/thread.h>')
mark='static int\nxg_run_stage(int s)'
assert s.count(mark)==1
helper=r"""
static volatile UInt32 gDedicatedReady;
static void
xg_dedicated_watchdog(void *, wait_result_t)
{
 uint64_t start = mach_absolute_time(), ns;
 OSCompareAndSwap(0, 1, &gDedicatedReady);
 IOLog("XeGfx: dedicated stage4 watchdog running\n");
 while (gRunning == 4) {
  IOSleep(100);
  absolutetime_to_nanoseconds(mach_absolute_time() - start, &ns);
  if (gRunning == 4 && ns > 60000000000ull)
   panic("XeGfx dedicated stage4 watchdog: progress %d, irqs %u, handled %u, max_spin_us %llu, long_spins %u",
     xg_progress, xg_pci_irqs, xg_pci_handled, xg_spin_max_us, xg_spin_long);
 }
 thread_terminate(current_thread());
 panic("XeGfx dedicated watchdog termination returned");
}

"""
s=s.replace(mark,helper+mark)
anchor='\tgRunning = s;\n\txg_progress = s * 10;'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+r"""
 if (s == 4) {
  thread_t monitor = THREAD_NULL;
  gDedicatedReady = 0;
  if (kernel_thread_start(xg_dedicated_watchdog, nullptr, &monitor) != KERN_SUCCESS) {
   gRunning = 0;
   return -ENOMEM;
  }
  thread_deallocate(monitor);
  for (unsigned i = 0; i < 1000 && !gDedicatedReady; i++) IOSleep(1);
  if (!gDedicatedReady) {
   gRunning = 0;
   return -ETIMEDOUT;
  }
 }
""")
s=s.replace('ptl-stage4-trace-v10','ptl-stage4-watch-v11')
p.write_text(s)
print('Dedicated watchdog installed; stage4 refuses to start without monitor readiness.')
