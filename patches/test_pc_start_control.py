from pathlib import Path
import subprocess, sys, tempfile
s = Path(sys.argv[1]).read_text()
a = s.index('static int xegfx_pc_start_for_probe(')
b = s.index('static struct xe_gt *', a)
code = r'''
#include <assert.h>
struct xe_guc_pc { int unused; };
static int present, value, calls, result, skipped;
int getenv_int(const char *name, int *v) { *v = value; return present; }
void xg_init_checkpoint(int id, const char *label) { assert(id == 48000); skipped++; }
int xe_guc_pc_start(struct xe_guc_pc *pc) { calls++; return result; }
''' + s[a:b] + r'''
int main(void) {
 struct xe_guc_pc pc = {0};
 result = -110;
 assert(xegfx_pc_start_for_probe(&pc) == -110 && calls == 1 && skipped == 0);
 present = 1; value = 0;
 assert(xegfx_pc_start_for_probe(&pc) == -110 && calls == 2 && skipped == 0);
 value = 1;
 assert(xegfx_pc_start_for_probe(&pc) == 0 && calls == 2 && skipped == 1);
 value = 2;
 assert(xegfx_pc_start_for_probe(&pc) == -110 && calls == 3 && skipped == 1);
 result = 0; value = 0;
 assert(xegfx_pc_start_for_probe(&pc) == 0 && calls == 4 && skipped == 1);
}
'''
assert s.count('ret = xegfx_pc_start_for_probe(&uc->guc.pc);') == 1
with tempfile.TemporaryDirectory() as directory:
 p = Path(directory)
 (p/'test.c').write_text(code)
 subprocess.run(['cc', '-Werror', '-o', str(p/'test'), str(p/'test.c')], check=True)
 subprocess.run([str(p/'test')], check=True)
print('Actual PC-start selector: default/zero/invalid value preserves call and errors; only explicit 1 bypasses and marks diagnostic.')
