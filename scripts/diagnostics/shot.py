# -*- coding: utf-8 -*-
"""截图一个提权窗口（UIPI 会挡住 UIA，所以用 PrintWindow 直接抓位图）。

用法: python shot.py <窗口标题子串> <输出png>
"""
import ctypes
import os
import sys
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")

u = ctypes.windll.user32
g = ctypes.windll.gdi32
u.SetProcessDPIAware()

needle = sys.argv[1] if len(sys.argv) > 1 else "安装程序"
OUT = sys.argv[2] if len(sys.argv) > 2 else r"D:\installer_shot.png"

found = []


def cb(h, l):
    buf = ctypes.create_unicode_buffer(512)
    u.GetWindowTextW(h, buf, 512)
    if needle in buf.value and u.IsWindowVisible(h):
        found.append((h, buf.value))
    return True


WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
u.EnumWindows(WNDENUMPROC(cb), 0)
print("匹配窗口:", found)
if not found:
    sys.exit("没找到窗口")

HWND = found[0][0]
rc = wintypes.RECT()
u.GetClientRect(HWND, ctypes.byref(rc))
W, H = rc.right, rc.bottom
print("客户区 %dx%d" % (W, H))
if W <= 0 or H <= 0:
    sys.exit("尺寸无效")

hdc = u.GetDC(HWND)
memdc = g.CreateCompatibleDC(hdc)
bmp = g.CreateCompatibleBitmap(hdc, W, H)
g.SelectObject(memdc, bmp)
ok = u.PrintWindow(HWND, memdc, 2)      # PW_RENDERFULLCONTENT
print("PrintWindow =", ok)


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


bi = BIH()
bi.biSize = ctypes.sizeof(BIH)
bi.biWidth, bi.biHeight = W, -H
bi.biPlanes, bi.biBitCount = 1, 32
buf = ctypes.create_string_buffer(W * H * 4)
g.GetDIBits(memdc, bmp, 0, H, buf, ctypes.byref(bi), 0)

from PIL import Image
im = Image.frombuffer("RGBA", (W, H), buf, "raw", "BGRA", 0, 1).convert("RGB")
# 放大 2 倍便于看清
im = im.resize((W * 2, H * 2), Image.LANCZOS)
im.save(OUT)
print("已保存", OUT, im.size)

g.DeleteObject(bmp)
g.DeleteDC(memdc)
u.ReleaseDC(HWND, hdc)
