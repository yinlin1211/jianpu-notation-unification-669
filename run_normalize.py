#!/usr/bin/env python3
"""
批量记谱方言归一化 + 双渲染验证
  1. 669 首 raw → 统一写法 → 统一简谱/{sid}_原始简谱.json
  2. 原版 & 统一版各过官方渲染器 → events 语义字段逐事件对比
  3. 输出 logs/verify_report.json + 验证报告.md
"""
import json, glob, subprocess, sys, os, re
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/lib')
from dialect import normalize_songdata

BASE = '/mnt/ssd/lian/白马入芦花janpu'
RAW_DIR = f'{BASE}/jp-svt/B_tools/jianpu_dataset/data/raw_jianpu_669'
OUT_DIR = f'{BASE}/0830/统一所有/统一简谱'
LOG_DIR = f'{BASE}/0830/统一所有/logs'
EXPORTER = f'{BASE}/jp-svt/B_tools/jianpu_dataset/scripts/playback_segments/export_playback_full.js'

# source_column 不对比: = → xx 改写使列坐标平移(指向新文本的正确位置, 属预期),
# 音乐语义字段(音高/拍轴/秒轴/歌词/定位行/occurrence)全对比。
KEYS = ['event_index','play_index','measure_index','midi_number','pitch_class','midi_octave',
        'scale','octave','onset_beat','offset_beat','duration_beat','note_duration_beat',
        'onset_sec','offset_sec','text_duration_sec','midi_duration_sec','lyric',
        'source_note_id','source_occurrence','source_line','part']

def render(json_in, json_out):
    r = subprocess.run(['node', EXPORTER, json_in, json_out], capture_output=True, text=True, timeout=120)
    return r.returncode == 0 and os.path.exists(json_out), (r.stdout + r.stderr).strip()[:200]

def events_diff(pa, pb):
    a = json.load(open(pa)); b = json.load(open(pb))
    if a['total_events'] != b['total_events']:
        return False, f"事件数 {a['total_events']} != {b['total_events']}"
    for i, (x, y) in enumerate(zip(a['events'], b['events'])):
        for k in KEYS:
            va, vb = x.get(k), y.get(k)
            if isinstance(va, float) and isinstance(vb, float):
                if abs(va - vb) > 1e-9: return False, f"[{i}] {k}: {va} != {vb}"
            elif va != vb: return False, f"[{i}] {k}: {va!r} != {vb!r}"
    return True, 'ok'

def process(raw_path):
    sid = raw_path.split('/')[-2]
    raw_json = f'/tmp/unif_raw_{sid}.json'
    uni_json = f'/tmp/unif_uni_{sid}.json'
    pf_raw = f'/tmp/unif_pf_raw_{sid}.json'
    pf_uni = f'/tmp/unif_pf_uni_{sid}.json'
    rec = {'sid': sid}
    try:
        d = json.load(open(raw_path))
        new_sd, rep = normalize_songdata(d['songdata'])
        rec['dialect'] = rep['dialect']; rec['rules_hit'] = rep['rules_hit']
        rec['changed'] = rep['changed']
        # 落盘统一版(skip 歌 = 原文照存 + skip 标记, 文件保持 669 全齐)
        out = {'songdata': new_sd}
        os.makedirs(OUT_DIR, exist_ok=True)
        json.dump(out, open(f'{OUT_DIR}/{sid}_原始简谱.json', 'w'), ensure_ascii=False, indent=1)
        if rep.get('skip_unproven'):
            rec.update(verify='SKIP_UNPROVEN', err=f"未证实记号: {rep['skip_unproven']}")
            return rec
        # 双渲染
        json.dump(d, open(raw_json, 'w'), ensure_ascii=False)
        json.dump(out, open(uni_json, 'w'), ensure_ascii=False)
        ok1, e1 = render(raw_json, pf_raw)
        ok2, e2 = render(uni_json, pf_uni)
        if not ok1: rec.update(verify='RENDER_RAW_FAIL', err=e1); return rec
        if not ok2: rec.update(verify='RENDER_UNI_FAIL', err=e2); return rec
        ok, detail = events_diff(pf_raw, pf_uni)
        if ok:
            # 残留自检: 与转换器同一分段逻辑逐段检测(拼接式剥段会产生假相邻伪影)
            # (渲染对比抓不到漏转——两边一致地"没转"也算 PASS)
            from dialect import _segments
            resid = set()
            for prot, seg in _segments(new_sd['notation']):
                if prot: continue
                if re.search(r'_', seg): resid.add('_')
                if re.search(r'(?<=[0-7dg#b])=', seg): resid.add('=')
                if re.search(r'(?<=[0-7]),', seg): resid.add(',')
            if resid:
                rec.update(verify='RESIDUAL', err=f'旧方言残留: {sorted(resid)}'); return rec
        rec.update(verify='PASS' if ok else 'EVENTS_DIFF', err=None if ok else detail)
    except Exception as ex:
        rec.update(verify='EXCEPTION', err=str(ex)[:200])
    finally:
        for f in (raw_json, uni_json, pf_raw, pf_uni):
            if os.path.exists(f): os.remove(f)
    return rec

def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    files = sorted(glob.glob(f'{RAW_DIR}/*/*原始简谱.json'))
    print(f'共 {len(files)} 首', flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(process, p): p for p in files}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            if i % 50 == 0 or r['verify'] != 'PASS':
                print(f'[{i}/{len(files)}] {r["sid"]}: {r["verify"]} {r.get("err") or ""}', flush=True)
    json.dump(results, open(f'{LOG_DIR}/verify_report.json', 'w'), ensure_ascii=False, indent=1)
    from collections import Counter
    st = Counter(r['verify'] for r in results)
    print('\n== 汇总 ==', dict(st))
    fails = [r for r in results if r['verify'] != 'PASS']
    for r in fails[:20]: print(' FAIL', r['sid'], r['verify'], (r.get('err') or '')[:120])

if __name__ == '__main__':
    main()
