#!/usr/bin/env python3
"""Check actual burned-in glyph pixels at every caption midpoint.

This is a presence/placement test, not OCR or a word-level alignment audit.
Fresh projects have no hard-coded pilot exclusion.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image
import single_shot_render as render


def main():
    ap=argparse.ArgumentParser();ap.add_argument('project');ap.add_argument('video');ap.add_argument('--from-frame',type=int,default=0);ap.add_argument('--until-frame',type=int);a=ap.parse_args()
    data=render.configure(a.project);ROOT=render.ROOT;video=(ROOT/a.video).resolve();start=a.from_frame;end=a.until_frame or data['meta']['durationFrames']
    info=render.probe(video);vs=next(s for s in info['streams'] if s['codec_type']=='video')
    if (int(vs['width']),int(vs['height']),int(vs['nb_frames']))!=(render.W,render.H,end-start):raise ValueError('Video geometry or frame count is not the requested interval')
    checks=[]
    for c in render.caption_groups(data['captions']):
        lo=max(start,c['startFrame']);hi=min(end,c['endFrame'])
        if hi-lo<3:continue
        checks.append({'cueIds':c['originalCueIds'],'text':c['text'],'globalFrame':(lo+hi)//2,'localFrame':(lo+hi)//2-start})
    key=hashlib.sha256(f'{video}:{video.stat().st_mtime_ns}:{start}:{end}'.encode()).hexdigest()[:12]
    frames=ROOT/'.build/qc'/('caption-midpoints-'+key);frames.mkdir(parents=True,exist_ok=True)
    unique=sorted(set(c['localFrame'] for c in checks))
    if not unique:raise ValueError('No captions in interval')
    # A linear sum of 100+ terms exceeds libavutil expression recursion depth.
    # A balanced expression handles the full film without reducing test coverage.
    def balanced(parts):
        if len(parts)==1:return parts[0]
        mid=len(parts)//2
        return '('+balanced(parts[:mid])+'+'+balanced(parts[mid:])+')'
    selector=balanced([f'eq(n,{n})' for n in unique])
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(video),'-an','-vf',f"select='{selector}'",'-fps_mode','vfr','-frames:v',str(len(unique)),str(frames/'frame-%04d.png')],check=True)
    images={frame:frames/f'frame-{i+1:04d}.png' for i,frame in enumerate(unique)}
    for c in checks:
        expected=np.asarray(Image.open(render.caption_png(c['text'])).convert('RGBA'))
        actual=np.asarray(Image.open(images[c['localFrame']]).convert('RGB'))[render.CAP_Y:render.H]
        glyph=(expected[:,:,3]>250)&(expected[:,:,:3].min(axis=2)>220)
        background=(expected[:,:,3]>200)&(expected[:,:,3]<240)&(expected[:,:,:3].max(axis=2)<40)
        bright=actual.mean(axis=2)
        c['brightGlyphMatch']=round(float((bright[glyph]>185).mean()),4)
        c['darkBackgroundMatch']=round(float((bright[background]<100).mean()),4)
        c['passed']=c['brightGlyphMatch']>=.90 and c['darkBackgroundMatch']>=.90
        c['sample']=str(images[c['localFrame']].relative_to(ROOT))
    report={'video':str(video),'method':'Known raster glyph-mask and dark-box pixel match at each caption midpoint; not OCR or word-level timing verification.',
      'intervalFrames':[start,end],'captionGroupsChecked':len(checks),'passed':all(c['passed'] for c in checks),
      'excludedFrames':0,'failedCueIds':[c['cueIds'] for c in checks if not c['passed']],'checks':checks}
    target=video.with_name(video.stem+'-caption-qc.json');target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False))
    if not report['passed']:raise SystemExit(2)


if __name__=='__main__':main()
