from pathlib import Path
import sys,tempfile,subprocess
s=Path(sys.argv[1]).read_text();a=s.index('static int __xe_guc_upload(');b=s.index('static int vf_guc_min_load_for_hwconfig(',a);fn=s[a:b]
code=r"""
#include <assert.h>
struct xe_guc {int pc,fw;};
#define UOS_MOVE 0
#define XE_UC_FIRMWARE_RUNNING 1
#define XE_UC_FIRMWARE_LOAD_FAIL 2
static int rsa_err,upload_err,wait_err,status,upload_calls,wait_calls;
void xe_guc_pc_raise_unslice(void*p){}
void guc_write_params(struct xe_guc*g){}
void guc_prepare_xfer(struct xe_guc*g){}
void xg_init_checkpoint(int i,const char*s){}
int guc_xfer_rsa(struct xe_guc*g){return rsa_err;}
int xe_uc_fw_upload(void*p,int a,int b){upload_calls++;return upload_err;}
int guc_wait_ucode(struct xe_guc*g){wait_calls++;return wait_err;}
void xe_uc_fw_change_status(void*p,int value){status=value;}
"""+fn+r"""
int main(void){struct xe_guc g={0};
assert(__xe_guc_upload(&g)==0 && status==XE_UC_FIRMWARE_RUNNING);
rsa_err=-5;upload_calls=wait_calls=0;
assert(__xe_guc_upload(&g)==-5 && status==XE_UC_FIRMWARE_LOAD_FAIL && !upload_calls && !wait_calls);
rsa_err=0;upload_err=-12;wait_calls=0;
assert(__xe_guc_upload(&g)==-12 && status==XE_UC_FIRMWARE_LOAD_FAIL && !wait_calls);
upload_err=0;wait_err=-110;
assert(__xe_guc_upload(&g)==-110 && status==XE_UC_FIRMWARE_LOAD_FAIL);
wait_err=0;assert(__xe_guc_upload(&g)==0 && status==XE_UC_FIRMWARE_RUNNING);
}
"""
pc=Path(sys.argv[2]).read_text();a=pc.index('int xe_guc_pc_start(');b=pc.index('/**',a);pc=pc[a:b]
assert pc.count('ret = wait_for_pc_state(')==2
assert 'return ret;' in pc
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(code)
 subprocess.run(['cc','-Werror','-o',str(p/'test'),str(p/'test.c')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('Actual GuC upload function propagates RSA/DMA/authentication errors; success marks RUNNING only after all pass. PC wait results stored.')
