/* Host resource-lifecycle tests for the actual Darwin userptr implementation.
 * GPU visibility and coherency are tested separately on the target hardware. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stddef.h>
#include <limits.h>
#include <errno.h>
#include <stdio.h>
#define XG_USERPTR_TEST
#define module_param_named(...)
#define PAGE_SIZE 4096UL
#define GFP_KERNEL 0
#define DMA_BIDIRECTIONAL 1
#define DMA_TO_DEVICE 2
#define DMA_ATTR_SKIP_CPU_SYNC 1
#define XE_VMA_DESTROYED 1
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
typedef uint64_t u64;
struct page { int refs, dirty; } pages[64];
struct sg_table { unsigned nents; };
struct mmu_interval_notifier { void *mm; unsigned long seq; };
struct xe_userptr { struct sg_table *sg; bool mapped; unsigned long notifier_seq;
    int unmap_mutex; struct mmu_interval_notifier notifier; };
struct xe_device { struct { void *dev; } drm; } device;
struct xe_vm { struct xe_device *xe; struct { int notifier_lock; } userptr; } vm;
struct xe_vma { struct { unsigned flags; } gpuva; struct xe_vm *vm;
    u64 start, size; bool readonly; };
struct xe_userptr_vma { struct xe_vma vma; struct xe_userptr userptr; };
struct { void *mm; } task, *current = &task;
static int dma_live, sg_live, pin_limit = -1, fail_sg, fail_dma;
static void mutex_lock(int *p) { assert(!*p); *p=1; }
static void mutex_unlock(int *p) { assert(*p); *p=0; }
static void down_read(int *p) { ++*p; }
static void up_read(int *p) { assert(*p); --*p; }
static struct xe_vm *xe_vma_vm(struct xe_vma *v) { return v->vm; }
static u64 xe_vma_userptr(struct xe_vma *v) { return v->start; }
static u64 xe_vma_size(struct xe_vma *v) { return v->size; }
static bool xe_vma_read_only(struct xe_vma *v) { return v->readonly; }
static unsigned long mmu_interval_read_begin(struct mmu_interval_notifier *n) { return n->seq; }
static bool mmu_interval_read_retry(struct mmu_interval_notifier *n,unsigned long s) { return s!=n->seq; }
#define kzalloc(n,f) calloc(1,n)
#define kcalloc(n,s,f) calloc(n,s)
#define kfree free
static long __get_user_pages_fast(unsigned long s,int n,int write,struct page **out) {
    (void)s; (void)write;
    if (pin_limit == -2) return -EFAULT;
    if (pin_limit >= 0 && n > pin_limit) n=pin_limit;
    assert(n<=64);
    for(int i=0;i<n;i++) { out[i]=&pages[i]; pages[i].refs++; }
    return n;
}
static void put_page(struct page *p) { assert(p->refs>0); p->refs--; }
static void set_page_dirty(struct page *p) { p->dirty=1; }
static int sg_alloc_table_from_pages(struct sg_table *s,struct page **p,unsigned long n,
    unsigned off,u64 size,int flags) {
    (void)p;(void)off;(void)size;(void)flags;
    if(fail_sg) return -ENOMEM;
    s->nents=n;sg_live++;return 0;
}
static void sg_free_table(struct sg_table *s) { assert(s->nents);s->nents=0;sg_live--; }
static int dma_map_sgtable(void *d,struct sg_table *s,int dir,int flags) {
    (void)d;(void)s;(void)dir;(void)flags;
    if(fail_dma)return -EIO;
    dma_live++;return 0;
}
static void dma_unmap_sgtable(void *d,struct sg_table *s,int dir,int flags) {
    (void)d;(void)s;(void)dir;(void)flags;assert(dma_live>0);dma_live--;
}
#include "xg_xe_userptr.inc"
static struct xe_userptr_vma fresh(void) {
    struct xe_userptr_vma v={0};vm.xe=&device;task.mm=&task;
    v.vma.vm=&vm;v.vma.start=0x10000;v.vma.size=8192;
    v.userptr.notifier.mm=task.mm;v.userptr.notifier.seq=2;
    return v;
}
static void clean(void) {
    assert(!dma_live && !sg_live && !vm.userptr.notifier_lock);
    for(int i=0;i<64;i++)assert(!pages[i].refs);
}
int main(void) {
    struct xe_userptr_vma v=fresh();
    assert(xe_hmm_userptr_populate_range(&v,false)==-EOPNOTSUPP);clean();
    xg_xe_userptr_enabled=true;
    task.mm=NULL;assert(xe_hmm_userptr_populate_range(&v,false)==-EFAULT);clean();task.mm=&task;
    v.vma.size=1;assert(xe_hmm_userptr_populate_range(&v,false)==-EINVAL);clean();v=fresh();
    pin_limit=1;assert(xe_hmm_userptr_populate_range(&v,false)==-EFAULT);clean();
    pin_limit=-2;assert(xe_hmm_userptr_populate_range(&v,false)==-EFAULT);clean();pin_limit=-1;
    fail_sg=1;assert(xe_hmm_userptr_populate_range(&v,false)==-ENOMEM);clean();fail_sg=0;
    fail_dma=1;assert(xe_hmm_userptr_populate_range(&v,false)==-EIO);clean();fail_dma=0;
    assert(!xe_hmm_userptr_populate_range(&v,false));assert(dma_live==1 && pages[0].refs==1);
    assert(!xe_hmm_userptr_populate_range(&v,false));assert(dma_live==1 && pages[0].refs==1);
    xe_hmm_userptr_unmap(&v);assert(!dma_live && pages[0].refs==1);
    task.mm=NULL;assert(!xe_hmm_userptr_populate_range(&v,false));assert(dma_live==1);
    v.userptr.notifier.seq=4;assert(xe_hmm_userptr_populate_range(&v,false)==-EAGAIN);
    assert(dma_live==1 && pages[0].refs==1);
    xe_hmm_userptr_free_sg(&v);assert(pages[0].dirty);clean();
    xe_hmm_userptr_free_sg(&v);clean();
    v=fresh();v.vma.readonly=true;pages[0].dirty=0;
    assert(!xe_hmm_userptr_populate_range(&v,false));xe_hmm_userptr_free_sg(&v);
    assert(!pages[0].dirty);clean();
    puts("PASS: opt-in, owner check, range validation, partial pin, SG/DMA failure, reuse, remap, invalidation, teardown");
}
