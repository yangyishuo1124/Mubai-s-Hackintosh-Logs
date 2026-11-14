"""Compile the patched init function and verify allocation/error/order semantics."""
from pathlib import Path
import subprocess, sys, tempfile
s=Path(sys.argv[1]).read_text()
a=s.index('int xe_ggtt_init(struct'); b=s.index('static void ggtt_invalidate_gt_tlb',a)
fn=s[a:b]
code=r'''
#include <assert.h>
#include <stddef.h>
struct xe_device {struct {void *dev;} drm;};
struct bo {int vmap; unsigned long size;};
struct xe_ggtt {void *tile; unsigned flags; struct bo *scratch;};
#define XE_BO_FLAG_PINNED 1
#define XE_BO_FLAG_SYSTEM 2
#define XE_BO_FLAG_VRAM_IF_DGFX(t) 4
#define XE_GGTT_FLAGS_64K 8
#define XE_PAGE_SIZE 4096
#define IS_ERR(p) ((long)(p)<0)
#define PTR_ERR(p) ((int)(long)(p))
static struct xe_device device;
static struct bo page={0,4096};
static int alloc_error,action_error,order,flags_seen;
struct xe_device *tile_to_xe(void *t){return &device;}
void xg_init_checkpoint(int i,const char *s){}
int xg_printf(const char *s,...){return 0;}
struct bo *xe_managed_bo_create_pin_map(struct xe_device *x,void *t,int n,int f){
 assert(order++==0 && n==4096);flags_seen=f;
 return alloc_error?(struct bo *)(long)alloc_error:&page;
}
void xe_map_memset(struct xe_device *x,void *m,int a,int b,unsigned long n){
 assert(order++==1 && m==&page.vmap && n==4096 && !a && !b);
}
void xe_ggtt_initial_clear(struct xe_ggtt *g){assert(order++==2 && g->scratch==&page);}
void ggtt_fini(void *a,void *b){}
int devm_add_action_or_reset(void *d,void (*f)(void *,void *),void *g){
 assert(order++==3 && f==ggtt_fini);return action_error;
}
'''+fn+r'''
int main(void){struct xe_ggtt g={0};
 assert(xe_ggtt_init(&g)==0 && order==4 && flags_seen==5);
 order=0;g.flags=XE_GGTT_FLAGS_64K;
 assert(xe_ggtt_init(&g)==0 && order==4 && flags_seen==3);
 order=0;alloc_error=-12;
 assert(xe_ggtt_init(&g)==-12 && order==1 && g.scratch==NULL);
 order=0;alloc_error=0;action_error=-5;
 assert(xe_ggtt_init(&g)==-5 && order==4);
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(code)
 subprocess.run(['cc','-Werror','-o',str(p/'test'),str(p/'test.c')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('Actual GGTT init preserves scratch flags, allocation failure, operation order and cleanup registration errors.')
