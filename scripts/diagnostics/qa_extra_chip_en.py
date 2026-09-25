# -*- coding: utf-8 -*-
"""Verify the English-layout EXTRA atlas.

The atlas is built by copying the shipping (Japanese-layout) atlas and editing
exactly five elements, so two invariants define correctness:

  1. STRUCTURE -- every element that is supposed to be kept must be byte-identical
     to the Japanese atlas (总游戏时间 / CG LIBRARY完成率 / % / TIPS数 / digit strip),
     and every separator must be byte-identical to the English original atlas.
     Byte equality catches wiping, moving and recolouring in one check, which a
     "is there any ink here" test cannot (a half-wiped label still has ink).

  2. FIT -- in each stat row, every ink column that falls inside a number's x
     range must be explained: either it is a separator sitting at that number's
     edge (the original design abuts them) or it is a failure. This is what
     catches a label left at the Japanese x, which would sit under a number.

It also confirms the Japanese layout cannot be served by this atlas (the EN
slashes land on JP's second number), which is the reason two atlases exist.
"""
import numpy as np
from PIL import Image
import os

BASE = r'D:\DATA\tran\agent tran\9.6文本外工作'
EN_ATLAS = BASE + r'\临时\cn\汉化好的\system\extra_chip_en_zh.png'
JP_ATLAS = BASE + r'\成品ing\补丁包\languagebarrier\c0data\extra_chip.png'

# The English original atlas, extracted from `-原版英文 副本\system.cpk`. It gets
# archived next to the produced atlas (repo + mirror), because the scratch dir it
# was first extracted into does not survive cleanup. Both archived copies are
# byte-identical; whichever exists is used. Keep this list ordered by preference.
EN_ORIG_CANDIDATES = [
    BASE + r'\临时\cn\汉化好的\system\data\_archive'
           r'\_source_backup_extra_chip_EN_original.png',
    BASE + r'\GitHub\RND_Chinese\图片汉化\system\data\_archive'
           r'\_source_backup_extra_chip_EN_original.png',
    BASE + r'\en_atlas_evidence\en_atlas\cpk_29_3120x3024.png',
]


def resolve_en_orig():
    for p in EN_ORIG_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit('EN original atlas not found. Looked in:\n  ' +
                     '\n  '.join(EN_ORIG_CANDIDATES))


EN_ORIG = resolve_en_orig()

S, OX = 0.66643, 157.34
ROW1 = (1846, 1882)
ROW2 = (1888, 1926)

# elements that must be carried over from the Japanese atlas unchanged
KEEP = [
    ('总游戏时间', 28, 197, ROW1),
    # The label sits at 869..1251 since the 2026-09-25 spacing fix: it was moved
    # right by 152 px so its right edge matches the originals' 1251/1249, which
    # restores the 84 px gap to the game-drawn percentage (was 236).
    ('CG LIBRARY完成率', 869, 1251, ROW1),
    ('%', 1422, 1452, ROW1),
    ('TIPS数', 27, 164, ROW2),
    ('digit strip', 1478, 1773, ROW1),
]
# elements that must equal the English original atlas
SEPS_EN = [
    (':1', 408, 413, ROW1),
    (':2', 498, 503, ROW1),
    ('/1', 315, 346, ROW2),
    ('/2', 428, 459, ROW2),
]
# the Japanese positions of the cleared elements: must now be empty.
# (row 1: 小时 / 分 / 秒 ; row 2: the two slashes)
SEPS_JP = [('小时', 343, 408, ROW1), ('分', 492, 523, ROW1),
           ('秒', 604, 636, ROW1), ('/', 260, 291, ROW2),
           ('/', 373, 404, ROW2)]

EN_NUMS = {'row1': [(372, 429), (451, 482), (509, 535)],
           'row2': [(319, 362), (389, 440), (464, 515)]}
JP_NUMS = {'row1': [(326, 379), (446, 481), (518, 553)],
           'row2': [(297, 328), (353, 404), (429, 479)]}

EDGE_TOL = 3


def a2s(x):
    return x * S + OX


def load_rgba(path):
    return np.array(Image.open(path).convert('RGBA'))


def load_ink(rgba):
    a = rgba.astype(int)
    lum = a[:, :, :3].mean(axis=2)
    return (a[:, :, 3] > 20) & (lum < 215)


