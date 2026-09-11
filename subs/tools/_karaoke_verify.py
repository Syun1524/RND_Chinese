# -*- coding: utf-8 -*-
"""Verify the installed karaoke tracks: visible text integrity, per-line sweep
duration vs the line span, and override-block syntax."""
import io
import re
import os
import importlib.util

spec = importlib.util.spec_from_file_location(
    'b', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_lyric_subs.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
SUBS = b.SUBS
KF = re.compile(r'\{\\kf\d+\}')
STRAY = re.compile(r'\\[a-zA-Z]')

bad_payload = bad_static = checked = stray = 0
tot_delta = 0
for base, xf in b.SONGS.items():
    rep = b.build_song(base, b.ROOT + '/' + xf)
    for suf, (lines, dl, tgts, _m, _v, _u, styles, pr) in rep.items():
        inst = io.open(os.path.join(SUBS, base + suf), encoding='utf-8-sig', newline='').read().splitlines()
        for d, rows in zip(dl, tgts):
            exp = b.render_entry(d, rows)
            got_raw = inst[d['idx']].split(',', 9)[9]
            checked += 1
            if rows and exp:
                pay, tot = b.karaoke_entry(d, rows)
                pv = b.visible(KF.sub('', got_raw))
                if pv != exp:
                    bad_payload += 1
                    print('PAYLOAD TEXT MISMATCH', base + suf, d['start'])
                    print('  exp:', exp[:50])
                    print('  vis:', pv[:50])
                span = (d['end'] - d['start']) * 100
                tot_delta = max(tot_delta, abs(tot - span))
            else:
                if b.visible(got_raw) != exp:
                    bad_static += 1
                    print('STATIC MISMATCH', base + suf, d['start'], repr(exp[:40]), repr(b.visible(got_raw)[:40]))
            outside = re.sub(r'\{[^}]*\}', '', got_raw)
            if STRAY.search(outside):
                stray += 1
                print('STRAY TAG', base + suf, got_raw[:60])
print('checked', checked, 'lines; payload text mismatches:', bad_payload,
      '; static mismatches:', bad_static, '; stray tags:', stray)
print('max |sweep - span| = %d cs' % tot_delta)
