# -*- coding: utf-8 -*-
"""负向自测：故意破坏每一处防护，确认 check_crash_guards.py 报 FAIL。

判据是「坏输入必须 CAUGHT、好输入必须 PASS」—— 只在好输入上跑过不算数。
做法：把源码/数据复制到临时目录，按用例改写，再让检查函数指向临时文件。
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import check_crash_guards as G  # noqa: E402

LB = os.path.join(ROOT, "..", "GitHub", "RND_Chinese", "LanguageBarrier_chs",
                  "LanguageBarrier")


def patch_text(src, dst, old, new, count=1):
    text = io.open(src, encoding="utf-8-sig", errors="replace").read()
    if old not in text:
        raise SystemExit("★ 用例失效：找不到待替换串\n  %s\n  在 %s" % (old[:80], src))
    io.open(dst, "w", encoding="utf-8-sig").write(text.replace(old, new, count))


def case_widthloop(tmp):
    """A1: 删掉兜底推进分支"""
    dst = os.path.join(tmp, "GameText_loop.cpp")
    patch_text(G.SRC_GAMETEXT, dst,
               "    } else {\n      // Single-byte control (line break, link markers, ...): "
               "not measured,\n      // but it still has to be consumed.\n      sc3string++;\n    }",
               "    }")
    return G.check_source_widthloop(dst)


def case_widthloop_bounds(tmp):
    """A1b: 去掉下标范围检查"""
    dst = os.path.join(tmp, "GameText_bounds.cpp")
    patch_text(G.SRC_GAMETEXT, dst,
               "        } else if (glyphId < (int)sizeof(widths) / (int)sizeof(widths[0])) {",
               "        } else {")
    return G.check_source_widthloop(dst)


def case_fmv_csri(tmp):
    """B: 去掉 csri 判空"""
    dst = os.path.join(tmp, "CriMana_csri.cpp")
    patch_text(G.SRC_CRIMANA, dst,
               "  if (!state->csri) {", "  if (false) {")
    return G.check_source_fmv(dst)


def case_fmv_guard(tmp):
    """B2: drawSubs 去掉 stagingTexture 校验"""
    dst = os.path.join(tmp, "CriMana_guard.cpp")
    patch_text(G.SRC_CRIMANA, dst,
               "    if (!state->csri || !state->stagingTexture) continue;",
               "    if (!state->csri) continue;")
    return G.check_source_fmv(dst)


def case_fmv_tex(tmp):
    """B3: 去掉 CreateTexture2D 的 HRESULT 检查"""
    dst = os.path.join(tmp, "CriMana_tex.cpp")
    patch_text(G.SRC_CRIMANA, dst,
               "  if (FAILED(hr) || !state->stagingTexture) {", "  if (false) {")
    return G.check_source_fmv(dst)


def case_fmv_fps(tmp):
    """B4: 去掉帧率除零保护"""
    dst = os.path.join(tmp, "CriMana_fps.cpp")
    patch_text(G.SRC_CRIMANA, dst,
               "  if (frameInfo->framerate_n != 0) {", "  if (true) {")
    return G.check_source_fmv(dst)


def case_iruo_div(tmp):
    """C: 恢复裸除 IruoSensitivity"""
    dst = os.path.join(tmp, "Input_div.cpp")
    patch_text(G.SRC_INPUT, dst,
               "    int sensitivity = IruoSensitivity > 0 ? IruoSensitivity : 500;\n"
               "    int axisMultiplier = gameExeScrWork[SW_AR_ANGLE_C] / sensitivity;",
               "    int axisMultiplier = gameExeScrWork[SW_AR_ANGLE_C] / IruoSensitivity;")
    return G.check_source_iruo(dst)


def case_iruo_bounds(tmp):
    """C2: 去掉地标 id 范围检查"""
    dst = os.path.join(tmp, "Input_bounds.cpp")
    patch_text(G.SRC_INPUT, dst,
               "        if (id < 0 || id >= *ARNumberOfGeoTags) continue;\n"
               "        int slot = ARSomeGeoTagArr[id];\n"
               "        if (slot < 0) continue;",
               "        int slot = ARSomeGeoTagArr[id];")
    return G.check_source_iruo(dst)


def case_iruo_window(tmp):
    """C3: 去掉窗口下标范围检查"""
    dst = os.path.join(tmp, "Input_window.cpp")
    patch_text(G.SRC_INPUT, dst,
               "    if (windowIndex < 0 || windowIndex > 64) windowIndex = 0;",
               "    ;")
    return G.check_source_iruo(dst)


CASES = [
    ("A1 删掉兜底推进分支", case_widthloop),
    ("A1b 去掉 widths 下标检查", case_widthloop_bounds),
    ("B  去掉 csri 判空", case_fmv_csri),
    ("B2 drawSubs 去掉 stagingTexture 校验", case_fmv_guard),
    ("B3 去掉 CreateTexture2D 检查", case_fmv_tex),
    ("B4 去掉帧率除零保护", case_fmv_fps),
    ("C  恢复裸除 IruoSensitivity", case_iruo_div),
    ("C2 去掉地标 id 范围检查", case_iruo_bounds),
    ("C3 去掉窗口下标检查", case_iruo_window),
]


def main():
    tmp = tempfile.mkdtemp(prefix="crashguard_neg_")
    caught = missed = 0
    print("=== 负向自测：崩溃防护门禁 ===")
    try:
        for label, fn in CASES:
            errs = fn(tmp)
            ok = bool(errs)
            print("  %-36s %s" % (label, "CAUGHT" if ok else "*** MISSED ***"))
            if ok:
                caught += 1
            else:
                missed += 1

        # 好输入必须 PASS
        good = [
            ("A1 原始源码", G.check_source_widthloop(G.SRC_GAMETEXT)),
            ("B  原始源码", G.check_source_fmv(G.SRC_CRIMANA)),
            ("C  原始源码", G.check_source_iruo(G.SRC_INPUT)),
            ("A2 原始数据", G.check_scene_data()),
        ]
        for label, errs in good:
            ok = not errs
            print("  %-36s %s" % (label, "PASS" if ok else "*** FALSE POSITIVE: %s ***" % errs[:1]))
            if not ok:
                missed += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nCAUGHT %d / MISSED %d" % (caught, missed))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
