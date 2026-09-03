# 统一所有 — 669 数据统一 JSON 记录方案 v1

> 2026-09-03。目标:把 669 首 × 3316 版散落在 15+ 种格式里的数据,统一成**一套 JSON 记录方法**;
> 每种原格式都能从统一格式**无损转回**(互转),用 roundtrip diff 验收。

---

## 一、现状盘点(为什么"不统一")

### 1.1 数据资产清单(实测计数)

| # | 资产 | 位置 | 文件数 | 层级 | 时间轴 |
|---|---|---|---|---|---|
| 1 | 原始简谱 | `jp-svt/B_tools/jianpu_dataset/data/raw_jianpu_669/` | 669 | 谱面 | - |
| 2 | playback_full.json | `download/669切分单行/{song}/` | 664 | 事件(42字段) | 谱面拍+秒 |
| 3 | line_XX.json | `download/669切分单行/{song}/` | 50922 | 小节 | 谱面拍 |
| 4 | bar_XX.mid | `download/669MIDI/按小节/` | 1495 | 小节 | 拍相对(PPQ3360) |
| 5 | 全曲 MIDI | `download/669MIDI/midi/` | 3265 | 全曲 | 秒(PPQ480) |
| 6 | 谱面对齐 | `669数据准备/669谱面对齐/` | 3072 | 行 | 谱面拍+秒 |
| 7 | 音频标注 | `download/669音频标注/` | 3072 | 行+f0观测音符 | 秒 |
| 8 | 音符标注 | `download/669音符标注/` | 3023 | 行+音符(双轴) | 谱面拍+秒+音频拍 |
| 9 | rmvpe f0 | `669数据准备/669rmvpe_f0/` | 3312 | 帧(100fps) | 秒 |
| 10 | 节拍检测 | `669数据准备/669节拍检测/` | 6632(含downbeat) | 拍点 | 秒 |
| 11 | 转写存档 | `669数据准备/669转写存档/` | 3316 | 词/字符 | 秒 |
| 12 | MFA 对齐 | `download/669MFA对齐/` | 3292 | 字符 | 秒 |
| 13 | 修正 LRC | `download/669修正LRC2/` | 125 | 行 | 秒 |
| 14 | 伴奏家族 | `669数据准备/669伴奏家族/families.json` | 2 | 版本聚类 | - |
| 15 | 段级标注/对齐(试点7首) | `0830/annotation/`、`0830/alignment/` | 7 + 35 | 段→行→音符 | 谱面拍+秒 |

**同一首歌同一版本(如 100041 童话/1_光良)被 7 个文件描述,schema 各不相同。**

### 1.2 不统一的实锤(全部实测)

**A. 同名异义(最危险)**
- `notes`:音频标注里 = **f0 观测音符段** `{pitch, start, end, score}`(秒轴);
  音符标注里 = **谱面音符+对齐** `{midi, onset_beat, duration_beat, offset_beat, onset_sec, offset_sec, audio_beat}`(三轴混用)。同名完全两物。
- `transpose`:音符标注 `=-12`(原始半音差);音频标注同版本却 `=0, octave=-1`(八度分解)。两种分解并存,raw 值对不上。
- `beats`:谱面对齐的 `beats[]`=谱面拍;音符标注行级 `onset_beat[]`=谱面拍,但同文件 note 里 `offset_beat` 却是**音频轴**(见 B)。
- `onset_beat`/`offset_beat`:100041 童话 329 音符中 **273 个 `onset_beat+duration_beat ≠ offset_beat`** —— offset_beat 实为音频拍轴的结束点,onset 却是谱面拍。字段前缀暗示同轴,实际跨轴。
- `audio_beat − onset_beat` 差值有 **0 和 4 两种**(前奏拍偏移),无任何字段解释。

**B. 同义异名**
- 行起始时间:`t`(谱面对齐) vs `audio_start`(音频标注/音符标注);音符起始:`beat`(0830 alignment) vs `onset_beat`(音符标注/playback) vs `score_beats[]`(音频标注);行数组名:`aligned` vs `annotated_lines` vs `aligned_lines`。

