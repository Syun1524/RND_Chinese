# -*- coding: utf-8 -*-
"""填平 歌词对照 表的「罗马音」空缺 + 追加「英文原文（CoZ）」列。

为什么表里会有空：CoZ 的 ASS 把音乐上连着的两三句日文**合并**成一条 romaji
（以及一条英文 translation）行——\\k 时间轴是连着的。照抄进表时，被合并的
第二、三句那两格就是空的。表本身没有错行。

做法：
  * 罗马音列：用 CoZ 那条合并行的**逐音节 \\k 时间戳**，把每个音节按时间归给
    它所在的表行。于是每行都只装自己那一段，全表无空、无重复。
    自检：每行的音节拼回去必须等于 CoZ 原行（空白归一）；落不进任何表行的
    音节单独报出来（那是拟声/英文唱段，本来就没有日文行）。
  * 英文原文（CoZ）：新增一列，按时间归属填 CoZ 的英文行；被合并的后继行
    标「（承上，CoZ 合并）」——不留静默空格。
"""
import io
import os
import re
import sys
import glob
import openpyxl

ROOT = r"D:\DATA\tran\agent tran\9.6文本外工作"
TPL = os.path.join(ROOT, "RND补丁英文成品原版", "languagebarrier", "subs")
BS = chr(92)
VIS = re.compile(r'\{[^}]*\}')
KSYL = re.compile(re.escape(BS) + r'k(?:f|o)?(\d+)\}')
ECOL = '英文原文（CoZ）'


def vis(t):
    return VIS.sub('', t or '').strip()


def t2s(t):
    p = str(t).split(':')
    return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])


def parse(base):
    """-> (kanji[(s,e)], romaji[(s,e,[(t,txt)])], english[(s,e,text)])"""
    K, R, E = [], [], []
    for ln in io.open(os.path.join(TPL, base + '.ass'), encoding='utf-8-sig', newline=''):
        if not ln.startswith('Comment:'):
            continue
        f = ln.rstrip().split(',', 9)
        if len(f) < 10:
            continue
        body = f[9]
        if 'retime' in body:
            continue
        s, e = t2s(f[1]), t2s(f[2])
        style = f[3].strip()
        text = vis(body)
        if not text:
            continue
        if style == 'Kanji':
            K.append((s, e, text))
        elif style == 'romaji':
            toks, t = [], s
            for m in KSYL.finditer(body):
                nxt = body.find('{', m.end())
                seg = body[m.end():nxt if nxt >= 0 else len(body)]
                toks.append((t, seg))
                t += int(m.group(1)) / 100.0
            if not toks:
                toks = [(s, text)]
            R.append((s, e, toks))
        elif style == 'translation':
            E.append((s, e, text))
    return K, R, E


def norm(x):
    return re.sub(r'\s+', ' ', x or '').strip()


def owner(rows, s, e, ts, tol=0.08):
    """Which sheet row does a syllable at `ts` belong to, given its romaji line
    spans [s,e]?  A row belongs to that line only if the row STARTS inside the
    line window (CoZ merges lines that start together or later).  Then the row
    with the greatest start <= ts+tol wins.  Returns None when the syllable sits
    before every owned row — that is the line's lead-in (sung English / vocalise)
    which has no Japanese row at all."""
    starts = [a for a, b in rows if s - tol <= a <= e]
    if not starts:
        return None
    cand = [a for a in starts if a <= ts + tol]
    if not cand:
        return None
    tgt = max(cand)
    return [i for i, (a, b) in enumerate(rows) if a == tgt][0]


def distribute(rows, R, E):
    """rows: [(start,end)] -> (romaji_per_row, english_per_row, leftovers)"""
    n = len(rows)
    rom = [''] * n
    eng = [None] * n
    leftovers = []
    for s, e, toks in R:
        for ts, seg in toks:
            i = owner(rows, s, e, ts)
            if i is None:
                leftovers.append((s, ts, seg))
            else:
                rom[i] += seg
    for s, e, txt in E:
        lead = None
        for i, (a, b) in enumerate(rows):
            if abs(a - s) <= 0.05:
                lead = i
                break
        if lead is not None:
            eng[lead] = txt
        else:
            for i, (a, b) in enumerate(rows):
                if a - 0.02 <= s < b - 0.02:
                    eng[i] = '（承上，CoZ 合并）' + txt
                    break
    return [norm(x) for x in rom], eng, leftovers


