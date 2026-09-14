# -*- coding: utf-8 -*-
"""Verify the vocalise lines are byte-identical to CoZ's original (romaji kept,
no Chinese, no sweep overlay)."""
import io
import os

BS = chr(92)
G = r'D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -副本\languagebarrier\subs' + BS
E = r'D:\DATA\tran\agent tran\9.6文本外工作\RND补丁英文成品原版\languagebarrier\subs' + BS

for base in ['mv_rnd_edfrau', 'mv_rnd_livedance']:
    gl = io.open(G + base + '.ass', encoding='utf-8-sig', newline='').read().splitlines()
    el = io.open(E + base + '.ass', encoding='utf-8-sig', newline='').read().splitlines()
    checked = 0
    shown = 0
    for i, ln in enumerate(el):
        if not (ln.startswith('Dialogue:') and ',translation,' in ln and 'Tu Tu Ru' in ln):
            continue
        f = ln.split(',', 9)
        for j, g in enumerate(gl):
            if g.startswith(f[0] + ',' + f[1]) and ',translation,' in g:
                nxt = gl[j + 1].split(',', 9) if j + 1 < len(gl) else []
                overlay = len(nxt) == 10 and 'kf' in nxt[9]
                if shown < 3:
                    print('%-16s %s  原版逐字一致=%s  有扫色覆盖=%s' % (base, f[1], g == ln, overlay))
                    shown += 1
                assert g == ln, ('DIFF', base, f[1])
                assert not overlay, ('OVERLAY', base, f[1])
                checked += 1
                break
    print('%-16s 拟声行核验 %d 条：全部保留原版罗马音、无扫色覆盖' % (base, checked))