**C. 状态/覆盖面不齐**
- status 枚举 `matched / version_mismatch(604) / inherited(246) / low_match(93)`,但 version_mismatch 未记录与哪个版本不匹配。
- 各资产覆盖面不同:谱面对齐 3072 vs 音符标注 3023(差49) vs 转写 3316 vs f0 3312 vs MFA 3292 —— 没有一个地方记录"这个版本有哪些资产、缺哪些"。

**D. 记谱方法实测:同一旋律被记成 9 种表示(用户核心痛点)**

| # | 记谱法 | 载体 | 样例 |
|---|---|---|---|
| 1 | **原始简谱 DSL(紧缩版)** | raw_jianpu `notation` 文本 | `{{3g--3g._2g__\|2g._(1g__1g-)…{!c.an_gq_ia.n_g!}…}}` |
| 2 | **渲染简谱 DSL(playback版)** | playback_full `notation` | `{bpm:72}⏎3g - - 3g_. 2g=\|(2)@ 倚音` |
| 3 | **行内 jianpu + 中文拍数注释** | 三份对齐文件的 `jianpu` 字段 | `5,_ 1_ 7,_ 1_. 5,= 5` / `2_(2.5拍)` / `N=(N.NN拍)` |
| 4 | MIDI 数组(谱面域) | 对齐文件 `midi[]` | `[61, 66, 65]` |
| 5 | MIDI 数值(演唱/观测域) | obs 音符 `pitch` | `49`(转调后) |
| 6 | 42字段结构化事件 | playback `events[]` | `midi_number/scale/octave/under_bar_count/dot_count` |
| 7 | c-t-dur 结构化 | 0830/annotation 音符 | `{"c":"0","t":0,"dur":0,"midi":null}` |
| 8 | MIDI 文件(两套) | PPQ480 秒轴 / PPQ3360 拍轴 | `100041_1_光良-童话.mid` |
| 9 | f0 Hz 序列 | rmvpe npy(100fps) | 演唱观测 Hz→midi |

**DSL 语法词表(实测确认)**:数字 0-7 音阶(`0`=休止);`-` 延一拍;`_` 与 `x` 混用均为一条减时线(八分),`__`/`xx` 两条(十六分),playback 渲染时合并为 `=`(十六分)——`7574 raw '3xx3xx1x' → playback '3= 3= 1_'` 已验证;`.` 附点;`g` 高八度点 / `,` 低八度点;`b`/`#` 升降号;`( )` 连音/倚音(渲染版 `@` 标记);`{!拼音!}` 歌词槽;`[2:` 反复跳房;`{dun}` 顿音;`{{ }}` 段结构;低频方言记号 `~ @ <> % $ + *` 及中文注记(前奏/间奏/渐慢/略)共 30+ 种,**parser 为混淆 JS(hc_12ab21fd54),部分记号语义未证实**(如 `8`/`9` 越界数字 517/43 次)。

**669 谱记谱方言普查(2026-09-03 全量实测,同一 DSL 语法的 205 种方言组合)**

三大正交方言轴 + 布尔开关,共 205 种组合:

| 方言轴 | 变体分布(歌数) |
|---|---|
| **减时线**(8 变体) | `x` 396 / `_` 83 / `_+=` 76 / `x+=` 60 / `x+_+=` 三种混用 35 / `x+_` 17 / `=` 1 / 无 1 |
| **低八度点**(8 变体) | `g+d` 213 / `g` 144 / `g+,` 129 / `d` 93 / `,` 56 / `g+d+,` 18 / `d+,` 13 / 无 3 |
| **段落结构**(8 变体) | `{play:}+段名行` 248 / 跳房`[1:` 187 / 无结构 132 / 混合约 100 |
| bpm 标记 | 有 258 首 / **无 411 首(61%)→ playback 一律填默认 72**(抽样 60 首全为 72,须标 `bpm_source: explicit\|default`) |
| 和弦标记 `{cn:}` | 192 首(Em/Cmaj7/Fsus2…) |
| 歌词拼音槽 `{!…!}` | 仅 69 首 |
| 全局移调 `{octave:}` | 7 首(-1×4, 1×2, 0×1) |
| 低频记号 `~ % $ <> + *` | 54 首 |

