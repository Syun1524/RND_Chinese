# -*- coding: utf-8 -*-
"""Standalone timing/visible-integrity test for karaoke_entry (no inline heredoc
escaping pain)."""
import importlib.util
import os

spec = importlib.util.spec_from_file_location(
    'b', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_lyric_subs.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
KF = '{' + chr(92) + 'kf'
# strip kf override blocks: split on '{\kf<n>}' tokens


def strip_kf(payload):
    out = []
    i = 0
    while i < len(payload):
        if payload.startswith(KF, i):
            j = payload.index('}', i)
            i = j + 1
        else:
            out.append(payload[i])
            i += 1
    return ''.join(out)


rep = b.build_song('mv_rnd_ed001', b.ROOT + '/歌词翻译/mv_rnd_ed001/ed001_歌词对照.xlsx')
lines, dl, tgts, m, v, u, styles, pr = rep['.ass']
d, rows = dl[0], tgts[0]
pay, tot = b.karaoke_entry(d, rows)
span = (d['end'] - d['start']) * 100
print('line1: total=%d span=%d delta=%+d' % (tot, span, tot - span))
print('visible==expected:', strip_kf(pay) == b.render_entry(d, rows))
print('head:', pay[:52])

worst = 0
mismatch = 0
for base, xf in b.SONGS.items():
    rep = b.build_song(base, b.ROOT + '/' + xf)
    for suf, (lines, dl, tgts, _m, _v, _u, styles, pr) in rep.items():
        for d, rows in zip(dl, tgts):
            if not rows:
                continue
            pay, tot = b.karaoke_entry(d, rows)
            if pay is None:
                continue
            span = (d['end'] - d['start']) * 100
            worst = max(worst, abs(tot - span))
            if strip_kf(pay) != b.render_entry(d, rows):
                mismatch += 1
                print('VIS MISMATCH', base + suf, d['start'])
print('all timed lines: max |total-span|=%d cs, visible mismatches=%d' % (worst, mismatch))
