# -*- coding: utf-8 -*-
r"""最终确认 op001：日文层逐字行与原版一致；中文三处英文段左对齐（\pos(63,1000)）。"""
import io
import re
import sys

BS = chr(92)
G = (r'D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -副本'
     r'\languagebarrier\subs\mv_rnd_op001.ass')
E = (r'D:\DATA\tran\agent tran\9.6文本外工作\RND补丁英文成品原版'
     r'\languagebarrier\subs\mv_rnd_op001.ass')
VIS = re.compile(r'\{[^}]*\}')


def vis(t):
    return VIS.sub('', t or '').strip()


# 宽度：VSFilter/GDI 把 \fs 当**字面高度**，实际 em = fs × upem/(winAsc+winDesc)。
# 不换算会高估 ~45%，锚点算得太靠右 → 英文整行右移（实机截图发现过）。
_FONT = (r'D:\DATA\tran\agent tran\9.6文本外工作\fonts\RNDLyricSC-Bold.ttf')
_fac = [None]


def _en_width(text, fs):
    from PIL import ImageFont
    if _fac[0] is None:
        from fontTools.ttLib import TTFont
        tf = TTFont(_FONT, lazy=True)
        _fac[0] = tf['head'].unitsPerEm / float(
            tf['OS/2'].usWinAscent + tf['OS/2'].usWinDescent)
    px = max(1, int(round(fs * _fac[0])))
    return ImageFont.truetype(_FONT, px).getlength(text)


def t2s(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def jp(p):
    out = []
    for l in io.open(p, encoding='utf-8-sig', newline='').read().splitlines():
        if not (l.startswith('Dialogue:') and ',Kanji,' in l):
            continue
        f = l.split(',', 9)
        if vis(f[9]) and not vis(f[9]).isascii():
            out.append((f[1], f[2], vis(f[9])))
    return sorted(out)


a, b = jp(G), jp(E)
print('日文层逐字行: 产物 %d / 原版 %d  完全一致=%s' % (len(a), len(b), a == b))
print()
print('中文层三处英文段:')
for ln in io.open(G, encoding='utf-8-sig', newline='').read().splitlines():
    if not ln.startswith('Dialogue:'):
        continue
    f = ln.split(',', 9)
    if len(f) < 10 or f[3].strip() != 'translation':
        continue
    if BS + 'N' in f[9] and any(k in f[9] for k in ('New World', 'God will', 'Once again')):
        # 英文左缘必须落在中文译文列(x=63)。排版用 \an2 锚在英文行中点，
        # 所以 左缘 = 锚点 - 英文宽/2；宽度按 GDI 的实际 em 量
        # （\fs 是字面高度：em = fs × upem/(winAsc+winDesc)，见 lyric_en_pass）。
        centered = 'an2' in f[9] and 'pos(960' not in f[9]
        ax = float(re.search(r'pos\(([\d.]+),', f[9]).group(1))
        en_txt = vis(f[9].split(BS + 'N')[-1])
        left = ax - _en_width(en_txt, 74.8) / 2.0
        ok_left = abs(left - 63.0) <= 1.0
        txt = vis(f[9]).replace(BS + 'N', ' / ')
        sys.stdout.write('  %s-%s  小注居中=%s  英文左缘=%.1f(目标63) %s\n     %s\n'
                         % (f[1], f[2], centered, left, 'OK' if ok_left else 'BAD', txt[:66]))
print()
print('竖排英文行数（右列 1818）:')
n = sum(1 for l in io.open(G, encoding='utf-8-sig', newline='').read().splitlines()
        if l.startswith('Dialogue:') and ',Kanji,' in l and 'pos(1818,' in l and vis(l.split(',', 9)[9]).isascii())
print('  ', n, '条')