**`{tag:}` 标签 20 种**:`{play:}`(段落演奏顺序,A B A B B 式,291) `{bpm:}`(264) `{cn:}`(和弦,192) `{f:}`(调号 auto/F/G/...,178,与 keynote 字段并存可能冲突) `{mark:}`(117) `{section:}`(107) `{omit:}`(72) `{ms:}`(时间微缩放 0.75 等,42) `{tip:}`(**转调提示** `转1=bA(前i=后3)`,25) `{text:}` `{lyric:}` `{octave:}` `{hint:}` `{graph:}` 等。

**对统一方案的含义**:
- DSL 方言只影响"渲染视图"层;**事件层(`dur_beat`)由 parser 已算好,方言无关** —— 统一格式的权威表示不受方言影响;
- `notation_raw` 照存 + `notation_unparsed` 清单保证可逆;
- `bpm_source` 必须记录 explicit/default,防止 411 首的默认 72 被当成真实速度;
- `{f:}` 与 `keynote` 双源调号需入 `key_signature` 冲突检查。

**调号/拍号字段同样失控**:keynote 26 种写法 —— `1=bE` `1=#C` `1=A4`(带八度) `1=F G`(双调) `1＝B`(全角等号) `1=dD`(错字) 及**37 首为空**;rhythm 有 `4/4 2/4`(变拍) `4/4 4/2`(错写) 及 3 首为空。

**E. 切分维度四套打架**
- 行 `score_line` / 段 `A1·B2`(0830 alignment)、`segments[]`(0830 annotation)/ 小节 `measure_index`(playback、line_XX)/ 出现次数 `source_occurrence`(playback)。同一谱面事件有四种定位方式,互不引用。

**F. 歌词记录形态实测:至少 9 种,且两套体系(汉字/拼音)并存**

| # | 形态 | 载体 | 实测特征 |
|---|---|---|---|
| 1 | raw `songdata.lyric` | **字符串里套 JSON 数组**(669 首全如此,均可解析) | 元素=段;`/` 分组(567 首)、`//` 空行(386 首);中文标点 669 首全部混排在词中;`(合唱:…)` 等注记混入;`_` 连音符(39 首,如 `我来到_你的城市`);空格=词组分隔且**多空格有对齐含义**(454 首,如 `就 此   告别吧`) |
| 2 | notation 内嵌**拼音槽** | `{!c.an_gq_ia.n_g!}` | 仅 69 首;**拼音+`.`隔音节体系**与汉字体系并存 |
| 3 | playback `lyric` | 单条连续串 | `_`=无词音符槽;生成规则复杂(471 events / 331 lyric_slots / 409 chars 三数不一致,规则待逆向) |
| 4 | playback `events[].lyric` | 音符级槽位 | 空串=无词 |
| 5 | line_XX `lyric` | 数组 `["手变成翅_膀守护你"]` | 字内 `_` = 多字音占位 |
| 6 | 三份对齐文件行 `lyric` | `忘了有多久 再没听到你` | 空格分词仅约 1/3 歌有 |
| 7 | LRC.fixed | `[mm:ss.xx]歌词` | 行级,无字级 |
| 8 | Whisper | text + words[] + chars[] | **听写观测,含错字/变体**(5443 流光记实证:标注词与谱面词根本不匹配) |
| 9 | MFA | 字级强制对齐 | 观测 |

**raw `songdata.lyric` 内部深查(聚焦原始 json)**:
- 类型:669 首全部是**字符串里套 JSON 数组**(均可解析,但非标准形态);
- 段数:1 段 408 / 2 段 227 / 3-5 段 34;**歌词段数与谱面段落结构基本不对应**(`{play:}` 歌 93% 不匹配 271/291;`{{}}` 歌 49 首中仅 7 首匹配,108965 有 28 个 `{{}}` 块而歌词 1 段)→ 歌词数组只是分块存文本,**无结构语义**;
- `_` 为延音拍填充且可连用(`说一句____` = 1-4 连,上下文统计 汉字_汉字 733 次);
- 语言含**日语歌**(44683 群青,假名);
- **11 首歌词/文本直接裸混排进 notation 正文**(`|间奏|`),不经任何标签;
- 字数≠音符数(童话 331 字 vs 421 音符位,差=休止/延音/无词槽),**歌词↔音符槽位机制各层规则不同且无统一约定**(playback `_` 填充 / line 字内 `_` / 拼音槽 `{!..!}` 三套互不兼容)。

