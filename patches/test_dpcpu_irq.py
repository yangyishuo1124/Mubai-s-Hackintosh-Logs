"""Execute the actual DPCPU function with deterministic allocation/publication races."""
from pathlib import Path
import subprocess
import sys
import tempfile

s = Path(sys.argv[1]).read_text()
a = s.index('static void\nxg_spin_lock(')
b = s.index('int\nxg_curcpu(', a)
locks = s[a:b]
a = s.index('void *\nxg_dpcpu_block(')
b = s.index('/* critical sections:', a)
function = s[a:b]
prefix = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
typedef unsigned int u_int;
#define XG_DPCPU_MAX 4
#define XG_MAXCPU 2
static struct { const void *tmpl; void *blk; } xg_dpcpu[XG_DPCPU_MAX];
static volatile u_int xg_dpcpu_lock;
static int irq_enabled = 1, allocations, frees, race;
static int template_value = 17, other_template;
static int winner[2] = {41, 42};
static int ml_set_interrupts_enabled(int enabled) {
 int previous = irq_enabled; irq_enabled = enabled; return previous;
}
static int atomic_cmpset_acq_int(volatile u_int *p, u_int old, u_int value) {
 /* An IRQ/preemption opportunity at acquisition must be masked. */
 assert(irq_enabled == 0);
 if (*p != old) return 0;
 *p = value; return 1;
}
static void atomic_store_rel_int(volatile u_int *p, u_int value) {
 assert(irq_enabled == 0); *p = value;
}
static void cpu_spinwait(void) { abort(); }
static void panic(const char *s) { abort(); }
static void *IOMallocZero(size_t size) {
 assert(xg_dpcpu_lock == 0 && irq_enabled == 1);
 allocations++;
 if (race) { xg_dpcpu[0].tmpl = &template_value; xg_dpcpu[0].blk = winner; }
 return calloc(1, size);
}
static void IOFree(void *p, size_t size) {
 assert(xg_dpcpu_lock == 0 && irq_enabled == 1);
 frees++; free(p);
}
'''
main = r'''
int main(void) {
 int *p;
 /* A new table entry receives a copy for every CPU. */
 p = xg_dpcpu_block(&template_value, sizeof(template_value));
 assert(p[0] == 17 && p[1] == 17 && allocations == 1 && irq_enabled == 1);
 assert(xg_dpcpu_lock == 0);
 /* Existing entries never allocate; prior interrupt state is restored. */
 assert(xg_dpcpu_block(&template_value, sizeof(template_value)) == p);
 assert(allocations == 1 && irq_enabled == 1);
 irq_enabled = 0;
 assert(xg_dpcpu_block(&template_value, sizeof(template_value)) == p);
 assert(irq_enabled == 0 && xg_dpcpu_lock == 0);
 irq_enabled = 1;
 free(p);
 memset(xg_dpcpu, 0, sizeof(xg_dpcpu));
 /* Another CPU publishes while allocation runs with interrupts enabled. */
 race = 1;
 assert(xg_dpcpu_block(&template_value, sizeof(template_value)) == winner);
 assert(frees == 1 && irq_enabled == 1 && xg_dpcpu_lock == 0);
 /* A different template must not alias the winner. */
 race = 0; other_template = 29;
 p = xg_dpcpu_block(&other_template, sizeof(other_template));
 assert(p != winner && p[0] == 29 && p[1] == 29);
 free(p);
 puts("DPCPU: new/hit/IRQ-state/publication-race/distinct-template passed");
}
'''
with tempfile.TemporaryDirectory() as directory:
    p = Path(directory)
    (p/'test.c').write_text(prefix + locks + function + main)
    subprocess.run(['cc', '-Werror', '-o', str(p/'test'), str(p/'test.c')], check=True)
    result = subprocess.run([str(p/'test')], capture_output=True, text=True)
    if '--expect-regression' in sys.argv:
        assert result.returncode != 0, 'Baseline unexpectedly passed IRQ safety checks'
        assert 'irq_enabled == 0' in result.stderr, result.stderr
        print('Baseline rejected: actual DPCPU lock acquisition leaves IRQs enabled')
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        print(result.stdout.strip())
