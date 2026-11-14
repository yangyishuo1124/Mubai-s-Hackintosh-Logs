#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

#include "drm.h"
#include "xe_drm.h"

struct drm_pciinfo {
	uint16_t domain;
	uint8_t bus, dev, func;
	uint16_t vendor_id, device_id, subvendor_id, subdevice_id;
	uint8_t revision_id;
};
#define DRM_IOCTL_GET_PCIINFO _IOR('d', 0x15, struct drm_pciinfo)

struct xg_drm_mmap {
	uint64_t offset;
	uint64_t size;
	uint32_t prot;
	uint32_t flags;
	uint64_t addr;
};
struct xg_drm_munmap {
	uint64_t addr;
	uint64_t size;
};
#define XG_DRM_IOCTL_MMAP   _IOWR('N', 0x40, struct xg_drm_mmap)
#define XG_DRM_IOCTL_MUNMAP _IOW('N', 0x41, struct xg_drm_munmap)

static int xioctl(int fd, unsigned long req, void *arg)
{
	int r;
	do {
		r = ioctl(fd, req, arg);
	} while (r == -1 && (errno == EINTR || errno == EAGAIN));
	return r;
}

static void *xe_query_alloc(int fd, uint32_t id, uint32_t *len_out)
{
	struct drm_xe_device_query q;
	memset(&q, 0, sizeof(q));
	q.query = id;
	if (xioctl(fd, DRM_IOCTL_XE_DEVICE_QUERY, &q) != 0 || q.size == 0) {
		printf("  query %u size failed: errno=%d (%s)\n", id, errno, strerror(errno));
		return NULL;
	}
	void *buf = calloc(1, q.size);
	if (!buf)
		return NULL;
	q.data = (uintptr_t)buf;
	if (xioctl(fd, DRM_IOCTL_XE_DEVICE_QUERY, &q) != 0) {
		printf("  query %u data failed: errno=%d (%s)\n", id, errno, strerror(errno));
		free(buf);
		return NULL;
	}
	if (len_out)
		*len_out = q.size;
	return buf;
}