**歌词层设计含义**:
- 权威表示 = **音符级字槽**(发声事件挂 `chars[]`,1 音符 0..n 字;多字音=1 音符多字;无词=空槽);
- `raw_lyric` 原文照存(`//`、标点、注记、多空格全保留)保证可逆;
- 69 首拼音槽歌双轨存 `lyric` + `pinyin`;
- Whisper/MFA/LRC 是**音频侧观测**,分源保存不与谱面歌词合并(错字/变体不能互相污染);
- 标点与 `(合唱:)` 类注记归 `lyric_marks`,不入字槽。

**G. 冗余三份对齐**
- 谱面对齐、音频标注、音符标注互相重叠(行级 midi/jianpu/lyric 三处重复),更新一处不同步 → 现在各文件之间已有差异风险。

---

## 二、统一数据模型 `bai-ma-unified-v1`

### 2.1 分层:歌级谱面 + 版本级对齐

**核心思想:谱面是 669 首歌各一份的"单一事实源"(同歌多版本共享);每版本的差异(转调、对齐、音频观测)放版本文件。音频大数据(f0/beats)用外置指针,不进 JSON。**

```
统一所有/
├── schema.md                          # 本文档
├── unified/
│   ├── {song_id}/
│   │   ├── song.json                  # 歌级:谱面单一事实源
│   │   └── {version}.json             # 版本级:该版本的转调+对齐+观测+资产指针
│   └── manifest.json                  # 全库索引:每版本有哪些资产/状态/家族
├── lib/
│   └── unified.py                     # load/validate/save + 轴换算工具
├── converters/                        # 每原格式一对:from_* 建库 / to_* 转回
│   ├── from_playback_full.py    to_playback_full.py
│   ├── from_note_align.py       to_note_align.py       (音符标注)
│   ├── from_audio_annot.py      to_audio_annot.py      (音频标注)
│   ├── from_score_align.py      to_score_align.py      (谱面对齐)
│   ├── from_line_json.py        to_line_json.py        (小节切分)
│   ├── from_annotation0830.py   to_annotation0830.py   (段级标注)
│   ├── from_align0830.py        to_align0830.py        (段级对齐 alignment_X1)
│   ├── from_whisper.py          to_whisper.py          (转写存档)
│   ├── from_beats_txt.py        to_beats_txt.py        (节拍检测)
│   ├── from_lrc_fixed.py        to_lrc_fixed.py        (修正LRC)
│   └── to_midi_480.py / to_midi_bar_3360.py / to_f0_npy.py  (派生物导出)
└── verify_roundtrip.py                # 统一→原格式→与现存原文件逐字段 diff(浮点容差1e-6)
```

### 2.2 三条时间轴,显式命名(防 1.2-A 类坑复发)

| 后缀 | 轴 | 单位 | 起点 | 例 |
|---|---|---|---|---|
| `_beat` | **谱面拍轴** | 拍 | 谱面第 1 拍=0 | `onset_beat: 14.5` |
| `_sec` | **音频秒轴** | 秒 | 音频 0s | `onset_sec: 16.83` |
| `_t` | **音频拍点轴** | 秒(落在 madmom 拍点上的时间) | 音频 0s | `onset_t: 18.5` |

规则:**任何字段必须带轴后缀;禁止裸 `onset/offset/start/end`**;跨轴换算只能走 `lib/unified.py` 的工具函数(用 bpm/meters 或 beats 表),禁止散落各脚本。

### 2.3 song.json — 谱面单一事实源

**记谱表示原则(由 1.2-D 得出)**:
- 谱面的**权威表示 = 结构化事件**(pitch 域 + 时值 + 修饰符 + loc),即 9 种记谱法中的第 6 种收敛而来;
- 三种 DSL 文本(raw/playback/行内)**全部降级为"可逆渲染视图"**:事件 → 可重新渲染出三种字符串;
- **raw DSL 原文一字不动照存**(`notation_raw`),转回 raw 格式 = 原文照抄,零风险(不被 parser 的未证实记号卡住);
- parser 未能消化的低频记号(`~ @ <> % $`、`{{}}`、`8/9` 等)进 `notation_unparsed` 清单,逐歌可见、逐个攻关。

