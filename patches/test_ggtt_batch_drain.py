from pathlib import Path
import subprocess,sys,tempfile
s=Path(sys.argv[1]).read_text();a=s.index('static void xe_ggtt_clear(');b=s.index('static void ggtt_fini_early',a)
code=r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
typedef uint64_t u64;typedef uint16_t u16;
#define XE_CACHE_WB 0
#define XE_PAGE_SIZE 4096
#define VF_CAP_REG 0
#define xe_tile_assert(t,c) assert(c)
struct pci_dev {int device;};
struct xe_device {struct {int idx[1];}pat;struct {struct pci_dev *dev;}drm;};
struct ops {u64 (*pte_encode_bo)(void*,int,int);void (*ggtt_set_pte)(void*,u64,u64);};
struct xe_ggtt {struct xe_device *tile;void *scratch;struct ops *pt_ops;};
#define tile_to_xe(t) (t)
#define to_pci_dev(d) (d)
#define xe_root_tile_mmio(x) (x)
static int writes,reads,last_read;
static u64 next;
void xg_init_checkpoint(int n,const char*s){}
int xg_printf(const char*s,...){return 0;}
u64 encode(void*p,int a,int b){return 0x12345001;}
void set(void*g,u64 addr,u64 pte){assert(addr==next && pte==0x12345001);next+=4096;writes++;}
int xe_mmio_read32(void*x,int reg){assert(writes>last_read && writes-last_read<=64);last_read=writes;reads++;return 0;}
'''+s[a:b]+r'''
int main(void){
 struct pci_dev p={0xb0a0};struct xe_device x={0};x.drm.dev=&p;
 struct ops op={encode,set};struct xe_ggtt g={&x,&x,&op};
 int counts[]={1,63,64,65,128,129,1031847};
 for(int control=0;control<2;control++)for(int i=0;i<7;i++){
  p.device=control?0x1234:0xb0a0;
  writes=reads=last_read=0;next=0x1927000;
  xe_ggtt_clear(&g,next,(u64)counts[i]*4096);
  assert(writes==counts[i]);
  assert(reads==(control?0:(counts[i]+63)/64));
  assert(next==0x1927000+(u64)counts[i]*4096);
 }
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(code)
 subprocess.run(['cc','-Werror','-o',str(p/'test'),str(p/'test.c')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('Actual GGTT clear preserves every PTE and order; 1/63/64/65/128/129/large batches and other-device control pass.')
