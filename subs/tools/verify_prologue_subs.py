# -*- coding: utf-8 -*-
"""验证 prologue 字幕在两份 PlayRes 下的实际落点与安全边距（差分法）。

用法：python verify_prologue_subs.py
判据：每段字幕都必须完整落在画面内（距底 > 20px）。

★ 为什么先把文件拷到 ASCII 临时目录：
   ffmpeg 的 filter 解析器（subtitles=...）对含中文的路径不稳定 ——
   绝对路径的盘符冒号会被当成选项分隔符，中文路径则报 Unable to open。
   实测唯一稳的做法是让 filter 里只出现纯 ASCII 的相对路径。
"""
import os
import shutil
import subprocess
import tempfile
import numpy as np
from PIL import Image

R = r"D:/DATA/tran/agent tran/9.6文本外工作"
FF = R + "/解包/usm工具/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe"
V = R + "/解包/解包cpk的产物(日语)/movie/解包mp4/mv_rnd_prologue.mp4"
SAMPLES = [3.5, 5.0, 21.5, 23.0, 25.5, 26.8]
FONT_FILES = ["RNDSerifSC-Regular.ttf", "RNDTitleSC-Light.ttf"]


def probe(ass_src, tag, work):
    print("=== %s ===" % tag)
    # 纯 ASCII 工作目录：ass + fonts 都拷进去，filter 里只写文件名
    shutil.copy2(ass_src, os.path.join(work, "sub.ass"))
    fdir = os.path.join(work, "fonts")
    os.makedirs(fdir, exist_ok=True)
    for f in FONT_FILES:
        shutil.copy2(os.path.join(R, "fonts", f), os.path.join(fdir, f))

    vf = "subtitles=sub.ass:fontsdir=fonts"
    ok = True
    for t in SAMPLES:
        w = os.path.join(work, "w.png")
        wo = os.path.join(work, "wo.png")
        r = subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                            "-i", V, "-ss", str(t), "-frames:v", "1", "-vf", vf, w],
                           cwd=work, capture_output=True, text=True)
        if r.returncode:
            print("  t=%5.1f  ★ffmpeg 失败: %s" % (t, (r.stderr or "")[:160]))
            ok = False
            continue
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", V, "-ss", str(t), "-frames:v", "1", wo],
                       cwd=work, capture_output=True, text=True)
        a = np.array(Image.open(w).convert("L")).astype(float)
        b = np.array(Image.open(wo).convert("L")).astype(float)
        d = np.abs(a - b)
        rows = (d > 10).sum(axis=1)
        nz = np.where(rows > 2)[0]
        if len(nz) == 0:
            print("  t=%5.1f  无字幕" % t)
            continue
        margin = 1079 - int(nz.max())
        flag = "" if margin > 20 else "  ★贴边/裁切"
        if margin <= 20:
            ok = False
        print("  t=%5.1f  字幕 y %4d-%4d  距底 %3dpx  差异像素 %6d%s"
              % (t, nz.min(), nz.max(), margin, int((d > 10).sum()), flag))
    return ok


if __name__ == "__main__":
    work = tempfile.mkdtemp(prefix="prolsub_")
    try:
        a = probe(R + "/视频字幕/mv_rnd_prologue.ass", "游戏版 PlayRes 1088", work)
        b = probe(R + "/视频字幕/mv_rnd_prologue_pr1080.ass", "PR 版 PlayRes 1080", work)
        print()
        print("RESULT:", "ALL PASS" if (a and b) else "★ FAIL")
    finally:
        shutil.rmtree(work, ignore_errors=True)