```jsonc
{
  "schema": "bai-ma-unified-v1",
  "type": "song",
  "song_id": "100041",
  "song_name": "童话",
  "key_signature": "1=bG",
  "rhythm": "4/4",
  "bpm": 72,
  "meters": [{"beat": 0, "beats_per_bar": 4, "beat_unit": 4}],
  "key_signature_norm": {"tonic": "Gb", "mode": "major"},   // keynote 规范化(26种写法→统一);原串保留在 keynote

  // raw DSL 原文照存(可逆的锚)
  "notation_raw": "{{3g--3g._2g__|2g._(1g__1g-)…}}",
  "notation_unparsed": [{"token": "~", "count": 173, "note": "parser 未证实语义"}],

  // 谱面事件流:由 playback_full.json 的事件规约而来(来源规则 rule-pf-1)
  "events": [
    {
      "id": "e0001",                 // 全局唯一事件 ID = n{line:03d}c{col:03d}o{occ:02d}
      "onset_beat": 0.0,             // 谱面拍轴
      "dur_beat": 3.0,               // 占拍
      "sound_beat": 1.0,             // 实际发声拍(duration_beat 与 note_duration_beat 之别,保留双值)
      "jianpu": "3g(3拍)",           // 原样简谱符号
      "midi": 82,                    // 谱面域 MIDI(休止=null)
      "rest": false,
      "lyric": "",                   // 字槽:0..n 字(多字音="翅,膀"式列表或原样连串);空=无词
      "pinyin": null,                // 仅 69 首拼音槽歌有(如 "c.an")
      "loc": {"line": 16, "col": 2, "occ": 1, "measure": 1},   // 四种切分维度都挂在 loc 下,统一入口
      "seg": "A1"                    // 段落 ID(与 segments 对应;无段落=null)
    }
  ],

  // 段落结构(来自 0830/annotation 的 segments;全量歌可为空表)
  "segments": [
    {"seg_id": "A1", "label": "开头", "named": "开头",
     "lines": [3], "event_ids": ["e0001", "e0002"]}
  ],

  "provenance": {
    "raw_jianpu": {"path": ".../100041_原始简谱.json", "sha1": "…"},
    "playback_full": {"path": ".../playback_full.json", "sha1": "…", "rule": "rule-pf-1"},
    "annotation0830": {"path": ".../0830/annotation/100041.json", "sha1": "…", "rule": "rule-ann-1"}
  }
}
```

- `id = n{line}c{col}o{occ}`:行/列/出现次数三元组定位,四个切分维度(行、段、小节、occ)全部由 `loc` 派生,**消除 D 类打架**。
- 谱面 midi 保持"谱面域"(与 raw/playback 一致);各版本的实际域由版本文件转调字段算出,**谱面文件不被版本污染**。

### 2.4 {version}.json — 版本级对齐与观测

