# -*- coding: utf-8 -*-
"""Final acceptance sweep across the installed karaoke tracks."""
import io
import re
import os
import importlib.util

spec = importlib.util.spec_from_file_location(
    'b', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_lyric_subs.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
SUBS = b.SUBS
BS = chr(92)
STRAY = re.compile(r'\\+[a-zA-Z]')          # any tag-ish token
TAGBLOCK = re.compile(r'\{[^}]*\}')


def kf_blocks(raw):
    """Strip kf override blocks so the visible text can be compared."""
    out = []
    i = 0
    token = '{' + BS + 'kf'
    while i < len(raw):
        if raw.startswith(token, i):
            j = raw.index('}', i)
            i = j + 1
        else:
            out.append(raw[i])
            i += 1
    return ''.join(out)


bad_vis = bad_syn = tot = 0
worst = 0
rep_all = {base: b.build_song(base, b.ROOT + '/' + xf) for base, xf in b.SONGS.items()}
for base in b.SONGS:
    for suf in b.VARIANTS:
        inst = io.open(SUBS + BS + base + suf, encoding='utf-8-sig', newline='').read().splitlines()
        lines, dl, tgts, _m, _v, _u, styles, pr = rep_all[base][suf]
        for d, rows in zip(dl, tgts):
            tot += 1
            raw = inst[d['idx']].split(',', 9)[9]
            vis = b.visible(kf_blocks(raw)).replace(BS + 'N', '')
            outside = b.visible(TAGBLOCK.sub('', raw)).replace(BS + 'N', '')
            if STRAY.search(outside.replace('\\\\', '')):
                pass
            # real stray = a tag char outside braces, ignoring the \N break
            probe = outside.replace(BS + 'N', '')
            if re.search(BS + BS + '[a-zA-Z]', probe) and not probe.endswith(BS):
                # \N already removed; any leftover tag is real
                if re.search(r'[\\][a-zA-Z]', probe):
                    bad_syn += 1
                    print('SYNTAX', base + suf, d['start'], raw[:70])
            exp = b.render_entry(d, rows)
            if rows and exp:
                pay, tcs = b.karaoke_entry(d, rows)
                if vis.replace(' ', '') != exp.replace(' ', ''):
                    bad_vis += 1
                    print('VIS', base + suf, d['start'])
                span = (d['end'] - d['start']) * 100
                worst = max(worst, abs(tcs - span))
            else:
                if vis != exp:
                    bad_vis += 1
                    print('VIS-STATIC', base + suf, d['start'])
print('lines', tot, '| visible mismatches', bad_vis, '| syntax problems', bad_syn,
      '| worst sweep delta %dcs' % worst)
