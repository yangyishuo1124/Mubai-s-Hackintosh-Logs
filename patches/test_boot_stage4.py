from pathlib import Path
import sys,tempfile,subprocess
s=Path(sys.argv[1]).read_text();a=s.index('static void\nxg_boot_initialize(void)\n{');b=s.index('static void\nxg_boot_fire(',a)
fn=s[a:b]
start=s[s.index('bool\nXeGfxResident::start'):s.index('OSDefineMetaClassAndStructors')]
assert 'thread_call_enter_delayed' in start and 'xg_boot_initialize();' not in start
assert '|| gBootInitCall)' in s
code=r'''
#include <assert.h>
#include <string.h>
static int arg,found,gStage,gResult[8],xg_progress,gDedicatedActive,wd_error,calls,fail,locked;
static void *gStageLock;static char xg_env[512];
static int probes,ready_after,sleeps,releases;
struct IOPCIDevice {void release(){releases++;}};
static IOPCIDevice gpu;
IOPCIDevice *xg_find_igpu(){return ++probes>ready_after?&gpu:nullptr;}
void IOSleep(int n){assert(!locked && n==100);sleeps++;}
bool PE_parse_boot_argn(const char*,void*p,int){*(int*)p=arg;return found;}
size_t strlcpy(char*d,const char*s,size_t n){assert(strlen(s)<n);strcpy(d,s);return strlen(s);}
int xg_printf(const char*,...){return 0;}
int xg_request_watchdog_start(){gDedicatedActive=!wd_error;return wd_error;}
void IOLockLock(void*){assert(!locked);locked=1;}
void IOLockUnlock(void*){assert(locked);locked=0;}
int xg_run_stage(int n){assert(locked && n==calls+1 && n<=4);calls++;return n==fail?-5:1;}
'''+fn+r'''
int main(){
 arg=4;xg_boot_initialize();assert(!calls);
 found=1;arg=5;xg_boot_initialize();assert(!calls);
 arg=0;xg_boot_initialize();assert(!calls);
 arg=4;ready_after=9999;xg_boot_initialize();assert(!calls && probes==600 && sleeps==600 && !releases);
 probes=sleeps=0;ready_after=3;
 wd_error=12;xg_boot_initialize();assert(!calls && !locked);
 wd_error=0;fail=3;xg_boot_initialize();assert(calls==3 && gStage==2 && gResult[3]==-5 && !locked && !gDedicatedActive);
 calls=gStage=fail=0;xg_boot_initialize();assert(calls==4 && gStage==4 && gResult[4]==1 && !locked && !gDedicatedActive);
 assert(strstr(xg_env,"xe_probe_display=0") && strstr(xg_env,"xe_probe_skip_pc_start=1"));
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.cpp').write_text(code)
 subprocess.run(['c++','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('Actual boot helper: absent/zero/unsupported argument, deferred scheduling, GPU discovery timeout/delay, watchdog failure, stage failure and 1-4 success pass; no stage 5.')
