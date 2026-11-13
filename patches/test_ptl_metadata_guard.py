#!/usr/bin/env python3
"""Execute the actual B0A0 containment branch with poisoned downstream access."""
from pathlib import Path
import subprocess, tempfile, sys
s=Path(sys.argv[1]).read_text()
start=s.index(' // B0A0: direct CPU reads')
end=s.index(' /* FreeBSD x86 VM_MEMATTR_WRITE_COMBINING',start)
branch=s[start:end]
assert end < s.index('gXeBootPixels = xg_vm_vmap_pa',end)
assert 'ptl-metadata-only-v1' in s
source=r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cerrno>
#include <map>
#include <string>
constexpr int kIOPCIConfigVendorID=0, kIOPCIConfigDeviceID=2;
constexpr bool kOSBooleanTrue=true;
struct GPU { unsigned id; unsigned configRead16(int r) {return r==0?0x8086:id;} };
struct Resident {std::map<std::string,uint64_t> p;
 void setProperty(const char*k,uint64_t v,int=0) {p[k]=v;}} resident;
auto gResident=&resident;
int gXeBootFound=-22, freed=0, downstream=0;
unsigned gXeBootSurf=0;
void IOFree(void*,size_t) {freed++;}
void IOLog(const char*,...) {}
uint64_t xg_fnv(uint64_t h,uint64_t v,unsigned bytes) {
 for(unsigned i=0;i<bytes;i++){h=(h^(v&255))*1099511628211ull;v>>=8;}return h;}
int probe(unsigned id, bool dm) {
 GPU device{id}; auto gpu=&device;
 unsigned n=2; unsigned long long *pa=nullptr;
 uint64_t table[2]={dm?0x800003ull:0x800001ull,dm?0x801003ull:0x801001ull};
 volatile uint64_t *gsm=table;
 uint64_t lo=0x7c800000,hi=lo+8192;
''' + branch + r'''
 downstream++; return 123;
}
int main(){
 assert(probe(0xb0a0,true)==-EOPNOTSUPP);
 assert(freed==1 && downstream==0 && gXeBootFound==-EOPNOTSUPP);
 assert(resident.p["XeGfxGOPCPUAccessBlocked"]==1);
 assert(resident.p["XeGfxGOPPageCount"]==2 && resident.p["XeGfxGOPDMPages"]==2);
 assert(resident.p["XeGfxGOPCandidateSpan"]==8192);
 assert(probe(0xb0a0,false)==-EOPNOTSUPP);
 assert(freed==2 && downstream==0 && resident.p["XeGfxGOPDMPages"]==0);
 assert(probe(0xb080,true)==123 && freed==2 && downstream==1);
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'guard.cpp'; p.write_text(source)
 exe=Path(d)/'guard'
 subprocess.run(['c++','-std=c++17','-Wall','-Werror','-fsanitize=undefined',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('B0A0 DM/non-DM containment and other-device control passed; no hardware claims.')
