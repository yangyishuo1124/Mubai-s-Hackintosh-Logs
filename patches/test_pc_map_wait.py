"""Exercise the actual patched PC wait with oversleep and state transitions."""
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()
start = source.index('static int wait_for_pc_state(')
end = source.index('\nstatic int pc_action_reset(', start)
function = source[start:end]
assert 'xe_map_memset(xe, &pc->bo->vmap, 0, 0, size);' in source
assert 'memset(pc->bo->vmap.vaddr' not in source
code = r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#define ETIMEDOUT 110
typedef int64_t ktime_t;
enum slpc_global_state { STOPPED, RUNNING };
struct xe_guc_pc { int unused; };
static int64_t now_us, state_at_us, sleep_us;
static unsigned sleeps;
static ktime_t ktime_get(void) { return now_us; }
static int64_t ktime_ms_delta(ktime_t a, ktime_t b) { return (a - b) / 1000; }
#define pc_to_xe(pc) (pc)
#define xe_device_assert_mem_access(xe) ((void)(xe))
#define slpc_shared_data_read(pc, field) (now_us >= state_at_us ? RUNNING : STOPPED)
static void usleep_range(int lo, int hi) {
    assert(lo > 0 && lo <= hi);
    now_us += sleep_us;
    assert(++sleeps < 100000);
}
''' + function + r'''
static void setup(int64_t start, int64_t ready, int64_t oversleep) {
    now_us = start; state_at_us = ready; sleep_us = oversleep; sleeps = 0;
}
int main(void) {
    struct xe_guc_pc pc = {0};
    setup(0, 0, 20);
    assert(wait_for_pc_state(&pc, RUNNING, 5) == 0 && sleeps == 0);
    setup(0, 300, 20);
    assert(wait_for_pc_state(&pc, RUNNING, 5) == 0 && now_us == 300);
    setup(0, INT64_MAX, 20);
    assert(wait_for_pc_state(&pc, RUNNING, 5) == -ETIMEDOUT && now_us == 5000);
    setup(0, INT64_MAX, 15000);
    assert(wait_for_pc_state(&pc, RUNNING, 5) == -ETIMEDOUT && sleeps == 1);
    setup(0, INT64_MAX, 37000);
    assert(wait_for_pc_state(&pc, RUNNING, 1000) == -ETIMEDOUT);
    assert(now_us >= 1000000 && now_us < 1037000);
    setup(0, INT64_MAX, 20);
    assert(wait_for_pc_state(&pc, RUNNING, 0) == -ETIMEDOUT && sleeps == 0);
    int64_t base = INT64_C(1000000000000);
    setup(base, base + 300, 20);
    assert(wait_for_pc_state(&pc, RUNNING, 5) == 0 && now_us == base + 300);
}
'''
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'test.c').write_text(code)
    subprocess.run(['cc', '-std=c11', '-Werror', '-o', str(root / 'test'), str(root / 'test.c')], check=True)
    subprocess.run([str(root / 'test')], check=True)
print('Actual PC wait passes immediate/delayed readiness, timeout, oversleep, extended timeout, zero timeout and large clock tests; mapping API checked.')
