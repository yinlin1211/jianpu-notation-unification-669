#!/usr/bin/env python3
"""
记谱方言归一化 — 669 谱 DSL → 主流写法

统一目标(众数方言, 2026-09-03 实测):
  减时线: x(一条线, 396 首) / xx(两条, 对齐 raw 中 __ 与 = 的语义) / xxx(三条)
  低音点: d(343 首主流, 取代 ,)
  高音点: g(本来就统一)
  其余记号(附点 . / 延音 - / 休止 0 / 括号 / 小节线 / 标签 / 段名行 / 跳房)全部原样保留。

验证(由调用方执行): 统一版与原版各过官方渲染器, events 语义字段必须逐事件一致。
"""
import re
from collections import Counter

# ── 分段: {…} 标签、{!…!} 歌词槽、跳房头 [1,2: 内部一律不动 ─────────────
# {{ }} 段结构自身作边界(原样保留), 其内容视为正文参与统一
_SEG = re.compile(r'(\{!!.*?!\}|\{\{|\}\}|\{[^{}\n]*\}|\[\d+(?:[,，]\d+)*\s*[:])')

def _segments(notation: str):
    """yield (is_protected, text) 分段; 标签/歌词槽/跳房头原样保护。"""
    pos = 0
    for m in _SEG.finditer(notation):
        if m.start() > pos:
            yield False, notation[pos:m.start()]
        yield True, m.group(0)
        pos = m.end()
    if pos < len(notation):
        yield False, notation[pos:]


# ── 正文替换规则(仅作用于非保护段) ─────────────────────────────────────
# 顺序敏感: 低音点 ,→d 必须先于 =→xx(否则 "7,=" 的 = 前是逗号, lookbehind 失配漏转);
# 长减时线先于短线; 减时线可跟修饰符(d/g/b/#)后, lookbehind 放宽;
# 单 _ 在正文内一律是减时线(歌词的 _ 在 lyric 字段, 标签内已保护), 不加 lookbehind。
_NOTE_PRE = r'(?<=[0-7dg#b])'
_RULES = [
    (re.compile(_NOTE_PRE + r'___'), 'xxx'),  # 三条线 ___ → xxx
    (re.compile(_NOTE_PRE + r'__'), 'xx'),    # 两条线 __ → xx
    (re.compile(r'(?<=[0-7]),'), 'd'),        # 低音点 , → d (先于 =→xx!)
    (re.compile(_NOTE_PRE + r'='), 'xx'),     # = (两条线) → xx
    (re.compile(r'_'), 'x'),                  # 一条线 _ → x (正文内全部)
]

def normalize_notation(notation: str) -> tuple[str, Counter]:
    """返回 (统一写法 notation, 各规则命中次数)。标签段原样保留。"""
    out = []
    hits = Counter()
    for prot, seg in _segments(notation):
        if prot:
            out.append(seg)
            continue
        for pat, rep in _RULES:
            seg, n = pat.subn(rep, seg)
            if n:
                hits[rep] += n
        out.append(seg)
    return ''.join(out), hits


# ── 方言特征检测(报告用) ────────────────────────────────────────────────
def dialect_features(notation: str) -> dict:
    body = _SEG.sub(lambda m: '' if m.group(0).startswith('{') else m.group(0), notation)
    return {
        'line_x':  bool(re.search(r'(?<=[0-7])x', body)),
        'line_us': bool(re.search(r'(?<=[0-7])_', body)),
        'line_eq': bool(re.search(r'(?<=[0-7])=', body)),
        'oct_d':   bool(re.search(r'(?<=[0-7])d', body)),
        'oct_comma': bool(re.search(r'(?<=[0-7]),', body)),
        'oct_g':   bool(re.search(r'(?<=[0-7])g', body)),
    }


# 未证实记号组合: 命中则跳过统一(原文照存), 待逐个弄清语义后再纳入
_UNPROVEN = [re.compile(r'=\}')]   # =} : parser 仅对方言原形容忍(67564 实证), 语义未证实

def check_unproven(notation: str) -> list[str]:
    return [p.pattern for p in _UNPROVEN if p.search(notation)]

def normalize_songdata(songdata: dict) -> tuple[dict, dict]:
    """返回 (新 songdata, 归一化报告)。lyric 等其余字段一律原样。"""
    n = songdata.get('notation') or ''
    unproven = check_unproven(n)
    sd = dict(songdata)
    sd['notation_raw'] = n                      # 原文照存 → 可逆锚
    sd['notation_dialect'] = dialect_features(n)
    if unproven:
        sd['notation_skip_unproven'] = unproven
        report = {'rules_hit': {}, 'changed': False, 'skip_unproven': unproven,
                  'dialect': sd['notation_dialect']}
        return sd, report
    new_n, hits = normalize_notation(n)
    sd['notation'] = new_n
    report = {'rules_hit': dict(hits), 'changed': new_n != n,
              'skip_unproven': [], 'dialect': sd['notation_dialect']}
    return sd, report


if __name__ == '__main__':
    import json, sys
    p = sys.argv[1]
    sd = json.load(open(p))['songdata']
    new_sd, rep = normalize_songdata(sd)
    print('dialect:', rep['dialect'])
    print('rules_hit:', rep['rules_hit'])
    print('--- 原(前120):', repr(sd['notation'][:120]))
    print('--- 统(前120):', repr(new_sd['notation'][:120]))
