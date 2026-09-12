# -*- coding: utf-8 -*-
r"""量窗口几何：客户区 vs 窗口矩形，判断截图里哪一块是客户区、按钮有没有被裁。

上一轮的教训：PrintWindow 抓的是**整个窗口矩形**（含标题栏/边框），
直接拿图像高度当客户区高度算，会把按钮位置算错 30 多像素，
然后误判成"按钮被裁切"。所以这里先把两个矩形都量出来，再换算。
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")

WS = r"D:\DATA\tran\agent tran\9.6文本外工作"
SRC = os.path.join(WS, "成品ing", "setup", "src")
GAME = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH"
TMP = os.environ.get("TEMP", r"C:\Windows\Temp")
BIN = os.path.join(TMP, "rnd_ui_shot")

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

kind = sys.argv[1] if len(sys.argv) > 1 else "uninstall"

if kind == "uninstall":
    exe_src = os.path.join(BIN, "ui_probe.exe")
    # 复刻 shot_ui.py 的编译（若不存在）
    if not os.path.exists(exe_src):
        sys.exit("先跑 shot_ui.py uninstall 生成 ui_probe.exe")
    shutil.copy2(exe_src, os.path.join(GAME, "ui_probe.exe"))
    exe = os.path.join(GAME, "ui_probe.exe")
    cwd = GAME
    needle = "卸载汉化"
    LOGICAL_W, LOGICAL_H = 480, 300
else:
    exe = os.path.join(GAME, "RNDZhLauncher.exe")
    cwd = GAME
    needle = "简体中文补丁"
    LOGICAL_W, LOGICAL_H = 820, 580

subprocess.run(["taskkill", "/F", "/IM", os.path.basename(exe)], capture_output=True)
time.sleep(1)
p = subprocess.Popen([exe], cwd=cwd)
time.sleep(4)

found = []
CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def cb(h, l):
    b = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, b, 512)
    if needle in b.value and user32.IsWindowVisible(h):
        found.append(h)
    return True


user32.EnumWindows(CB(cb), 0)
if not found:
    sys.exit("没找到窗口: %s" % needle)
h = found[0]

cr = wintypes.RECT(); user32.GetClientRect(h, ctypes.byref(cr))
wr = wintypes.RECT(); user32.GetWindowRect(h, ctypes.byref(wr))
sr = wintypes.RECT(); user32.GetClientRect(h, ctypes.byref(sr))
pt = wintypes.POINT(0, 0); user32.ClientToScreen(h, ctypes.byref(pt))

dpi = user32.GetDpiForWindow(h)
S = dpi / 96.0

print("窗口: %s" % needle)
print("  DPI=%d  缩放=%.3f" % (dpi, S))
print("  客户区 : %d x %d 物理 = %.1f x %.1f 逻辑"
      % (cr.right, cr.bottom, cr.right / S, cr.bottom / S))
print("  期望逻辑: %d x %d" % (LOGICAL_W, LOGICAL_H))
print("  窗口矩形: %d x %d" % (wr.right - wr.left, wr.bottom - wr.top))
print("  客户区左上角在窗口内的偏移: (%d, %d)  ← PrintWindow 图里要先减掉它"
      % (pt.x - wr.left, pt.y - wr.top))
print()
print("  结论: 客户区 %s" % ("与期望一致 ✓" if abs(cr.right / S - LOGICAL_W) < 2
                              and abs(cr.bottom / S - LOGICAL_H) < 2
                              else "与期望不符 ✗"))
print("  标题栏高度(物理): %d" % (pt.y - wr.top))

try:
    p.kill()
except OSError:
    pass
subprocess.run(["taskkill", "/F", "/IM", "ui_probe.exe"], capture_output=True)
time.sleep(1)
try:
    os.remove(os.path.join(GAME, "ui_probe.exe"))
except OSError:
    pass
