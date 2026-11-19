/* SPDX-License-Identifier: MIT
 * Darwin Xe userptr: wire the caller's pages for the VMA's lifetime instead
 * of using Linux HMM invalidation. Never populate from a worker's address space.
 */
#ifndef XG_USERPTR_TEST
#include <linux/mm.h>
#include <linux/scatterlist.h>
#include <linux/dma-mapping.h>
#include "xe_vm.h"
#include "xe_device.h"
#endif

/* Re-read the existing runtime tunables bridge so testing does not require
 * enabling host import at boot or adding another native sysctl. */
extern int getenv_int(const char *name, int *value);

struct xg_xe_userptr_hold {
    struct sg_table sgt;
    struct page **pages;
    unsigned long npages;
    bool write;
};

static void xg_xe_userptr_unmap_locked(struct xe_userptr_vma *uvma)
{
    struct xe_userptr *up = &uvma->userptr;
    if (up->sg && up->mapped) {
        struct xg_xe_userptr_hold *h = container_of(up->sg, struct xg_xe_userptr_hold, sgt);
        dma_unmap_sgtable(xe_vma_vm(&uvma->vma)->xe->drm.dev, up->sg,
                         h->write ? DMA_BIDIRECTIONAL : DMA_TO_DEVICE, 0);
    }
    up->mapped = false;
}

void xe_hmm_userptr_unmap(struct xe_userptr_vma *uvma)
{
    mutex_lock(&uvma->userptr.unmap_mutex);
    xg_xe_userptr_unmap_locked(uvma);
    mutex_unlock(&uvma->userptr.unmap_mutex);
}

/* xe_vma_destroy_late calls this after the final GPU access fence. */
void xe_hmm_userptr_free_sg(struct xe_userptr_vma *uvma)
{
    struct xe_userptr *up = &uvma->userptr;
    struct xg_xe_userptr_hold *h;
    unsigned long i;
    mutex_lock(&up->unmap_mutex);
    if (!up->sg) goto out;
    h = container_of(up->sg, struct xg_xe_userptr_hold, sgt);
    xg_xe_userptr_unmap_locked(uvma);
    up->sg = NULL;
    sg_free_table(&h->sgt);
    for (i = 0; i < h->npages; i++) {
        if (h->write) set_page_dirty(h->pages[i]);
        put_page(h->pages[i]);
    }
    kfree(h->pages);
    kfree(h);
out:
    mutex_unlock(&up->unmap_mutex);
}

int xe_hmm_userptr_populate_range(struct xe_userptr_vma *uvma, bool locked)
{
    struct xe_userptr *up = &uvma->userptr;
    struct xe_vma *vma = &uvma->vma;
    struct xe_vm *vm = xe_vma_vm(vma);
    struct xg_xe_userptr_hold *h = NULL;
    u64 start = xe_vma_userptr(vma), size = xe_vma_size(vma);
    unsigned long seq, npages, i;
    long pinned;
    int err = 0, enabled = 0;
    bool write = !xe_vma_read_only(vma);
    (void)locked;
    if (vma->gpuva.flags & XE_VMA_DESTROYED) return 0;
    if (!size || (start & (PAGE_SIZE - 1)) || (size & (PAGE_SIZE - 1)) ||
        start + size < start || size / PAGE_SIZE > INT_MAX)
        return -EINVAL;

    down_read(&vm->userptr.notifier_lock);
    mutex_lock(&up->unmap_mutex);
    seq = mmu_interval_read_begin(&up->notifier);
    if (up->sg) {
        /* Wired pages remain valid across GPU resets and DMA unmap/remap.
         * An unexpected invalidation must fail instead of freeing live pages. */
        if (seq != up->notifier_seq) { err = -EAGAIN; goto out; }
        if (!up->mapped) {
            h = container_of(up->sg, struct xg_xe_userptr_hold, sgt);
            err = dma_map_sgtable(vm->xe->drm.dev, up->sg,
                                 h->write ? DMA_BIDIRECTIONAL : DMA_TO_DEVICE,
                                 DMA_ATTR_SKIP_CPU_SYNC);
            if (!err) up->mapped = true;
        }
        goto out;
    }
    if (!getenv_int("compat.linuxkpi.xe_userptr", &enabled) || enabled != 1) {
        err = -EOPNOTSUPP; goto out;
    }
    if (!current->mm || current->mm != up->notifier.mm) { err = -EFAULT; goto out; }
    npages = size / PAGE_SIZE;
    h = kzalloc(sizeof(*h), GFP_KERNEL);
    if (!h) { err = -ENOMEM; goto out; }
    h->pages = kcalloc(npages, sizeof(*h->pages), GFP_KERNEL);
    if (!h->pages) { err = -ENOMEM; goto free_hold; }
    h->write = write;
    pinned = __get_user_pages_fast((unsigned long)start, (int)npages, write, h->pages);
    if (pinned < 0) { err = (int)pinned; goto free_pages; }
    h->npages = pinned;
    if ((unsigned long)pinned != npages) { err = -EFAULT; goto put_pages; }
    err = sg_alloc_table_from_pages(&h->sgt, h->pages, npages, 0, size, GFP_KERNEL);
    if (err) goto put_pages;
    err = dma_map_sgtable(vm->xe->drm.dev, &h->sgt,
                         write ? DMA_BIDIRECTIONAL : DMA_TO_DEVICE,
                         DMA_ATTR_SKIP_CPU_SYNC);
    if (err) goto free_sg;
    if (mmu_interval_read_retry(&up->notifier, seq)) {
        dma_unmap_sgtable(vm->xe->drm.dev, &h->sgt,
                         write ? DMA_BIDIRECTIONAL : DMA_TO_DEVICE, 0);
        err = -EAGAIN;
        goto free_sg;
    }
    up->sg = &h->sgt;
    up->mapped = true;
    up->notifier_seq = seq;
    goto out;
free_sg:
    sg_free_table(&h->sgt);
put_pages:
    for (i = 0; i < h->npages; i++) put_page(h->pages[i]);
free_pages:
    kfree(h->pages);
free_hold:
    kfree(h);
out:
    mutex_unlock(&up->unmap_mutex);
    up_read(&vm->userptr.notifier_lock);
    return err;
}
