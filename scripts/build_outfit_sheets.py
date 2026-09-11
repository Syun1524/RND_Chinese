# -*- coding: utf-8 -*-
"""Dump the textures embedded in every character .lkm and build identification sheets.

Each .lkm is a chunked container holding raw DDS (DXT1/DXT5) blobs, each preceded by
a little-endian uint32 giving the blob's total size:

    <uint32 size> "DDS " <124-byte header> <compressed pixels>

`size` counts from the "DDS " magic, i.e. 128 + pixel data. A 2048x2048 DXT1 blob is
0x00200080 = 2097280 bytes, which is what the files actually contain.

Output (default `成品ing/服装核对/`):

  sheets/variant/<char>_<variant>.png   one montage per outfit, all its textures
  sheets/grid/<char>.png                texture-index x variant grid (对比用: 同一槽位
                                        在各变体间的差异就是换装差异)
  index.html                            browser for both views
  服装核对表.json                        placeholder -> 待填名字的记录表

Textures are addressed by their *slot index* (order inside the .lkm). The slot order is
stable per character, so slot k of every variant is the same body part — that is what
makes the grid view useful for spotting which variant is which outfit.
"""
import argparse
import html
import io
import json
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# characters whose name leaked into a motion file name (c002_010_akiho, c003_070_frau, ...)
NAME_HINT = {
    "c002": "akiho",
    "c003": "frau",
    "c004": "junna",
    "c013": "kou",
    "c018": "daru",
}

TILE = 256          # tile size in the per-variant montage
GRID_TILE = 128     # tile size in the cross-variant grid
GRID_COLS = 24      # texture slots shown in the grid


def log(*a):
    print(*a)
    sys.stdout.flush()


def find_dds(data):
    """Yield (offset, size, blob) for every '<uint32 size>"DDS "' record in `data`."""
    out = []
    i = 0
    while True:
        i = data.find(b"DDS ", i)
        if i < 0:
            break
        pre = i - 4
        if pre >= 0:
            size = struct.unpack("<I", data[pre:i])[0]
            if 128 <= size <= len(data) - i:
                out.append((i, size, data[i:i + size]))
        i += 4
    return out


def load_font(px):
    for cand in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
                 "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(cand):
            try:
                return ImageFont.truetype(cand, px)
            except Exception:
                pass
    return ImageFont.load_default()


