"""Bounded artifact-only candidate build. Never tags, publishes or edits a remote.
Run in a fresh Python 3.11 target environment on a standard Windows/macOS runner.
"""
from pathlib import Path
import hashlib, importlib.metadata as md, json, os, platform, re, shutil
import subprocess, sys, traceback, zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WORK = ROOT / 'candidate-work'
EVIDENCE = ROOT / 'candidate-evidence'
UPLOAD = ROOT / 'candidate-upload'
ARCHIVE_CAP = 220 * 1024 * 1024
EVIDENCE_CAP = 10 * 1024 * 1024
UPSTREAM_SHA = '79a66ad50688c0b794dd501dc340a736992a6342f7f95e5811be60b5224a26a7'
BAD = re.compile(r'(^|[/\\.])av([/\\.]|$)|(?:avcodec|avformat|avutil|avfilter|avdevice|swresample|swscale|postproc|ffmpeg|virtualkeyboard)', re.I)

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, data):
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / name).write_text(json.dumps(data, indent=2), encoding='utf-8')

def run(args, label, env=None, cwd=ROOT):
    EVIDENCE.mkdir(exist_ok=True)
    with (EVIDENCE / (label + '.txt')).open('w', encoding='utf-8') as out:
        result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                                stdout=out, stderr=subprocess.STDOUT)
    print(label, 'exit', result.returncode, flush=True)
    if result.returncode:
        print((EVIDENCE / (label + '.txt')).read_text(encoding='utf-8', errors='replace')[-8000:])
        raise RuntimeError(label + ' failed: ' + str(result.returncode))


def stage_dependency():
    run([sys.executable, '-m', 'pip', 'install', 'wheel==0.45.1', 'packaging==25.0'], 'build-tools')
    downloads = WORK / 'downloads'; downloads.mkdir()
    run([sys.executable, '-m', 'pip', 'download', '--no-deps', '--only-binary=:all:',
         'faster-whisper==1.2.1', '-d', downloads], 'download-upstream')
    wheel = next(downloads.glob('*.whl'))
    assert digest(wheel) == UPSTREAM_SHA, 'Unreviewed upstream wheel'
    unpacked = WORK / 'unpacked'
    with zipfile.ZipFile(wheel) as z:
        z.extractall(unpacked)
    pkg = unpacked / 'faster_whisper'
    pristine = WORK / 'pristine'; shutil.copytree(pkg, pristine)
    sys.path.insert(0, str(ROOT / 'installer'))
    from guarded_source import guarded_audio_source
    from reconcile_metadata import reconcile, BOUNDARY
    meta = next(unpacked.glob('*.dist-info/METADATA'))
    old = meta.read_text(encoding='utf-8')
    new = ''.join(line for line in old.splitlines(keepends=True)
                  if line.strip() != 'Requires-Dist: av>=11')
    (pkg / 'audio.py').write_text(guarded_audio_source('1.2.1', (pkg/'audio.py').read_bytes(),
                                     (pkg/'transcribe.py').read_bytes()), encoding='utf-8', newline='')
    reconciliation = reconcile(old, new, pristine, pkg, BOUNDARY)
    # Original helper is review-only. This script performs the separately bounded build.
    save('metadata-reconciliation.json', reconciliation)
    (WORK/'pristine.METADATA').write_text(old,encoding='utf-8',newline='')
    env=os.environ.copy();env.update(PYTHONPATH=str(ROOT),KEYSTOW_PRISTINE_PACKAGE=str(pristine),KEYSTOW_PRISTINE_METADATA=str(WORK/'pristine.METADATA'))
    run([sys.executable,'-m','unittest','test_metadata_contract','test_source_staging'], 'pristine-contract-tests',env,ROOT/'tests')
    meta.write_text(new, encoding='utf-8', newline='')
    wheels = WORK / 'wheels'; wheels.mkdir()
    run([sys.executable, '-m', 'wheel', 'pack', unpacked, '-d', wheels], 'repack-adapted')
    adapted = next(wheels.glob('*.whl'))
    save('wheel-identity.json', {'upstream_sha256': digest(wheel),
         'adapted_sha256': digest(adapted), 'same_upstream_version_local_candidate': True,
         'not_published_distribution': True})
    run([sys.executable, '-m', 'pip', 'install', '--report', EVIDENCE/'resolve.json',
         adapted, 'sounddevice>=0.4.6', 'numpy>=1.24.0', 'pynput>=1.7.6',
         'pyperclip>=1.8.2', 'PySide6>=6.6.0', 'pyinstaller==6.16.0', 'pillow'], 'install-target')
    run([sys.executable, '-m', 'pip', 'check'], 'pip-check')
    assert md.version('faster-whisper') == '1.2.1'
    import importlib.util
    assert importlib.util.find_spec('av') is None
    save('installed-dependencies.json', sorted(
        [{'name': d.metadata['Name'], 'version': d.version,
          'requirements': d.requires or []} for d in md.distributions()], key=lambda d:d['name'].lower()))
    # Exact sources must survive target installation without newline translation.
    from keystow.numpy_guard import verify_dependency
    verify_dependency()