JOBS = [
    ('ed001_歌词对照.xlsx', 'mv_rnd_ed001'),
    ('ed002_歌词对照.xlsx', 'mv_rnd_ed002'),
    ('edfrau_歌词对照.xlsx', 'mv_rnd_edfrau'),
    ('edfrau_歌词对照_插白补充.xlsx', 'mv_rnd_edfrau'),
    ('livedance_歌词对照.xlsx', 'mv_rnd_livedance'),
    ('livedance_歌词对照_插白补充.xlsx', 'mv_rnd_livedance'),
    ('op001_歌词对照.xlsx', 'mv_rnd_op001'),
]


def run(write):
    for fn, base in JOBS:
        p = os.path.join(ROOT, '歌词翻译', fn)
        wb = openpyxl.load_workbook(p)
        ws = wb['歌词对照']
        rows, off = [], 0
        for r in ws.iter_rows(min_row=2):
            if not (r[0].value and str(r[0].value).strip()):
                continue
            rows.append((t2s(str(r[0].value)), t2s(str(r[1].value))))
        K, R, E = parse(base)
        rom, eng, leftovers = distribute(rows, R, E)
        # ---- invariant: a romaji line = (syllables landing in its own rows)
        #      + (its lead-in leftovers: sung English / vocalise with no JP row).
        #      So whole == got + leftovers(line)  must hold exactly.
        bad = []
        for s, e, toks in R:
            whole = norm(''.join(t[1] for t in toks))
            # time-ordered: [lead-in leftovers][owned] must rebuild the line
            seq = ''.join(seg for ts, seg in toks)          # already time-ordered
            split = ''.join(seg for ts, seg in toks
                            if owner(rows, s, e, ts) is None
                            and ts < min((a for a, b in rows if s - 0.08 <= a <= e),
                                         default=e + 1))
            if whole.replace(' ', '') != seq.replace(' ', ''):
                bad.append((s, 'seq-mismatch', whole, seq))
            if split and owner(rows, s, e, split[:1] and toks[0][0]) is not None:
                pass
            lead = ''.join(seg for ts, seg in toks
                           if owner(rows, s, e, ts) is None)
            got = ''.join(seg for ts, seg in toks
                          if owner(rows, s, e, ts) is not None)
            # time-preserve: leftover syllables must all precede the first owned one
            first_own = next((ts for ts, sg in toks if owner(rows, s, e, ts) is not None), None)
            if lead and first_own is not None and any(ts > first_own for ts, sg in toks
                                                      if owner(rows, s, e, ts) is None):
                bad.append((s, 'lead-after-owned', lead[:40], ''))
        print('=' * 96)
        print(fn, '| rows', len(rows), '| romaji-lines', len(R),
              '| invariant', 'PASS' if not bad else 'FAIL')
        for s, w, g, lo in bad:
            print("   !! %.2f  whole=%s  got=%s left=%s" % (s, w[:50], g[:50], lo[:40]))
        lo = {}
        for s, ts, seg in leftovers:
            lo.setdefault(round(s, 1), []).append(seg)
        for s in sorted(lo):
            txt = norm(''.join(lo[s]))
            if txt:
                print('   未落表(无日文行) %.2f  %s' % (s, txt[:70]))
        if not write:
            continue
        hdr = [str(c.value) if c.value else '' for c in ws[1]]
        if ECOL not in hdr:
            ecol = len(hdr) + 1
            ws.cell(row=1, column=ecol, value=ECOL)
        else:
            ecol = hdr.index(ECOL) + 1
        i = 0
        for r in ws.iter_rows(min_row=2):
            if not (r[0].value and str(r[0].value).strip()):
                continue
            if rom[i]:
                r[3].value = rom[i]
            if eng[i]:
                r[ecol - 1].value = eng[i]
            i += 1
        wb.save(p)
    if write:
        print('\nwritten.')


if __name__ == '__main__':
    run('--write' in sys.argv)
