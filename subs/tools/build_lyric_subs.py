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

SONGS = {
    "mv_rnd_ed001":    "歌词翻译/mv_rnd_ed001/ed001_歌词对照.xlsx",
    "mv_rnd_ed002":    "歌词翻译/mv_rnd_ed002/ed002_歌词对照.xlsx",
    "mv_rnd_edfrau":   "歌词翻译/mv_rnd_edfrau/edfrau_歌词对照.xlsx",
    "mv_rnd_livedance": "歌词翻译/mv_rnd_livedance/livedance_歌词对照.xlsx",
    "mv_rnd_op001":    "歌词翻译/mv_rnd_op001/op001_歌词对照.xlsx",
}
VARIANTS = ["_tlonly.ass", ".ass"]  # _karaonly.ass has no rendered translation lines

# --- non-lyric interjections / vocalise (not present in the spreadsheet) -----------
VOCALISE_A = "嘟 嘟噜 嘟噜 嘟♪ 嘟 嘟噜 嘟噜 嘟♪"
VOCALISE_B = "嘟 嘟噜 嘟噜 嘟♪ 哒哩哒哩呀啊啊♪"
VOCALISE_C = "嘟嘟噜 啦啦啦啦♪"


def filler_zh(en):
    """Chinese for ASS lines the spreadsheet does not carry (scene chatter,
    on-screen interjections, vocalise).  Returns None for anything that must be
    matched against the spreadsheet."""
    if "Tu Tu Ru" in en:
        if "Da-li-da-li" in en:
            return VOCALISE_B
        if "La La La La" in en:
            return VOCALISE_C
        return VOCALISE_A
    if en == "Dance with me":
        return "和我一起跳吧"
    if en == "Everybody now!":
        return "大家一起来！"
    if en == "One more time!":
        return "再来一次！"
    if en == "Frau-tan, c'mon!":
        return "芙兰碳，来吧！"
    if en.startswith("Enako-chan"):
        return "Enako，来和我们一起跳！"
    if en.startswith("Oh man, now I really wanna dance"):
        return "糟了，我也真想跳起来……"
    if en.startswith("Ah, I'm beat"):
        return "啊，累死了……消耗的热量\\N比想象中多太多了。"
    return None


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
    ends belongs to the NEXT line), in time order.  Pre-classified filler
    dialogues own nothing.  Returns list of row-lists ([] = filler)."""
    result = []
    for d in dialogues:
        if filler[d["idx"]] is not None:
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
        filler = {d["idx"]: filler_zh(d["en"]) for d in dialogues}

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
    """Return the Chinese text for one dialogue (rows = assigned spreadsheet rows)."""
    if rows:
        return " ".join(r["zh"] for r in rows if r["zh"])
    return filler_zh(dialogue["en"])


# --- karaoke timing ----------------------------------------------------------------
def s2cs(seconds):
    """ASS \\k units are centiseconds."""
    return int(round(seconds * 100))


def karaoke_entry(dialogue, rows):
    """Per-line karaoke payload: every Chinese character gets a \\kf duration.

    \\kf units start counting from the LINE start, so any window where nothing
    is sung (before the first row, or between rows) is folded into the unit
    that is on screen during it: the lead-in joins character 1, an inter-row
    pause joins the last character of the previous row.  The visible payload is
    therefore exactly the Chinese text.  The spreadsheet carries the real sung
    time per row (start/end), so each row spans exactly its own duration.
    Inside a row, characters share that row's duration evenly (syllable time
    distributed over the Chinese text); inter-character spaces get a short
    unit so word gaps stay visible.

    Returns (payload, total_cs) or (None, 0) when there is nothing to time."""
    if not rows:
        return None, 0
    line_start = s2cs(dialogue["start"])
    units = []          # (char, cs)

    prev_end = 0
    for r in rows:
        st = s2cs(r["start"]) - line_start
        en = s2cs(r["end"]) - line_start
        zh = r["zh"]
        n = sum(1 for c in zh if not c.isspace())
        if n == 0:
            prev_end = max(prev_end, en)
            continue
        hold_first = False
        join_space_cs = 0
        if st > prev_end:
            gap = st - prev_end
            if units:
                # inter-row pause: sweep holds on the previous character.  The
                # visible join space between rows is emitted as its own unit,
                # so reserve its share from the gap instead of adding on top.
                join_space_cs = max(1, int(round(gap * 0.15)))
                units[-1] = (units[-1][0], units[-1][1] + (gap - join_space_cs))
            elif zh.lstrip():
                # lead-in: the sweep holds on character 1 until the vocal
                units.append((zh.lstrip()[0], gap))
                hold_first = True
        dur = max(n, en - st)
        # Weighted share: non-space characters split most of `dur`; spaces get
        # a short unit.  Shares normalize so the WHOLE row lands exactly on
        # `dur` (spaces consume sweep time too); the last non-space character
        # absorbs the rounding residue.
        ns_units = max(1, sum(1 for c in zh if not c.isspace()))
        sp_units = sum(1 for c in zh if c.isspace())
        sp_weight = 0.15
        weight_sum = ns_units + sp_weight * sp_units
        scale = dur / weight_sum
        alloc = [max(1, int(round(scale * (sp_weight if c.isspace() else 1))))
                 for c in zh]
        idx_ns = [i for i, c in enumerate(zh) if not c.isspace()]
        spent = sum(alloc)
        if spent != dur and idx_ns:
            alloc[idx_ns[-1]] = max(1, alloc[idx_ns[-1]] + (dur - spent))
        emit = list(zip(zh, alloc))
        if hold_first:
            # char 1's lead-holding unit is already in `units`; fold char 1's
            # own share into it so the row total stays exact
            first_share = alloc[0] if zh[0] not in (' ',) else alloc[1]
            units[-1] = (units[-1][0], units[-1][1] + first_share)
            skip = 1 if zh[0] == units[-1][0] else 0
            emit = emit[skip:]
        elif units and not zh.startswith(' '):
            # multi-row join: render_entry separates rows with a single space;
            # emit that space as its own unit, funded from the reserved gap
            units.append((' ', join_space_cs or
                          max(1, int(round(0.15 * dur / max(1, weight_sum))))))
        for c, k in emit:
            units.append((c, k))
        prev_end = max(prev_end, en)
    if not units:
        return None, 0
    total = sum(k for _, k in units)
    payload = "".join("{\\kf%d}%s" % (k, c) for c, k in units)
    return payload, total



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
        w = max(w, _font(size).getlength(seg) * st["sx"] / 100.0
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
    print("font ->", globals()["FONT_NAME"], "/", ff, " size x", globals()["SIZE_SCALE"],
          " karaoke", globals()["KARAOKE"])
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
    if not write:
        print("dry run only; pass --write to emit files.")
        return

    # ---- write build output + install ----
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for base, xlsx in SONGS.items():
        report = build_song(base, os.path.join(ROOT, xlsx))
        for suf, (lines, dialogues, tgts, _m, _v, _u, styles, playres) in report.items():
            new = list(lines)
            changed_styles = False
            for d, rows in zip(dialogues, tgts):
                zh = render_entry(d, rows)
                if zh is None:
                    raise SystemExit(f"unresolved translation line in {base}{suf}: {d['en']!r}")
                p = d["parts"]
                prefix = re.match(r"^(?:\{[^}]*\})*", p[9]).group(0)
                # bump only through the style when no override is needed, so the
                # text payload stays clean; a pinned line gets an explicit \fs.
                st = styles.get(d["style"])
                fs_override = None
                if st is not None and zh:
                    size, pinned = fit_size(zh, d, st, playres[0], globals()["SIZE_SCALE"])
                    if pinned:
                        fs_override = size
                if globals()["KARAOKE"] and rows and zh:
                    payload, total_cs = karaoke_entry(d, rows)
                    if payload:
                        zh = payload
                p[9] = prefix + zh
                if fs_override is not None:
                    # line-local size cap, in its own override block
                    p[9] = prefix + "{\\fs%g}" % round(fs_override, 1) + zh
                new[d["idx"]] = ",".join(p) + d["eol"]
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
                        new[i] = "Style: " + ",".join(fields) + ln[len(body):]
            assert len(new) == len(lines)
            out_path = os.path.join(OUT, base + suf)
            with io.open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
                fh.write("".join(new))
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
