# -*- coding: utf-8 -*-
"""最终确认 op001：日文层逐字行与原版一致；中文三处英文段居中、无残留 pos。"""
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
        centered = BS + 'an2' in f[9] and '960' in f[9]
        clean = 'pos(63,' not in f[9]
        txt = vis(f[9]).replace(BS + 'N', ' / ')
        sys.stdout.write('  %s-%s  居中=%s  无残留pos=%s\n     %s\n'
                         % (f[1], f[2], centered, clean, txt[:66]))
print()
print('竖排英文行数（右列 1818）:')
n = sum(1 for l in io.open(G, encoding='utf-8-sig', newline='').read().splitlines()
        if l.startswith('Dialogue:') and ',Kanji,' in l and 'pos(1818,' in l and vis(l.split(',', 9)[9]).isascii())
print('  ', n, '条')
