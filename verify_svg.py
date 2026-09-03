#!/usr/bin/env python3
"""全量 SVG 级验证: 原版/统一版各渲染 SVG → 剥除嵌入 payload → 剩余图形部分逐字节对比"""
import json, glob, subprocess, os, re, sys
from concurrent.futures import ProcessPoolExecutor, as_completed

BASE = '/mnt/ssd/lian/白马入芦花janpu'
RAW_DIR = f'{BASE}/jp-svt/B_tools/jianpu_dataset/data/raw_jianpu_669'
UNI_DIR = f'{BASE}/0830/统一所有/统一简谱'
J2S = f'{BASE}/jp-svt/B_tools/jianpu_dataset/scripts/website_renderer/json2svg.py'
B64 = re.compile(r'[A-Za-z0-9+/=]{1000,}')

def strip_payload(svg):
    # 1) 剥嵌入源数据 payload: 按 data-encoding="base64" 标签边界(长度不限, 防短段逃逸)
    svg = re.sub(r'(data-encoding="base64">)[^<]*(</)', r'\1[PAYLOAD]\2', svg)
    svg = B64.sub('[PAYLOAD]', svg)   # 兜底: 其他位置的长 base64
    # 2) 剥溯源列坐标: = → xx 改写使文本列平移(+1), 几何坐标(x/y)不受影响
    svg = re.sub(r'firstColumn="\d+"', 'firstColumn="?"', svg)
    svg = re.sub(r'lastColumn="\d+"', 'lastColumn="?"', svg)
    return svg

def process(pair):
    sid, raw_path, uni_path = pair
    pf_raw = f'/tmp/svgv_r_{sid}.svg'; pf_uni = f'/tmp/svgv_u_{sid}.svg'
    rec = {'sid': sid}
    try:
        ok1 = subprocess.run(['python3', J2S, '--input', raw_path, '--output', pf_raw],
                             capture_output=True, timeout=120).returncode == 0 and os.path.exists(pf_raw)
        ok2 = subprocess.run(['python3', J2S, '--input', uni_path, '--output', pf_uni],
                             capture_output=True, timeout=120).returncode == 0 and os.path.exists(pf_uni)
        if not ok1: rec['verify'] = 'RENDER_RAW_FAIL'; return rec
        if not ok2: rec['verify'] = 'RENDER_UNI_FAIL'; return rec
        sa = strip_payload(open(pf_raw).read())
        sb = strip_payload(open(pf_uni).read())
        rec['verify'] = 'PASS' if sa == sb else 'SVG_DIFF'
        rec['bytes'] = len(sa)
    except Exception as ex:
        rec['verify'] = 'EXCEPTION'; rec['err'] = str(ex)[:150]
    finally:
        for f in (pf_raw, pf_uni):
            if os.path.exists(f): os.remove(f)
    return rec

def main():
    pairs = []
    for uni in sorted(glob.glob(f'{UNI_DIR}/*_原始简谱.json')):
        sid = uni.split('/')[-1].replace('_原始简谱.json', '')
        sd = json.load(open(uni))['songdata']
        if sd.get('notation_skip_unproven'):
            continue   # 原文照存, SVG 必然一致
        raws = glob.glob(f'{RAW_DIR}/{sid}/*原始简谱.json')
        if raws: pairs.append((sid, raws[0], uni))
    print(f'待验证 {len(pairs)} 首', flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(process, p) for p in pairs]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result(); results.append(r)
            if i % 50 == 0: print(f'[{i}/{len(pairs)}]', flush=True)
            if r['verify'] != 'PASS':
                print(' ', r['verify'], r['sid'], (r.get('err') or '')[:100], flush=True)
    from collections import Counter
    out = f'{BASE}/0830/统一所有/logs/svg_verify_report.json'
    json.dump(results, open(out, 'w'), ensure_ascii=False, indent=1)
    print('== SVG 汇总 ==', dict(Counter(r['verify'] for r in results)), flush=True)

if __name__ == '__main__':
    main()
