# -*- coding: utf-8 -*-
"""量启动器窗口的真实几何与 DPI，用来定位「开始游戏」按钮显示异常。

源码里 StartRect() = X 660, 宽 250 → 右边界 910，而逻辑窗口宽 WIN_W = 900。
如果客户区就是 900 逻辑像素，按钮必然被切掉 10 px。但实机截图看起来切得更多，
所以要么客户区不是 900，要么 DPI 缩放让坐标被放大了。
"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

GAME = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH"

subprocess.run(["taskkill", "/F", "/IM", "RNDZhLauncher.exe"], capture_output=True)
time.sleep(1)
proc = subprocess.Popen([os.path.join(GAME, "RNDZhLauncher.exe")], cwd=GAME)
time.sleep(4)

found = []
CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def cb(h, l):
    b = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, b, 512)
    if "简体中文补丁" in b.value and user32.IsWindowVisible(h):
        found.append(h)
    return True


user32.EnumWindows(CB(cb), 0)
if not found:
    print("没找到窗口")
    sys.exit(1)
h = found[0]

cr = wintypes.RECT()
user32.GetClientRect(h, ctypes.byref(cr))
wr = wintypes.RECT()
user32.GetWindowRect(h, ctypes.byref(wr))

print("客户区   : %d x %d" % (cr.right, cr.bottom))
print("窗口矩形 : %d x %d @ (%d,%d)"
      % (wr.right - wr.left, wr.bottom - wr.top, wr.left, wr.top))
try:
    dpi = user32.GetDpiForWindow(h)
    print("窗口 DPI : %d  → 缩放 %d%%" % (dpi, round(dpi * 100 / 96)))
except Exception as e:
    print("DPI 查询失败:", e)
try:
    print("系统 DPI : %d" % user32.GetDpiForSystem())
except Exception:
    pass

print()
print("源码布局（逻辑像素）:")
print("  WIN_W/WIN_H   = 900 x 620")
print("  StartRect()   = X 660, 宽 250  → 右边界 910")
print("  OptRect(0)    = X 384")
print("  OutfitRect()  = X 508, 宽 210  → 右边界 718")
print()
cw = cr.right
print("按钮右边界 910 vs 客户区宽 %d → %s"
      % (cw, ("超出 %d px ✗ 会被切" % (910 - cw)) if 910 > cw else "未超出 ✓"))
print("窗口标题栏：%s" % ("含标题/边框" if (wr.bottom - wr.top) > cr.bottom else "??"))

subprocess.run(["taskkill", "/F", "/IM", "RNDZhLauncher.exe"], capture_output=True)
