"""Stage a reviewed source adaptation; never install globally or build artifacts.

Input is an extracted pristine faster-whisper1.2.1 source package. Output is a
separate import root. The installer dependency metadata remains unresolved.
"""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
# Candidate adaptation implementation copied into installer/guarded_source.py.
from guarded_source import guarded_audio_source

def stage(source,out,version):
    if out.exists():raise ValueError('Output must not already exist')
    a=(source/'audio.py').read_bytes();t=(source/'transcribe.py').read_bytes()
    adapted=guarded_audio_source(version,a,t)
    shutil.copytree(source,out/'faster_whisper')
    (out/'faster_whisper'/'audio.py').write_text(adapted,encoding='utf-8',newline='')
    return {'version':version,'source_hashes':{n:hashlib.sha256(b).hexdigest() for n,b in [('audio.py',a),('transcribe.py',t)]},'adapted_audio_sha256':hashlib.sha256(adapted.encode()).hexdigest(),'dependency_metadata_modified':False,'global_install_modified':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--version',required=True);a=p.parse_args();print(json.dumps(stage(a.source,a.out,a.version),indent=2))
