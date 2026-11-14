from pathlib import Path
import sys, subprocess, tempfile
s=Path(sys.argv[1]).read_text()
a=s.index('static void\nxg_dedicated_watchdog(')
b=s.index('static int\nxg_request_watchdog_start(',a)
fn=s[a:b]
code=r'''#include <assert.h>
#include <stdint.h>
#include <stdexcept>
typedef int wait_result_t;
static unsigned gDedicatedClaim=1,gDedicatedReady=0,gDedicatedActive=1;
static int gRunning=4,gStage=3,xg_progress=44006;
static unsigned xg_pci_irqs=1,xg_pci_handled=1,xg_spin_long=0;
static unsigned long long xg_spin_max_us=0;
static uint64_t now,stop_at; static int beats,panicked,terminated;
uint64_t mach_absolute_time(){return now;}
void absolutetime_to_nanoseconds(uint64_t v,uint64_t*p){*p=v;}
void IOSleep(int n){assert(n==100); now+=100000000; if(stop_at && now>=stop_at)gDedicatedActive=0;}
bool OSCompareAndSwap(unsigned a,unsigned b,volatile unsigned*p){if(*p!=a)return false;*p=b;return true;}
int xg_printf(const char*,...){beats++;return 0;}
void* current_thread(){return nullptr;}
void thread_terminate(void*){terminated++;throw std::runtime_error("exit");}
void panic(const char*,...){panicked++;throw std::runtime_error("panic");}
'''+fn+r'''
int main(){
 stop_at=12000000000ull;
 try{xg_dedicated_watchdog(nullptr,0);}catch(const std::runtime_error&){}
 assert(beats==2&&!panicked&&terminated==1&&!gDedicatedReady&&!gDedicatedClaim);
 now=stop_at=0;beats=panicked=terminated=0;gDedicatedActive=gDedicatedClaim=1;
 try{xg_dedicated_watchdog(nullptr,0);}catch(const std::runtime_error&){}
 assert(beats==12&&panicked==1&&!terminated&&now>60000000000ull);
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.cpp').write_text(code)
 subprocess.run(['c++','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('Actual watchdog: 5s heartbeat cadence, clean completion, and original >60s timeout pass.')
