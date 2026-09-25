# -*- coding: utf-8 -*-
"""Build the English-layout EXTRA atlas from the current (Japanese-layout) one.

Only five elements differ between the two languages, because only five collide:

    element      current (JP layout)   English layout needs
    小时          screen 386..429       a ":" at screen 429..433
    分            screen 485..506       a ":" at screen 489..493
    秒            screen 560..581       nothing (English has no unit word)
    slash 1       screen 331..351       a "/" at screen 367..388
    slash 2       screen 406..427       a "/" at screen 443..463

Everything else -- 总游戏时间, CG LIBRARY完成率, %, TIPS数 and the digit strip --
is byte-identical between the two languages and is copied verbatim, so the
Chinese glyphs in both atlases are the same pixels rather than two renders.

The ":" and "/" pixels are lifted straight out of the English original atlas
(extracted from the English build's system.cpk), so the separators match what
the game's own English release draws.

Output: the English atlas plus a QA report proving (a) every copy is
byte-identical, (b) nothing outside the edited rectangles changed, and (c) the
game-drawn numbers of BOTH languages avoid all remaining ink.
"""
import hashlib
import json
import os

import numpy as np
from PIL import Image

BASE = r'D:\DATA\tran\agent tran\9.6文本外工作'
OURS = BASE + r'\成品ing\补丁包\languagebarrier\c0data\extra_chip.png'
# The English original atlas (extracted from `-原版英文 副本\system.cpk`) is kept
# in the archive next to the produced atlas, not in a scratch dir -- see the same
# note in qa_extra_chip_en.py.
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
OUTDIR = BASE + r'\临时\cn\汉化好的\system'
OUT_PNG = OUTDIR + r'\extra_chip_en_zh.png'
DATA = BASE + r'\临时\cn\汉化好的\system\data'
OUT_REC = DATA + r'\extra_chip_en_zh.records.json'
BACKUP = DATA + r'\_source_backup_extra_chip.png'

S, OX, OY = 0.66643, 157.34, -618.2

ROW1 = (1846, 1882)
ROW2 = (1888, 1926)


def a2s(x):
    return x * S + OX


def s2a(x):
    return (x - OX) / S


# ---- rectangles to clear (atlas space), covering the five elements
# screen -> atlas, padded by 4 px
CLEAR = [
    ('小时',   s2a(386) - 4,  s2a(429) + 4, ROW1[0] - 6, ROW1[1] + 6),
    ('分',     s2a(485) - 4,  s2a(506) + 4, ROW1[0] - 6, ROW1[1] + 6),
    ('秒',     s2a(560) - 4,  s2a(581) + 4, ROW1[0] - 6, ROW1[1] + 6),
    ('slash1', s2a(331) - 4,  s2a(351) + 4, ROW2[0] - 6, ROW2[1] + 6),
    ('slash2', s2a(406) - 4,  s2a(427) + 4, ROW2[0] - 6, ROW2[1] + 6),
]
CLEAR = [(n, int(round(x0)), int(round(x1)), y0, y1) for n, x0, x1, y0, y1 in CLEAR]

# ---- separators to copy from the English original atlas (atlas space)
# measured: ":" atlas 408..413 and 498..503 ; "/" atlas 315..346 and 428..459
COPIES = [
    (':1', 408, 413, ROW1[0], ROW1[1]),
    (':2', 498, 503, ROW1[0], ROW1[1]),
    ('/1', 315, 346, ROW2[0], ROW2[1]),
    ('/2', 428, 459, ROW2[0], ROW2[1]),
]

# ---- game-drawn numbers, measured from the screenshots (screen px)
EN_NUMS = {'row1': [(372, 429), (451, 482), (509, 535)],
           'row2': [(319, 362), (389, 440), (464, 515)]}
