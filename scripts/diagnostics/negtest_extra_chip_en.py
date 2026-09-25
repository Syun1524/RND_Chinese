# -*- coding: utf-8 -*-
"""Negative self-test for the EN-atlas QA gate.

A gate that never fails is worthless, so this deliberately corrupts the atlas
three ways and checks the QA reports each one. The QA script is copied with its
EN_ATLAS constant pointed at the corrupted file, so the real checks run.

Cases:
  A. 小时 not cleared          (the original bug)  -> labels-vs-number overlap
  B. slash1 left at the JP x   (the wrong layout)  -> label overlap
  C. an untouched label wiped  (collateral damage) -> JP-atlas comparison

For each, the QA's own final verdict line is read, not a substring of the body.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

BASE = r'D:\DATA\tran\agent tran\9.6文本外工作'
GOOD = BASE + r'\临时\cn\汉化好的\system\extra_chip_en_zh.png'
JP_ATLAS = (BASE + r'\成品ing\补丁包\languagebarrier\c0data\extra_chip.png')
QA = BASE + r'\scripts\diagnostics\qa_extra_chip_en.py'
# Scratch files go to the system temp dir: keeping them in the workspace means
# they break the moment someone tidies that directory (which is exactly what
# happened to the first version of this script).
TMPDIR = tempfile.mkdtemp(prefix='negtest_extra_chip_')
TMP = os.path.join(TMPDIR, '_negtest.png')
TMP_PY = os.path.join(TMPDIR, '_qa_neg.py')


def run_qa(path):
    src = open(QA, encoding='utf-8').read()
    src = src.replace(
        "EN_ATLAS = BASE + r'" + "\\" + "临时" + "\\" + "cn" + "\\" + "汉化好的"
        + "\\" + "system" + "\\" + "extra_chip_en_zh.png'",
        "EN_ATLAS = r'%s'" % path)
    open(TMP_PY, 'w', encoding='utf-8').write(src)
    r = subprocess.run([sys.executable, TMP_PY], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = r.stdout + r.stderr
    for line in out.splitlines():
        if line.startswith('RESULT:'):
            return line.strip(), out
    return '(no verdict line)', out


def main():
    good = np.array(Image.open(GOOD).convert('RGBA')).copy()
    jp = np.array(Image.open(JP_ATLAS).convert('RGBA')).copy()

    cases = []

    # A: restore 小时 from the JP atlas (i.e. forgot to clear it)
    a = good.copy()
    a[1840:1888, 335:415] = jp[1840:1888, 335:415]
    cases.append(('A: 小时 not cleared', a))

    # B: slash1 at the JP x instead of the EN x
    b = good.copy()
    b[1882:1932, 311:350, 3] = 0
    b[1882:1932, 255:300] = jp[1882:1932, 255:300]
    cases.append(('B: slash1 at JP x', b))

    # C: wipe the untouched CG LIBRARY label
    c = good.copy()
    c[1846:1883, 720:1000, 3] = 0
    cases.append(('C: CG label wiped', c))

    print('=== negative self-test: QA must FAIL on every case ===')
    allcaught = True
    for name, arr in cases:
        Image.fromarray(arr).save(TMP)
        verdict, out = run_qa(TMP)
        caught = 'structure=False' in verdict or 'fit=False' in verdict
        allcaught &= caught
        print('  %-26s -> %s   %s'
              % (name, 'CAUGHT' if caught else '★MISSED (gate is dead)',
                 verdict))
        for line in out.splitlines():
            if 'FAIL' in line:
                print('        %s' % line.strip()[:104])
                break

    # and the good file must still pass
    verdict, out = run_qa(GOOD)
    goodpasses = 'structure=True' in verdict and 'fit=True' in verdict
    print()
    print('  %-26s -> %s   %s'
          % ('GOOD atlas (control)', 'ok' if goodpasses else '★FALSE ALARM',
             verdict))
    print()
    ok = allcaught and goodpasses
    print('gate is %s' % ('LIVE (catches all three faults, passes the good file)'
                          if ok else 'BROKEN'))
    return 0 if ok else 1


raise SystemExit(main())
