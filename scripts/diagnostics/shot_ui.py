# -*- coding: utf-8 -*-
r"""抓三个窗口的界面截图（离线复刻 / 实机）。

安装器和卸载器都带 requireAdministrator，提权窗口会被 UIPI 挡住截图，
所以这里编一份**去掉清单**的同源 exe 来抓图 —— 代码同一份，只有清单不同，
界面完全一致（这个手法在项目里已经用过多次，见 AGENTS.md「调试经验」）。

用法:
    python shot_ui.py setup      # 安装器
    python shot_ui.py uninstall  # 卸载器
    python shot_ui.py launcher   # 启动器（非提权，直接抓）
"""
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

WS = r"D:\DATA\tran\agent tran\9.6文本外工作"
SRC = os.path.join(WS, "成品ing", "setup", "src")
SHOT = os.path.join(WS, "scripts", "diagnostics", "shot.py")
GAME = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH"
TMP = os.environ.get("TEMP", r"C:\Windows\Temp")

what = (sys.argv[1] if len(sys.argv) > 1 else "uninstall").lower()
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(WS, "tmp_%s_ui.png" % what)

PROBE = "ui_probe.exe"      # 名字避开 setup/install/卸载，否则被"安装程序启发式"要求提权
BIN = os.path.join(TMP, "rnd_ui_shot")


def build_probe(src_cpp, ico, label):
    """编一份无清单版（非提权，可截图）"""
    os.makedirs(BIN, exist_ok=True)
    shutil.copy2(src_cpp, os.path.join(BIN, "p.cpp"))
    shutil.copy2(ico, os.path.join(BIN, "p.ico"))
    with open(os.path.join(BIN, "p.rc"), "w") as f:
        f.write('#include <windows.h>\n101 ICON "p.ico"\n')
    bat = os.path.join(BIN, "b.bat")
    with open(bat, "w", newline="\r\n") as f:
        f.write(
            '@echo off\n'
            'call "C:\\VS2022BT\\VC\\Auxiliary\\Build\\vcvars32.bat" >nul\n'
            'cd /d "%s"\n'
            'rc /nologo /fo p.res p.rc\n'
            # advapi32: 安装器的 AutoDetectGame 读注册表找 Steam 库；
            # comctl32: SetWindowSubclass（EDIT 子控件的输入法支持）
            'cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE p.cpp '
            '/link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup gdiplus.lib '
            'shell32.lib user32.lib gdi32.lib ole32.lib advapi32.lib comctl32.lib '
            'p.res /OUT:%s\n'
            % (BIN, PROBE))
    r = subprocess.run(["cmd", "/c", bat], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    exe = os.path.join(BIN, PROBE)
    if not os.path.exists(exe):
        print("!! 编译失败:\n%s" % (r.stdout or "")[-800:])
        return None
    raw = open(exe, "rb").read()
    print("  无清单版: %s（requireAdministrator=%s）"
          % (label, "有(不对)" if b"requireAdministrator" in raw else "无 ✓"))
    return exe


def kill(*names):
    for n in names:
        subprocess.run(["taskkill", "/F", "/IM", n], capture_output=True)
    time.sleep(1)


def shoot(exe, cwd, title, out, wait=4):
    kill(os.path.basename(exe), "Game.exe")
    p = subprocess.Popen([exe], cwd=cwd)
    time.sleep(wait)
    r = subprocess.run(["python", SHOT, title, out], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    print("  %s" % (r.stdout or "").strip().replace("\n", "\n  "))
    try:
        p.kill()
    except OSError:
        pass
    kill("Game.exe")
    return os.path.exists(out)


if what == "launcher":
    exe = os.path.join(GAME, "RNDZhLauncher.exe")
    print("启动器（非提权，直接抓）")
    shoot(exe, GAME, "简体中文", OUT)   # 标题为「…简体中文 AI人工精校版 v<VER>」

elif what == "setup":
    print("安装器")
    exe = build_probe(os.path.join(SRC, "RNDZhSetup.cpp"),
                      os.path.join(SRC, "game.ico"), "安装器")
    if not exe:
        sys.exit(1)
    # 安装器从自身目录取 payload，抓图只需要界面，随便给个目录
    shoot(exe, BIN, "安装程序", OUT)

elif what == "uninstall":
    print("卸载器")
    exe = build_probe(os.path.join(SRC, "RNDZhUninstall.cpp"),
                      os.path.join(SRC, "uninstall.ico"), "卸载器")
    if not exe:
        sys.exit(1)
    # 卸载器要求所在目录有 Game.exe；放到游戏目录里才过得去自检
    shutil.copy2(exe, os.path.join(GAME, PROBE))
    shoot(os.path.join(GAME, PROBE), GAME, "卸载汉化", OUT)
    try:
        os.remove(os.path.join(GAME, PROBE))
    except OSError:
        pass

else:
    sys.exit("用法: shot_ui.py [setup|uninstall|launcher] [输出png]")

print("输出: %s" % OUT)
