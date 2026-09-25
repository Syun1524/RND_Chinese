# -*- coding: utf-8 -*-
"""Gate: the CG LIBRARY完成率 label must sit at the original design's spacing.

Why this exists
---------------
The label is baked into the atlas; the percentage number is drawn by the game at
a fixed x. The originals leave ~84 px between them:

    JP original `コンプリート率` ends 1251 -> number starts 1335  (gap 84)
    EN original `Complete Rate`  ends 1249 -> number starts 1335  (gap 86)

Our translation `完成率` is 152 px narrower than `コンプリート率`. With the label
anchored at the original's left edge, the label ended at 1099 and the gap grew to
236 px -- the label looked detached from its own number (user report
2026-09-25). The fix moves the whole label right by 152 px so its right edge is
1251 again, restoring the original gap.

This gate pins all three facts, because none of the other gates can see them:
  * the gap to the game-drawn number is the original ~84 px (not too wide)
  * the label has not been pushed into the number (not too narrow)
  * the label clears the 秒 glyph on its left (no crowding there either)

It also verifies the move was a PIXEL MOVE, not a re-render: the Latin run
`CG LIBRARY` must be byte-identical to the pristine original atlas's same run
shifted by exactly 152 px. A re-render would silently change the letter spacing
and no other gate would notice.
"""
import os
import sys

import numpy as np
from PIL import Image

BASE = r'D:\DATA\tran\agent tran\9.6文本外工作'
PKG = BASE + r'\成品ing\补丁包\languagebarrier\c0data'

# Pristine JP atlas as shipped by the game (extracted from system.cpk). Prefer
# the archived copy that travels with the deliverable.
PRISTINE_CANDIDATES = [
    BASE + r'\en_atlas_evidence\gapcheck\jp_pristine_3120x3024.png',
    BASE + r'\临时\cn\汉化好的\system\data\_archive'
           r'\_source_backup_extra_chip_JP_original.png',
]
EN_ORIG_CANDIDATES = [
    BASE + r'\临时\cn\汉化好的\system\data\_archive'
           r'\_source_backup_extra_chip_EN_original.png',
    BASE + r'\GitHub\RND_Chinese\图片汉化\system\data\_archive'
           r'\_source_backup_extra_chip_EN_original.png',
]

ROW1 = (1846, 1882)
SHIFT = 152                  # the applied right-shift, in atlas px
LABEL_L = 869                # label ink after the shift
LABEL_R = 1251               # == the originals' right edge
NUM_L = 1335                 # leftmost x the game-drawn percentage can occupy
SEC_R = 636                  # 秒 right edge (label's left neighbour)
GAP_ORIGINAL = 84            # NUM_L - LABEL_R, i.e. the original design's gap
GAP_TOL = 6                  # a few px of slack; the point is "not 236"


def resolve(cands, what):
    for p in cands:
        if os.path.exists(p):
            return p
    raise SystemExit('%s not found. Looked in:\n  %s'
                     % (what, '\n  '.join(cands)))


def ink(a):
    a = a.astype(int)
    return (a[:, :, 3] > 20) & (a[:, :, :3].mean(axis=2) < 215)


def label_span(a):
    """Ink span of the CG label, excluding the % glyph and the digit strip."""
    m = ink(a)
    cols = np.nonzero(m[ROW1[0]:ROW1[1] + 1].any(axis=0))[0]
    cols = [int(c) for c in cols if 700 <= c <= 1410]
    return (min(cols), max(cols)) if cols else (None, None)


def main():
    jp = np.array(Image.open(os.path.join(PKG, 'extra_chip.png')).convert('RGBA'))
    en = np.array(Image.open(os.path.join(PKG, 'extra_chip_en.png')).convert('RGBA'))
    pristine = np.array(Image.open(resolve(PRISTINE_CANDIDATES,
                                           'pristine JP atlas')).convert('RGBA'))
    en_orig = np.array(Image.open(resolve(EN_ORIG_CANDIDATES,
                                          'EN original atlas')).convert('RGBA'))

    ok = True
    print('=' * 78)
    print('CG LIBRARY完成率 label spacing (both atlases)')
    print('=' * 78)

    # ---- 1. the originals' own gap, as the reference we are matching
    for tag, arr in (('JP original', pristine), ('EN original', en_orig)):
        lo, hi = label_span(arr)
        print('  %-12s label %d..%d -> gap to number %d'
              % (tag, lo, hi, NUM_L - hi))
    ref_lo, ref_hi = label_span(pristine)
    ref_gap = NUM_L - ref_hi

    # ---- 2. both shipped atlases sit at the same spacing
    for tag, arr in (('extra_chip', jp), ('extra_chip_en', en)):
        lo, hi = label_span(arr)
        gap = NUM_L - hi
        print()
        print('  %-14s label %d..%d' % (tag, lo, hi))
        print('       gap to number %d (original %d, before fix 236)'
              % (gap, ref_gap))
        if abs(gap - ref_gap) > GAP_TOL:
            print('       FAIL gap %d is not the original %d (+-%d)'
                  % (gap, ref_gap, GAP_TOL))
            ok = False
        else:
            print('       ok  gap matches the original design')
        if hi >= NUM_L:
            print('       FAIL label overlaps the game-drawn number')
            ok = False
        if lo <= SEC_R:
            print('       FAIL label crowds 秒 (ends %d)' % SEC_R)
            ok = False

    # ---- 3. the move was a pixel move, not a re-render
    print()
    print('  pixel-move proof (label Latin run vs the pristine atlas)')
    # `CG LIBRARY` = the label's Latin part; take the span the original uses,
    # shifted, and require byte equality with the pristine atlas's same span.
    lat_x0, lat_x1 = 713, 993          # original Latin run
    a = jp[ROW1[0]:ROW1[1] + 1, lat_x0 + SHIFT:lat_x1 + 1 + SHIFT]
    b = pristine[ROW1[0]:ROW1[1] + 1, lat_x0:lat_x1 + 1]
    same = bool((a == b).all())
    print('       %s  CG LIBRARY byte-identical after +%d px shift: %s'
          % ('ok ' if same else 'FAIL', SHIFT, same))
    ok &= same

    # ---- 4. the old position must be empty (no ghost of the moved label)
    print()
    vac = jp[ROW1[0]:ROW1[1] + 1, lat_x0:lat_x0 + SHIFT, 3]
    n = int((vac > 0).sum())
    print('       %s  old position x%d..%d vacated (opaque px %d)'
          % ('ok ' if n == 0 else 'FAIL', lat_x0, lat_x0 + SHIFT - 1, n))
    ok &= n == 0

    print()
    print('RESULT: label_gap=%s' % ok)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
