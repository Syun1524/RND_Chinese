# -*- coding: utf-8 -*-
r"""量启动器右栏提示文字的宽度，确认会不会超出右栏被窗口裁掉。

背景：`DrawTxt()` 用 `RectF(x, y, 0, 0)` 绘制 —— 宽度给 0 表示"不约束"，
GDI+ 会把整句画成**一行**，太长就直接顶出窗口右边被裁掉（不换行）。
所以"这句会不会太长"必须按像素算，不能凭感觉。

这里用界面上真正用的字体（Microsoft YaHei UI）+ 字号，量出像素宽度，
再和右栏可用宽度比较。

用法: python scripts/diagnostics/measure_hint_width.py
"""
import os
import sys

from PIL import ImageFont

sys.stdout.reconfigure(encoding="utf-8")

# ── 与 RNDZhLauncher.cpp 一致的布局常量（逻辑像素）──
WIN_H = 620
RIGHT_W = 460
PAD_R = 32.0
# 左栏宽按主题图 540x720 算
LEFT_W = int(WIN_H * 540.0 / 720.0 + 0.5)
WIN_W = LEFT_W + RIGHT_W
RXL = LEFT_W + 36.0            # 右栏内容左边界
RW = WIN_W - PAD_R             # 右栏内容右边界
AVAIL = RW - RXL               # 提示文字可用的逻辑宽度

FONT_PX = 12                   # DrawTxt 用的字号

CANDIDATES = {
    "当前（用 LB 钩子）":
        "用 LB 钩子重定向模型归档，运行时切换到该套立绘；不改动游戏文件",
    "全名 + 详细":
        "用 LanguageBarrier 重定向模型归档，运行时切换到该套立绘；不改动游戏文件",
    "全名 + 紧凑":
        "由 LanguageBarrier 重定向模型归档，切换该套立绘；不改动游戏文件",
    "全名 + 更紧凑":
        "LanguageBarrier 重定向模型归档，运行时切换该套立绘",
    "全名 + 最短":
        "LanguageBarrier 运行时重定向模型，不改动游戏文件",
    "字幕说明":
        "影片播放时叠加的字幕轨",
    "DXVK 说明（现有）":
        "用 Vulkan 转译渲染，缓解新显卡上的兼容问题",
    "鼠标说明（现有）":
        "在 ADV 场景里用鼠标控制视角与推进",
}

# 找界面同款字体（F(12) 用的是 g_ff，候选顺序见源码）
FONTS = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
         "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"]


def load(px):
    for p in FONTS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px), p
            except Exception:
                pass
    return ImageFont.load_default(), "(default)"


font, fpath = load(FONT_PX)
print("字体: %s  字号: %dpx" % (fpath, FONT_PX))
print("右栏: RXL=%.0f .. RW=%.0f  →  可用宽度 %.0f 逻辑像素" % (RXL, RW, AVAIL))
print("窗口: %d x %d 逻辑像素" % (WIN_W, WIN_H))
print()
print("%-18s %7s  %s" % ("文案", "宽度", "结论"))
print("-" * 92)

for label, text in CANDIDATES.items():
    w = font.getlength(text)
    fits = w <= AVAIL
    # 超出多少 / 还剩多少
    diff = AVAIL - w
    verdict = ("✓ 放得下（余 %.0f px）" % diff) if fits else \
              ("✗ 超出 %.0f px —— 会被窗口裁掉" % -diff)
    print("%-18s %6.0f   %s" % (label, w, verdict))
    # 如果放不下，算一下需要多宽的右栏
    if not fits:
        print("%-18s %6s   需要右栏再加宽 %.0f px（窗口宽 → %d）"
              % ("", "", -diff, int(WIN_W - diff)))

print()
# 也报一下：如果保持当前右栏，能容纳多少字（中文按 12px 估）
import math
print("参考：右栏 %.0f px 在 %.0fpx 字号下大约能放 %.1f 个全角字符"
      % (AVAIL, FONT_PX, AVAIL / FONT_PX))
