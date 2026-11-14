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
 IOSleep(3000);
 xg_printf("XeGfx BOOT: GPU discovered; starting stages\n");
 strlcpy(xg_env, "compat.linuxkpi.xe_probe_display=0 compat.linuxkpi.xe_probe_skip_pc_start=1 compat.linuxkpi.xe_probe_skip_lrc_ggtt_remove=1", sizeof(xg_env));
 xg_printf("XeGfx BOOT V33: automatic stages 1-4 (after 3s delay); display=0 PC bypass=1 LRC ggtt_remove bypass=1 sync_drain=1 Stage 6 store unlocked\n");
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

old_store = '''#ifdef XEGFX_KMD_XE
 IOLog("XeGfx: stage 6 store not implemented for xe (M1)\\n");
 return -ENOTSUP;
#else'''
new_store = '''#ifdef XEGFX_KMD_XE
 static struct xg_xe_store sd;
 int err = xg_xe_store(&sd, 2000);
 int rc = err ? err : (!sd.engines || sd.truncated || sd.ok != sd.engines ? -EIO : 1);
 OSDictionary *d = OSDictionary::withCapacity(2 * XG_XE_MAX_ENGINES + 4);
 if (d) {
  for (int i = 0; i < sd.engines; i++) {
   char k[32];
   snprintf(k, sizeof(k), "%s-got", sd.name[i]);
   xg_put(d, k, sd.got[i]);
   snprintf(k, sizeof(k), "%s-err", sd.name[i]);
   xg_put(d, k, (uint32_t)sd.err[i]);
  }
  xg_put(d, "engines", (uint32_t)sd.engines);
  xg_put(d, "ok", (uint32_t)sd.ok);
  xg_put(d, "irqs", sd.irq_delta);
  xg_put(d, "result", (uint32_t)rc);
  if (gResident) gResident->setProperty("XeGfxStore", d);
  d->release();
 }
 return rc;
#else'''
assert s.count(old_store) == 1
s = s.replace(old_store, new_store)
p.write_text(s)

root = Path(sys.argv[1])
hdr_p = root / 'shim/include/xg_xe.h'
hdr = hdr_p.read_text()
old_hdr = 'int xg_xe_exec(struct xg_xe_exec *ex, int timeout_ms);'
new_hdr = '''struct xg_xe_store {
 int engines, ok, truncated;
 unsigned int irq_delta;
 char name[XG_XE_MAX_ENGINES][24];
 unsigned int want[XG_XE_MAX_ENGINES], got[XG_XE_MAX_ENGINES];
 long long ns[XG_XE_MAX_ENGINES];
 int err[XG_XE_MAX_ENGINES];
};
int xg_xe_exec(struct xg_xe_exec *ex, int timeout_ms);
int xg_xe_store(struct xg_xe_store *sd, int timeout_ms);'''
assert hdr.count(old_hdr) == 1
hdr_p.write_text(hdr.replace(old_hdr, new_hdr))

