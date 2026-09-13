# -*- coding: utf-8 -*-
"""Acceptance sweep v3: pair each expected lyric line with a ghost line by TEXT
(not by order), then require its overlay to share the window+text.  Robust to
inserted lines (op001 English pass)."""
import io
import os
import re
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    'b', os.path.join(_here, 'build_lyric_subs.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
SUBS = b.SUBS
BS = chr(92)


def t2s(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


bad = []
pairs = 0
for base, xf in b.SONGS.items():
    rep = b.build_song(base, b.ROOT + '/' + xf)
    for suf in b.VARIANTS:
        lines, dl, tgts, _m, _v, _u, styles, pr = rep[suf]
        inst = io.open(SUBS + BS + base + suf, encoding='utf-8-sig', newline='').read().splitlines()
        tr = []
        for ln in inst:
            if not ln.startswith('Dialogue:'):
                continue
            f = ln.rstrip().split(',', 9)
            if len(f) < 10 or not f[3].strip().lower().startswith('translation'):
                continue
            txt = b.visible(f[9]).replace(BS + 'N', '')
            if not txt and 'kf' not in f[9]:
                continue
            tr.append((f, txt, 'kf' in f[9]))
        mn = lambda s: s.replace(' ', '')
        for d, rows in zip(dl, tgts):
            exp = b.render_entry(d, rows)
            if not exp:
                continue
            expn = mn(exp.replace(BS + 'N', ''))
            gi = next((i for i, (f, txt, kf) in enumerate(tr)
                       if not kf and mn(txt) == expn), None)
            if gi is None:
                bad.append((base + suf, d['start'], 'no ghost for', expn[:22]))
                continue
            gf = tr[gi][0]
            ov = tr[gi + 1] if gi + 1 < len(tr) else None
            if ov and ov[2]:
                if ov[0][1] != gf[1] or ov[0][2] != gf[2]:
                    bad.append((base + suf, d['start'], 'overlay window differs'))
                elif mn(ov[1]) != expn:
                    bad.append((base + suf, d['start'], 'overlay text', mn(ov[1])[:22]))
                else:
                    pairs += 1
                    span = (t2s(ov[0][2]) - t2s(ov[0][1])) * 100
                    if sum(int(x) for x in re.findall(r'kf(\d+)', ov[0][9])) > span + 60:
                        bad.append((base + suf, d['start'], 'sweep overshoot'))
            else:
                # static lines are EXPECTED to have no overlay: the vocalise
                # (CoZ romaji) and the spoken chatter
                is_voc = 'Tu Tu Ru' in d['en']
                is_chat = (not rows) and (not b.singable_filler(exp)) and (not is_voc)
                if is_voc or is_chat:
                    continue
                bad.append((base + suf, d['start'], 'overlay missing', expn[:22]))
print('pairs verified:', pairs, '| problems:', len(bad))
for x in bad[:24]:
    print('  ', x)
