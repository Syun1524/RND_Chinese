# -*- coding: utf-8 -*-
"""Build Chinese karaoke subtitle tracks for the 5 R;N DaSH songs.

Source of truth: 歌词翻译/mv_*/*_歌词对照.xlsx  (per-line zh translations, with times)
Templates:       <game>/languagebarrier/subs/mv_rnd_*.ass  (CoZ English tracks)

We do NOT retime anything: every visible `Dialogue: <translation*> ` line keeps its
Layer/Start/End/Style/Margins/Effect, only the text payload is swapped for Chinese and
the translation* styles are pointed at a CJK font.  Non-lyric interjections (vocalise,
"Dance with me", scene chatter) that the spreadsheet does not cover are translated from
a small explicit table.

Usage:
  python build_lyric_subs.py                 # dry run: print the mapping, write nothing
  python build_lyric_subs.py --write         # write build/ then install into the game
"""
import io
import os
import re
import sys
import glob
import json
import shutil
import datetime
import openpyxl

# Both paths are overridable so the copy shipped in the release repo
# (subs/tools/) can be pointed at a workspace without editing the file:
#   RND_ROOT = tree holding 歌词翻译/ and RND补丁英文成品原版/
#   RND_GAME = the game's languagebarrier/ directory to install into
ROOT = os.environ.get("RND_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.environ.get("RND_GAME") or \
    r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -副本\languagebarrier"
SUBS = os.path.join(GAME, "subs")
# Templates are ALWAYS the pristine CoZ English tracks: the live game directory
# holds the Chinese result of a previous run, so it must never be the input.
TEMPLATE = os.path.join(ROOT, "RND补丁英文成品原版", "languagebarrier", "subs")
OUT = os.path.join(ROOT, "歌词翻译", "build")
# Lyric font for the `translation*` styles, and the uniform size multiplier.
# These defaults ARE the delivered configuration; override per run with:
#   --font "RND Lyric SC" --font-file RNDLyricSC-Bold.ttf --size-scale 1.10
# RNDLyricSC-Bold.ttf is the renamed Noto Sans SC Bold (see make_lyric_font.py):
# Windows already registers a *variable* font as "Noto Sans SC", so keeping the
# original family name would make font matching ambiguous.
FONT_NAME = "RND Lyric SC"
FONT_FILE = "RNDLyricSC-Bold.ttf"
FONT_PATH = None      # resolved at startup, used for width measurement
SIZE_SCALE = 1.10     # uniform multiplier on the translation* style font size
KARAOKE = False       # --karaoke: per-character \kf sweep on timed lyric lines
DIM_SCALE = 0.70      # --dim: unsung-side brightness on light-base lines (1.0 = invisible)

SONGS = {
    "mv_rnd_ed001":    "歌词翻译/mv_rnd_ed001/ed001_歌词对照.xlsx",
    "mv_rnd_ed002":    "歌词翻译/mv_rnd_ed002/ed002_歌词对照.xlsx",
    "mv_rnd_edfrau":   "歌词翻译/mv_rnd_edfrau/edfrau_歌词对照.xlsx",
    "mv_rnd_livedance": "歌词翻译/mv_rnd_livedance/livedance_歌词对照.xlsx",
    "mv_rnd_op001":    "歌词翻译/mv_rnd_op001/op001_歌词对照.xlsx",
}
VARIANTS = ["_tlonly.ass", ".ass"]  # _karaonly.ass has no rendered translation lines

# per-song passes applied after the normal build (see lyric_en_pass.py)
try:
    import lyric_en_pass
    EN_PASS = {"mv_rnd_op001": lyric_en_pass.apply_pass}
except Exception as _e:                      # pragma: no cover
    print("WARNING: lyric_en_pass unavailable:", _e)
    EN_PASS = {}

# --- non-lyric interjections / vocalise (not present in the spreadsheet) -----------
def is_vocalise(dialogue):
    """The sung nonsense syllables ("Tu Tu Ru …").  CoZ ships the ROMAJI as the
    translation-layer text for these (verified in the original ASS), showing no
    localised onomatopoeia.  We keep that exactly as shipped: no Chinese mimicry
    and no sweep, so these lines read the same as the original patch."""
    return "Tu Tu Ru" in dialogue["en"]


def filler_zh(en):
    """Chinese for ASS lines the spreadsheet does not carry (scene chatter,
    on-screen interjections).  Returns None for anything that must be matched
    against the spreadsheet."""
    if en == "Dance with me":
        return "和我一起跳吧"
    if en == "Everybody now!":
        return "大家一起来！"
    if en == "One more time!":
        return "再来一次！"
    if en == "Frau-tan, c'mon!":
        return "芙劳炭，来吧！"
    if en.startswith("Enako-chan"):
        # "Enako" is CoZ's ear-transcription of a shout in the MV audio; the name
        # appears nowhere in the game's text (all encodings searched).  Ship the
        # name-free call so no unverifiable Latin name lands in a Chinese line.
        return "来和我们一起跳吧！"
    if en.startswith("Oh man, now I really wanna dance"):
        return "糟了，我也真想跳起来……"
    if en.startswith("Ah, I'm beat"):
        return "啊，累死了……消耗的热量\\N比想象中多太多了。"
    return None


# "Dance with me" is an English sung ad-lib (user confirmed it may sweep);
# the on-screen chatter lines (Everybody now / Frau-tan / Enako / Oh man /
# I'm beat) are spoken and stay static.
SINGABLE_FILLERS = ("和我一起跳吧",)


def singable_filler(zh):
    return zh in SINGABLE_FILLERS


def t2s(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def visible(text):
    return re.sub(r"\{[^}]*\}", "", text or "").strip()


def norm_en(text):
    return re.sub(r"\s+", " ", visible(text)).strip()


def load_sheet(path):
    wb = openpyxl.load_workbook(path)
    main, var = [], []
    for ws in wb.worksheets:
        is_var = "声部" in ws.title
        it = ws.iter_rows(values_only=True)
        next(it, None)
        for r in it:
            if not r or r[0] is None:
                continue
            if is_var:
                var.append(dict(start=t2s(str(r[0])), end=t2s(str(r[1])),
                                style=str(r[2] or "").strip(), zh=str(r[4] or "").strip()))
            else:
                main.append(dict(start=t2s(str(r[0])), end=t2s(str(r[1])),
                                 zh=str(r[4] or "").strip()))
    return main, var


def parse_ass(path):
    """Return (lines, dialogues, styles, (PlayResX, PlayResY)).

    `dialogues` covers the visible translation lines; `parts` excludes the line
    ending, which is kept separately so a rewrite cannot merge lines."""
    with io.open(path, "r", encoding="utf-8-sig", newline="") as fh:
        raw = fh.read()
    lines = raw.splitlines(keepends=True)
    res = re.search(r'PlayResX:\s*(\d+)', raw)
    resy = re.search(r'PlayResY:\s*(\d+)', raw)
    playres = (int(res.group(1)) if res else 1280, int(resy.group(1)) if resy else 720)
    styles = {}
    for rawln in lines:
        body = rawln.rstrip("\r\n")
        if not body.startswith("Style: "):
            continue
        f = body[7:].split(",")
        if len(f) >= 21:
            styles[f[0]] = dict(size=float(f[2]), sx=float(f[11]), sp=float(f[13]),
                                outline=float(f[16]), shadow=float(f[17]),
                                ml=float(f[19]), mr=float(f[20]))
    out = []
    for i, rawln in enumerate(lines):
        body = rawln.rstrip("\r\n")
        eol = rawln[len(body):] or "\n"
        if not body.startswith("Dialogue:"):
            continue
        parts = body.split(",", 9)
        if len(parts) != 10:
            continue
        style = parts[3].strip()
        if not style.lower().startswith("translation"):
            continue
        if not visible(parts[9]):
            continue
        out.append(dict(idx=i, start=t2s(parts[1]), end=t2s(parts[2]),
                        style=style, parts=parts, eol=eol, en=norm_en(parts[9])))
    return lines, out, styles, playres


def assign(rows, dialogues, used, filler):
    """Greedy: a lyric dialogue owns every unused row whose start falls in
    [d.start-0.6, d.end)  (half-open: a row that starts exactly when the line
    ends belongs to the NEXT line), in time order.  Pre-classified filler and
    vocalise dialogues own nothing — a "Tu Tu Ru" line must not steal the sheet
    row that belongs to the neighbouring "Aah~ Foo~↑" line.  Returns
    row-lists ([] = nothing to translate)."""
    result = []
    for d in dialogues:
        if filler[d["idx"]] is not None or is_vocalise(d):
            result.append([])
            continue
        lo, hi = d["start"] - 0.6, d["end"] - 0.05
        take = [r for r in rows if id(r) not in used and lo <= r["start"] < hi]
        take.sort(key=lambda r: r["start"])
        for r in take:
            used.add(id(r))
        result.append(take)
    return result


def build_song(base, xlsx):
    main, var = load_sheet(xlsx)
    report = {}
    for suf in VARIANTS:
        path = os.path.join(TEMPLATE, base + suf)
        lines, dialogues, styles, playres = parse_ass(path)
        # split dialogues by source family
        #  - style == 'translation'           -> main rows (greedy, grouped)
        #  - style 'translation - N' / 'Copy' -> matching var rows; if the counts line
        #    up 1:1 use order, otherwise fall back to time proximity.
        tgts = [None] * len(dialogues)
        used = set()
        filler = {d["idx"]: ("__vocalise__" if is_vocalise(d) else filler_zh(d["en"]))
                  for d in dialogues}

        # index dialogues by source bucket
        main_idx, var_groups = [], {}
        for i, d in enumerate(dialogues):
            s = d["style"]
            if s == "translation":
                main_idx.append(i)
            else:
                var_groups.setdefault(s, []).append(i)

        # main sheet -> 'translation' dialogues (grouped by containment)
        sub = [dialogues[i] for i in main_idx]
        taken = assign(main, sub, used, filler)
        for i, t in zip(main_idx, taken):
            tgts[i] = t

        # var sheet -> variant styles (match each translation line to the nearest
        # unused var row; prefer rows carrying the same style name, since the ASS
        # 'translation - Copy' style has no matching row in every sheet).
        for style, idxs in var_groups.items():
            same = [r for r in var if r["style"] == style]
            other = [r for r in var if r["style"] != style]
            cand = same + other
            for i in idxs:
                d = dialogues[i]
                if filler[d["idx"]] is not None:
                    tgts[i] = []
                    continue
                best, bd = None, 9e9
                for r in cand:
                    if id(r) in used:
                        continue
                    dd = min(abs(r["start"] - d["start"]), abs(r["end"] - d["end"]))
                    if dd < bd:
                        best, bd = r, dd
                if best is not None and bd <= 0.8:
                    used.add(id(best))
                    tgts[i] = [best]
                else:
                    tgts[i] = []
        report[suf] = (lines, dialogues, tgts, main, var, used, styles, playres)
    return report


def render_entry(dialogue, rows):
    """Return the text this dialogue should show: the sheet's Chinese for timed
    lyric rows, CoZ's own ROMAJI for the sung vocalise (kept verbatim — the line
    is left untouched at build time), else the mapped filler."""
    if rows:
        return " ".join(r["zh"] for r in rows if r["zh"])
    if is_vocalise(dialogue):
        return visible(dialogue["parts"][9])
    return filler_zh(dialogue["en"])


# --- karaoke: left-to-right sweep locked to the JP syllable timeline ---------------
def s2cs(seconds):
    """ASS timing in centiseconds."""
    return int(round(seconds * 100))


def parse_kanji_timelines(path):
    r"""Syllable timelines from the combined track's karaoke comments, on the
    Kanji AND romaji layers: (start_cs, end_cs, [\k durations]).  Both layers
    carry the same melody; the vocalise segments ("Tu Tu Ru", "Dance with me")
    live on the romaji layer only, so it must be included."""
    BS = chr(92)
    KT = re.compile(re.escape(BS) + r'k(?:f|o)?(\d+)')
    out = []
    for ln in io.open(path, encoding='utf-8-sig', newline='').read().splitlines():
        if not ln.startswith('Comment:'):
            continue
        f = ln.rstrip().split(',', 9)
        if len(f) < 10:
            continue
        style = f[3].strip().lower()
        if not (style.startswith('kanji') or style.startswith('romaji')):
            continue
        if 'karaoke' not in f[8]:
            continue
        ks = [int(x) for x in KT.findall(f[9])]
        if not ks:
            continue
        out.append((s2cs(t2s(f[1])), s2cs(t2s(f[2])), ks))
    return out


def _nearest_timeline(t0, timelines, tol):
    best = None
    for t in timelines:
        if best is None or abs(t[0] - t0) < abs(best[0] - t0):
            best = t
    if best is None or abs(best[0] - t0) > tol:
        return None
    return best


def row_bounds(row, timelines, line_start):
    """Cumulative syllable boundaries (cs rel. to line start) for one sheet row,
    rescaled to land exactly on the row's sung window.  None when the Japanese
    timeline for that row is missing (falls back to even sweep)."""
    best = _nearest_timeline(s2cs(row["start"]), timelines, 5)
    if best is None:
        return None
    rs, re_, ks = s2cs(row["start"]) - line_start, s2cs(row["end"]) - line_start, best[2]
    raw = [0]
    acc = 0
    for k in ks:
        acc += k
        raw.append(acc)
    span = max(1, raw[-1])
    return [rs + (re_ - rs) * b / span for b in raw]


def interp(bounds, f):
    M = len(bounds) - 1
    x = min(max(f, 0.0), 1.0) * M
    j = min(int(x), M - 1)
    return bounds[j] + (bounds[j + 1] - bounds[j]) * (x - j)


def kf_overlay(dialogue, rows, timelines):
    r"""Payload for the sweep overlay: the Chinese line where each character
    carries a \kf duration read off the Japanese syllable timeline (via its
    text-position fraction), so the fill sweeps fast where the melody is fast
    and holds through held notes and inter-row pauses.

    Returns (payload, total_cs)."""
    BS = chr(92)
    K = BS + 'kf'
    line_start = s2cs(dialogue["start"])
    units = []
    prev_end = None
    for r in rows:
        zh = r["zh"]
        if not zh:
            continue
        rs = s2cs(r["start"]) - line_start
        re_ = s2cs(r["end"]) - line_start
        bounds = row_bounds(r, timelines, line_start)
        if bounds is None:
            bounds = [rs + (re_ - rs) * i / len(zh) for i in range(len(zh) + 1)]
        if prev_end is not None:
            # the join space between two rows: sweep sits there for the pause
            # (emit it even when the rows butt together, or the overlay text
            # loses a column and drifts against the ghost)
            units.append((' ', max(1, rs - prev_end)))
        L = len(zh)
        for i, c in enumerate(zh):
            d = interp(bounds, (i + 1) / L) - interp(bounds, i / L)
            if prev_end is None and i == 0:
                d += rs                     # lead-in: hold until the vocal
            units.append((c, max(1, int(round(d)))))
        prev_end = max(prev_end or 0, re_)
    if not units:
        return None, 0
    payload = "".join("{%s%d}%s" % (K, k, c) for c, k in units)
    return payload, sum(k for _, k in units)


def sweep_colors(prefix):
    """(secondary, primary_override) for the sweep overlay, borrowing CoZ's
    karaoke palette: their flash fills pure WHITE over the dim ghost, so on
    dark-base lines the sung side goes FFFFFF while the unsung side stays the
    line's own colour (seamless against the ghost).  On light-base lines
    (white/near-white fills) white-on-white would be invisible, so the unsung
    side dims instead and the sweep reveals the normal colour.  DIM_SCALE sets
    how far down that unsung tone goes (higher = brighter = softer contrast)."""
    BS = chr(92)
    m = re.search(re.escape(BS) + r'c&H([0-9A-Fa-f]{6})&', prefix)
    fill = m.group(1).upper() if m else 'FFFFFF'
    b, g, r = int(fill[0:2], 16), int(fill[2:4], 16), int(fill[4:6], 16)
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    if lum <= 0.85:
        return fill, 'FFFFFF'          # dark base: sweep into the flash white
    dim = '%02X%02X%02X' % (int(b * globals()["DIM_SCALE"]),
                            int(g * globals()["DIM_SCALE"]),
                            int(r * globals()["DIM_SCALE"]))
    return dim, None                   # light base: dim unsung, normal sung



# --- font metrics for the overflow guard ------------------------------------------
_FCACHE = {}
_NB = chr(92) + "N"


def _font(size):
    from PIL import ImageFont
    key = round(size, 2)
    if key not in _FCACHE:
        _FCACHE[key] = ImageFont.truetype(FONT_PATH, max(1, int(round(size))))
    return _FCACHE[key]


def _line_width(text, size, st):
    """Rendered width in PlayRes units, worst segment after \\N breaks."""
    w = 0.0
    for seg in text.split(_NB):
        if not seg:
            continue
        # 可见翻译样式的 ScaleX 在构建时统一归一到 100（见样式循环），
        # 所以宽度按 100 计算，不能用模板里原始的 80/110。
        w = max(w, _font(size).getlength(seg) * 100.0 / 100.0
                + st["sp"] * max(0, len(seg) - 1))
    return w + st["outline"] * 2 + st["shadow"]


def _margin_r(dialogue, st):
    """ASS treats a 0 margin field as 'use the style margin'."""
    mr = dialogue["parts"][6].strip()
    v = float(mr) if mr else 0.0
    return v if v > 0 else st["mr"]


def _anchor_x(dialogue, st):
    pre = dialogue["parts"][9].split('}')[0]
    m = re.search(r'\\pos\((-?[\d.]+),', pre)
    if m:
        return float(m.group(1))
    ml = dialogue["parts"][5].strip()
    v = float(ml) if ml else 0.0
    return v if v > 0 else st["ml"]


def fit_size(text, dialogue, st, playres_w, bump, margin=6.0):
    """Scale a line by `bump`, but never past the right margin box.  Returns
    (size, pinned) where `size` is the absolute font size to emit."""
    size = st["size"] * bump
    avail = playres_w - _anchor_x(dialogue, st) - _margin_r(dialogue, st) - margin
    if avail <= 0:
        return size, False
    w = _line_width(text, size, st)
    if w <= avail:
        return size, False
    return size * avail / w, True


def main():
    write = "--write" in sys.argv
    timelines = {}                       # song -> JP syllable timelines
    if "--font" in sys.argv:
        globals()["FONT_NAME"] = sys.argv[sys.argv.index("--font") + 1]
    if "--font-file" in sys.argv:
        globals()["FONT_FILE"] = sys.argv[sys.argv.index("--font-file") + 1]
    global FONT_PATH
    ff = globals()["FONT_FILE"]
    FONT_PATH = next((c for c in (os.path.join(ROOT, "fonts", ff),
                                  os.path.join(GAME, "fonts", ff),
                                  os.path.join(SUBS, "fonts", ff))
                      if os.path.exists(c)), None)
    if FONT_PATH is None:
        raise SystemExit("font file not found for metrics: " + ff)
    if "--size-scale" in sys.argv:
        globals()["SIZE_SCALE"] = float(sys.argv[sys.argv.index("--size-scale") + 1])
    if "--karaoke" in sys.argv:
        globals()["KARAOKE"] = True
    if "--dim" in sys.argv:
        globals()["DIM_SCALE"] = float(sys.argv[sys.argv.index("--dim") + 1])
    print("font ->", globals()["FONT_NAME"], "/", ff, " size x", globals()["SIZE_SCALE"],
          " karaoke", globals()["KARAOKE"], " dim", globals()["DIM_SCALE"])
    os.makedirs(OUT, exist_ok=True)
    unresolved_total = 0
    pinned_total = []
    for base, xlsx in SONGS.items():
        report = build_song(base, os.path.join(ROOT, xlsx))
        for suf, (lines, dialogues, tgts, main_rows, var_rows, used, styles, playres) in report.items():
            print("=" * 100)
            print(base + suf, "| dialogues", len(dialogues), "| PlayRes", playres)
            for d, rows in zip(dialogues, tgts):
                zh = render_entry(d, rows)
                mark = ""
                if zh is None:
                    mark = "   <<< UNRESOLVED"
                    unresolved_total += 1
                elif zh:
                    st = styles.get(d["style"], dict(size=45, sx=80, sp=0, outline=2, shadow=2, ml=25, mr=25))
                    size, pinned = fit_size(zh, d, st, playres[0], globals()["SIZE_SCALE"])
                    if pinned:
                        mark = "   [pinned %.1f]" % size
                        pinned_total.append((base + suf, d["start"], round(size, 1), zh[:34]))
                        st = None
                src = "+".join(f"{r['start']:.1f}" for r in rows) or "FILLER"
                print(f"  {d['start']:8.2f}-{d['end']:8.2f} {d['style']:16} "
                      f"[{src:18}] {d['en'][:42]:44} => {zh}{mark}")
            left = [r for r in main_rows if id(r) not in used]
            if left:
                print("  -- unconsumed main-sheet rows:",
                      ", ".join(f"{r['start']:.2f}:{r['zh'][:12]}" for r in left))
    print("\nUNRESOLVED:", unresolved_total)
    if pinned_total:
        print("PINNED (kept inside margin box):")
        for row in pinned_total:
            print("   ", row)
    if globals()["KARAOKE"]:
        # load the JP syllable timelines once (from each song's combined track)
        for base in SONGS:
            timelines[base] = parse_kanji_timelines(
                os.path.join(TEMPLATE, base + ".ass"))
        n = sum(len(v) for v in timelines.values())
        print("syllable timelines loaded: %d Japanese lines across %d songs"
              % (n, len(timelines)))
    if not write:
        print("dry run only; pass --write to emit files.")
        return

    # ---- write build output + install ----
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for base, xlsx in SONGS.items():
        report = build_song(base, os.path.join(ROOT, xlsx))
        for suf, (lines, dialogues, tgts, _m, _v, _u, styles, playres) in report.items():
            new = list(lines)
            extras = {}                      # ghost idx -> overlay lines to insert
            changed_styles = False
            for d, rows in zip(dialogues, tgts):
                if not rows and is_vocalise(d):
                    continue                 # leave CoZ's romaji line untouched
                zh = render_entry(d, rows)
                if zh is None:
                    raise SystemExit(f"unresolved translation line in {base}{suf}: {d['en']!r}")
                p = d["parts"]
                prefix = re.match(r"^(?:\{[^}]*\})*", p[9]).group(0)
                # CoZ 给英文用了横向/纵向缩放（如 ed002 的 \fscy70 压扁、样式
                # ScaleX=110 拉宽）。中文是方块字，压/拉都会显得又胖又扁，
                # 所以可见中文行里的行内 \fscx/\fscy 一律去掉，用字体本色。
                prefix = re.sub(re.escape(chr(92)) + r'fs(?:cx|cy)[\d.]+', '',
                               prefix)
                # bump only through the style when no override is needed, so the
                # text payload stays clean; a pinned line gets an explicit \fs.
                st = styles.get(d["style"])
                fs_override = None
                if st is not None and zh:
                    size, pinned = fit_size(zh, d, st, playres[0], globals()["SIZE_SCALE"])
                    if pinned:
                        fs_override = size
                p[9] = prefix + zh
                if fs_override is not None:
                    # line-local size cap, in its own override block
                    p[9] = prefix + "{\\fs%g}" % round(fs_override, 1) + zh
                new[d["idx"]] = ",".join(p) + d["eol"]
                # sweep overlay: a copy of the line that fills left-to-right at
                # the speed of the Japanese syllable timeline.  Colours borrow
                # CoZ's karaoke palette (see sweep_colors): dark-base lines sweep
                # into their flash white; light-base lines sweep out of a dim.
                # Sheet rows sweep as-is.  A filler sweeps only when it is
                # actually SUNG (see singable_filler): the "Tu Tu Ru" vocalise
                # and "Dance with me" are; pure chatter stays static.
                if globals()["KARAOKE"] and zh:
                    if rows:
                        sweep_rows = rows
                    elif (singable_filler(zh)
                          and _nearest_timeline(s2cs(d["start"]), timelines[base], 35)):
                        sweep_rows = [{"start": d["start"], "end": d["end"], "zh": zh}]
                    else:
                        sweep_rows = None
                    payload, total_cs = (kf_overlay(d, sweep_rows, timelines[base])
                                         if sweep_rows else (None, 0))
                    if payload and total_cs:
                        sec, prim = sweep_colors(prefix)
                        tag = "{\\2c&H" + sec + "&"
                        if prim:
                            tag += "\\1c&H" + prim + "&"
                        op = list(p)
                        op[9] = (prefix + tag + "}"
                                 + (("{\\fs%g}" % round(fs_override, 1)) if fs_override else "")
                                 + payload)
                        extras[d["idx"]] = [",".join(op) + d["eol"]]
            for i, ln in enumerate(new):
                body = ln.rstrip("\r\n")
                if body.startswith("Style: "):
                    fields = body[7:].split(",")
                    if fields[0].lower().startswith("translation"):
                        if fields[1] != FONT_NAME:
                            fields[1] = FONT_NAME
                            changed_styles = True
                        if globals()["SIZE_SCALE"] != 1.0 and not fields[0].endswith("-furigana"):
                            base_size = float(fields[2])
                            fields[2] = "%g" % round(base_size * globals()["SIZE_SCALE"], 1)
                            changed_styles = True
                        # CoZ 用 ScaleX/ScaleY 把英文变形（ed002 是 110/70，横向
                        # 拉宽又纵向压扁），中文是方块字，这样会显得又胖又扁。
                        # 可见翻译样式一律恢复 100/100（宋体类字宽的 furigana
                        # 小注不动）。
                        if not fields[0].endswith("-furigana"):
                            if fields[11] != "100" or fields[12] != "100":
                                fields[11] = "100"
                                fields[12] = "100"
                                changed_styles = True
                        new[i] = "Style: " + ",".join(fields) + ln[len(body):]
            assert len(new) == len(lines)
            # interleave the sweep overlays right after their ghost lines
            out_lines = []
            for i, ln in enumerate(new):
                out_lines.append(ln)
                out_lines.extend(extras.get(i, []))
            # per-song extra pass (op001's sung-English segments: English on the
            # Japanese layer, English big + Chinese note on the Chinese layer)
            if base in EN_PASS:
                out_lines = EN_PASS[base](out_lines, styles, dialogues, tgts,
                                          timelines[base])
            out_path = os.path.join(OUT, base + suf)
            with io.open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
                fh.write("".join(out_lines))
            # install; keep exactly one pristine English rollback per track, and
            # only on the first conversion (the English templates stay in TEMPLATE
            # anyway, so repeated builds must not pile up backups)
            src = os.path.join(SUBS, base + suf)
            rollback = src + ".bak_original_en"
            if not os.path.exists(rollback):
                shutil.copy2(src, rollback)
            shutil.copy2(out_path, src)
            print("installed", base + suf, "styles_font_changed=", changed_styles)

    # font for the csri/VSFilter movie-subtitle renderer: the file must sit in
    # subs/fonts AND be listed in patchdef base.fmv.fonts, which is what
    # CriManaMod::criManaModInit feeds to AddFontResourceExA.
    ff = globals()["FONT_FILE"]
    fdst = os.path.join(SUBS, "fonts", ff)
    candidates = [os.path.join(ROOT, "fonts", ff),
                  os.path.join(GAME, "fonts", ff),
                  fdst]
    fsrc = next((c for c in candidates if os.path.exists(c)), None)
    if fsrc is None:
        raise SystemExit("font file not found (looked in project fonts/, game fonts/, subs/fonts/): " + ff)
    if os.path.abspath(fsrc) != os.path.abspath(fdst):
        shutil.copy2(fsrc, fdst)
    print("font in place: subs/fonts/" + ff)
    register_fmv_font()
    print("done; backups suffixed .bak_original_" + stamp)


def register_fmv_font():
    """Ensure FONT_FILE is in base.fmv.fonts, rewriting patchdef.json the way the
    project's other patchdef editors do: utf-8 with NO BOM, CRLF, indent 2.
    (A BOM here is not what CoZ ships and is best avoided.)"""
    path = os.path.join(GAME, "patchdef.json")
    FONT_FILE = globals()["FONT_FILE"]
    with io.open(path, "rb") as fh:
        raw = fh.read()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw.decode("utf-8-sig"))
    fonts = data["base"]["fmv"]["fonts"]
    if FONT_FILE in fonts:
        print("patchdef fmv.fonts already lists", FONT_FILE)
        changed = False
    else:
        fonts.append(FONT_FILE)
        changed = True
    out = json.dumps(data, ensure_ascii=False, indent=2).replace("\n", "\r\n")
    if changed or had_bom:
        shutil.copy2(path, path + ".bak_lyriczh_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        with io.open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
        print("registered %s in patchdef base.fmv.fonts%s"
              % (FONT_FILE, " (BOM removed)" if had_bom and not changed else ""))
    else:
        print("patchdef fmv.fonts already lists", FONT_FILE)


if __name__ == "__main__":
    main()