def model_and_fixture():
    from huggingface_hub import snapshot_download
    contract = json.loads((HERE/'model-contract.json').read_text())
    model = WORK/'models/faster-whisper-base'
    snapshot_download(contract['repo'], revision=contract['revision'], local_dir=model,
                      allow_patterns=list(contract['files']))
    for name, expected in contract['files'].items():
        assert digest(model/name) == expected, 'Model hash mismatch: '+name
    shutil.rmtree(model/'.cache', ignore_errors=True)
    fixture = json.loads((HERE/'fixture-source.json').read_text())
    assert digest(HERE/'sample.npy') == fixture['sample_sha256']
    save('model-contract.json', contract); save('fixture-source.json', fixture)
    return model


def tests_and_build(model):
    # Metadata/staging tests need pristine source. Run these against pristine fixture
    # separately rather than mislabel adapted-install failures as runtime failures.
    env = os.environ.copy(); env['QT_QPA_PLATFORM'] = 'offscreen'; env['PYNPUT_BACKEND'] = 'dummy'; env['PYTHONPATH'] = os.pathsep.join([str(ROOT),str(ROOT/'tests')])
    runtime = [p.stem for p in (ROOT/'tests').glob('test_*.py')
               if p.stem not in ('test_metadata_contract','test_source_staging')]
    run([sys.executable, '-m', 'unittest', *runtime], 'runtime-regressions', env,ROOT)
    run([sys.executable, '-m', 'unittest', 'test_virtual_keyboard_filter'], 'qt-filter-tests', env, HERE)
    run([sys.executable, HERE/'probe.py', '--model', model, '--sample', HERE/'sample.npy'],
        'installed-inference', env)
    # Windows RNNoise comes from the same native dependency route as the release.
    binary_args = []
    if sys.platform == 'win32':
        rn = WORK/'rnnoise'; rn.mkdir()
        run([sys.executable, '-m', 'pip', 'download', 'pyrnnoise==0.4.5', '--no-deps',
             '--only-binary=:all:', '-d', rn], 'rnnoise-download')
        w = next(rn.glob('*.whl'))
        with zipfile.ZipFile(w) as z:
            names = [n for n in z.namelist() if n.endswith('/rnnoise.dll')]
            assert len(names) == 1
            native = ROOT/'keystow/vendor/rnnoise.dll'; native.write_bytes(z.read(names[0]))
        save('rnnoise-source.json', {'wheel':w.name,'wheel_sha256':digest(w),
             'native_sha256':digest(native)})
        binary_args = ['--add-binary',str(native)+os.pathsep+'keystow/vendor']
    else:
        save('rnnoise-source.json', {'bundled':False,
             'boundary':'Existing macOS passthrough, not native denoise acceptance'})
    import importlib.util
    pkg = Path(next(iter(importlib.util.find_spec('faster_whisper').submodule_search_locations)))
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
       '--console', '--name', 'KeyStowCandidate', '--distpath', WORK/'dist',
       '--workpath', WORK/'pyinstaller', '--specpath', WORK,
       '--additional-hooks-dir', HERE, '--paths', HERE, '--runtime-hook', HERE/'runtime_hook.py',
       '--exclude-module','PySide6.QtVirtualKeyboard',
       '--exclude-module','PySide6.QtVirtualKeyboardQml',
       '--hidden-import','pynput.keyboard._dummy', '--hidden-import','pynput.mouse._dummy',
       '--collect-all','faster_whisper','--collect-all','ctranslate2',
       '--add-data',str(model)+os.pathsep+'models/faster-whisper-base',
       '--add-data',str(pkg/'audio.py')+os.pathsep+'faster_whisper',
       '--add-data',str(pkg/'transcribe.py')+os.pathsep+'faster_whisper',
       '--add-data',str(ROOT/'keystow/numpy_source_hashes.json')+os.pathsep+'keystow',
       '--add-data',str(HERE/'sample.npy')+os.pathsep+'candidate-fixture',
       *binary_args, ROOT/'run_keystow.py']
    run(args,'pyinstaller')
    dist = WORK/'dist/KeyStowCandidate'
    exe = dist/('KeyStowCandidate.exe' if sys.platform=='win32' else 'KeyStowCandidate')
    run([exe,'--candidate-probe'], 'frozen-inference', env)
    run([exe,'--candidate-code-substitution'], 'frozen-code-substitution', env)
    for matching_manifest in (False, True):
        copy = WORK/('tampered-'+str(matching_manifest)); shutil.copytree(dist,copy,symlinks=True)
        source = next(copy.rglob('faster_whisper/audio.py'))
        source.write_bytes(source.read_bytes()+b'\n# altered source\n')
        if matching_manifest:
            manifest = next(copy.rglob('numpy_source_hashes.json'))
            data = json.loads(manifest.read_text()); data['audio.py'] = digest(source)
            manifest.write_text(json.dumps(data))
        target = copy/exe.name
        result = subprocess.run([str(target),'--candidate-probe'], env=env,
                                capture_output=True,text=True)
        (EVIDENCE/('tampered-'+str(matching_manifest)+'.txt')).write_text(result.stdout+result.stderr)
        assert result.returncode != 0 and 'Unreviewed faster-whisper source' in result.stderr
        shutil.rmtree(copy)
    # Explicit dummy keyboard backend, isolated profile; this does not prove real input.
    home = WORK/'smoke-home'; home.mkdir()
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home/'AppData/Roaming'),
       LOCALAPPDATA=str(home/'AppData/Local'), KEYSTOW_MODEL='base',
       CANDIDATE_EVIDENCE_DIR=str(EVIDENCE), QT_QPA_PLATFORM='offscreen',
       HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    run([exe,'--candidate-ui-smoke'],'actual-entrypoint-ui',env)
    native_inventory(dist,exe)
    (dist/'NOT-FOR-RELEASE.txt').write_text(
       'Candidate engineering evidence only. Not installed-device, legal, sales or release clearance.\n'
       'Dummy keyboard/offscreen Ready smoke does not prove microphone, hotkey, paste, tray or login.\n')
    archive_base = WORK/'KeyStowCandidate-NOT-FOR-RELEASE'
    archive = Path(shutil.make_archive(str(archive_base), 'zip' if sys.platform=='win32' else 'gztar', dist.parent,dist.name))
    save('candidate-archive.json',{'filename':archive.name,'bytes':archive.stat().st_size,'sha256':digest(archive),
        'cap_bytes':ARCHIVE_CAP,'under_cap':archive.stat().st_size<=ARCHIVE_CAP})
    assert archive.stat().st_size<=ARCHIVE_CAP, 'Candidate archive exceeds safe upload cap'
    shutil.copy2(archive,EVIDENCE/archive.name)


