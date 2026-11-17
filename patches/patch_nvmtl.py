from pathlib import Path
import sys

root = Path(sys.argv[1])

# 1. NVMTLObjects.h: add strided host resync fields to NVMTLBuffer
h_path = root / "plugin" / "NVMTLObjects.h"
h = h_path.read_text()
old_h = "    void *_hostPtr; size_t _hostLen; id _hostDealloc;"
assert old_h in h, "NVMTLObjects.h _hostPtr anchor missing"
h = h.replace(
    old_h,
    "    void *_hostPtr; size_t _hostLen; id _hostDealloc;\n    size_t _hostSrcBpr; size_t _hostDstBpr; size_t _hostRows;",
    1,
)
h_path.write_text(h)

# 2. NVMTLObjects.m: 32B-align stand-in bytesPerRow in newTiledTextureWithDescriptor & newTextureWithDescriptor
m_path = root / "plugin" / "NVMTLObjects.m"
m = m_path.read_text()

old_tiled = """    if (d.usage != MTLTextureUsageUnknown && !ru && !getenv("NVMTL_NO_TILED_RESYNC")) {
        NVMTLBuffer *s = [NVMTLBuffer new];
        const size_t n = MIN((size_t)bpr * d.height, _b.size - offset);
        if (s && !nvmtl_vk_buffer_create(n, 1, &s->_b) && s->_b.map) {
            s->_storage = MTLStorageModeShared;
            memcpy(s->_b.map, (char *)base + offset, n);
            s->_hostPtr = (char *)base + offset; s->_hostLen = n;
            NVMTLBuffer *src = self;   // the caller's bytes live as long as the stand-in does
            s->_hostDealloc = ^(void *p, NSUInteger l) { (void)p; (void)l; (void)src; };
            // the copy below only ever filled level 0 of slice 0, so a single-level view loses nothing
            MTLTextureDescriptor *sd = [d copy]; sd.mipmapLevelCount = 1; sd.sampleCount = 1; sd.arrayLength = 1; sd.depth = 1;
            id<MTLTexture> v = [s newTextureWithDescriptor:sd offset:0 bytesPerRow:bpr];"""

new_tiled = """    if (d.usage != MTLTextureUsageUnknown && !ru && !getenv("NVMTL_NO_TILED_RESYNC")) {
        NVMTLBuffer *s = [NVMTLBuffer new];
        const NSUInteger sbpr = (bpr + 31u) & ~(NSUInteger)31u;
        const size_t srcAvail = _b.size - offset;
        const size_t n = (sbpr == bpr) ? MIN((size_t)bpr * d.height, srcAvail) : ((size_t)sbpr * d.height);
        if (s && n && !nvmtl_vk_buffer_create(n, 1, &s->_b) && s->_b.map) {
            s->_storage = MTLStorageModeShared;
            s->_hostPtr = (char *)base + offset;
            s->_hostLen = MIN((size_t)bpr * d.height, srcAvail);
            if (sbpr == bpr) {
                memcpy(s->_b.map, s->_hostPtr, s->_hostLen);
            } else {
                const char *sp = (const char *)s->_hostPtr;
                char *dp = (char *)s->_b.map;
                for (size_t y = 0; y < (size_t)d.height; y++) {
                    size_t off = y * bpr;
                    if (off >= s->_hostLen) break;
                    size_t rlen = MIN((size_t)bpr, s->_hostLen - off);
                    memcpy(dp + y * sbpr, sp + off, rlen);
                }
                s->_hostSrcBpr = bpr;
                s->_hostDstBpr = sbpr;
                s->_hostRows = d.height;
            }
            NVMTLBuffer *src = self;   // the caller's bytes live as long as the stand-in does
            s->_hostDealloc = ^(void *p, NSUInteger l) { (void)p; (void)l; (void)src; };
            // the copy below only ever filled level 0 of slice 0, so a single-level view loses nothing
            MTLTextureDescriptor *sd = [d copy]; sd.mipmapLevelCount = 1; sd.sampleCount = 1; sd.arrayLength = 1; sd.depth = 1;
            id<MTLTexture> v = [s newTextureWithDescriptor:sd offset:0 bytesPerRow:sbpr];"""

assert old_tiled in m, "NVMTLObjects.m old_tiled anchor missing"
m = m.replace(old_tiled, new_tiled, 1)

