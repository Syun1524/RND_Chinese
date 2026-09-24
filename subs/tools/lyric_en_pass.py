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
import io
import os
import re

BS = chr(92)
VIS = re.compile(r'\{[^}]*\}')
KSYL = re.compile(re.escape(BS) + r'k(?:f|o)?(\d+)\}')

# 由 build_lyric_subs 在调用 pass 前塞进来：
#   TEMPLATE_DIR —— 英文原版字幕目录（取 romaji 的 \k 时间轴）
#   sweep_colors —— 复用它那套调色（暗底扫白 / 亮底从暗调回本色）
#   SWEEP        —— 是否加扫色（跟主构建的 --karaoke 同一个开关）
TEMPLATE_DIR = None
sweep_colors = None
SWEEP = True

# 宽度测量：英文行是整个文字块里最宽的一行，用它的宽度反推 \an2 的锚点，
# 就能让英文左缘正好落在中文译文的左列（x=63），同时让较短的中文小注
# 在这条英文正上方居中。字体路径由 build_lyric_subs 在调用前塞进来。
#
# ★★ 字号必须换算成 GDI 实际用的 em，否则宽度会高估 ~45%（实测踩过）：
#    VSFilter 走 GDI，`\fs` 被当作**字面高度**（usWinAscent+usWinDescent），
#    不是 em 尺寸。本字体 1160+288 = 1448 / upem 1000 ⇒ 实际 em = fs / 1.448。
#    不换算的话锚点算得太靠右，英文整行右移（用户实机截图发现：
#    英文左缘 172px，应为 42px）。
FONT_PATH = None
_fonts = {}
_emfac = [None]


def _em_factor():
    if _emfac[0] is None:
        fac = 1.0
        try:
            from fontTools.ttLib import TTFont
            f = TTFont(FONT_PATH, lazy=True)
            cell = float(f['OS/2'].usWinAscent + f['OS/2'].usWinDescent)
            if cell > 0:
                fac = f['head'].unitsPerEm / cell
        except Exception:
            fac = 1.0
        _emfac[0] = fac
    return _emfac[0]


def _text_width(text, fs):
    if not FONT_PATH or not text:
        return 0.0
    from PIL import ImageFont
    px = max(1, int(round(fs * _em_factor())))
    if px not in _fonts:
        _fonts[px] = ImageFont.truetype(FONT_PATH, px)
    return _fonts[px].getlength(text)


def _romaji_tokens(en0):
    """CoZ 的 romaji karaoke 行（起点 = 这段英文的起唱）→ [(文本, 时长cs)]。
    CoZ 把英文唱词和随后的日文歌词放在**同一条 \\k 流**里，所以开头那几个
    token 正好就是这段英文的时间轴。

    用 re.split 按标签切，避免手工找下标时把下一个标签的 `{` 卷进文本里。"""
    if not TEMPLATE_DIR:
        return None
    path = os.path.join(TEMPLATE_DIR, 'mv_rnd_op001.ass')
    for ln in io.open(path, encoding='utf-8-sig', newline=''):
        if not ln.startswith('Comment:'):
            continue
        f = ln.rstrip().split(',', 9)
        if len(f) < 10 or f[3].strip() != 'romaji' or 'retime' in f[9]:
            continue
        if abs(t2s(f[1]) - en0) > 0.05:
            continue
        parts = re.split(re.escape(BS) + r'k(?:f|o)?(\d+)\}', f[9])
        # parts = [前导, dur0, text0, dur1, text1, ...]
        # 每段文本的**末尾**带着下一个标签的开头 '{'（源文件里标签写作 {\kNN}），
        # 必须剥掉，否则它会作为普通字符被渲染出来。
        toks = []
        for i in range(1, len(parts) - 1, 2):
            txt = parts[i + 1]
            if txt.endswith('{'):
                txt = txt[:-1]
            toks.append((txt, int(parts[i])))
        return toks
    return None