exec_p = root / 'xkpi/xe/src/xg_xe_exec.c'
exec_c = exec_p.read_text()
store_fn = '''
extern volatile int xg_lrc_fini_pending;
extern int pause_sbt(const char *, int64_t, int64_t, int);

int xg_xe_store(struct xg_xe_store *sd, int timeout_ms)
{
 struct pci_dev *pdev;
 struct xe_device *xe;
 struct xe_gt *gt;
 struct xe_hw_engine *hwe;
 enum xe_hw_engine_id h;
 unsigned int irq0;
 unsigned long deadline;
 u8 id;
 memset(sd, 0, sizeof(*sd));
 if (timeout_ms <= 0 || timeout_ms > 2000) return -EINVAL;
 for (int w = 0; w < 500 && __sync_fetch_and_add(&xg_lrc_fini_pending, 0) > 0; w++)
  pause_sbt("xgqfin", 4294967LL, 0, 0);
 xe = xg_xe_find(&pdev);
 if (!xe) return -ENODEV;
 xe_pm_runtime_get(xe);
 irq0 = READ_ONCE(xg_pci_irqs);
 deadline = jiffies + msecs_to_jiffies(20000);
 for_each_gt(gt, xe, id) {
  for_each_hw_engine(hwe, gt, h) {
   struct xg_xe_exec_pool *state;
   struct xe_exec_queue *q;
   struct xe_bb *bb;
   struct xe_sched_job *job;
   struct dma_fence *fence;
   volatile u32 *slot;
   u64 target_ggtt;
   ktime_t t0 = ktime_get();
   long t;
   unsigned long remaining;
   int n = sd->engines;
   if (n == XG_XE_MAX_ENGINES) { sd->truncated = 1; goto out; }
   sd->engines++;
   snprintf(sd->name[n], sizeof(sd->name[n]), "gt%u-%s", id, hwe->name);
   sd->want[n] = 0x58670000u | ((unsigned int)id << 12) | ((unsigned int)n << 8) | ((unsigned int)hwe->class & 0xffu);
   if (gt->uc.guc.fw.status != XE_UC_FIRMWARE_RUNNING ||
       !gt->uc.guc.submission_state.enabled ||
       atomic_read(&gt->uc.guc.submission_state.stopped)) {
    sd->err[n] = -EIO; goto report;
   }
   if (time_after_eq(jiffies, deadline)) {
    sd->err[n] = -ETIMEDOUT; sd->truncated = 1; goto report;
   }
   state = xg_xe_exec_pool_get(gt);
   if (IS_ERR(state)) { sd->err[n] = PTR_ERR(state); goto report; }
   q = xe_exec_queue_create(xe, NULL, BIT(hwe->logical_instance), 1, hwe, EXEC_QUEUE_FLAG_KERNEL, 0);
   if (IS_ERR(q)) { sd->err[n] = PTR_ERR(q); goto report; }
   bb = xg_xe_bb_new(state->manager);
   if (IS_ERR(bb)) { sd->err[n] = PTR_ERR(bb); goto put_q; }
   slot = (volatile u32 *)&bb->cs[256];
   *slot = 0xdeadbeefu;
   __sync_synchronize();
   target_ggtt = xe_sa_bo_gpu_addr(bb->bo) + 1024ULL;
   bb->cs[bb->len++] = (0x20u << 23) | (1u << 22) | 2u;
   bb->cs[bb->len++] = (u32)(target_ggtt & 0xffffffffULL);
   bb->cs[bb->len++] = (u32)(target_ggtt >> 32);
   bb->cs[bb->len++] = sd->want[n];
   job = xe_bb_create_job(q, bb);
   if (IS_ERR(job)) { sd->err[n] = PTR_ERR(job); xe_bb_free(bb, NULL); goto put_q; }
   xe_sched_job_arm(job);
   fence = dma_fence_get(&job->drm.s_fence->finished);
   xe_sched_job_push(job);
   remaining = time_before(jiffies, deadline) ? deadline - jiffies : 0;
   t = dma_fence_wait_timeout(fence, false, min_t(unsigned long, remaining, msecs_to_jiffies(timeout_ms)));
   if (t <= 0) sd->err[n] = t < 0 ? (int)t : -ETIMEDOUT;
   else if (dma_fence_get_status(fence) < 0) sd->err[n] = dma_fence_get_status(fence);
   else {
    __sync_synchronize();
    sd->got[n] = *slot;
    if (sd->got[n] == sd->want[n]) sd->ok++;
    else sd->err[n] = -EIO;
   }
   if (!dma_fence_is_signaled(fence))
    state->pending = dma_fence_get(fence);
   xe_bb_free(bb, fence);
   dma_fence_put(fence);
   if (sd->err[n]) q->ops->kill(q);
put_q:
   xe_exec_queue_put(q);
   for (int w = 0; w < 500 && __sync_fetch_and_add(&xg_lrc_fini_pending, 0) > 0; w++)
    pause_sbt("xgqfin", 4294967LL, 0, 0);
report:
   sd->ns[n] = ktime_to_ns(ktime_sub(ktime_get(), t0));
   printf("xegfx: store %s want=%#x got=%#x ns=%lld err=%d\\n",
       sd->name[n], sd->want[n], sd->got[n], sd->ns[n], sd->err[n]);
   if (sd->err[n] == -ETIMEDOUT) goto out;
  }
 }
out:
 sd->irq_delta = READ_ONCE(xg_pci_irqs) - irq0;
 printf("xegfx: xe store %d/%d verified, IRQ delta=%u\\n", sd->ok, sd->engines, sd->irq_delta);
 xe_pm_runtime_put(xe);
 pci_dev_put(pdev);
 return 0;
}
'''
assert 'int xg_xe_store(' not in exec_c
exec_p.write_text(exec_c + store_fn)
print('Opt-in boot stage 4 initialization + Stage 6 store installed.')