def native_inventory(dist,exe):
    entries=[]; native=[]; linked_bad=[]
    for p in sorted(dist.rglob('*')):
        name=p.relative_to(dist).as_posix()
        assert not BAD.search(name), 'Forbidden filename: '+name
        if p.is_symlink():
            entries.append({'path':name,'kind':'symlink','target':os.readlink(p)});continue
        if not p.is_file():continue
        entries.append({'path':name,'kind':'file','bytes':p.stat().st_size,'sha256':digest(p)})
        with p.open('rb') as f:magic=f.read(4)
        deps=[]
        if magic[:2]==b'MZ':
            import pefile
            pe=pefile.PE(str(p),fast_load=True)
            pe.parse_data_directories(directories=[1,13])
            for attr in ('DIRECTORY_ENTRY_IMPORT','DIRECTORY_ENTRY_DELAY_IMPORT'):
                deps += [x.dll.decode('ascii',errors='replace') for x in getattr(pe,attr,[])]
            native.append({'path':name,'format':'PE','machine':hex(pe.FILE_HEADER.Machine),'dependencies':deps})
            pe.close()
        elif magic in (b'\xcf\xfa\xed\xfe',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):
            arch=subprocess.check_output(['lipo','-archs',str(p)],text=True).strip()
            deps=subprocess.check_output(['otool','-L',str(p)],text=True).splitlines()[1:]
            native.append({'path':name,'format':'Mach-O','architectures':arch,'dependencies':deps})
        linked_bad += [d for d in deps if BAD.search(d)]
    assert native, 'No native objects inspected'
    save('native-file-inventory.json', {'regular_files':sum(e['kind']=='file' for e in entries),
         'symlinks':sum(e['kind']=='symlink' for e in entries),'entries':entries})
    save('native-link-inventory.json',{'native_objects':len(native),'objects':native,'forbidden_links':linked_bad})
    assert not linked_bad, 'Forbidden native dependency'
    from PyInstaller.archive.readers import CArchiveReader
    reader=CArchiveReader(str(exe))
    pyzs=[k for k in reader.toc if k.startswith('PYZ')]
    assert len(pyzs)==1, 'Expected actual frozen PYZ'
    modules=sorted(reader.open_embedded_archive(pyzs[0]).toc)
    save('frozen-module-inventory.json',{'complete':True,'modules':modules})
    assert not [m for m in modules if BAD.search(m)], 'Forbidden frozen module'