int main(void)
{
	printf("=== XeGfx Userspace DRM/Xe UAPI Probe ===\n");
	DIR *dir = opendir("/dev/dri");
	if (!dir) {
		printf("FAIL: opendir(/dev/dri) errno=%d (%s)\n", errno, strerror(errno));
		return 1;
	}
	struct dirent *ent;
	while ((ent = readdir(dir)) != NULL) {
		if (ent->d_name[0] == '.')
			continue;
		char p[256];
		struct stat st;
		snprintf(p, sizeof(p), "/dev/dri/%s", ent->d_name);
		if (stat(p, &st) == 0)
			printf("  node %s: mode=%06o rdev=0x%08x\n", p, st.st_mode, (unsigned)st.st_rdev);
	}
	closedir(dir);

	const char *node = "/dev/dri/renderD128";
	int fd = open(node, O_RDWR | O_CLOEXEC);
	if (fd < 0) {
		node = "/dev/dri/card0";
		fd = open(node, O_RDWR | O_CLOEXEC);
	}
	if (fd < 0) {
		printf("FAIL: open(%s) errno=%d (%s)\n", node, errno, strerror(errno));
		return 1;
	}
	printf("Opened %s -> fd=%d\n", node, fd);

	char name_buf[64] = {0}, date_buf[64] = {0}, desc_buf[128] = {0};
	struct drm_version ver;
	memset(&ver, 0, sizeof(ver));
	ver.name_len = sizeof(name_buf) - 1;
	ver.name = name_buf;
	ver.date_len = sizeof(date_buf) - 1;
	ver.date = date_buf;
	ver.desc_len = sizeof(desc_buf) - 1;
	ver.desc = desc_buf;
	if (xioctl(fd, DRM_IOCTL_VERSION, &ver) != 0) {
		printf("FAIL: DRM_IOCTL_VERSION errno=%d (%s)\n", errno, strerror(errno));
		close(fd);
		return 1;
	}
	printf("DRM_IOCTL_VERSION: name=\"%s\" %d.%d.%d desc=\"%s\"\n",
	       name_buf, ver.version_major, ver.version_minor, ver.version_patchlevel, desc_buf);

	struct drm_pciinfo pi;
	memset(&pi, 0, sizeof(pi));
	if (xioctl(fd, DRM_IOCTL_GET_PCIINFO, &pi) != 0) {
		printf("FAIL: DRM_IOCTL_GET_PCIINFO errno=%d (%s)\n", errno, strerror(errno));
		close(fd);
		return 1;
	}
	printf("DRM_IOCTL_GET_PCIINFO: %04x:%02x:%02x.%u vendor=0x%04x device=0x%04x sub=0x%04x:0x%04x rev=0x%02x\n",
	       pi.domain, pi.bus, pi.dev, pi.func, pi.vendor_id, pi.device_id,
	       pi.subvendor_id, pi.subdevice_id, pi.revision_id);

	struct drm_xe_query_config *cfg = xe_query_alloc(fd, DRM_XE_DEVICE_QUERY_CONFIG, NULL);
	if (!cfg) {
		close(fd);
		return 1;
	}
	printf("DRM_XE_DEVICE_QUERY_CONFIG: num_params=%u rev_devid=0x%llx flags=0x%llx min_align=0x%llx va_bits=%llu max_prio=%llu\n",
	       cfg->num_params,
	       (unsigned long long)cfg->info[DRM_XE_QUERY_CONFIG_REV_AND_DEVICE_ID],
	       (unsigned long long)cfg->info[DRM_XE_QUERY_CONFIG_FLAGS],
	       (unsigned long long)cfg->info[DRM_XE_QUERY_CONFIG_MIN_ALIGNMENT],
	       (unsigned long long)cfg->info[DRM_XE_QUERY_CONFIG_VA_BITS],
	       (unsigned long long)cfg->info[DRM_XE_QUERY_CONFIG_MAX_EXEC_QUEUE_PRIORITY]);
	free(cfg);

	struct drm_xe_query_gt_list *gts = xe_query_alloc(fd, DRM_XE_DEVICE_QUERY_GTS, NULL);
	if (!gts) {
		close(fd);
		return 1;
	}
	printf("DRM_XE_DEVICE_QUERY_GTS: num_gt=%u\n", gts->num_gt);
	for (uint32_t i = 0; i < gts->num_gt; i++) {
		printf("  GT[%u]: type=%u tile_id=%u gt_id=%u ref_clock=%u near_mem=0x%llx\n",
		       i, gts->gt_list[i].type, gts->gt_list[i].tile_id, gts->gt_list[i].gt_id,
		       gts->gt_list[i].reference_clock, (unsigned long long)gts->gt_list[i].near_mem_regions);
	}
	free(gts);

	struct drm_xe_query_mem_regions *mems = xe_query_alloc(fd, DRM_XE_DEVICE_QUERY_MEM_REGIONS, NULL);
	if (!mems) {
		close(fd);
		return 1;
	}
	printf("DRM_XE_DEVICE_QUERY_MEM_REGIONS: num_mem_regions=%u\n", mems->num_mem_regions);
	for (uint32_t i = 0; i < mems->num_mem_regions; i++) {
		printf("  MEM[%u]: class=%u instance=%u min_page=%u total=%llu used=%llu\n",
		       i, mems->mem_regions[i].mem_class, mems->mem_regions[i].instance,
		       mems->mem_regions[i].min_page_size,
		       (unsigned long long)mems->mem_regions[i].total_size,
		       (unsigned long long)mems->mem_regions[i].used);
	}
	free(mems);

	struct drm_xe_query_engines *engs = xe_query_alloc(fd, DRM_XE_DEVICE_QUERY_ENGINES, NULL);
	if (!engs || engs->num_engines == 0) {
		printf("FAIL: DRM_XE_DEVICE_QUERY_ENGINES returned no engines\n");
		close(fd);
		return 1;
	}
	printf("DRM_XE_DEVICE_QUERY_ENGINES: num_engines=%u\n", engs->num_engines);
	for (uint32_t i = 0; i < engs->num_engines; i++) {
		printf("  ENG[%u]: class=%u instance=%u gt_id=%u\n",
		       i, engs->engines[i].instance.engine_class,
		       engs->engines[i].instance.engine_instance,
		       engs->engines[i].instance.gt_id);
	}

	struct drm_xe_vm_create vmc;
	memset(&vmc, 0, sizeof(vmc));
	vmc.flags = DRM_XE_VM_CREATE_FLAG_SCRATCH_PAGE;
	if (xioctl(fd, DRM_IOCTL_XE_VM_CREATE, &vmc) != 0) {
		memset(&vmc, 0, sizeof(vmc));
		if (xioctl(fd, DRM_IOCTL_XE_VM_CREATE, &vmc) != 0) {
			printf("FAIL: DRM_IOCTL_XE_VM_CREATE errno=%d (%s)\n", errno, strerror(errno));
			free(engs);
			close(fd);
			return 1;
		}
	}
	printf("DRM_IOCTL_XE_VM_CREATE: vm_id=%u\n", vmc.vm_id);

	struct drm_xe_gem_create gc;
	memset(&gc, 0, sizeof(gc));
	gc.size = 4096;
	gc.placement = 1u;
	gc.cpu_caching = DRM_XE_GEM_CPU_CACHING_WB;
	if (xioctl(fd, DRM_IOCTL_XE_GEM_CREATE, &gc) != 0) {
		printf("FAIL: DRM_IOCTL_XE_GEM_CREATE errno=%d (%s)\n", errno, strerror(errno));
		free(engs);
		close(fd);
		return 1;
	}
	printf("DRM_IOCTL_XE_GEM_CREATE: handle=%u size=%llu\n", gc.handle, (unsigned long long)gc.size);

	struct drm_xe_gem_mmap_offset mmo;
	memset(&mmo, 0, sizeof(mmo));
	mmo.handle = gc.handle;
	if (xioctl(fd, DRM_IOCTL_XE_GEM_MMAP_OFFSET, &mmo) != 0) {
		printf("FAIL: DRM_IOCTL_XE_GEM_MMAP_OFFSET errno=%d (%s)\n", errno, strerror(errno));
		free(engs);
		close(fd);
		return 1;
	}

	struct xg_drm_mmap xmap;
	memset(&xmap, 0, sizeof(xmap));
	xmap.offset = mmo.offset;
	xmap.size = 4096;
	xmap.prot = 3;
	if (xioctl(fd, XG_DRM_IOCTL_MMAP, &xmap) != 0 || !xmap.addr) {
		printf("FAIL: XG_DRM_IOCTL_MMAP errno=%d (%s)\n", errno, strerror(errno));
		free(engs);
		close(fd);
		return 1;
	}
	printf("XG_DRM_IOCTL_MMAP: offset=0x%llx -> user_addr=0x%llx\n",
	       (unsigned long long)mmo.offset, (unsigned long long)xmap.addr);

	volatile uint32_t *cs = (volatile uint32_t *)(uintptr_t)xmap.addr;
	cs[256] = 0xdeadbeefu;
	__sync_synchronize();
	if (cs[256] != 0xdeadbeefu) {
		printf("FAIL: CPU readback mismatch on mapped BO\n");
		return 1;
	}

	struct drm_syncobj_create soc;
	memset(&soc, 0, sizeof(soc));
	if (xioctl(fd, DRM_IOCTL_SYNCOBJ_CREATE, &soc) != 0) {
		printf("FAIL: DRM_IOCTL_SYNCOBJ_CREATE errno=%d (%s)\n", errno, strerror(errno));
		return 1;
	}

	const uint64_t gpu_va = 0x200000ULL;
	const uint16_t pat_candidates[] = { 3, 4, 2, 0, 1 };
	int bound = 0;
	uint16_t used_pat = 0;
	for (size_t p = 0; p < sizeof(pat_candidates) / sizeof(pat_candidates[0]); p++) {
		struct drm_xe_sync sync;
		memset(&sync, 0, sizeof(sync));
		sync.type = DRM_XE_SYNC_TYPE_SYNCOBJ;
		sync.flags = DRM_XE_SYNC_FLAG_SIGNAL;
		sync.handle = soc.handle;

		struct drm_xe_vm_bind bind;
		memset(&bind, 0, sizeof(bind));
		bind.vm_id = vmc.vm_id;
		bind.num_binds = 1;
		bind.bind.obj = gc.handle;
		bind.bind.obj_offset = 0;
		bind.bind.range = 4096;
		bind.bind.addr = gpu_va;
		bind.bind.op = DRM_XE_VM_BIND_OP_MAP;
		bind.bind.pat_index = pat_candidates[p];
		bind.num_syncs = 1;
		bind.syncs = (uintptr_t)&sync;
		if (xioctl(fd, DRM_IOCTL_XE_VM_BIND, &bind) == 0) {
			used_pat = pat_candidates[p];
			bound = 1;
			break;
		}
	}
	if (!bound) {
		printf("FAIL: DRM_IOCTL_XE_VM_BIND failed for all PAT candidates, last errno=%d (%s)\n",
		       errno, strerror(errno));
		return 1;
	}

	struct drm_syncobj_wait sw;
	memset(&sw, 0, sizeof(sw));
	sw.handles = (uintptr_t)&soc.handle;
	sw.count_handles = 1;
	sw.timeout_nsec = INT64_MAX;
	if (xioctl(fd, DRM_IOCTL_SYNCOBJ_WAIT, &sw) != 0) {
		printf("FAIL: DRM_IOCTL_SYNCOBJ_WAIT (vm_bind) errno=%d (%s)\n", errno, strerror(errno));
		return 1;
	}
	printf("DRM_IOCTL_XE_VM_BIND: mapped BO at PPGTT VA=0x%llx with pat_index=%u\n",
	       (unsigned long long)gpu_va, used_pat);

	uint32_t ok_engines = 0;
	for (uint32_t i = 0; i < engs->num_engines; i++) {
		struct drm_xe_exec_queue_create eqc;
		memset(&eqc, 0, sizeof(eqc));
		eqc.vm_id = vmc.vm_id;
		eqc.width = 1;
		eqc.num_placements = 1;
		eqc.instances = (uintptr_t)&engs->engines[i].instance;
		if (xioctl(fd, DRM_IOCTL_XE_EXEC_QUEUE_CREATE, &eqc) != 0) {
			printf("  ENG[%u] class=%u inst=%u gt=%u EXEC_QUEUE_CREATE failed: errno=%d (%s)\n",
			       i, engs->engines[i].instance.engine_class,
			       engs->engines[i].instance.engine_instance,
			       engs->engines[i].instance.gt_id, errno, strerror(errno));
			continue;
		}

		uint32_t want = 0x58677000u | (i << 8) | (engs->engines[i].instance.engine_class & 0xffu);
		uint64_t target_va = gpu_va + 1024ULL;
		cs[256] = 0xdeadbeefu;
		cs[0] = (0x20u << 23) | 2u; /* MI_STORE_DWORD_IMM (PPGTT) */
		cs[1] = (uint32_t)(target_va & 0xffffffffULL);
		cs[2] = (uint32_t)(target_va >> 32);
		cs[3] = want;
		cs[4] = (0x0au << 23); /* MI_BATCH_BUFFER_END */
		__sync_synchronize();

		struct drm_syncobj_array sa = { .handles = (uintptr_t)&soc.handle, .count_handles = 1 };
		xioctl(fd, DRM_IOCTL_SYNCOBJ_RESET, &sa);

		struct drm_xe_sync sync;
		memset(&sync, 0, sizeof(sync));
		sync.type = DRM_XE_SYNC_TYPE_SYNCOBJ;
		sync.flags = DRM_XE_SYNC_FLAG_SIGNAL;
		sync.handle = soc.handle;

		struct drm_xe_exec exec;
		memset(&exec, 0, sizeof(exec));
		exec.exec_queue_id = eqc.exec_queue_id;
		exec.num_syncs = 1;
		exec.syncs = (uintptr_t)&sync;
		exec.address = gpu_va;
		exec.num_batch_buffer = 1;

		int exec_rc = xioctl(fd, DRM_IOCTL_XE_EXEC, &exec);
		if (exec_rc != 0) {
			printf("  ENG[%u] DRM_IOCTL_XE_EXEC failed: errno=%d (%s)\n", i, errno, strerror(errno));
		} else {
			memset(&sw, 0, sizeof(sw));
			sw.handles = (uintptr_t)&soc.handle;
			sw.count_handles = 1;
			sw.timeout_nsec = INT64_MAX;
			int wait_rc = xioctl(fd, DRM_IOCTL_SYNCOBJ_WAIT, &sw);
			__sync_synchronize();
			uint32_t got = cs[256];
			if (wait_rc == 0 && got == want) {
				ok_engines++;
				printf("  ENG[%u] class=%u inst=%u gt=%u qid=%u PPGTT store want=0x%08x got=0x%08x PASS\n",
				       i, engs->engines[i].instance.engine_class,
				       engs->engines[i].instance.engine_instance,
				       engs->engines[i].instance.gt_id, eqc.exec_queue_id, want, got);
			} else {
				printf("  ENG[%u] class=%u inst=%u gt=%u qid=%u wait_rc=%d want=0x%08x got=0x%08x FAIL\n",
				       i, engs->engines[i].instance.engine_class,
				       engs->engines[i].instance.engine_instance,
				       engs->engines[i].instance.gt_id, eqc.exec_queue_id, wait_rc, want, got);
			}
		}

		struct drm_xe_exec_queue_destroy eqd = { .exec_queue_id = eqc.exec_queue_id };
		xioctl(fd, DRM_IOCTL_XE_EXEC_QUEUE_DESTROY, &eqd);
		usleep(20000);
	}

	printf("xe-uapi-probe summary: %u/%u userspace PPGTT engines verified\n", ok_engines, engs->num_engines);

	struct xg_drm_munmap xunmap = { .addr = xmap.addr, .size = 4096 };
	xioctl(fd, XG_DRM_IOCTL_MUNMAP, &xunmap);
	struct drm_gem_close gclose = { .handle = gc.handle };
	xioctl(fd, DRM_IOCTL_GEM_CLOSE, &gclose);
	struct drm_syncobj_destroy sod = { .handle = soc.handle };
	xioctl(fd, DRM_IOCTL_SYNCOBJ_DESTROY, &sod);
	struct drm_xe_vm_destroy vmd = { .vm_id = vmc.vm_id };
	xioctl(fd, DRM_IOCTL_XE_VM_DESTROY, &vmd);
	usleep(20000);
	close(fd);
	free(engs);
	return ok_engines == engs->num_engines ? 0 : 2;
}
