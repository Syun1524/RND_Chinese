# -*- coding: utf-8 -*-
"""Final acceptance run: for each install, verify the patch LOADS, then uninstall and
verify the folder is clean again.

Load check uses the only unambiguous signal: LanguageBarrier writes
languagebarrier/log.txt the moment it initialises, and nothing else in the game creates
that file. cwd is set to the game dir because the path is relative.

Clean check: after uninstalling, none of the patch artifacts may remain (the two tool
exes are expected to stay; they are what the user runs to uninstall/reinstall).
"""
import hashlib
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

INSTALLS = [
    ("Steam 正本",     r"D:/Ruanjian/Steam/steamapps/common/ROBOTICS;NOTES DaSH"),
    ("日文副本入口",   r"D:/Ruanjian/Steam/steamapps/common/RND_DaSH_jp_copy"),
    ("英文副本入口",   r"D:/Ruanjian/Steam/steamapps/common/RND_DaSH_en_copy"),
    ("盗版英文(旧版)", r"D:/ZZGAME/ROBOTICS NOTES DaSH"),
]

ART = ["dinput8.dll", "VSFilter.dll", "RNDZhLauncher.exe", "d3d9", "d3d10", "d3d10_1",
       "d3d10core", "d3d11", "dxgi", "安装说明.txt", "_cn_patch_boot_orig.bat",
       "languagebarrier", os.path.join("NOTES DaSH", "dinput8.dll")]
KILLER = r"D:/DATA/tran/agent tran/9.6文本外工作/scripts/diagnostics/rndkill.exe"


def kill_all():
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "$p=Start-Process -FilePath '%s' -Verb RunAs -PassThru "
                    "-WindowStyle Hidden;"
                    "$p|Wait-Process -Timeout 60 -EA SilentlyContinue"
                    % KILLER.replace("/", "\\")], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
    time.sleep(2)


def check_load(root):
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
        return False, "无 log.txt（补丁未加载）"
    txt = open(log, encoding="utf-8", errors="replace").read()
    errs = txt.lower().count("error") + txt.lower().count("exception")
    redir = [l.strip() for l in txt.splitlines() if "redirecting physical fopen" in l]
    return True, "log %dB, 错误 %d, %s" % (len(txt), errs,
                                          redir[0].split("]")[-1].strip() if redir else "-")


def uninstall(root):
    ui = os.path.join(root, "RNDZhUninstall.exe")
    if not os.path.exists(ui):
        return None
    ps = ("$p=Start-Process -FilePath '%s' -ArgumentList '/silent' -Verb RunAs "
          "-PassThru; $p.Id" % ui.replace("/", "\\"))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True)
    for i in range(40):
        time.sleep(1)
        if not [a for a in ART if os.path.exists(os.path.join(root, a))]:
            return i + 1
    return None


print("=" * 74)
print(" 验收：补丁加载 + 卸载干净")
print("=" * 74)
rc = 0
for tag, root in INSTALLS:
    print("\n=== %s ===" % tag)
    if not os.path.isdir(root):
        print("  (目录不存在)")
        continue
    loaded, why = check_load(root)
    print("  加载: %s  (%s)" % ("✓" if loaded else "✗", why))
    if not loaded:
        rc = 1
    secs = uninstall(root)
    left = [a for a in ART if os.path.exists(os.path.join(root, a))]
    print("  卸载: %s  剩余 %s" % ("✓ 第%d秒完成" % secs if secs else "✗ 未完成",
                                  left or "无"))
    if left or secs is None:
        rc = 1
    baks = [d for d in os.listdir(root) if d.startswith("_cn_patch_backup")]
    print("  备份残留: %s" % (baks or "无"))
    if baks:
        rc = 1

print("\n" + "=" * 74)
print(" 结果: %s" % ("★ 全部通过" if rc == 0 else "★ 有问题，见上"))
print("=" * 74)
sys.exit(rc)
