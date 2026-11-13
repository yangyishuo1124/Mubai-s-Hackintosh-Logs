from pathlib import Path
import subprocess,sys,tempfile
p=Path(sys.argv[1]);s=p.read_text()
fnv=s[s.index('static uint64_t\nxg_fnv'):s.index('\nextern "C" int\nxg_xe_bootfb_checksum')]
layout=s[s.index('static int\nxg_xe_bootfb_layout'):s.index('\n#include "xg_ptl_gop_metadata.h"')]
header=(p.parent/'xg_ptl_gop_metadata.h').read_text()
code=r'''
#include <cassert>
#include <cstdint>
#include <cerrno>
#include <vector>
''' + fnv + layout + header + r'''
int main() {
 std::vector<uint32_t> mm(16*1024*1024/4);
 auto r=mm.data();
 r[0x70180/4]=0x84000008; r[0x70188/4]=160;
 r[0x70190/4]=104794623; r[0x7019c/4]=0xff000000;
 r[0x70008/4]=0x80000000; r[0x1080c0/4]=0x7c800000;
 auto gtt=(uint64_t*)(r+(8ull<<20)/4); unsigned first=0xff000000u>>12;
 for(unsigned i=0;i<4000;i++) gtt[first+i]=0x800003ull+i*4096ull;
 xg_ptl_gop_snapshot a={},b={};
 assert(xg_ptl_gop_read(r,mm.size()*4,&a)==0);
 assert(a.bytes==16384000 && a.dsm==0x7c800000);
 r[0x70040/4]=6; assert(xg_ptl_gop_read(r,mm.size()*4,&b)==0);
 assert(xg_ptl_gop_compare(&a,&b)==1);
 b.frame=a.frame; assert(xg_ptl_gop_compare(&a,&b)==-ETIMEDOUT);
 a.frame=0xfffffffe; b.frame=2; assert(xg_ptl_gop_compare(&a,&b)==1);
 b.offset++; assert(xg_ptl_gop_compare(&a,&b)==-EPROTO); b.offset--;
 gtt[first+3999]^=1ull<<63;
 assert(xg_ptl_gop_read(r,mm.size()*4,&b)==0);
 assert(xg_ptl_gop_compare(&a,&b)==-EPROTO);
 gtt[first+3999]&=~1ull;
 assert(xg_ptl_gop_read(r,mm.size()*4,&b)==-EINVAL);
 assert(xg_ptl_gop_read(r,8ull<<20,&b)==-EIO);
 r[0x7019c/4]=0xfffff000;
 assert(xg_ptl_gop_read(r,mm.size()*4,&b)==-EOVERFLOW);
 r[0x70008/4]=0; assert(xg_ptl_gop_read(r,mm.size()*4,&b)==-ENXIO);
}
'''
with tempfile.TemporaryDirectory() as d:
 f=Path(d)/'snapshot.cpp';f.write_text(code);exe=Path(d)/'snapshot'
 subprocess.run(['c++','-std=c++17','-Wall','-Werror','-fsanitize=undefined',str(f),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('GOP snapshot tests passed: captured layout, frame/wrap/stall, geometry, last-PTE high bit, missing PTE, bounds and pipe-off.')
