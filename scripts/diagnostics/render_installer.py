# -*- coding: utf-8 -*-
"""离线渲染安装器界面（按 RNDZhSetup.cpp 里的实际坐标与配色画一遍）。

为什么要离线画：安装器带 requireAdministrator，UIPI 会挡住 ZCode 的截图，
PrintWindow 对提权窗口也返回失败。与其反复折腾截图，不如按源码里的同一套
坐标/颜色/字号直接画出设计稿 —— 用于确认对齐与观感，逻辑仍以实机为准。

坐标与颜色必须与 src/RNDZhSetup.cpp 保持一致（改源码时同步改这里）。
"""
import io
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

# ── 与源码一致的外观常量 ──
WIN_W, WIN_H = 480, 268
C_BG       = (255, 255, 255)
C_PANEL    = (245, 246, 248)
C_FIELD    = (255, 255, 255)
C_BORDER   = (216, 220, 227)
C_TEXT     = (31, 35, 40)
C_DIM      = (107, 114, 128)
C_MUTED    = (156, 163, 175)
C_ACCENT   = (11, 107, 203)
C_ACCENTH  = (10, 95, 176)
C_TRACK    = (232, 235, 240)
C_WHITE    = (255, 255, 255)
C_OK       = (26, 127, 55)
C_WARN     = (154, 103, 0)

PAD = 24
CW = WIN_W - PAD * 2

SCALE = 2


def font(px, bold=False):
    for c in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
              "C:/Windows/Fonts/simhei.ttf"):
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, px * SCALE)
            except Exception:
                pass
    return ImageFont.load_default()


def rr(dr, box, rad, fill=None, outline=None, width=1):
    x0, y0, x1, y1 = [v * SCALE for v in box]
    dr.rounded_rectangle([x0, y0, x1, y1], radius=rad * SCALE, fill=fill,
                         outline=outline, width=width * SCALE)


def text(dr, s, f, color, x, y, anchor="la"):
    dr.text((x * SCALE, y * SCALE), s, font=f, fill=color, anchor=anchor)


def render(state, out):
    """state: 'empty' | 'found' | 'installing' | 'done' | 'error'"""
    im = Image.new("RGB", (WIN_W * SCALE, WIN_H * SCALE), C_BG)
    dr = ImageDraw.Draw(im)

    # 顶部标题条
    dr.rectangle([0, 0, WIN_W * SCALE, 54 * SCALE], fill=C_PANEL)
    # 图标占位（真实程序画的是 game.ico）
    rr(dr, (PAD, 14, PAD + 26, 14 + 26), 6, fill=(200, 214, 229))
    text(dr, "ROBOTICS;NOTES DaSH 简体中文补丁", font(16, True), C_TEXT, PAD + 36, 18)

    # 游戏目录标签
    text(dr, "游戏目录", font(13), C_DIM, PAD, 62)

    # 目录框
    focus = state == "empty"
    rr(dr, (PAD, 84, PAD + CW - 76, 84 + 34), 4, fill=C_FIELD,
       outline=C_ACCENT if focus else C_BORDER, width=2 if focus else 1)
    if state == "empty":
        text(dr, "选择或粘贴游戏目录（内含 Game.exe）", font(13), C_MUTED, PAD + 8, 84 + 17,
             anchor="lm")
    else:
        text(dr, r"D:\Ruanjian\Steam\...\ROBOTICS;NOTES DaSH", font(13), C_TEXT,
             PAD + 8, 84 + 17, anchor="lm")

    # 浏览按钮
    rr(dr, (PAD + CW - 68, 84, PAD + CW, 84 + 34), 4, fill=C_BG,
       outline=C_BORDER, width=1)
    text(dr, "浏览…", font(13), C_TEXT, PAD + CW - 34, 84 + 17, anchor="mm")

    # 提示行
    hints = {
        "empty":      ("未自动找到游戏，请点「浏览…」或直接把游戏文件夹拖进来", C_WARN),
        "found":      ("已找到游戏（日文版）", C_DIM),
        "installing": ("已找到游戏（日文版）", C_DIM),
        "done":       ("已找到游戏（日文版）", C_DIM),
        "error":      ("复制失败：languagebarrier\\patchdef.json", C_WARN),
    }
    hs, hc = hints[state]
    text(dr, hs, font(12), hc, PAD, 124)

    # 进度条（仅安装中/完成/失败时）
    if state in ("installing", "done", "error"):
        rr(dr, (PAD, 152, PAD + CW, 152 + 6), 3, fill=C_TRACK)
        pct = {"installing": 0.45, "done": 1.0, "error": 0.30}[state]
        if pct > 0:
            rr(dr, (PAD, 152, PAD + CW * pct, 152 + 6), 3,
               fill=(207, 34, 46) if state == "error" else C_ACCENT)

    # 状态文字
    st = {
        "empty":      ("点击「安装」开始（请先完全关闭游戏）", C_DIM),
        "found":      ("点击「安装」开始（请先完全关闭游戏）", C_DIM),
        "installing": ("正在安装…  45%", C_DIM),
        "done":       ("安装完成", C_OK),
        "error":      ("安装失败", (207, 34, 46)),
    }[state]
    text(dr, st[0], font(12), st[1], PAD, 166)

    # 按钮（右下）
    by = WIN_H - 54
    can = state in ("found",)
    rr(dr, (PAD + CW - 196, by, PAD + CW - 100, by + 34), 4,
       fill=C_ACCENT if can else C_TRACK)
    text(dr, "已完成" if state == "done" else "安装", font(14, True),
         C_WHITE if (can or state == "done") else C_MUTED,
         PAD + CW - 148, by + 17, anchor="mm")
    rr(dr, (PAD + CW - 92, by, PAD + CW, by + 34), 4, fill=C_BG,
       outline=C_BORDER, width=1)
    text(dr, "关闭" if state == "done" else "取消", font(14), C_TEXT,
         PAD + CW - 46, by + 17, anchor="mm")

    im.save(out)
    print("  %-12s -> %s" % (state, out))


OUTDIR = r"D:\DATA\tran\agent tran\9.6文本外工作\scripts\diagnostics"
for s in ("empty", "found", "installing", "done"):
    render(s, os.path.join(OUTDIR, "installer_%s.png" % s))
print("完成")
