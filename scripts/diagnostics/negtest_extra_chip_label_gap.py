# -*- coding: utf-8 -*-
"""Negative self-test for the label-gap gate.

A gate that never fails is worthless, so this deliberately breaks the label
position three ways and checks qa_extra_chip_label_gap.py reports each one.

Cases (each is a mistake that could plausibly ship):
  A. label not moved at all      (the original bug: gap back to 236)
  B. label moved too far         (pushed into the game-drawn number)
  C. label re-rendered, not moved (letter spacing silently changed)

For each, the gate's own final verdict line is read -- never a substring of the
body, since words like "FAIL" also appear in passing output.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

BASE = r'D:\DATA\tran\agent tran\9.6文本外工作'
PKG = BASE + r'\成品ing\补丁包\languagebarrier\c0data'
QA = BASE + r'\scripts\diagnostics\qa_extra_chip_label_gap.py'

ROW1 = (1846, 1882)
SHIFT = 152
LAT_X0, LAT_X1 = 713, 993


def run_gate(pkg_dir):
    """Run the gate against a (possibly corrupted) package dir."""
    src = open(QA, encoding='utf-8').read()
    src = src.replace("PKG = BASE + r'\\成品ing\\补丁包\\languagebarrier\\c0data'",
                      "PKG = r'%s'" % pkg_dir)
    tmp_py = os.path.join(pkg_dir, '_qa_label_gap_neg.py')
    open(tmp_py, 'w', encoding='utf-8').write(src)
    r = subprocess.run([sys.executable, tmp_py], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = r.stdout + r.stderr
    m = re.search(r'^RESULT: label_gap=(\w+)', out, re.M)
    return (m.group(1) if m else '(no verdict)'), out


def main():
    tmp = tempfile.mkdtemp(prefix='negtest_label_gap_')
    good_jp = os.path.join(PKG, 'extra_chip.png')
    good_en = os.path.join(PKG, 'extra_chip_en.png')

    def stage(jp_arr=None, en_arr=None):
        d = tempfile.mkdtemp(prefix='pkg_', dir=tmp)
        if jp_arr is None:
            shutil.copy2(good_jp, os.path.join(d, 'extra_chip.png'))
        else:
            Image.fromarray(jp_arr).save(os.path.join(d, 'extra_chip.png'))
        if en_arr is None:
            shutil.copy2(good_en, os.path.join(d, 'extra_chip_en.png'))
        else:
            Image.fromarray(en_arr).save(os.path.join(d, 'extra_chip_en.png'))
        return d

    jp = np.array(Image.open(good_jp).convert('RGBA'))
    pristine = np.array(Image.open(
        BASE + r'\en_atlas_evidence\gapcheck\jp_pristine_3120x3024.png'
    ).convert('RGBA'))

    y0, y1 = ROW1
    cases = []

    # A. not moved: put the label back where it used to be (713..1101)
    a = jp.copy()
    span = jp[y0:y1 + 1, LAT_X0 + SHIFT:LAT_X1 + 1 + SHIFT].copy()
    a[y0:y1 + 1, LAT_X0 + SHIFT:LAT_X1 + 1 + SHIFT] = 0
    a[y0:y1 + 1, LAT_X0:LAT_X1 + 1] = span
    cases.append(('A: label not moved (gap 236 again)', a))

    # B. moved too far right: +80 px beyond the design position
    b = jp.copy()
    over = 80
    b[y0:y1 + 1, LAT_X0 + SHIFT:LAT_X1 + 1 + SHIFT] = 0
    b[y0:y1 + 1, LAT_X0 + SHIFT + over:LAT_X1 + 1 + SHIFT + over] = span
    cases.append(('B: moved %d px too far (into the number)' % over, b))

    # C. re-rendered instead of moved: replace the Latin run with the pristine
    #    atlas's run drawn at the ORIGINAL x (so the glyphs differ by a 1px
    #    horizontal jitter -- exactly what a re-render produces).
    c = jp.copy()
    run = pristine[y0:y1 + 1, LAT_X0:LAT_X1 + 1].copy()
    c[y0:y1 + 1, LAT_X0 + SHIFT:LAT_X1 + 1 + SHIFT] = 0
    c[y0:y1 + 1, LAT_X0 + SHIFT - 1:LAT_X1 + SHIFT] = run
    cases.append(('C: re-rendered, not moved (1px jitter)', c))

    # D. moved correctly but the old position was never cleared (ghost). This is
    #    a realistic slip -- clearing the old spot is a separate step -- and only
    #    the vacated check can see it.
    d = jp.copy()
    d[y0:y1 + 1, LAT_X0:LAT_X1 + 1] = pristine[y0:y1 + 1, LAT_X0:LAT_X1 + 1]
    cases.append(('D: ghost left at the old position', d))

    # E. moved LEFT instead of right: label crowds 秒. Only the crowding check
    #    can see this (the pixel proof compares against a +152 shift, so it fires
    #    too -- but the crowding line is the one that names the real problem).
    e = jp.copy()
    e[y0:y1 + 1, LAT_X0 + SHIFT:LAT_X1 + 1 + SHIFT] = 0
    e[y0:y1 + 1, LAT_X0 - 60:LAT_X1 + 1 - 60] = span
    cases.append(('E: moved left, crowds 秒', e))

    # F. THE most realistic slip: the label is two records columns -- the Latin
    #    run is pixel-moved, the Chinese 完成率 is re-drawn at its own ink anchor.
    #    Drift only the Chinese and the label reads as two separated pieces.
    #    Shifted RIGHT so the Latin comparison window stays pristine: the pixel
    #    proof must still PASS and only the gap check may fire -- which is what
    #    proves the gap check is alive rather than riding on the pixel proof.
    #    The Chinese span is MEASURED, not guessed: the two halves sit ~7 px apart
    #    (Latin ends 1142, Chinese starts 1149), so a hand-picked boundary silently
    #    eats a Latin glyph and the pixel proof fires too, masking the real check.
    f = jp.copy()
    m = ((jp[:, :, 3] > 20) & (jp[:, :, :3].mean(axis=2) < 215))[y0:y1 + 1]
    cols = np.nonzero(m.any(axis=0))[0]
    cols = [int(c) for c in cols if 1100 <= c <= 1260]
    gaps = [(cols[i], cols[i + 1]) for i in range(len(cols) - 1)
            if cols[i + 1] - cols[i] > 5]
    cn_x0 = gaps[-1][1] if gaps else cols[0]
    cn_x1 = max(cols)
    print('  (case F uses the measured Chinese span %d..%d)' % (cn_x0, cn_x1))
    cn = jp[y0:y1 + 1, cn_x0:cn_x1 + 1].copy()
    f[y0:y1 + 1, cn_x0:cn_x1 + 1] = 0
    f[y0:y1 + 1, cn_x0 + 60:cn_x1 + 1 + 60] = cn
    cases.append(('F: Chinese drifted 60px right', f))

    print('=== negative self-test: the label-gap gate must FAIL on each case ===')
    allcaught = True
    independent = False
    for name, arr in cases:
        d2 = stage(jp_arr=arr)
        verdict, out = run_gate(d2)
        caught = verdict == 'False'
        allcaught &= caught
        print('  %-40s -> %s   RESULT: label_gap=%s'
              % (name, 'CAUGHT' if caught else '★MISSED (gate is dead)',
                 verdict))
        # show every failing check, so it is visible WHICH invariant fired
        fails = [l.strip()[:100] for l in out.splitlines() if 'FAIL' in l]
        for line in fails[:4]:
            print('        %s' % line)
        if not fails:
            print('        (no FAIL line printed -- gate reported False silently)')
        # case F must trip a positional check WITHOUT the pixel proof
        if name.startswith('F:') and caught and not any('byte-identical' in l
                                                        for l in fails):
            independent = True
        shutil.rmtree(d2, ignore_errors=True)

    # and the real shipped files must pass
    d = stage()
    verdict, out = run_gate(d)
    goodpasses = verdict == 'True'
    print()
    print('  %-40s -> %s   RESULT: label_gap=%s'
          % ('GOOD atlases (control)', 'ok' if goodpasses else '★FALSE ALARM',
             verdict))
    shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)

    print()
    ok = allcaught and goodpasses and independent
    if not independent:
        print('★ the gap/crowding checks never fired on their own -- every case '
              'was caught by the pixel proof instead, so they may be dead.')
    print('gate is %s' % ('LIVE (catches all six faults incl. a split label, '
                          'and passes the good files)' if ok else 'BROKEN'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