old_standin = """        if (need > _b.size && offset < _b.size && [self contents] && !getenv("NVMTL_NO_BUFTEX_STANDIN")) {
            NVMTLBuffer *sb = [NVMTLBuffer new];
            if (sb && !nvmtl_vk_buffer_create((need - offset + 4095) & ~(size_t)4095, 1, &sb->_b) && sb->_b.map) {
                sb->_storage = MTLStorageModeShared;
                sb->_hostPtr = (char *)[self contents] + offset; sb->_hostLen = _b.size - offset;
                memcpy(sb->_b.map, sb->_hostPtr, sb->_hostLen);
                NVMTLBuffer *src = self;   // the caller's bytes live as long as the stand-in does
                sb->_hostDealloc = ^(void *p, NSUInteger l) { (void)p; (void)l; (void)src; };
                id<MTLTexture> v = [sb newTextureWithDescriptor:d offset:0 bytesPerRow:bpr];"""

new_standin = """        if ((need > _b.size || (bpr % 32) != 0) && offset < _b.size && [self contents] && !getenv("NVMTL_NO_BUFTEX_STANDIN")) {
            NVMTLBuffer *sb = [NVMTLBuffer new];
            const NSUInteger sbpr = (bpr + 31u) & ~(NSUInteger)31u;
            const size_t sneed = (size_t)sbpr * (h - 1) + w * bpp;
            if (sb && !nvmtl_vk_buffer_create((sneed + 4095) & ~(size_t)4095, 1, &sb->_b) && sb->_b.map) {
                sb->_storage = MTLStorageModeShared;
                sb->_hostPtr = (char *)[self contents] + offset; sb->_hostLen = _b.size - offset;
                if (sbpr == bpr) {
                    memcpy(sb->_b.map, sb->_hostPtr, sb->_hostLen);
                } else {
                    const char *sp = (const char *)sb->_hostPtr;
                    char *dp = (char *)sb->_b.map;
                    for (size_t y = 0; y < h; y++) {
                        size_t off = y * bpr;
                        if (off >= sb->_hostLen) break;
                        size_t rlen = MIN((size_t)bpr, sb->_hostLen - off);
                        memcpy(dp + y * sbpr, sp + off, rlen);
                    }
                    sb->_hostSrcBpr = bpr;
                    sb->_hostDstBpr = sbpr;
                    sb->_hostRows = h;
                }
                NVMTLBuffer *src = self;   // the caller's bytes live as long as the stand-in does
                sb->_hostDealloc = ^(void *p, NSUInteger l) { (void)p; (void)l; (void)src; };
                id<MTLTexture> v = [sb newTextureWithDescriptor:d offset:0 bytesPerRow:sbpr];"""

assert old_standin in m, "NVMTLObjects.m old_standin anchor missing"
m = m.replace(old_standin, new_standin, 1)

old_syncin = """static void nvmtl_buffer_sync_in(NVMTLBuffer *b)
{
    if (!b || !b->_hostPtr || !b->_b.map || !b->_hostLen) return;
    const uint64_t t0 = nvmtl_perf_now();
    memcpy(b->_b.map, b->_hostPtr, b->_hostLen);
    nvmtl_perf_note(NVP_SYNCIN, t0, b->_hostLen);
}"""

new_syncin = """static void nvmtl_buffer_sync_in(NVMTLBuffer *b)
{
    if (!b || !b->_hostPtr || !b->_b.map || !b->_hostLen) return;
    const uint64_t t0 = nvmtl_perf_now();
    if (b->_hostRows && b->_hostDstBpr && b->_hostSrcBpr && b->_hostDstBpr != b->_hostSrcBpr) {
        const char *sp = (const char *)b->_hostPtr;
        char *dp = (char *)b->_b.map;
        const size_t sbpr = b->_hostSrcBpr, dbpr = b->_hostDstBpr, avail = b->_hostLen;
        for (size_t y = 0; y < b->_hostRows; y++) {
            size_t off = y * sbpr;
            if (off >= avail) break;
            size_t rlen = MIN(sbpr, avail - off);
            memcpy(dp + y * dbpr, sp + off, rlen);
        }
    } else {
        memcpy(b->_b.map, b->_hostPtr, b->_hostLen);
    }
    nvmtl_perf_note(NVP_SYNCIN, t0, b->_hostLen);
}"""

assert old_syncin in m, "NVMTLObjects.m old_syncin anchor missing"
m = m.replace(old_syncin, new_syncin, 1)

m_path.write_text(m)
print("Patched NVMTLObjects.h and NVMTLObjects.m")
