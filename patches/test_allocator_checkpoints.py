from pathlib import Path
import sys,tempfile,subprocess
s=Path(sys.argv[1]).read_text();fn=s[s.index('int __xe_ttm_vram_mgr_init('):s.index('\nint xe_ttm_vram_mgr_init(')]
code=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
typedef uint32_t u32;typedef uint64_t u64;
#define XE_PL_STOLEN 3
#define XE_PL_VRAM0 1
#define IS_ERR(p) false
#define PTR_ERR(p) (-1)
struct ttm_resource_manager {void *cg,*func;u64 size;};
struct xe_ttm_vram_mgr {struct ttm_resource_manager manager;u32 mem_type;int lock,mm;u64 default_page_size,visible_size,visible_avail;};
struct xe_device {int drm,ttm;};
static int xe_ttm_vram_mgr_func,ttm_vram_mgr_fini,buddy_error,cleanup_error,n,events[32],installed;
void xg_init_checkpoint(int id,const char *label){events[n++]=id;}
void *drmm_cgroup_register_region(void *d,const char *name,u64 size){return 0;}
void mutex_init(int *lock){*lock=1;}
void ttm_resource_manager_init(struct ttm_resource_manager *m,void*t,u64 size){m->size=size;}
int drm_buddy_init(int *mm,u64 size,u64 page){return buddy_error;}
void ttm_set_driver_manager(void*t,u32 ty,void*m){installed++;}
void ttm_resource_manager_set_used(void*m,bool used){}
int drmm_add_action_or_reset(void*d,int f,void*m){return cleanup_error;}
"""+fn+r"""
int main(void){
 struct xe_device xe={0};struct xe_ttm_vram_mgr mgr={0};
 assert(__xe_ttm_vram_mgr_init(&xe,&mgr,XE_PL_STOLEN,0x1060000,0x1060000,4096)==0);
 assert(n==11 && installed==1 && mgr.lock==1 && mgr.manager.size==0x1060000);
 for(int i=0;i<11;i++)assert(events[i]==31001+i);
 n=installed=0;buddy_error=-12;
 assert(__xe_ttm_vram_mgr_init(&xe,&mgr,XE_PL_STOLEN,4096,4096,4096)==-12);
 assert(n==7 && events[n-1]==31007 && installed==0);
 n=0;buddy_error=0;cleanup_error=-22;
 assert(__xe_ttm_vram_mgr_init(&xe,&mgr,XE_PL_STOLEN,4096,4096,4096)==-22);
 assert(n==11 && events[n-1]==31011);
}
"""
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'allocator.c';p.write_text(code);exe=Path(d)/'allocator'
 subprocess.run(['cc','-std=gnu11','-Wall','-Werror','-fsanitize=undefined',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('Actual allocator checkpoints preserve success, buddy failure and cleanup failure return paths.')