```jsonc
{
  "schema": "bai-ma-unified-v1",
  "type": "version",
  "song_id": "100041",
  "version": "1_光良-童话",          // 原样保留(含空格/括号),slug 另存 meta.slug
  "meta": {
    "status": "matched",             // matched | version_mismatch | inherited | low_match
    "status_detail": {"mismatch_ref": null},   // C 类补全:不匹配时记录参照版本
    "family": "F0123",               // 伴奏家族(来自 families.json;无=null)
    "dup_of": null,                  // 文件级重复上传(169对)指向本体版本
    "assets": {"score_align": true, "note_align": true, "audio_annot": true,
               "whisper": true, "mfa": true, "lrc_fixed": false, "f0": true,
               "beats": true, "midi480": true, "midi_bar": false}
  },

  // 转调:raw 与分解同时记录,两种旧表示都能无损还原
  "key": {
    "transpose_raw": -12,            // 音符标注/0830 的原始半音差
    "octave": -1,                    // 音频标注的八度分解
    "transpose_in_octave": 0,        // = transpose_raw - 12*octave
    "domain": "midi"                 // 谱面域 + 12*(octave) 后为该版本演唱域
  },

  // 音符级对齐:按事件 ID 引用谱面,不再重复存谱面内容(消灭 E 类冗余)
  "align": [
    {
      "ref": "e0047",                        // → song.json events[].id
      "onset_beat": 14.5,                    // 谱面拍轴(来自原 onset_beat)
      "dur_beat": 0.5,
      "onset_sec": 16.83, "offset_sec": 17.27,   // 音频秒轴(实测/推算)
      "onset_t": 18.5, "offset_t": 19.0,     // 音频拍点轴 ← 原 audio_beat / 原 offset_beat(判定跨轴后归此)
      "matched": true,
      "match_rate": 0.79, "K": 42.0, "ratio": 1.0,   // 行级质量分上提为可选
      "amb_rule": "rule-na-2"                // 命中的歧义消解规则(可逆回放用)
    }
  ],

  // 行级对齐信息(谱面对齐 + 各文件行级字段的并集)
  "lines": [
    {
      "score_line": 16,
      "lyric": "忘了有多久 再没听到你",
      "jianpu": "5,_ 1_ 7,_ …",
      "audio_start": 13.72,                 // ← 原 t / audio_start(统一为此名,转回时改名)
      "matched": true,
      "event_ids": ["e0047", "e0048", "…"], // 行→事件引用
      "pitch_match": [0.999, …], "chars": [...]
    }
  ],

  // f0 观测音符(音频标注的 notes,换名 obs_notes 防同名)
  "obs_notes": [{"pitch": 49, "onset_sec": 13.3, "offset_sec": 13.71, "score": 0.999}],

  // 歌词区:谱面字槽(song 级 events 引用)+ 音频侧观测分源
  "lyrics": {
    "raw_lyric": "['忘了有多/久再没听到/…']",     // raw 原文照存(字符串套数组的原样)
    "raw_lyric_parsed": ["忘了有多/久再没听到/…"], // 解析后数组
    "marks": [{"type": "note", "text": "(合唱:…)", "loc": "…"}],   // 注记/标点归此
    "whisper": {"text": "…", "words": [{"text":"忘","start":12.28,"end":13.28}], "chars": []},
    "mfa": {"chars": []},
    "lrc_lines": [{"t": 13.72, "text": "…"}]
  },

  // 音频资产:指针+校验,不内嵌
  "audio": {
    "f0": {"path": "669数据准备/669rmvpe_f0/100041_童话/1_光良-童话_vocals.f0.npy",
           "fps": 100, "dtype": "float32", "sha1": "…"},
    "beats": {"path": "…/1_光良-童话.txt", "times": null, "sha1": "…"},      // 小文件可选择性内嵌 times
    "downbeats": {"path": "…/1_光良-童话.downbeat.txt", "sha1": "…"},
    "vocal": {"path": "…/vocal_sep/1_光良-童话_vocals.flac", "sha1": "…"}
  },

  // 歧义消解规则表:转换器做过的每个判定在此可回放,保证 to_* 能重建原字段
  "convert_rules": {"rule-na-2": "音符标注offset_beat与onset_beat跨轴→归音频拍点轴;依据:onset+duration≠offset 占 83%"},

  // 无法映射的原始顶层字段原样保存(零信息丢失兜底)
  "legacy": {"音符标注": {"beat_source": "fixed"}}
}
```

### 2.5 manifest.json — 全库账本

```jsonc
{
  "schema": "bai-ma-unified-v1", "type": "manifest",
  "songs": {"100041": {"song_name": "童话", "versions": ["1_光良-童话", "…"], "families": {...}}},
  "versions": {
    "100041/1_光良-童话": {
      "status": "matched", "assets": {...}, "family": "F0123", "dup_of": null,
      "unified": "unified/100041/1_光良-童话.json", "unified_sha1": "…"
    }
  },
  "coverage": {"score_align": 3072, "note_align": 3023, "whisper": 3316, …}   // C 类:一处看清缺什么
}
```

---

## 三、映射规则表(转换器照此实现)

