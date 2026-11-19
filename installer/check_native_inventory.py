"""Fail closed on a supplied, complete target-platform inventory. Does not build.
Input: {platform: windows|macos, stage: analysis|frozen, complete: true,
        files: [actual collected file or module names]}
An analysis pass is never a frozen-archive pass.
"""
import argparse,json,re
from pathlib import Path
BAD=re.compile(r'(^|[/\\.])av([/\\.]|$)|(^|[/\\])(?:lib)?(?:avcodec|avformat|avutil|avfilter|avdevice|swresample|swscale|postproc|ffmpeg)[^/\\]*',re.I)
def check(data):
    if data.get('platform') not in ('windows','macos') or data.get('stage') not in ('analysis','frozen') or data.get('complete') is not True:
        raise ValueError('Complete, explicitly scoped target inventory required')
    files=data.get('files')
    if not isinstance(files,list) or not files or any(not isinstance(x,str) or not x for x in files):
        raise ValueError('Nonempty actual inventory required')
    bad=[x for x in files if BAD.search(x)]
    if bad:raise ValueError('Forbidden PyAV/FFmpeg inventory entries: '+repr(bad))
    return {'platform':data['platform'],'stage':data['stage'],'files_checked':len(files),'forbidden_entries':[]}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inventory',type=Path);a=p.parse_args();print(json.dumps(check(json.loads(a.inventory.read_text())),indent=2))
