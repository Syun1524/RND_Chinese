# -*- coding: utf-8 -*-
"""op001「Avant Story」英文唱词补全（在中文构建之后应用）。

CoZ 把三句英文 rap/chant **只**记在 romaji 层，Kanji 层那几秒没有字。
用户拍板：
  * 日文层那几段写**英文原文**（一行，不逐字拆）；
  * 中文层写英文大字，中文翻译以小字标注在**英文上方**，该段静态；
  * 紧随其后的日文歌词仍按原样（中文 + 扫色）；
  * アバンストーリー → Avant Story（逐字行就地换字），其余片假名保留。

中文措辞（用户指定）：我正走向新世界秩序 / 神明将降临于世 / 再一次
"""
import re

BS = chr(92)
VIS = re.compile(r'\{[^}]*\}')

# (英文起唱, 日文起唱, 中文行原点, 英文原文, 中文小注)
SEGS = [
    (77.43, 80.16, 77.13, "I am to the New World Order", "我正走向新世界秩序"),
    (82.90, 85.60, 82.60, "God will come down to the world", "神明将降临于世"),
    (93.85, 95.08, 93.55, "Once again", "再一次"),
]


def sec2ass(s):
    s = max(0.0, float(s))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return "%d:%02d:%05.2f" % (h, m, s % 60)


def t2s(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def vis(t):
    return VIS.sub('', t or '').strip()


def _fld(raw):
    body = raw.rstrip('\r\n')
    return body.split(',', 9), raw[len(body):]


def _set_text(raw, text, replace_prefix=False):
    """Replace the rendered text.  With replace_prefix=True the whole leading
    override block is swapped for `text`'s own prefix (avoids prefix stacking)."""
    f, eol = _fld(raw)
    if replace_prefix:
        f[9] = text
    else:
        cut = f[9].rfind('}')
        f[9] = (f[9][:cut + 1] if cut >= 0 else '') + text
    return ','.join(f) + eol


def _set_time(raw, start, end):
    f, eol = _fld(raw)
    f[1], f[2] = sec2ass(start), sec2ass(end)
    return ','.join(f) + eol


def apply_pass(lines, styles, dialogues=None, tgts=None, timelines=None):
    """dialogues/tgts/timelines: build_song 的原始数据，用于重算被截短行的扫色。"""
    out = list(lines)

    # 日文层：**完全不动**。CoZ 在这三处本来就让日文列空着（英文只记在 romaji
    # 层），竖排英文试过、观感差，已按用户要求去掉。
    jp_adds = []          # (start_s, line)

    # ---- 只补三处缺漏的英文；片假名（含 アバンストーリー）一律保持原样 ----

    # ---- 中文层切分：英文段（英文大字 + 中文小注）/ 日文段（原样带扫色） ----
    for en0, jp0, tr0, en, zh in SEGS:
        # --- 中文层：找 ghost(无kf) ---
        gi = None
        for i, l in enumerate(out):
            if not l.startswith('Dialogue:'):
                continue
            f, _ = _fld(l)
            if len(f) < 10 or f[3].strip() != 'translation':
                continue
            if abs(t2s(f[1]) - tr0) <= 0.03 and 'kf' not in f[9]:
                gi = i
                break
        if gi is None:
            continue
        ghost = out[gi]
        gf, _ = _fld(ghost)
        orig_end = t2s(gf[2])
        prefix = re.match(r'^(?:\{[^}]*\})*', gf[9]).group(0)
        size = styles.get(gf[3].strip(), {}).get('size', 68) or 68
        # 中文小注：略大一点，并加字距，让短小的汉字与长英文视觉平衡；
        # 整行居中（\an2 底部居中 + \pos 到屏幕水平中心），避免贴左孤立。
        note_fs = max(18, int(round(size * 0.52)))
        note_sp = max(2, int(round(size * 0.10)))       # 字间距
        # 英文与中文都居中：**丢掉原前缀里的 \pos**（否则与居中冲突），
        # 用 \an2 覆盖样式里的 \an1，再 \pos 到屏幕水平中心。
        keep = re.sub(re.escape(BS) + r'pos\([^)]*\)', '', prefix)
        keep = re.sub(re.escape(BS) + r'an\d', '', keep)
        en_text = ('%s{%sfscy83\\an2\\pos(960,1038)}{\\fs%d\\fsp%d}%s\\N{\\fs%g\\fsp0}%s'
                   % (keep, BS, note_fs, note_sp, zh, size, en))
        orig_text = vis(gf[9])

        ov = None
        # overlay = 同一起点、含 kf 的那条（底行本身不含 kf，不会误配）
        oi = None
        for i, l in enumerate(out):
            if not l.startswith('Dialogue:'):
                continue
            f, _ = _fld(l)
            if len(f) < 10 or f[3].strip() != 'translation' or 'kf' not in f[9]:
                continue
            if abs(t2s(f[1]) - tr0) <= 0.05:
                oi = i
                break
        if oi is not None:
            nf, eol_nf = _fld(out[oi])
            nf2 = list(nf)
            nf2[1], nf2[2] = sec2ass(jp0), sec2ass(orig_end)
            # 扫色时长按新窗口等比缩放（原时长对应原窗口）
            kfs = [int(x) for x in re.findall(r'kf(\d+)', nf[9])]
            if kfs:
                old_span = (orig_end - tr0) * 100
                new_span = (orig_end - jp0) * 100
                scale = (new_span / old_span) if old_span else 1.0
                scaled, acc = [], 0.0
                for k in kfs:
                    acc += k * scale
                    scaled.append(max(1, int(round(acc)) - sum(scaled)))
                it = iter(scaled)
                nf2[9] = re.sub(re.escape('{' + BS + 'kf') + r'\d+\}',
                                lambda m: '{' + BS + 'kf%d}' % next(it), nf[9])
            ov = ','.join(nf2) + eol_nf
            out.pop(oi)                     # 先摘掉旧 overlay，稍后重新插入

        out[gi] = _set_text(_set_time(ghost, tr0, jp0), en_text, replace_prefix=True)
        jp_ghost = _set_text(_set_time(ghost, jp0, orig_end), orig_text)
        if ov:
            out[gi] = out[gi]
            out.insert(gi + 1, jp_ghost)
            out.insert(gi + 2, ov)
        else:
            out.insert(gi + 1, jp_ghost)

    for _, rows in sorted(jp_adds, key=lambda x: x[0], reverse=True):
        block = rows if isinstance(rows, list) else [rows]
        ts = t2s(block[0].split(',')[1])
        at = len(out)
        for i, l2 in enumerate(out):
            if l2.startswith('Dialogue:') and t2s(l2.split(',')[1]) > ts:
                at = i
                break
        out[at:at] = block
    return out
