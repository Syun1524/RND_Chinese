# -*- coding: utf-8 -*-
"""Derive the lyric font with a UNIQUE family name.

Why: the delivered lyric tracks request `Noto Sans SC`, but Windows already has a
*variable* font registered under exactly that family name
(C:\\Windows\\Fonts\\NotoSansSC-VF.ttf).  With two faces answering to one name,
GDI/VSFilter may pick either, and the variable one renders unpredictably.
Renaming our copy makes the match deterministic; glyphs are untouched.

input : fonts/NotoSansSC-Bold-static.ttf
output: fonts/RNDLyricSC-Bold.ttf   (family "RND Lyric SC", weight 700)
"""
import os
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "fonts", "NotoSansSC-Bold-static.ttf")
DST = os.path.join(ROOT, "fonts", "RNDLyricSC-Bold.ttf")

FAMILY = "RND Lyric SC"
SUBFAMILY = "Bold"
FULL = FAMILY + " " + SUBFAMILY
PS = "RNDLyricSC-Bold"
UNIQUE = "RND Lyric SC Bold; lyric tracks"

# Windows/legacy IDs must all agree.  Typographic IDs (16/17) are dropped so
# there is no second family name that could re-expose the original.
NAME_IDS = {
    1: FAMILY,
    2: SUBFAMILY,
    3: UNIQUE,
    4: FULL,
    6: PS,
}

font = TTFont(SRC)
name = font["name"]
name.names = [r for r in name.names if r.nameID not in (16, 17)]
for rec in list(name.names):
    if rec.nameID in NAME_IDS:
        rec.string = NAME_IDS[rec.nameID].encode("utf-16-be") \
            if rec.platformID == 3 else NAME_IDS[rec.nameID].encode("latin-1", "replace")
font["OS/2"].usWeightClass = 700
font.save(DST)
print("wrote", DST)

chk = TTFont(DST, lazy=True)["name"]
for i in (1, 2, 4, 6, 16, 17):
    print("  name%-3d %s" % (i, chk.getDebugName(i)))
