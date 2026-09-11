# -*- coding: utf-8 -*-
"""Build outfit-only identification sheets, filtered by texture content hashing.

The full per-variant montage is mostly noise: a character carries a dozen textures for
face / eyes / mouth / body that every outfit shares. Hashing every embedded DDS shows
that only **3–10 textures per variant are actually unique to it** — those are the outfit.

This script recomputes that hash census and emits one sheet per character where each row
is one variant and only its unique textures are shown, at 304px, labelled. That is the
image a human can name outfits from without launching the game 61 times.

Caveat it deliberately handles: texture *slot order* is not stable across variants
(c004_070 puts the face textures first, c004_010 puts them last), so this matches by
content hash, never by index.

    python scripts/build_outfit_diff_sheets.py
    -> 成品ing/服装核对/服装对比_<char>.png   (one per multi-variant character)
    -> 成品ing/服装核对/服装对比_index.html
"""
import html
import io
import json
import os
import struct
import sys
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TILE = 304
PAD = 4
ROWLAB_W = 132
NAMECOL_W = 230     # 手写「这是什么服装」的一列：看图时直接对照着填
ROWLAB_H = 30
MAX_COLS = 10

NAME_HINT = {
    "c002": "akiho", "c003": "frau", "c004": "junna", "c013": "kou", "c018": "daru",
}


def find_dds(data):
    out, i = [], 0
    while True:
        i = data.find(b"DDS ", i)
        if i < 0:
            break
        pre = i - 4
        if pre >= 0:
            size = struct.unpack("<I", data[pre:i])[0]
            if 128 <= size <= len(data) - i:
                out.append(data[i:i + size])
        i += 4
    return out


def load_font(px):
    for c in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
              "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, px)
            except Exception:
                pass
    return ImageFont.load_default()