### 3.1 from_*(建库,原格式 → 统一)

| 源 | 规则 | 关键映射 |
|---|---|---|
| playback_full | rule-pf-1 | events→song.events;`duration_beat`→`dur_beat`,`note_duration_beat`→`sound_beat`,`source_line/col/occurrence/measure`→`loc`,`onset_beat/offset_beat/onset_sec/offset_sec` 保留进 align(初始对齐);**raw notation 原文照存 `notation_raw`**,parser 未消化记号入 `notation_unparsed`;keynote/rhythm 原串+规范化双存 |
| 音符标注 | rule-na-1 行级 `midi[]/onset_beat[]` 冗余数组:不单独入库,由 notes[] 重建<br>rule-na-2 **跨轴判定**:note 中若 `onset_beat+dur_beat ≈ offset_beat` → offset_beat 归谱面轴 `_beat`;否则 offset_beat 归 `offset_t`(音频拍点轴),`audio_beat` → `onset_t`,判定依据写入 convert_rules<br>rule-na-3 `K/ratio/match_rate/matched` 行级字段上提到行,音符级 matched 由 onset_sec 存在性派生<br>rule-na-4 `transpose` → `key.transpose_raw` |
| 音频标注 | rule-aa-1 `notes[]{pitch,start,end,score}` → `obs_notes[]`(改名防同名)<br>rule-aa-2 `transpose/octave` → `key.transpose_in_octave/octave`<br>rule-aa-3 行级 `audio_beat/audio_downbeat`(秒) → `lines[].audio_beat_t/audio_downbeat_t`(拍点轴) |
| 谱面对齐 | rule-sa-1 `aligned[]{t,beats[],durs[],midi[]}` → `lines[]`+`align[]`(beats/durs/midi 冗余数组由事件重建);`t` → `audio_start` |
| line_XX | rule-lj-1 notation/lyric/slots → 不入库(由 playback_full 事件重建),provenance 记录;仅小节边界可校验 |
| 0830 annotation | rule-an-1 segments→song.segments;行/段→event_ids 引用 |
| 0830 alignment_X1 | rule-al-1 `notes[]{beat,dur_beat,midi,line,col,onset_sec,offset_sec}` → align[](ref 由 line/col+occ 定位);`K/ratio/match_rate` → 段级质量 |
| Whisper/MFA/LRC | rule-ly-1 各自并入 lyrics.* 分源区,不合并时间戳(来源不同不可混) |
| beats txt | rule-bt-1 times 数组(可内嵌,6632 文件总 <10MB) |
| families.json | rule-fm-1 family/dup_of 写 manifest |

### 3.2 to_*(转回,统一 → 原格式)

每条 to_ 规则是 from_ 的逆放 + 字段改名还原(`audio_start→t`、`obs_notes→notes`、行级冗余数组用 align[] 重建、轴名还原)。**要求:重建文件与现存原文件语义 diff 为空**(`verify_roundtrip.py`,浮点容差 1e-6,键序不敏感)。MIDI 两套按 provenance 里的 PPQ/时间轴参数重导出,逐 tick diff。

### 3.3 可逆性三保险

1. **convert_rules 回放**:所有歧义判定的依据入库,to_* 按同一规则逆推。
2. **legacy 兜底**:映射覆盖不到的字段原样进 legacy,to_* 时优先还原。
3. **roundtrip 验收**:全量(3023+3072+3072+…)逐文件 diff,输出报告;任何 FAIL 不允许上线。

---

## 四、实施步骤(建议)

1. **lib/unified.py**:schema 校验(load/save/validate)+ 轴换算工具(beat↔sec 用 bpm/meters;beat↔t 用 beats 表)。
2. **试点 7 首**(0830 已有 annotation/alignment 的 5995/6141/4620/…):跑通 from_* ×10 → verify_roundtrip 全绿。
3. **全量 669**:后台批量建库 + roundtrip 报告;产出 manifest.json 的 coverage 总表。
4. **派生物导出**:to_midi_480 / to_midi_bar_3360 重导出与现存 diff。
5. 之后所有新分析(母版迁移、命中率、网站)一律读 unified/,旧目录冻结为只读源。
