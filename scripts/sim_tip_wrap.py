# -*- coding: utf-8 -*-
"""Offline replica of semiTokeniseSc3String + processSc3TokenList (wrap part).

Mirrors LanguageBarrier_rndchs_mysource/LanguageBarrier/GameText.cpp so a wrap
change can be regression-tested against every TIPS entry before compiling.
Reads the deployed enscript + charset + font metrics, so it sees exactly the
bytes and advances the game will see.
"""
import argparse, glob, json, os, sys
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG = os.path.join(ROOT, '成品ing', '补丁包', 'languagebarrier')

# --- mirrors isNoLineStartChar / isNoLineEndChar / isWideGlyphChar ---
NO_START = '。，、．：；？！）〕］｝〉》」』】”’…‥ー々ぁぃぅぇぉっゃゅょァィゥェォッャュョ・ヽヾゝゞ～－／％＞＜＝＋'
NO_END = '（〔［｛〈《「『【“‘＜'
def is_wide(c):
    o = ord(c)
    return (0x1100 <= o <= 0x115F) or (0x2E80 <= o <= 0xA4CF) or \
           (0xAC00 <= o <= 0xD7A3) or (0xF900 <= o <= 0xFAFF) or \
           (0xFE30 <= o <= 0xFE6F) or (0xFF00 <= o <= 0xFF60) or \
           (0xFFE0 <= o <= 0xFFE6)

class Wrap:
    def __init__(self, patchdef, font_path):
        self.cs = patchdef['base']['charset']
        self.SPACE_PX = patchdef['base']['spaceWidthPixels']
        self.CJK = patchdef['base'].get('cjkLineBreak', False)
        ft = TTFont(font_path)
        self.upem = ft['head'].unitsPerEm
        self.cmap = ft.getBestCmap()
        self.hmtx = ft['hmtx']
        # glyph id 0 is forced to spaceWidthPixels by TextRendering::Init
        self._cache = {0: self.SPACE_PX}

    def adv(self, g, size=32):
        if g == 0:
            return self.SPACE_PX
        if g >= len(self.cs):
            return size
        k = (g, size)
        if k in self._cache:
            return self._cache[k]
        gg = self.cmap.get(ord(self.cs[g]))
        v = round(self.hmtx[gg][0] * size / self.upem) if gg else size
        self._cache[k] = v
        return v

    # ---- semiTokeniseSc3String ----
    def tokenise(self, glyphs, line_length, size=32):
        words = []
        w = {'s': 0, 'e': None, 'cost': 0, 'sw': False}
        prev = None
        hist = []
        for i, g in enumerate(glyphs):
            cur = self.cs[g] if g < len(self.cs) else ''
            if g in (0, 63):                      # full/halfwidth space
                w['e'] = i - 1
                words.append(dict(w))
                w = {'s': i, 'e': None, 'cost': self.adv(g, size), 'sw': True}
                hist = []
                prev = cur
                continue
            width = self.adv(g, size)
            has_content = i > (w['s'] + (1 if w['sw'] else 0))
            brk = w['cost'] + width > line_length
            if self.CJK and has_content and prev is not None:
                if not (prev in NO_START or cur in NO_END) and (is_wide(prev) or is_wide(cur)):
                    brk = True
            # push-out: never strand punctuation at the start of a line
            if brk and self.CJK and cur in NO_START and hist:
                k = len(hist) - 1
                while k >= 0 and hist[k][2] in NO_START:
                    k -= 1
                if k >= 0:
                    moved = sum(h[1] for h in hist[k:])
                    newstart = hist[k][0]
                    w['e'] = newstart - 1
                    w['cost'] -= moved
                    words.append(dict(w))
                    w = {'s': newstart, 'e': None, 'cost': moved, 'sw': False}
                    hist = hist[k:]
                    brk = False
            if brk:
                w['e'] = i - 1
                words.append(dict(w))
                w = {'s': i, 'e': None, 'cost': 0, 'sw': False}
                hist = []
            w['cost'] += width
            hist.append((i, width, cur))
            prev = cur
        w['e'] = len(glyphs) - 1
        words.append(dict(w))
        return words

    # ---- processSc3TokenList (wrap/emit part) ----
    def layout(self, glyphs, line_length, size=32):
        lines = [[]]
        cur = 0
        for w in self.tokenise(glyphs, line_length, size):
            if cur == 0 and w['sw']:
                wc = w['cost'] - self.SPACE_PX
            else:
                wc = w['cost']
            if cur + wc > line_length:
                if cur != 0 and w['sw']:
                    wc -= self.SPACE_PX
                lines.append([])
                cur = 0
            s = w['s'] + 1 if (cur == 0 and w['sw']) else w['s']
            for i in range(s, w['e'] + 1):
                g = glyphs[i]
                if g == 0 and i == w['s'] and cur == 0:
                    continue
                lines[-1].append(g)
                cur += self.adv(g, size)
        return lines

    def text(self, glyphs):
        return ''.join(self.cs[g] if g < len(self.cs) else '?' for g in glyphs)


def entries(buf, minlen=6):
    out = []
    for p in buf.split(b'\xff'):
        if len(p) < 4:
            continue
        gs, i, ok = [], 0, True
        while i < len(p):
            c = p[i]
            if c & 0x80:
                if i + 1 >= len(p):
                    ok = False
                    break
                gs.append(((c & 0x7f) << 8) | p[i + 1])
                i += 2
            else:
                ok = False
                break
        if ok and len(gs) >= minlen:
            out.append(gs)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--patchdef', default=os.path.join(PKG, 'patchdef.json'))
    ap.add_argument('--font', default=os.path.join(PKG, 'fonts', 'NotoSansCJKsc-Regular.otf'))
    ap.add_argument('--enscript', default=os.path.join(PKG, 'enscript'))
    ap.add_argument('--report', default=None)
    a = ap.parse_args()

    patchdef = json.load(open(a.patchdef, encoding='utf-8-sig'))
    line_len = patchdef['base']['tipReimplementationLineLength']
    size = patchdef['base']['tipReimplementationGlyphSize']
    W = Wrap(patchdef, a.font)

    files = sorted(glob.glob(os.path.join(a.enscript, '*.msb')))
    tot_lines = viol = 0
    fill = []
    worst = []
    for f in files:
        for gs in entries(open(f, 'rb').read()):
            if not any(W.cs[g] for g in gs if g < len(W.cs)):
                continue
            L = W.layout(gs, line_len, size)
            if len(L) < 2:
                continue
            for n, ln in enumerate(L):
                if not ln:
                    continue
                wpx = sum(W.adv(g, size) for g in ln)
                if n < len(L) - 1:
                    tot_lines += 1
                    fill.append(wpx)
                    c = W.cs[ln[0]]
                    if c in NO_START:
                        viol += 1
                    if wpx < 0.85 * line_len:
                        worst.append((wpx, os.path.basename(f), W.text(ln)[:40]))
    avg = sum(fill) / len(fill) if fill else 0
    print(f'lineLength={line_len}  cjkLineBreak={W.CJK}')
    print(f'非末行数={tot_lines}  平均填充={avg:.0f}/{line_len} ({avg/line_len*100:.1f}%)')
    print(f'行首标点违规={viol} ({viol/tot_lines*100:.2f}%)')
    print(f'填充<85%的行={len(worst)} ({len(worst)/tot_lines*100:.2f}%)')
    worst.sort()
    for wpx, f, t in worst[:8]:
        print(f'   {wpx:>5}px  {f}  \"{t}\"')


if __name__ == '__main__':
    main()