def main():
    out_dir = os.path.join(ROOT, "成品ing", "服装核对")
    model_dir = os.path.join(ROOT, "解包", "解包cpk的产物(日语)", "model")
    mapping = json.load(io.open(os.path.join(ROOT, "成品ing", "服装映射表.json"),
                                encoding="utf-8"))
    # 已确认的服装名（CoZ 泳装那 10 套），用于在名称列预填
    known_names = {}
    nm_path = os.path.join(out_dir, "服装名称表.json")
    if os.path.exists(nm_path):
        known_names = {k: v for k, v in
                       json.load(io.open(nm_path, encoding="utf-8")).items() if v}
    os.makedirs(out_dir, exist_ok=True)

    f_row = load_font(19)
    f_tok = load_font(15)
    f_head = load_font(26)

    summary, cards = {}, []

    for ch in sorted(mapping):
        entries = sorted(mapping[ch], key=lambda e: e["variant"])
        nv = len(entries)
        # variant -> list of (slot_index, dds_blob)
        by_variant = {}
        for e in entries:
            p = os.path.join(model_dir, "%s_%s.lkm" % (ch, e["variant"]))
            by_variant[e["variant"]] = find_dds(open(p, "rb").read())

        # content census: how many variants contain each texture
        census = Counter()
        for v, blobs in by_variant.items():
            for h in {hash(b) for b in blobs}:
                census[h] += 1

        rows = []
        for e in entries:
            v = e["variant"]
            uniq = [b for b in by_variant[v] if census[hash(b)] == 1]
            if nv == 1:                       # 单变体角色：没有"独有"概念，全展示
                uniq = by_variant[v]
            imgs = []
            for b in uniq[:MAX_COLS]:
                try:
                    im = Image.open(io.BytesIO(b))
                    im.load()
                    imgs.append(im.convert("RGB").resize((TILE, TILE), Image.LANCZOS))
                except Exception:
                    pass
            rows.append((v, e["fileId"], len(uniq), imgs))

        ncol = max((len(r[3]) for r in rows), default=1)
        ncol = max(1, min(ncol, MAX_COLS))
        W = ROWLAB_W + NAMECOL_W + ncol * (TILE + PAD) + PAD
        H = 46 + len(rows) * (TILE + PAD + ROWLAB_H) + PAD
        canvas = Image.new("RGB", (W, H), (18, 18, 22))
        dr = ImageDraw.Draw(canvas)
        title = "ROBOTICS;NOTES DaSH  服装对比  %s" % ch
        if NAME_HINT.get(ch):
            title += "  (~%s)" % NAME_HINT[ch]
        dr.text((10, 10), title, font=f_head, fill=(255, 255, 255))

        # 名称列表头 + 分隔线
        nx = ROWLAB_W + (TILE + PAD) * 0
        dr.line([(ROWLAB_W + NAMECOL_W - 8, 40), (ROWLAB_W + NAMECOL_W - 8, H - 6)],
                fill=(60, 66, 80), width=2)
        dr.text((ROWLAB_W + 6, 8), "服装名（填这里）", font=f_tok, fill=(140, 200, 255))

        for r, (v, fid, nuniq, imgs) in enumerate(rows):
            y = 46 + r * (TILE + PAD + ROWLAB_H)
            dr.text((8, y + TILE // 2 - 10), "%s_%s" % (ch, v), font=f_row,
                    fill=(255, 214, 120))
            dr.text((8, y + TILE // 2 + 14), "fileId %d · %d 张服装贴图" % (fid, nuniq),
                    font=f_tok, fill=(150, 158, 172))
            # 名称列：已确认的（CoZ 泳装那 10 套）预填，其余留空待手写
            known = known_names.get("%s_%s" % (ch, v), "")
            dr.text((ROWLAB_W + 6, y + TILE // 2 - 12), known, font=f_row,
                    fill=(120, 230, 150) if known else (90, 96, 110))
            if not known:
                dr.text((ROWLAB_W + 6, y + TILE // 2 + 14), "_________",
                        font=f_tok, fill=(80, 86, 100))
            for k, im in enumerate(imgs):
                canvas.paste(im, (ROWLAB_W + NAMECOL_W + k * (TILE + PAD), y))

        fn = "服装对比_%s.png" % ch
        canvas.save(os.path.join(out_dir, fn))
        cards.append((ch, nv, fn))
        summary[ch] = [{"variant": v, "fileId": f, "outfit_textures": n}
                       for v, f, n, _ in rows]
        print("%-6s %2d 变体 -> %s  (%dx%d)" % (ch, nv, fn, W, H))

    # ---- index ------------------------------------------------------------
    p = ["<!doctype html><meta charset='utf-8'><title>服装对比</title>",
         "<style>body{background:#141418;color:#ddd;font:15px/1.7 'Microsoft YaHei',sans-serif;"
         "margin:0;padding:28px}h1{color:#fff;font-size:22px}h2{color:#8cf;font-size:19px;"
         "margin-top:34px;border-bottom:1px solid #333;padding-bottom:6px}"
         "img{width:100%;max-width:1700px;display:block;border:1px solid #2c2c34;border-radius:6px}"
         "code{background:#222;padding:1px 5px;border-radius:3px;color:#ffd479}</style>",
         "<h1>服装对比图（只看服装贴图）</h1>",
         "<p>已按内容哈希过滤：每个变体只展示<b>它独有的贴图</b>，也就是服装本体；",
         "脸/眼睛/身体等所有变体共用的贴图已去掉。每个变体通常只剩 3~10 张，看图即可认。</p>",
         "<p>这是<b>离线认服装</b>用的。认完之后用启动器的「换装核对」下拉框选同一项进游戏确认。</p>"]
    total = sum(nv for _, nv, _ in cards if nv > 1)
    p.append("<p>需要核对的变体：<b>%d</b> 个（%d 个角色；单变体角色无其它服装可切，不需要核对）</p>"
             % (total, sum(1 for _, nv, _ in cards if nv > 1)))
    for ch, nv, fn in cards:
        if nv == 1:
            continue
        p.append("<h2>%s%s —— %d 套</h2><img src='%s'>"
                 % (ch, "  ~ %s" % NAME_HINT[ch] if NAME_HINT.get(ch) else "", nv, fn))
    for ch, nv, fn in cards:
        if nv == 1:
            p.append("<p style='color:#888'>%s（单变体，略）</p>" % ch)
    io.open(os.path.join(out_dir, "服装对比_index.html"), "w", encoding="utf-8") \
        .write("\n".join(p))
    json.dump(summary, io.open(os.path.join(out_dir, "服装贴图统计.json"), "w",
                               encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n-> %s/服装对比_index.html" % out_dir)


if __name__ == "__main__":
    main()