def seal():
    # Fixed allowlist only. Never upload build roots, environment, HOME, git data,
    # downloaded wheels or credentials. Upload only enumerated evidence files.
    allowed={
      'identity.json','build-tools.txt','download-upstream.txt','metadata-reconciliation.json',
      'repack-adapted.txt','wheel-identity.json','resolve.json','install-target.txt','pip-check.txt',
      'installed-dependencies.json','model-contract.json','fixture-source.json',
      'pristine-contract-tests.txt','runtime-regressions.txt','qt-filter-tests.txt','installed-inference.txt','icons.txt',
      'rnnoise-download.txt','rnnoise-source.json','pyinstaller.txt','frozen-inference.txt',
      'frozen-code-substitution.txt','tampered-False.txt','tampered-True.txt',
      'actual-entrypoint-ui.txt','ready-ui.png','ui-smoke.json','candidate-archive.json',
      'native-file-inventory.json','native-link-inventory.json','frozen-module-inventory.json','failure.json'}
    if not EVIDENCE.exists():return
    files=[p for p in EVIDENCE.iterdir() if p.name in allowed and p.is_file()]
    assert sum(p.stat().st_size for p in files)<=EVIDENCE_CAP,'Evidence cap exceeded'
    UPLOAD.mkdir(exist_ok=False)
    for p in files:shutil.copy2(p,UPLOAD/p.name)
    archives=[p for p in EVIDENCE.iterdir() if p.name in ('KeyStowCandidate-NOT-FOR-RELEASE.zip','KeyStowCandidate-NOT-FOR-RELEASE.tar.gz')]
    assert len(archives)<=1
    if archives:
        archive=archives[0]
        assert archive.stat().st_size<=ARCHIVE_CAP
        shutil.copy2(archive,UPLOAD/archive.name)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('ready=true\n')
    print('Sealed bounded evidence',sum(p.stat().st_size for p in UPLOAD.iterdir()),'bytes')


def main():
    if '--seal' in sys.argv:return seal()
    assert sys.platform in ('win32','darwin'), 'Target-native execution only'
    assert sys.version_info[:2]==(3,11)
    assert not WORK.exists() and not EVIDENCE.exists(), 'Fresh build root required'
    WORK.mkdir();EVIDENCE.mkdir()
    sys.path.insert(0,str(ROOT))
    save('identity.json',{'sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'platform':platform.platform(),'architecture':platform.machine(),'python':sys.version,
        'runner_image':os.environ.get('ImageOS'),'runner_image_version':os.environ.get('ImageVersion'),
        'candidate_only':True,'hardware_acceptance':False,'release_clearance':False})
    try:
        stage_dependency();model=model_and_fixture();tests_and_build(model)
    except Exception:
        save('failure.json',{'error':traceback.format_exc(),'native_candidate_pass':False})
        raise

if __name__=='__main__':main()