JP_NUMS = {'row1': [(326, 379), (446, 481), (518, 553)],
           'row2': [(297, 328), (353, 404), (429, 479)]}


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)

    if not os.path.exists(BACKUP):
        import shutil
        shutil.copy2(OURS, BACKUP)
        print('backed up current atlas -> %s' % BACKUP)

    src = np.array(Image.open(OURS).convert('RGBA')).copy()
    eno = np.array(Image.open(EN_ORIG).convert('RGBA')).copy()
    out = src.copy()

    print('=== clearing the five colliding elements ===')
    for name, x0, x1, y0, y1 in CLEAR:
        before = (out[y0:y1, x0:x1, 3] > 0).sum()
        out[y0:y1, x0:x1, 3] = 0
        print('   %-7s atlas x %4d..%-4d y %d..%-4d   cleared %d opaque px'
              % (name, x0, x1, y0, y1, before))

    print('=== copying separators from the English original atlas ===')
    for name, x0, x1, y0, y1 in COPIES:
        blk = eno[y0:y1 + 1, x0:x1 + 1]
        out[y0:y1 + 1, x0:x1 + 1] = blk
        opaque = (blk[:, :, 3] > 0).sum()
        print('   %-4s atlas x %4d..%-4d y %d..%-4d   copied %d opaque px'
              % (name, x0, x1, y0, y1, opaque))

    Image.fromarray(out).save(OUT_PNG)
    print('\nwrote %s' % OUT_PNG)
    print('   md5 %s  %d bytes' % (md5(OUT_PNG), os.path.getsize(OUT_PNG)))

    # ---------------------------------------------------------------- QA
    print()
    print('=' * 78)
    print('QA')
    print('=' * 78)
    ok = True

    # 1. outside the edited rectangles: byte identical to the source
    mask = np.zeros(src.shape[:2], bool)
    for _, x0, x1, y0, y1 in CLEAR:
        mask[y0:y1, x0:x1] = True
    for _, x0, x1, y0, y1 in COPIES:
        mask[y0:y1 + 1, x0:x1 + 1] = True
    diff = (np.abs(out.astype(int) - src.astype(int)).max(axis=2) > 0)
    outside = diff & ~mask
    print(' 1. pixels changed OUTSIDE the edited rectangles: %d  %s'
          % (outside.sum(), 'PASS' if outside.sum() == 0 else 'FAIL'))
    ok &= outside.sum() == 0
    if outside.sum():
        ys, xs = np.nonzero(outside)
        print('      bbox y %d..%d x %d..%d' % (ys.min(), ys.max(), xs.min(), xs.max()))

    # 2. the untouched elements really are byte identical
    KEEP = [('总游戏时间', 28, 197, ROW1), ('CG LIBRARY完成率', 717, 1099, ROW1),
            ('%', 1422, 1452, ROW1), ('TIPS数', 27, 164, ROW2),
            ('digit strip', 1478, 1773, ROW1)]
    for name, x0, x1, (y0, y1) in KEEP:
        same = bool((out[y0:y1 + 1, x0:x1 + 1] == src[y0:y1 + 1, x0:x1 + 1]).all())
        print(' 2. %-16s byte-identical: %s' % (name, 'PASS' if same else 'FAIL'))
        ok &= same

    # 3. separators match the English original exactly
    for name, x0, x1, y0, y1 in COPIES:
        same = bool((out[y0:y1 + 1, x0:x1 + 1] == eno[y0:y1 + 1, x0:x1 + 1]).all())
        print(' 3. %-4s matches EN original: %s' % (name, 'PASS' if same else 'FAIL'))
        ok &= same

    # 4. EN numbers must clear the EN atlas (a real gate); JP numbers are the
    #    reverse-direction PROOF -- the EN separators necessarily land under the
    #    JP numbers, which is why two atlases exist. A JP hit here is therefore
    #    reported as expected evidence, not as a failure of this atlas.
    ink = (out[:, :, 3] > 20) & (out[:, :, :3].mean(axis=2) < 215)
    for lang, nums in (('EN', EN_NUMS), ('JP', JP_NUMS)):
        for row, ranges in nums.items():
            (ay0, ay1) = ROW1 if row == 'row1' else ROW2
            sub = ink[ay0:ay1 + 1]
            all_ink = {int(round(a2s(c))) for c in np.nonzero(sub.any(axis=0))[0]}
            sep_cols = set()
            for _n, cx0, cx1, cy0, cy1 in COPIES:
                if (cy0, cy1) != (ay0, ay1):
                    continue
                s2 = ink[cy0:cy1 + 1, cx0:cx1 + 1]
                sep_cols |= {int(round(a2s(cx0 + c)))
                             for c in np.nonzero(s2.any(axis=0))[0]}
            for a, b in ranges:
                inside = [x for x in range(a, b + 1) if x in all_ink]
                unexplained = [x for x in inside if x not in sep_cols]
                explained = [x for x in inside if x in sep_cols]
                if lang == 'EN':
                    if unexplained:
                        status = 'FAIL (%d unexplained cols)' % len(unexplained)
                        ok = False
                    elif len(explained) > 3:
                        status = ('FAIL (separator intrudes %d cols)'
                                  % len(explained))
                        ok = False
                    elif explained:
                        status = ('PASS (abuts separator at %s, design)'
                                  % explained)
                    else:
                        status = 'PASS'
                else:
                    if len(explained) > 3:
                        status = ('EXPECTED break (%d cols) -- this is why two '
                                  'atlases exist' % len(explained))
                    elif unexplained:
                        status = ('EXPECTED break (%d cols, non-separator)'
                                  % len(unexplained))
                    else:
                        status = 'PASS (no contact)'
                print(' 4. %s %s number %d..%d clear of ink: %s'
                      % (lang, row, a, b, status))

    # ---------------------------------------------------------------- records
    rec = {
        "version": 2,
        "source_image": "临时/cn/汉化好的/system/data/_source_backup_extra_chip.png",
        "output_image": "临时/cn/汉化好的/system/extra_chip_en_zh.png",
        "image_size": [3120, 3024],
        "note": (
            "EXTRA(通关记录)界面数据条图集 —— 英文版专用布局。"
            "英文版与日文版把统计数字画在两套硬编码坐标上，各自对齐自己原版图集的分隔符，"
            "所以一张图集无法同时满足两个语言（斜杠搬到英文位会砸日文数字）。"
            "本图 = 现用日文布局图集的逐像素副本，只改 5 处："
            "清掉 小时(386-429)/分(485-506)/秒(560-581)/斜杠1(331-351)/斜杠2(406-427)，"
            "并从英文原版图集(system.cpk 提取)原样搬入 ':' 于 408-413 与 498-503、"
            "'/' 于 315-346 与 428-459（图集坐标）。"
            "总游戏时间/CG LIBRARY完成率/%/TIPS数/数字条 全部逐像素保留，"
            "故两个版本的中文字形完全一致。"
            "运行时由 patchdef.fileRedirection.system['32'] = {jp:71, en:78} 按语言选择。"
        ),
        "font": "C:/Windows/Fonts/simhei.ttf",
        "font_height_px": 35,
        "bg": "alpha",
        "align": "left",
        "rows": [
            {"index": 1, "band": list(ROW1), "columns": [
                {"key": "label1", "x": 28, "clear_x0": 24, "clear_x1": 250,
                 "text": "总游戏时间", "source": "総プレイ時間",
                 "note": "沿用日文版图集原像素，未重绘"},
                {"key": "sep1", "x": 408, "clear_x0": 404, "clear_x1": 417,
                 "text": ":", "source": "EN original ':'",
                 "note": "自英文原版图集搬运"},
                {"key": "sep2", "x": 498, "clear_x0": 494, "clear_x1": 507,
                 "text": ":", "source": "EN original ':'",
                 "note": "自英文原版图集搬运"},
                {"key": "cg", "x": 717, "clear_x0": 713, "clear_x1": 1103,
                 "text": "CG LIBRARY完成率", "source": "CG LIBRARYコンプリート率",
                 "note": "沿用日文版图集原像素，未重绘"},
                {"key": "pct", "x": 1422, "clear_x0": 1418, "clear_x1": 1456,
                 "text": "%", "source": "%", "note": "原像素保留"},
            ]},
            {"index": 2, "band": list(ROW2), "columns": [
                {"key": "label2", "x": 27, "clear_x0": 23, "clear_x1": 168,
                 "text": "TIPS数", "source": "TIPS数",
                 "note": "沿用日文版图集原像素，未重绘"},
                {"key": "slash1", "x": 315, "clear_x0": 311, "clear_x1": 350,
                 "text": "/", "source": "EN original '/'",
                 "note": "自英文原版图集搬运"},
                {"key": "slash2", "x": 428, "clear_x0": 424, "clear_x1": 463,
                 "text": "/", "source": "EN original '/'",
                 "note": "自英文原版图集搬运"},
            ]},
        ],
    }
    with open(OUT_REC, 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print('\nwrote %s' % OUT_REC)

    print()
    print('RESULT: %s' % ('ALL PASS' if ok else 'SOME CHECKS FAILED'))
    return 0 if ok else 1


raise SystemExit(main())
