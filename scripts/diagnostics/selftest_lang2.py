# -*- coding: utf-8 -*-
"""自检调用器 v2：直接用 CreateProcessW 提权启动，命令行由我们自己拼。

之前几种 PowerShell 传参方式都会把引号吃掉或转义错误，导致被调程序收到的
路径在空格处截断 —— 看起来像"语言判定失败"，其实是调用方的问题。

这里用 ShellExecuteExW + runas 提权，lpParameters 由我们精确控制。
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")

SETUP = r"D:\DATA\tran\agent tran\9.6文本外工作\成品ing\setup\bin\RNDZhSetup.exe"
LOG = r"D:\rnd_selftest.txt"

CASES = [
    ("Steam正本",      r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH", "JP"),
    ("英文副本-副本",   r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本", "EN"),
    ("日文副本-副本",   r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版日语 副本 - 副本", "JP"),
    ("盗版英文",       r"D:\ZZGAME\ROBOTICS NOTES DaSH", "EN"),
]

shell32 = ctypes.windll.shell32
kernel32 = ctypes.windll.kernel32


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_NOASYNC = 0x00000100
SW_HIDE = 0

print("=== 语言判定自检（ShellExecuteEx runas，参数由我们拼）===")
for tag, d, expect in CASES:
    if os.path.exists(LOG):
        os.remove(LOG)
    # 参数就是 "路径" + /selftest，引号由这里精确给出
    params = '"%s" /selftest' % d
    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    sei.lpVerb = "runas"
    sei.lpFile = SETUP
    sei.lpParameters = params
    sei.nShow = SW_HIDE
    ok = shell32.ShellExecuteExW(ctypes.byref(sei))
    if not ok:
        print("  %-14s ★提权启动失败 err=%d" % (tag, kernel32.GetLastError()))
        continue
    if sei.hProcess:
        kernel32.WaitForSingleObject(sei.hProcess, 60000)
        kernel32.CloseHandle(sei.hProcess)
    time.sleep(1)
    if os.path.exists(LOG):
        txt = open(LOG, encoding="utf-8-sig", errors="replace").read()
        tgt = lang = ""
        for l in txt.splitlines():
            if l.startswith("target="): tgt = l.split("=", 1)[1]
            if l.startswith("detectedLang="): lang = l.split("=", 1)[1].strip()
        print("  %-14s 判定=%-3s 期望=%-3s %s" % (tag, lang or "?", expect,
                                                   "✓" if lang == expect else "★错"))
        if lang != expect:
            print("        收到: %r" % tgt)
    else:
        print("  %-14s ★无输出" % tag)