def _en_sweep(en, en0, lead_cs=0):
    r"""英文行的 \kf 扫色负载 + 总时长(cs)。

    只取属于**英文唱词**的那些 token：同一条 romaji 行后面接着日文歌词，
    那些音节不能算到这一行头上。边界靠字母比对（忽略空格/标点）确定：
    累积到与英文文本等长就停；中途对不上就放弃（不猜）。

    lead_cs：本行显示起点到**起唱**之间的空档（\fad 那 0.3s）。按中文歌词的
    既有做法，把这段垫进**首字**的时长里 —— 首字从行一出现就开始慢慢填，
    其余各字仍严格跟着唱腔走（另起一个空 \kf 标签也可以，但与既有风格不一致）。"""
    toks = _romaji_tokens(en0)
    if not toks:
        return None, 0
    want = re.sub(r'[^A-Za-z]', '', en).lower()
    got, units = '', []
    for txt, dur in toks:
        if len(got) >= len(want):
            break
        got += re.sub(r'[^A-Za-z]', '', txt).lower()
        if not want.startswith(got):
            return None, 0
        units.append([txt, dur])
    if len(got) != len(want) or not units:
        return None, 0
    if lead_cs > 0:
        units[0][1] += lead_cs
    payload = ''.join('{%skf%d}%s' % (BS, d, t) for t, d in units)
    return payload, sum(d for _, d in units)


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
        # 用户拍板：英文大字与简中译文**一样大**。主歌词最终渲染 =
        # 样式 68 × 构建期 SIZE_SCALE 1.10 = 74.8，所以这里就用 size × scale，
        # 不再额外放大（曾短暂用过 1.08，已按用户要求收回）。
        scale = float(__import__('os').environ.get('LYRIC_SIZE_SCALE', '1.10'))
        en_fs = round(size * scale, 1)
        note_fs = max(18, int(round(size * scale * 0.52)))
        note_sp = max(2, int(round(size * scale * 0.10)))   # 字间距
        # 排版：英文左缘对齐中文译文那一列（x=63），中文小注仍**居中于英文上方**。
        # ASS 的 \an2（底部居中）是「每一行各自以锚点 x 为中心」，所以把锚点放在
        # 英文行的中点，英文左缘就正好落在 63，小注也自然居中于英文之上。
        # 英文是块内最宽的一行，故锚点 = 63 + 英文宽/2。
        w_en = _text_width(en, en_fs)
        if w_en:
            keep = re.sub(re.escape(BS) + r'pos\([^)]*\)', '', prefix)
            keep = re.sub(re.escape(BS) + r'an\d', '', keep)
            keep += ('{' + BS + 'an2' + BS + 'pos(%g,1000)}' % round(63 + w_en / 2.0, 1))
        else:
            keep = prefix          # 测不出宽度就退回两行都左对齐（不猜）
        en_text = ('%s{\\fs%d\\fsp%d}%s\\N{\\fs%g\\fsp0}%s'
                   % (keep, note_fs, note_sp, zh, en_fs, en))
        orig_text = vis(gf[9])

        # ---- 英文扫色 overlay（与中文歌词同一套视觉语言）----
        # 单独一条只含英文的行：\an2 锚点相同 ⇒ 底边与 ghost 的英文行重合，
        # 逐字 \kf 按 CoZ 记在 romaji 层的音节时长从左往右扫。
        # ★ 中文小注**不参与扫色**：它是翻译注解、不是唱的内容，跟着扫会抢戏；
        #   而且它就压在英文上方，英文本身已经在指示进度了。
        ov_en = None
        if SWEEP and sweep_colors is not None:
            # 空档 = ghost 显示起点 → 英文起唱（这一段扫色原地不动）。
            # ★ 必须夹住窗口：CoZ 的 \k 总和偶尔比显示窗口长 1cs（两端各自
            #   四舍五入），不夹的话扫色会在行结束之后才走完、末字永远填不满。
            lead_cs = max(0, int(round((en0 - tr0) * 100)))
            win_cs = int(round((jp0 - tr0) * 100))
            payload, total_cs = _en_sweep(en, en0, lead_cs)
            if payload:
                body_cs = total_cs - lead_cs
                lead_cs = max(0, min(lead_cs, win_cs - body_cs))
                payload, total_cs = _en_sweep(en, en0, lead_cs)
            if payload and total_cs:
                sec, prim = sweep_colors(keep)
                tag = '{' + BS + '2c&H' + sec + '&'
                if prim:
                    tag += BS + '1c&H' + prim + '&'
                tag += '}'
                ef, eeol = _fld(ghost)
                ef2 = list(ef)
                # 起点同 ghost：开场那 0.3s 先静态显示，唱起来再开始扫
                ef2[1], ef2[2] = sec2ass(tr0), sec2ass(jp0)
                ef2[9] = (keep + '{\\fs%g\\fsp0}' % en_fs + tag + payload)
                ov_en = ','.join(ef2) + eeol
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
        # 顺序：英文 ghost → 英文扫色 → 日文 ghost → 日文扫色。
        # 每条 overlay 紧跟自己的 ghost（VSFilter 同层按文件顺序叠放，
        # 后画的盖在上面；也让 _sweep_verify 的「ghost 后一条即 overlay」成立）。
        ins = []
        if ov_en:
            ins.append(ov_en)
        ins.append(jp_ghost)
        if ov:
            ins.append(ov)
        for k, extra in enumerate(ins):
            out.insert(gi + 1 + k, extra)

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
