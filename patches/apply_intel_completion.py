from pathlib import Path
import subprocess
import sys

source = Path(sys.argv[1]).resolve()
patch = Path(__file__).with_name('intel-completion.patch').resolve()
subprocess.run(['patch', '--dry-run', '--batch', '-p1', '-d', str(source), '-i', str(patch)], check=True)
subprocess.run(['patch', '--batch', '-p1', '-d', str(source), '-i', str(patch)], check=True)
