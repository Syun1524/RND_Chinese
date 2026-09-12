# -*- coding: utf-8 -*-
r"""验证卸载器的两个新行为：① 卸载完只剩一个按钮；② 卸载后把自己删掉。

② 的关键点：运行中的 exe 删不掉（文件被映射着），所以做法是
「改名 + 登记重启后删除」。测的是**改名这一步是否真的发生** ——
它一成功，游戏目录里当场就看不到"卸载汉化.exe"了，玩家观感即达成。

本脚本用无清单版（自动化跑得动），流程：
    装 → 确认 exe 在 → 卸载 → 确认 exe 不见了（或被改名/登记删除）

注意：不要用 subprocess 直接跑**发布版**（带 requireAdministrator，非提权会被挡）。
"""
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

WS = r"D:\DATA\tran\agent tran\9.6文本外工作"
SRC = os.path.join(WS, "成品ing", "setup", "src")
PAYLOAD = os.path.join(WS, "成品ing", "补丁包")
TARGET = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本"
FRAG = "NOTES DaSH -原版英文 副本 - 副本"

TMP = os.environ.get("TEMP", r"C:\Windows\Temp")
BUILD = os.path.join(TMP, "rnd_selfdel_build")
STAGE = os.path.join(TMP, "rnd_selfdel_payload")
INST = "ui_probe.exe"
UNINST = "ui_rm.exe"          # 不含 setup/install/uninst，避免"安装程序启发式"要求提权


def killall():
    for e in ("Game.exe", "launcher.exe", INST, UNINST):
        subprocess.run(["taskkill", "/F", "/IM", e], capture_output=True)
    time.sleep(1)


def build():
    for d in (BUILD, STAGE):
        os.makedirs(d, exist_ok=True)
    shutil.copy2(os.path.join(SRC, "game.ico"), os.path.join(BUILD, "game.ico"))
    with open(os.path.join(BUILD, "t.rc"), "w") as f:
        f.write('#include <windows.h>\n101 ICON "game.ico"\n')
    for src, out in [("RNDZhSetup.cpp", INST), ("RNDZhUninstall.cpp", UNINST)]:
        shutil.copy2(os.path.join(SRC, src), os.path.join(BUILD, src))
        bat = os.path.join(BUILD, "b_%s.bat" % out)
        with open(bat, "w", newline="\r\n") as f:
            f.write('@echo off\n'
                    'call "C:\\VS2022BT\\VC\\Auxiliary\\Build\\vcvars32.bat" >nul\n'
                    'cd /d "%s"\nrc /nologo /fo t.res t.rc\n'
                    'cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE '
                    '%s /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup gdiplus.lib '
                    'shell32.lib user32.lib gdi32.lib ole32.lib advapi32.lib '
                    't.res /OUT:%s\n' % (BUILD, src, out))
        r = subprocess.run(["cmd", "/c", bat], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if not os.path.exists(os.path.join(BUILD, out)):
            print("!! 编译失败 %s\n%s" % (src, (r.stdout or "")[-700:]))
            return False
    for n in os.listdir(PAYLOAD):
        if n in ("RNDZhSetup.exe", "RNDZhUninstall.exe"):
            continue
        s, d = os.path.join(PAYLOAD, n), os.path.join(STAGE, n)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    # 安装器从自身目录取 payload，所以卸载器也要放进去。
    # 用刚编译的无清单版（发布版带 requireAdministrator，自动化跑不动），
    # 但仍部署成产品名「卸载汉化.exe」—— 测的就是这个名字会不会自删。
    shutil.copy2(os.path.join(BUILD, UNINST),
                 os.path.join(STAGE, "卸载汉化.exe"))
    shutil.copy2(os.path.join(BUILD, INST), os.path.join(STAGE, INST))
    return True


def run(exe, args, cwd=None, timeout=300):
    return subprocess.run([exe] + args, capture_output=True, cwd=cwd, timeout=timeout)


print("=== 编译无清单版 ===")
if not build():
    sys.exit(1)
INST_EXE = os.path.join(STAGE, INST)
print("  OK")

# 清到纯净
killall()
if os.path.isdir(os.path.join(TARGET, "languagebarrier")):
    u = os.path.join(TARGET, "卸载汉化.exe")
    if os.path.exists(u):
        shutil.copy2(os.path.join(BUILD, UNINST), u)
        run(u, ["/silent"], cwd=TARGET)
        for _ in range(90):
            time.sleep(1)
            if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
                break
    time.sleep(2)
for n in ([FRAG] if os.path.isdir(os.path.join(TARGET, FRAG)) else []) + \
         [INST, UNINST, "卸载汉化.exe", "_uninstall_del.exe", "RNDZhUninstall.exe"]:
    p = os.path.join(TARGET, n)
    if os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)
    elif os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass
time.sleep(1)

print()
print("=== 安装 ===")
r = run(INST_EXE, [TARGET, "/silent"], cwd=STAGE)
print("  rc=%s" % r.returncode)
uexe = os.path.join(TARGET, "卸载汉化.exe")
print("  卸载器就位: %s" % ("是 ✓" if os.path.exists(uexe) else "否 ✗"))
if not os.path.exists(uexe):
    sys.exit("安装没落卸载器，无法继续")

print()
print("=== 卸载（观察是否自删）===")
print("  卸载前: 卸载汉化.exe=%s  _uninstall_del.exe=%s"
      % (os.path.exists(uexe), os.path.exists(os.path.join(TARGET, "_uninstall_del.exe"))))
r = run(uexe, ["/silent"], cwd=TARGET)
print("  rc=%s" % r.returncode)
time.sleep(3)

still = os.path.exists(uexe)
renamed = os.path.exists(os.path.join(TARGET, "_uninstall_del.exe"))
print()
print("  卸载后 卸载汉化.exe      : %s" % ("仍存在 ✗" if still else "已消失 ✓"))
print("  卸载后 _uninstall_del.exe: %s" % ("存在（等重启删除）" if renamed else "无"))

# 其它痕迹
left = [n for n in ("languagebarrier", "dinput8.dll", "dxgi", "d3d9",
                    "RNDZhLauncher.exe", FRAG)
        if os.path.exists(os.path.join(TARGET, n))]
print("  其它补丁痕迹: %s" % (left if left else "无 ✓"))

print()
ok = (not still) and (not left)
print("★ %s" % ("通过：卸载器自己也没了，其余痕迹清干净"
                if ok else "未通过（见上）"))

killall()
# 保留编译产物：shot_uninstall_done.py（抓完成态界面）要用同一个无清单版。
# 只清 payload 里拷出来的那一大堆补丁文件。
shutil.rmtree(STAGE, ignore_errors=True)
print("（已清理 payload 暂存；编译产物保留在 %s）" % BUILD)
