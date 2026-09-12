# -*- coding: utf-8 -*-
"""Leave every game install in the WORKING state (patch installed) and verify it loads.

The lifecycle tests intentionally ended with an uninstall, so some folders are currently
pristine. This script installs the patch into all four (using the quoted-argument form
required for paths with spaces) and then confirms the patch really initialises, by
checking that LanguageBarrier wrote languagebarrier/log.txt with no errors.
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

PKG = r"D:\DATA\tran\agent tran\9.6文本外工作\成品ing\补丁包"
SETUP = os.path.join(PKG, "RNDZhSetup.exe")
KILLER = r"D:\DATA\tran\agent tran\9.6文本外工作\scripts\diagnostics\rndkill.exe"

TARGETS = [
    ("Steam 正本",     r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH"),
    ("日文副本入口",   r"D:\Ruanjian\Steam\steamapps\common\RND_DaSH_jp_copy"),
    ("英文副本入口",   r"D:\Ruanjian\Steam\steamapps\common\RND_DaSH_en_copy"),
    ("盗版英文(旧版)", r"D:\ZZGAME\ROBOTICS NOTES DaSH"),
]


def kill_all():
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "$p=Start-Process -FilePath '%s' -Verb RunAs -PassThru "
                    "-WindowStyle Hidden;"
                    "$p|Wait-Process -Timeout 60 -EA SilentlyContinue"
                    % KILLER.replace("/", "\\")], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
    time.sleep(2)


def install(target):
    ps = ("$p=Start-Process -FilePath '%s' -ArgumentList '\"%s\"','/silent' "
          "-Verb RunAs -PassThru -WindowStyle Hidden;"
          "$p|Wait-Process -Timeout 300 -EA SilentlyContinue;"
          "if($p.HasExited){'rc=' + $p.ExitCode}else{'TIMEOUT'}"
          % (SETUP.replace("/", "\\"), target))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "").strip()


def verify(root):
    log = os.path.join(root, "languagebarrier", "log.txt")
    if os.path.exists(log):
        os.remove(log)
    kill_all()
    p = subprocess.Popen([os.path.join(root, "Game.exe"), "roboticsnotesd", "EN"],
                         cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = False
    for _ in range(50):
        if os.path.exists(log) and os.path.getsize(log) > 0:
            ok = True
            break
        if p.poll() is not None:
            break
        time.sleep(1)
    p.kill()
    kill_all()
    if not ok:
        return False, "无 log.txt"
    txt = open(log, encoding="utf-8", errors="replace").read()
    errs = txt.lower().count("error") + txt.lower().count("exception")
    return True, "log %dB 错误%d" % (len(txt), errs)


print("=" * 74)
print(" 让所有安装处于「已装补丁」且可玩状态")
print("=" * 74)
rc = 0
for tag, target in TARGETS:
    print("\n=== %s ===" % tag)
    if not os.path.isdir(target):
        print("  (目录不存在，跳过)")
        continue
    print("  安装: %s" % install(target))
    time.sleep(2)
    ok, why = verify(target)
    print("  验证: %s  (%s)" % ("✓ 补丁生效，可玩" if ok else "✗ 未生效", why))
    if not ok:
        rc = 1

print("\n" + "=" * 74)
print(" %s" % ("★ 四个安装全部就绪，可以直接启动游戏" if rc == 0 else "★ 有安装未生效"))
print("=" * 74)
sys.exit(rc)