def montage(tiles, tile, cols, font, label_with_index=True):
    """tiles: list of (index, PIL.Image). Returns a new montage image."""
    rows = (len(tiles) + cols - 1) // cols
    pad = 2
    lab = 16
    W = cols * (tile + pad) + pad
    H = rows * (tile + pad + lab) + pad
    canvas = Image.new("RGB", (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(canvas)
    for k, (idx, im) in enumerate(tiles):
        r, c = divmod(k, cols)
        x = pad + c * (tile + pad)
        y = pad + r * (tile + pad + lab)
        canvas.paste(im, (x, y))
        if label_with_index:
            dr.text((x + 2, y + tile + 1), "#%d" % idx, font=font, fill=(190, 190, 200))
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unpacked", default=os.path.join(ROOT, "解包", "解包cpk的产物(日语)"))
    ap.add_argument("--mapping", default=os.path.join(ROOT, "成品ing", "服装映射表.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "成品ing", "服装核对"))
    ap.add_argument("--only", default=None, help="只处理某个角色，如 c002")
    args = ap.parse_args()

    model_dir = os.path.join(args.unpacked, "model")
    mapping = json.load(io.open(args.mapping, encoding="utf-8"))
    if args.only:
        mapping = {k: v for k, v in mapping.items() if k == args.only}

    svar = os.path.join(args.out, "sheets", "variant")
    sgrid = os.path.join(args.out, "sheets", "grid")
    for d in (svar, sgrid):
        os.makedirs(d, exist_ok=True)

    f_tile = load_font(13)
    f_tag = load_font(20)

    table = {}
    cards = []

    for ch in sorted(mapping):
        log("=== %s ===" % ch)
        per_variant = []          # (variant, fileId, [PIL tiles])
        for entry in sorted(mapping[ch], key=lambda e: e["variant"]):
            v = entry["variant"]
            fid = entry["fileId"]
            path = os.path.join(model_dir, "%s_%s.lkm" % (ch, v))
            data = open(path, "rb").read()
            blobs = find_dds(data)
            tiles = []
            for k, (off, size, blob) in enumerate(blobs):
                try:
                    im = Image.open(io.BytesIO(blob))
                    im.load()
                    im = im.convert("RGB").resize((TILE, TILE), Image.LANCZOS)
                except Exception as e:
                    log("    ! %s_%s #%d 解码失败 %s" % (ch, v, k, e))
                    continue
                tiles.append((k, im))
            per_variant.append((v, fid, len(blobs), tiles))
            log("  %s_%s  fileId=%d  贴图 %d 张   %.1f MB"
                % (ch, v, fid, len(blobs), os.path.getsize(path) / 1e6))

            sheet = montage(tiles, TILE, 6, f_tile)
            # caption bar with the placeholder id
            cap = Image.new("RGB", (sheet.width, 34), (12, 12, 16))
            ImageDraw.Draw(cap).text(
                (8, 6), "%s  变体 %s   fileId %d   贴图 %d 张"
                % (ch, v, fid, len(blobs)), font=f_tag, fill=(240, 240, 245))
            combined = Image.new("RGB", (sheet.width, sheet.height + 34), (12, 12, 16))
            combined.paste(cap, (0, 0))
            combined.paste(sheet, (0, 34))
            fn = "%s_%s.png" % (ch, v)
            combined.save(os.path.join(svar, fn))
            table.setdefault(ch, []).append({
                "variant": v, "fileId": fid, "textures": len(blobs),
                "sheet": "sheets/variant/" + fn, "name": "",
            })

        # cross-variant grid: rows = variants, cols = texture slot
        rows = [(v, fid, tiles) for v, fid, n, tiles in per_variant]
        ncol = min(GRID_COLS, max((len(t) for _, _, t in rows), default=1))
        lab_w, lab_h = 150, 26
        pad = 2
        W = lab_w + ncol * (GRID_TILE + pad) + pad
        H = lab_h + len(rows) * (GRID_TILE + pad + 14) + pad
        g = Image.new("RGB", (W, H), (22, 22, 26))
        dr = ImageDraw.Draw(g)
        for c in range(ncol):
            dr.text((lab_w + c * (GRID_TILE + pad) + 3, 6), "#%d" % c,
                    font=f_tile, fill=(200, 200, 210))
        for r, (v, fid, tiles) in enumerate(rows):
            y = lab_h + r * (GRID_TILE + pad + 14)
            dr.text((6, y + GRID_TILE // 2 - 8), "%s_%s" % (ch, v),
                    font=f_tile, fill=(240, 220, 120))
            for k, im in tiles[:ncol]:
                x = lab_w + k * (GRID_TILE + pad)
                g.paste(im.resize((GRID_TILE, GRID_TILE), Image.LANCZOS), (x, y))
        g.save(os.path.join(sgrid, "%s.png" % ch))
        cards.append(ch)

    # ---- index.html -------------------------------------------------------
    def esc(s):
        return html.escape(str(s))

    parts = ["<!doctype html><meta charset='utf-8'>",
             "<title>R;N DaSH 服装核对</title>",
             "<style>body{background:#141418;color:#ddd;font:14px/1.6 'Microsoft YaHei',sans-serif;margin:0;padding:24px}",
             "h1{font-size:22px;color:#fff}h2{font-size:18px;color:#8cf;margin-top:36px;border-bottom:1px solid #333;padding-bottom:6px}",
             ".v{display:inline-block;vertical-align:top;margin:0 14px 20px 0;background:#1c1c22;border:1px solid #2c2c34;border-radius:6px;padding:8px}",
             ".v img{display:block;width:900px;max-width:100%;image-rendering:auto}",
             ".v .lab{font-weight:bold;color:#ffd479;margin-bottom:6px}",
             "table{border-collapse:collapse}td,th{border:1px solid #333;padding:2px 6px;font-size:12px}",
             "th{background:#222;color:#9cf}a{color:#8cf}",
             "</style>",
             "<h1>R;N DaSH 服装核对表</h1>",
             "<p>每张图是一套模型的全部内嵌贴图（2048×2048 DXT），已缩到 256px。",
             "同一角色各变体的<b>贴图槽位顺序一致</b>，所以「贴图 #k 在不同变体间的差异」就是换装差异 —— "
             "先看下面的横向对照图（行=变体，列=槽位），认出哪一行是什么服装，再回到上面看细节。</p>"]

    for ch in cards:
        hint = NAME_HINT.get(ch)
        parts.append("<h2>%s%s <span style='color:#888;font-weight:normal;font-size:13px'>"
                     "（%d 套）</span></h2>"
                     % (esc(ch), "  ~ %s" % esc(hint) if hint else "", len(table[ch])))
        gname = "sheets/grid/%s.png" % ch
        if os.path.exists(os.path.join(args.out, gname)):
            parts.append("<p><a href='%s'>横向对照图 %s</a>（行=变体，列=贴图槽位）</p>"
                         % (esc(gname), esc(ch)))
        for e in table[ch]:
            parts.append("<div class='v'><div class='lab'>%s 变体 %s &nbsp; fileId %d &nbsp; %d 张贴图"
                         "</div><a href='%s'><img src='%s'></a></div>"
                         % (esc(ch), esc(e["variant"]), e["fileId"], e["textures"],
                            esc(e["sheet"]), esc(e["sheet"])))

    with io.open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    with io.open(os.path.join(args.out, "服装核对表.json"), "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=1)

    log("")
    log("完成 -> %s" % args.out)
    log("  index.html / 服装核对表.json / sheets/variant/*.png / sheets/grid/*.png")


if __name__ == "__main__":
    main()
