# -*- coding: utf-8 -*-
r"""抓卸载器**卸载完成后**的界面，验证"只剩一个按钮"。

为什么要专门抓完成态：卸载器点"确认卸载"后会做实际卸载（删文件、恢复备份），
而完成态的界面以前是「灰色·已完成 + 关闭」两个按钮 —— 看着像还有一步没做完。
现在应该只剩一个「关闭」。

做法：用无清单版（自动化跑得动），装一次补丁，然后用换装工具**点确认卸载**，
等它跑完再 PrintWindow 抓图。不要用 /silent —— 那不会建窗口。
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
GAME = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本"
SHOT = os.path.join(WS, "scripts", "diagnostics", "shot.py")
OUT = os.path.join(WS, "tmp_uninstall_done.png")
TMP = os.environ.get("TEMP", r"C:\Windows\Temp")
BUILD = os.path.join(TMP, "rnd_selfdel_build")

PROBE = "ui_rm.exe"

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()


def kill():
    for e in ("Game.exe", "launcher.exe", PROBE):
        subprocess.run(["taskkill", "/F", "/IM", e], capture_output=True)
    time.sleep(1)


exe = os.path.join(BUILD, PROBE)
if not os.path.exists(exe):
    sys.exit("找不到 %s —— 先跑 test_self_delete.py 生成" % exe)

# 确保游戏目录里装着补丁（这样卸载器有事可做，能看到完成态）
if not os.path.isdir(os.path.join(GAME, "languagebarrier")):
    sys.exit("游戏目录没装补丁，先跑 leave_installed.py")

kill()
# 卸载器要求所在目录有 Game.exe
dst = os.path.join(GAME, "卸载汉化.exe")
shutil.copy2(exe, dst)
print("已放入 卸载汉化.exe（无清单版）")

p = subprocess.Popen([dst], cwd=GAME)
time.sleep(4)

# 找窗口
found = []
CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def cb(h, l):
    b = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, b, 512)
    if "卸载汉化" in b.value and user32.IsWindowVisible(h):
        found.append(h)
    return True


user32.EnumWindows(CB(cb), 0)
if not found:
    sys.exit("没找到卸载窗口")
h = found[0]
cr = wintypes.RECT()
user32.GetClientRect(h, ctypes.byref(cr))
S = cr.right / 480.0
print("客户区 %dx%d  缩放 %.3f" % (cr.right, cr.bottom, S))

# 点「确认卸载」（逻辑坐标 OkRect 中心）
ok = (480 - 24 - 150 - 12 - 100 + 75, 300 - 24 - 20)
x, y = int(ok[0] * S), int(ok[1] * S)
pack = lambda xx, yy: (yy << 16) | xx
print("点击确认卸载 @物理(%d,%d)" % (x, y))
user32.SetForegroundWindow(h)
for msg, wp in ((0x0200, 0), (0x0201, 1), (0x0202, 0)):
    user32.PostMessageW(h, msg, wp, pack(x, y))
    time.sleep(0.2)

# 还会弹一个确认框（MB_YESNO）—— 用 UIA 点不了提权窗口，但这是无清单版，可以按键。
time.sleep(2)
user32.keybd_event(0x0D, 0, 0, 0)      # Enter = 默认按钮
user32.keybd_event(0x0D, 0, 2, 0)
time.sleep(1)

# 等卸载跑完（进度走完 + 完成态）
print("等待卸载完成…")
for i in range(60):
    time.sleep(1)
    # 完成态下 languagebarrier 已被删除
    if not os.path.isdir(os.path.join(GAME, "languagebarrier")):
        print("  第 %d 秒：补丁已移除" % (i + 1))
        break
time.sleep(3)          # 让界面重绘到完成态

r = subprocess.run(["python", SHOT, "卸载汉化", OUT], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(r.stdout[-400:])

try:
    p.kill()
except OSError:
    pass
kill()
# 清理：卸载器自删可能留下东西
for n in ("卸载汉化.exe", "_uninstall_del.exe"):
    q = os.path.join(GAME, n)
    if os.path.exists(q):
        try:
            os.remove(q)
        except OSError:
            pass
print("输出: %s" % OUT)
