#!/usr/bin/env python3
"""
歌词层统一 — 音符级字槽

权威表示: 谱面音符 (line, col, occurrence) → 字槽 chars(0..n 字, 多字音=连音符, 空=无词)
数据来源: 官方渲染器 playback events[].lyric + source_line/source_column/source_occurrence
原文锚:   raw songdata.lyric 原文照存(可逆)
拼音轨:   notation {!...!} 槽原文提取(69 首), 对齐后置
验证:     批量脚本已含 events[].lyric 逐事件对比(统一版 vs 原版); 本模块另做字数守恒检查
"""
import re, json

_PINYIN_SLOT = re.compile(r'\{!!(.*?)!?\}', re.S)
_HAN = re.compile(r'[一-鿿]')

def note_key(e):
    return (e.get('source_line'), e.get('source_column'), e.get('source_occurrence'))

def extract_slots(pf_json_path):
    """官方渲染 playback_full → 谱面音符级字槽表。
    返回 {
      notes: [{line, col, occ, chars}],     # 播放序展开的谱面音符(含 occurrence)
      n_events, n_syllable, chars_all
    }"""
    d = json.load(open(pf_json_path))
    order = []            # 保持首次出现顺序
    slots = {}
    for e in d['events']:
        k = note_key(e)
        if k not in slots:
            slots[k] = []
            order.append(k)
        ly = (e.get('lyric') or '').strip()
        if ly:
            slots[k].append(ly)
    notes = []
    for k in order:
        chars = ''.join(slots[k])
        notes.append({'line': k[0], 'col': k[1], 'occ': k[2], 'chars': chars})
    syll = sum(1 for n in notes if n['chars'])
    return {'notes': notes, 'n_events': d['total_events'],
            'n_syllable': syll, 'chars_all': ''.join(n['chars'] for n in notes)}

def extract_pinyin(notation):
    """notation 中 {!拼音!} 槽 → 原样列表(对齐后置)。"""
    return _PINYIN_SLOT.findall(notation or '')

def conservation_check(slots, raw_lyric):
    """字数守恒: 字槽中的汉字(去重计)应被原文汉字覆盖(字槽可能略少——延音/无词)。
    返回 {n_slot_chars, n_raw_chars, missing(字槽有而原文无的字)}"""
    raw_s = ''.join(str(x) for x in json.loads(raw_lyric)) if isinstance(raw_lyric, str) else ''.join(str(x) for x in raw_lyric)
    raw_chars = set(_HAN.findall(raw_s))
    slot_chars = set(_HAN.findall(slots['chars_all']))
    missing = slot_chars - raw_chars
    return {'n_slot_han': len(_HAN.findall(slots['chars_all'])),
            'n_raw_han': len(_HAN.findall(raw_s)),
            'missing': sorted(missing)}

def build_song_lyric_layer(raw_json_path, pf_json_path):
    """songdata + 官方渲染 → 歌词层统一记录(存入统一简谱 json 的 lyric_layer 字段)"""
    sd = json.load(open(raw_json_path))['songdata']
    slots = extract_slots(pf_json_path)
    layer = {
        'raw_lyric': sd.get('lyric'),              # 原文照存(字符串套 JSON 的原样)
        'raw_lyric_parsed': json.loads(sd.get('lyric') or '[]'),
        'pinyin_slots': extract_pinyin(sd.get('notation')),
        'slots': slots['notes'],
        'stats': {'n_notes': len(slots['notes']), 'n_syllable': slots['n_syllable'],
                  'n_events': slots['n_events']},
    }
    if sd.get('lyric'):
        layer['conservation'] = conservation_check(slots, sd['lyric'])
    return layer

if __name__ == '__main__':
    import sys
    print(json.dumps(build_song_lyric_layer(sys.argv[1], sys.argv[2]), ensure_ascii=False)[:600])
