# -*- coding: utf-8 -*-
r"""补测：payload 带进去的 NOTES DaSH\，卸载时会不会被清掉？

probe_notes_subdir.py 的 C 组发现：装到**无分号**目录（`D:\ZZGAME\ROBOTICS NOTES DaSH`）时，
payload 里那份 `NOTES DaSH\` 会被原样拷进去，而该目录名根本没有分号、加载器也不需要它
—— 纯垃圾（7 个文件，约 15 MB）。

那么它至少卸载时会被清掉吧？卸载器的目录清单里有硬编码的 `NOTES DaSH`
（`const wchar_t* dirs[] = { L"languagebarrier", L"NOTES DaSH" };`），按代码看是会清的，
但这里实测确认一下，免得又是一个"看着会清其实没清"。

只测一个场景：无分号目录 → 装（含 NOTES DaSH 的 payload）→ 真·卸载器 → 看残留。
"""
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

WS = r"D:\DATA\tran\agent tran\9.6文本外工作"
SETUP_SRC = os.path.join(WS, "成品ing", "setup", "src")
PAYLOAD_SRC = os.path.join(WS, "成品ing", "补丁包")

TARGET = r"D:\ZZGAME\ROBOTICS NOTES DaSH"      # 无分号，所以不需要任何片段子目录

TMP = os.environ.get("TEMP", r"C:\Windows\Temp")
BUILD = os.path.join(TMP, "rnd_un_notes_build")
STAGE = os.path.join(TMP, "rnd_un_notes_payload")
INST = "ui_probe.exe"
UNINST = "ui_rm.exe"


def killall():
    for e in ("Game.exe", "launcher.exe", INST, UNINST):
        subprocess.run(["taskkill", "/F", "/IM", e], capture_output=True)


def build():
    os.makedirs(BUILD, exist_ok=True)
    shutil.copy2(os.path.join(SETUP_SRC, "game.ico"), os.path.join(BUILD, "game.ico"))
    with open(os.path.join(BUILD, "test.rc"), "w") as f:
        f.write('#include <windows.h>\n101 ICON "game.ico"\n')
    for src_name, out_name in [("RNDZhSetup.cpp", INST),
                               ("RNDZhUninstall.cpp", UNINST)]:
        shutil.copy2(os.path.join(SETUP_SRC, src_name), os.path.join(BUILD, src_name))
        bat = os.path.join(BUILD, "b_%s.bat" % out_name)
        with open(bat, "w", newline="\r\n") as f:
            f.write('@echo off\n'
                    'call "C:\\VS2022BT\\VC\\Auxiliary\\Build\\vcvars32.bat" >nul\n'
                    'cd /d "%s"\n'
                    'rc /nologo /fo test.res test.rc\n'
                    'cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE '
                    '%s /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup '
                    'gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib advapi32.lib '
                    'test.res /OUT:%s\n' % (BUILD, src_name, out_name))
        subprocess.run(["cmd", "/c", bat], capture_output=True)
        if not os.path.exists(os.path.join(BUILD, out_name)):
            print("!! 编译失败 %s" % src_name)
            return False
    # payload：保留 NOTES DaSH\ 子目录（就是要测它）
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE)
    for n in os.listdir(PAYLOAD_SRC):
        if n in ("RNDZhSetup.exe", "RNDZhUninstall.exe"):
            continue
        s, d = os.path.join(PAYLOAD_SRC, n), os.path.join(STAGE, n)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    shutil.copy2(os.path.join(BUILD, INST), os.path.join(STAGE, INST))
    return True


def run(exe, args, cwd=None):
    return subprocess.run([exe] + args, capture_output=True, cwd=cwd, timeout=300)


print("=== 编译 ===")
if not build():
    sys.exit(1)
print("  OK")

# 先清干净
killall()
time.sleep(1)
if os.path.isdir(os.path.join(TARGET, "languagebarrier")):
    shutil.copy2(os.path.join(BUILD, UNINST), os.path.join(TARGET, UNINST))
    run(os.path.join(TARGET, UNINST), ["/silent"], cwd=TARGET)
    for _ in range(90):
        time.sleep(1)
        if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
            break
    time.sleep(2)
for junk in ("NOTES DaSH", INST, UNINST):
    p = os.path.join(TARGET, junk)
    if os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)
    elif os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass
time.sleep(1)

print()
print("=== 装（payload 含 NOTES DaSH\\）到无分号目录 ===")
r = run(os.path.join(STAGE, INST), [TARGET, "/silent"], cwd=STAGE)
print("  安装 rc=%s" % r.returncode)
sub = os.path.join(TARGET, "NOTES DaSH")
if os.path.isdir(sub):
    n = len(os.listdir(sub))
    sz = sum(os.path.getsize(os.path.join(sub, f)) for f in os.listdir(sub))
    print("  安装后 NOTES DaSH\\ : 存在（%d 文件 / %.1f MB）—— 该目录名无分号，纯垃圾"
          % (n, sz / 1048576))
else:
    print("  安装后 NOTES DaSH\\ : 不存在")

print()
print("=== 真·卸载器（/silent）===")
shutil.copy2(os.path.join(BUILD, UNINST), os.path.join(TARGET, UNINST))
r = run(os.path.join(TARGET, UNINST), ["/silent"], cwd=TARGET)
print("  卸载 rc=%s" % r.returncode)
time.sleep(3)

left = os.path.isdir(sub)
print("  卸载后 NOTES DaSH\\ : %s" % ("仍存在 ✗（卸载没清掉）" if left
                                       else "已清除 ✓"))
if left:
    print("    残留: %s" % sorted(os.listdir(sub)))
others = [f for f in ("languagebarrier", "dinput8.dll", "dxgi", "d3d9", "VSFilter.dll")
          if os.path.exists(os.path.join(TARGET, f))]
print("  其它补丁痕迹: %s" % (others if others else "无 ✓"))

# 清场
for junk in ("NOTES DaSH", INST, UNINST):
    p = os.path.join(TARGET, junk)
    if os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)
    elif os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass
for d in (BUILD, STAGE):
    shutil.rmtree(d, ignore_errors=True)
print()
print("（已清理测试产物）")
