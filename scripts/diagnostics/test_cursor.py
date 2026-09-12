# -*- coding: utf-8 -*-
"""验证光标逻辑：对目录框区域/按钮区域分别发 WM_SETCURSOR，看程序设了哪种光标。

判据：调用 GetCursorInfo 必须在被查询进程内才有意义，所以换个做法 ——
直接读源码逻辑对应的坐标，确认 Hit() 返回值：
  Hit() 返回 4  → 应设 IDC_IBEAM(I 型)
  返回 1/2/3    → 应设 IDC_HAND(手型)

这里用 GetClassLong/GetCursor 无法跨进程取"将要设的光标"，
所以改为：在探针进程里查它窗口的光标类，并用真实坐标核对 Hit 的期望值。
"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")

u = ctypes.windll.user32
u.SetProcessDPIAware()

EXE = os.path.join(os.environ.get("TEMP", ""), "ui_probe.exe")
subprocess.run(["taskkill", "/F", "/IM", "ui_probe.exe"], capture_output=True)
time.sleep(0.8)
p = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
time.sleep(3)

hwnd = 0
for _ in range(40):
    h = u.GetForegroundWindow()
    o = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(o))
    if o.value == p.pid:
        hwnd = h
        break
    time.sleep(0.25)
print("hwnd =", hwnd)

# 取客户区坐标 → 屏幕坐标，再由屏幕坐标反查光标类型要用的信息
# 简化：直接问窗口"当前光标"在指定点是什么 —— 通过发送 WM_SETCURSOR + 读 GetCursor
# 但 GetCursor 是全局的、且需前台。退一步：核对 Hit() 的坐标期望是否正确。
edit = u.FindWindowExW(hwnd, 0, "Edit", None)
er = wintypes.RECT()
u.GetWindowRect(edit, ctypes.byref(er))
wr = wintypes.RECT()
u.GetWindowRect(hwnd, ctypes.byref(wr))
print("窗口 rect:", wr.left, wr.top, wr.right, wr.bottom)
print("EDIT rect:", er.left, er.top, er.right, er.bottom)

# EDIT 在客户区里的相对位置
print("EDIT 相对客户区:", er.left - wr.left, er.top - wr.top)

# 程序里 FieldRect 的坐标（与源码一致）：x=24, y=84, w=432-76=356, h=34
# EDIT 子控件被创建在 FieldRect 内缩 2px 处
print()
print("=== 预期 ===")
print("  鼠标在 EDIT 上 → WM_SETCURSOR 交给 EDIT → EDIT 自己设 IDC_IBEAM（I 型）")
print("  鼠标在按钮上   → 父窗口设 IDC_HAND（手型）")
print("  鼠标在空白处   → IDC_ARROW")

# 检查 EDIT 控件是否真的会自己处理 WM_SETCURSOR
# 发送 WM_SETCURSOR 给 EDIT，看它返回什么（TRUE 表示它处理了）
res = u.SendMessageW(edit, 0x0020, edit, (1 << 16) | 0)   # WM_SETCURSOR, HTCLIENT
print()
print("EDIT 对 WM_SETCURSOR(HTCLIENT) 的返回:", res,
      "(1=自己处理了 → 会设 I 型)" if res else "(0=未处理)")
p.kill()
