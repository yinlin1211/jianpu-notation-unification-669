#!/usr/bin/env python3
"""对 654 首统一版渲染 → 提取歌词字槽层 → 写回统一简谱 json (songdata.lyric_layer)"""
import json, glob, subprocess, os, sys, re
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/lib')
from lyric_slots import build_song_lyric_layer

BASE = '/mnt/ssd/lian/白马入芦花janpu'
OUT_DIR = f'{BASE}/0830/统一所有/统一简谱'
EXPORTER = f'{BASE}/jp-svt/B_tools/jianpu_dataset/scripts/playback_segments/export_playback_full.js'

def process(uni_path):
    sid = uni_path.split('/')[-1].replace('_原始简谱.json', '')
    pf = f'/tmp/ll_pf_{sid}.json'
    rec = {'sid': sid}
    try:
        d = json.load(open(uni_path))
        if d['songdata'].get('notation_skip_unproven'):
            rec['verify'] = 'SKIP'; return rec
        r = subprocess.run(['node', EXPORTER, uni_path, pf], capture_output=True, text=True, timeout=120)
        if not os.path.exists(pf):
            rec['verify'] = 'RENDER_FAIL'; rec['err'] = (r.stdout + r.stderr)[:150]; return rec
        layer = build_song_lyric_layer(uni_path, pf)
        d['songdata']['lyric_layer'] = layer
        json.dump(d, open(uni_path, 'w'), ensure_ascii=False, indent=1)
        cons = layer.get('conservation', {})
        ok = (cons.get('missing') == [] if cons else None)
        rec.update(verify='PASS' if ok in (True, None) else 'CONSERVATION',
                   err=None if ok in (True, None) else f"字槽字不在原文: {cons['missing'][:8]}",
                   n_syllable=layer['stats']['n_syllable'], n_notes=layer['stats']['n_notes'])
    except Exception as ex:
        rec.update(verify='EXCEPTION', err=str(ex)[:150])
    finally:
        if os.path.exists(pf): os.remove(pf)
    return rec

def main():
    files = sorted(glob.glob(f'{OUT_DIR}/*_原始简谱.json'))
    print(f'共 {len(files)} 首', flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(process, p) for p in files]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result(); results.append(r)
            if i % 100 == 0: print(f'[{i}/{len(files)}]', flush=True)
            if r['verify'] not in ('PASS', 'SKIP'):
                print(' ', r['verify'], r['sid'], (r.get('err') or '')[:100], flush=True)
    json.dump(results, open(f'{BASE}/0830/统一所有/logs/lyric_layer_report.json', 'w'), ensure_ascii=False, indent=1)
    from collections import Counter
    print('== 汇总 ==', dict(Counter(r['verify'] for r in results)))

if __name__ == '__main__':
    main()
