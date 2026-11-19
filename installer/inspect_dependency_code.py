"""Local loader-code integrity feasibility only, not a trust root or signature.

A manifest must be generated and reviewed for each target Python build. Code
hashes are runtime-version dependent. A self-contained manifest cannot protect
against replacement of the executable and manifest together.
"""
import hashlib,importlib.machinery,importlib.util,json,marshal,sys

def inspect_code():
    if any(k=='faster_whisper' or k.startswith('faster_whisper.') for k in sys.modules):
        raise RuntimeError('Dependency loaded before inspection')
    package=importlib.util.find_spec('faster_whisper')
    if package is None or not package.submodule_search_locations:raise RuntimeError('Missing package')
    entries={}
    for leaf in ('audio','transcribe'):
        name='faster_whisper.'+leaf
        spec=importlib.machinery.PathFinder.find_spec(name,list(package.submodule_search_locations))
        if spec is None or not hasattr(spec.loader,'get_code'):raise RuntimeError('Unsupported dependency loader')
        code=spec.loader.get_code(name)
        if code is None:raise RuntimeError('Missing loader code')
        entries[name]=hashlib.sha256(marshal.dumps(code)).hexdigest()
    return {'python_cache_tag':sys.implementation.cache_tag,'modules':entries,'target_archive_verified':False}

def verify_code(observed,expected):
    if expected.get('python_cache_tag')!=observed.get('python_cache_tag'):raise RuntimeError('Python ABI mismatch')
    if set(expected.get('modules',{}))!={'faster_whisper.audio','faster_whisper.transcribe'}:raise RuntimeError('Incomplete integrity manifest')
    if expected['modules']!=observed.get('modules'):raise RuntimeError('Dependency code mismatch')
    return True
if __name__=='__main__':print(json.dumps(inspect_code(),indent=2))