def check_fit(ink, nums, title, verbose=True):
    print('=' * 78)
    print(title)
    print('=' * 78)
    ok = True
    for row, ranges in nums.items():
        band = ROW1 if row == 'row1' else ROW2
        all_ink = set()
        sub = ink[band[0]:band[1] + 1]
        for c in np.nonzero(sub.any(axis=0))[0]:
            all_ink.add(int(round(a2s(c))))

        sep_cols = set()
        for _, x0a, x1a, _b in SEPS_EN:
            if _b != band:
                continue
            s2 = ink[band[0]:band[1] + 1, x0a:x1a + 1]
            for c in np.nonzero(s2.any(axis=0))[0]:
                sep_cols.add(int(round(a2s(x0a + c))))

        for a, b in ranges:
            inside = sorted(x for x in range(a, b + 1) if x in all_ink)
            if not inside:
                continue
            unexplained = [x for x in inside if x not in sep_cols]
            explained = [x for x in inside if x in sep_cols]
            if unexplained:
                ok = False
                print('   FAIL %s number %d..%d hits ink at %s'
                      % (row, a, b, unexplained[:12]))
            elif len(explained) > EDGE_TOL:
                ok = False
                print('   FAIL %s number %d..%d meets separator over %d px'
                      % (row, a, b, len(explained)))
            elif verbose and explained:
                print('   ok   %s number %d..%d abuts separator at %s (design)'
                      % (row, a, b, explained))
    print('   => %s' % ('clean' if ok else 'problems found'))
    return ok


def main():
    en = load_rgba(EN_ATLAS)
    jp = load_rgba(JP_ATLAS)
    eo = load_rgba(EN_ORIG)
    ink = load_ink(en)

    print('=' * 78)
    print('1) STRUCTURE: kept elements byte-identical to the JP atlas')
    print('=' * 78)
    struct_ok = True
    for name, x0, x1, (y0, y1) in KEEP:
        same = bool((en[y0:y1 + 1, x0:x1 + 1] == jp[y0:y1 + 1, x0:x1 + 1]).all())
        if not same:
            diff = (np.abs(en[y0:y1 + 1, x0:x1 + 1].astype(int)
                           - jp[y0:y1 + 1, x0:x1 + 1].astype(int)).max(axis=2) > 0)
            print('   FAIL %-16s differs in %d px' % (name, diff.sum()))
        else:
            print('   ok   %-16s byte-identical' % name)
        struct_ok &= same

    print()
    print('=' * 78)
    print('2) STRUCTURE: separators byte-identical to the EN original atlas')
    print('=' * 78)
    for name, x0, x1, (y0, y1) in SEPS_EN:
        same = bool((en[y0:y1 + 1, x0:x1 + 1] == eo[y0:y1 + 1, x0:x1 + 1]).all())
        if not same:
            print('   FAIL %-4s differs from the EN original' % name)
        else:
            print('   ok   %-4s matches the EN original' % name)
        struct_ok &= same

    print()
    print('=' * 78)
    print('3) STRUCTURE: the JP element positions are now empty')
    print('=' * 78)
    # The EN separators were pasted into ranges that overlap the cleared JP
    # elements (the first colon starts where 小时 ends), so those columns are
    # excluded -- what is being checked is that the JP ink itself is gone.
    en_sep_cols = {}
    for _, x0, x1, (y0, y1) in SEPS_EN:
        en_sep_cols.setdefault((y0, y1), set()).update(range(x0, x1 + 1))
    for name, x0, x1, (y0, y1) in SEPS_JP:
        skip = en_sep_cols.get((y0, y1), set())
        keep = [c for c in range(x0, x1 + 1) if c not in skip]
        n = 0
        for c in keep:
            n += int(ink[y0:y1 + 1, c].sum())
        if n:
            print('   FAIL %-4s still has %d ink px in atlas x %d..%d (excl. the EN separators)'
                  % (name, n, x0, x1))
            struct_ok = False
        else:
            print('   ok   %-4s at atlas x %d..%d is clear' % (name, x0, x1))

    print()
    fit_en = check_fit(ink, EN_NUMS, '4) FIT: EN atlas vs EN-mode numbers')

    print()
    jp_ink = load_ink(jp)
    fit_jp = check_fit(jp_ink, JP_NUMS, '5) FIT: JP atlas vs JP-mode numbers',
                       verbose=False)

    print()
    print('=' * 78)
    print('6) the EN atlas provably breaks the JP layout (why two atlases exist)')
    print('=' * 78)
    broke = not check_fit(ink, JP_NUMS, 'EN atlas vs JP numbers', verbose=False)

    print()
    print('RESULT: structure=%s  EN fit=%s  JP fit=%s  JP-broken-by-EN=%s'
          % (struct_ok, fit_en, fit_jp, broke))
    return 0 if (struct_ok and fit_en and fit_jp and broke) else 1


raise SystemExit(main())
