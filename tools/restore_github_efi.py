import subprocess, pathlib, tarfile, io, hashlib, json, datetime, shutil, plistlib

repo = pathlib.Path(r'C:\Users\yangy\.gemini\antigravity\scratch\ASUS-Vivobook-S16-S5650AA-Hackintosh')
workspace = pathlib.Path(__file__).resolve().parent
commit = subprocess.check_output(['git','rev-parse','048d6e2'],cwd=repo,text=True).strip()
root = workspace / 'backups' / ('github-efi-restore-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
stage = root / 'baseline'
stage.mkdir(parents=True)
archive = subprocess.check_output(['git','archive',commit,'EFI'],cwd=repo)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    for item in tar.getmembers():
        dest = (stage / item.name).resolve()
        if not dest.is_relative_to(stage.resolve()) or item.issym() or item.islnk():
            raise RuntimeError('Unsafe archive entry')
    tar.extractall(stage,filter='data')
validator = pathlib.Path(r'C:\Users\yangy\.gemini\antigravity\scratch\ASUS-S5650AA-Hackintosh\downloads\oc_extracted\Utilities\ocvalidate\ocvalidate.exe')
subprocess.run([str(validator),str(stage/'EFI/OC/config.plist')],check=True)
config = plistlib.loads((stage/'EFI/OC/config.plist').read_bytes())
for entry in config['Kernel']['Add']:
    if entry['Enabled']:
        bundle = stage/'EFI/OC/Kexts'/entry['BundlePath']
        for key in ('PlistPath','ExecutablePath'):
            if entry.get(key) and not (bundle/entry[key]).is_file():
                raise RuntimeError(f'Missing enabled kext {bundle}/{entry[key]}')
def manifest(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}
efi = pathlib.Path('Z:/EFI')
names = ('OC','Diagnostics','Boot')
original = root/'original/EFI'
original.mkdir(parents=True)
before = {}
for name in names:
    source = efi/name
    before[name] = manifest(source)
    shutil.copytree(source,original/name)
    if manifest(original/name) != before[name]:
        raise RuntimeError('Backup verification failed: '+name)
protected = manifest(efi/'Microsoft')
(root/'before-sha256.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
print('VERIFIED BACKUP:',root,flush=True)
for name in names:
    target = efi/name
    if target.resolve().parent != efi.resolve() or name not in names:
        raise RuntimeError('Invalid EFI target')
    shutil.rmtree(target)
    source = stage/'EFI'/('BOOT' if name=='Boot' else name)
    shutil.copytree(source,target)
    if manifest(target) != manifest(source):
        raise RuntimeError('Restore readback failed: '+name)
if manifest(efi/'Microsoft') != protected:
    raise RuntimeError('Microsoft EFI changed')
subprocess.run([str(validator),str(efi/'OC/config.plist')],check=True)
report = {'source_commit':commit,'restored_scopes':list(names),'all_file_hashes_verified':True,
          'microsoft_unchanged':True,'files':{n:len(manifest(efi/n)) for n in names},
          'boot_args':config['NVRAM']['Add']['7C436110-AB2A-4BBB-A880-FE41995C9F82']['boot-args']}
(root/'restore-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
