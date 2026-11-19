"""Real fixed-sample inference and loader substitution checks, no desktop I/O."""
from pathlib import Path
import argparse, importlib.util, importlib.machinery, json, sys, types

if not getattr(sys,'frozen',False):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


def check(model,sample,substitute=False):
    import numpy as np
    from keystow.numpy_guard import verify_dependency,validate_waveform
    if substitute:
        assert getattr(sys,'frozen',False), 'Frozen loader substitution only'
        original=importlib.machinery.PathFinder.find_spec
        def changed(name,*args,**kwargs):
            spec=original(name,*args,**kwargs)
            if name=='faster_whisper.audio':
                actual=spec.loader.get_code(name)
                return types.SimpleNamespace(loader=types.SimpleNamespace(
                    get_code=lambda _:compile('substituted_execution=True',actual.co_filename,'exec')))
            return spec
        importlib.machinery.PathFinder.find_spec=changed
        try:
            verify_dependency()
        except RuntimeError as exc:
            assert 'Unreviewed frozen dependency code' in str(exc)
            print(json.dumps({'substituted_loader_code_rejected':True,
                 'experiment':'Executed loader-code substitution; adjacent source unchanged',
                 'whole_executable_authenticity':False}))
            return
        finally:
            importlib.machinery.PathFinder.find_spec=original
        raise AssertionError('Substituted code accepted')
    root=verify_dependency()
    assert importlib.util.find_spec('av') is None
    from faster_whisper import WhisperModel
    audio=np.load(sample,allow_pickle=False);validate_waveform(audio)
    m=WhisperModel(str(model),device='cpu',compute_type='int8',local_files_only=True)
    segments,_=m.transcribe(audio,beam_size=1)
    text=' '.join(x.text for x in segments).strip()
    assert 'ask not what your country can do for you' in text.lower(), text
    assert not any(n=='av' or n.startswith('av.') for n in sys.modules)
    print(json.dumps({'frozen':bool(getattr(sys,'frozen',False)),
       'integrity_guard':'PASS','dependency_root':str(root),'transcript':text,
       'PyAV_present':False,'model_source':str(model),'platform':sys.platform,
       'desktop_IO_exercised':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True)
    p.add_argument('--sample',type=Path,required=True);a=p.parse_args();check(a.model,a.sample)
