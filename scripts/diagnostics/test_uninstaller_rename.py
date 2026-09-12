# -*- coding: utf-8 -*-
r"""升级路径验证：装着**旧版**补丁的目录，装新版后应该只剩新名卸载器。

场景（真实玩家会遇到）：
    玩家装过旧版补丁 → 游戏目录里有 RNDZhUninstall.exe（旧名卸载器）。
    现在跑新版安装包升级。新版部署的是「卸载汉化.exe」，
    如果不清旧名，目录里会**同时躺着新旧两个卸载器** —— 玩家更懵。

预期：
    安装后存在「卸载汉化.exe」；旧的 RNDZhUninstall.exe 被清掉；
    补丁正常生效；卸载后回到纯净（工具自身除外）。

做法：先人为放一个旧名卸载器（模拟旧版残留），再跑新版安装。
"""
import hashlib
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

WS = r"D:\DATA\tran\agent tran\9.6文本外工作"
SETUP = os.path.join(WS, "成品ing", "RNDZh-Setup-v1.1.exe")
PAYLOAD = os.path.join(WS, "成品ing", "补丁包")
TARGET = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本"

NEWNAME = "卸载汉化.exe"
OLDNAME = "RNDZhUninstall.exe"


def kill():
    for e in ("Game.exe", "launcher.exe", SETUP, NEWNAME, OLDNAME):
        subprocess.run(["taskkill", "/F", "/IM", e], capture_output=True)
    time.sleep(1)


def ps_run(exe, args, wait=300):
    parts = ",".join("'\"%s\"'" % a if (" " in a or ";" in a) else "'%s'" % a
                     for a in args)
    cmd = ("$p=Start-Process -FilePath '%s' -ArgumentList %s -PassThru "
           "-Verb RunAs; $p|Wait-Process -Timeout %d -EA SilentlyContinue; "
           "$p.ExitCode" % (exe, parts, wait))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=wait + 60)
    return (r.stdout or "").strip()


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def snap(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith("_cn_patch_backup")]
        for n in fns:
            p = os.path.join(dp, n)
            out[os.path.relpath(p, root)] = (os.path.getsize(p), md5(p))
    return out


print("目标: %s" % os.path.basename(TARGET))
kill()

# 先回到纯净
if os.path.isdir(os.path.join(TARGET, "languagebarrier")):
    u = os.path.join(TARGET, NEWNAME)
    if not os.path.exists(u):
        u = os.path.join(TARGET, OLDNAME)
    print("先卸载现有补丁…")
    ps_run(u, ["/silent"])
    for _ in range(90):
        time.sleep(1)
        if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
            break
    time.sleep(2)
for junk in (OLDNAME, NEWNAME, "NOTES DaSH -原版英文 副本 - 副本"):
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
print("=== 模拟旧版残留：放一个旧名卸载器 ===")
# 用旧名做一份（内容就是新版卸载器，名字才是关键变量）
shutil.copy2(os.path.join(PAYLOAD, NEWNAME), os.path.join(TARGET, OLDNAME))
print("  已放 %s" % OLDNAME)

print()
print("=== 跑新版安装包（升级安装）===")
rc = ps_run(SETUP, [TARGET, "/silent"])
print("  退出码 %s" % rc)
time.sleep(2)

has_new = os.path.exists(os.path.join(TARGET, NEWNAME))
has_old = os.path.exists(os.path.join(TARGET, OLDNAME))
print()
print("  新版卸载器 %s : %s" % (NEWNAME, "存在 ✓" if has_new else "缺失 ✗"))
print("  旧名残留 %s : %s" % (OLDNAME, "仍存在 ✗" if has_old else "已清掉 ✓"))

print()
print("=== 补丁是否生效 ===")
log = os.path.join(TARGET, "languagebarrier", "log.txt")
if os.path.exists(log):
    os.remove(log)
kill()
p = subprocess.Popen([os.path.join(TARGET, "Game.exe"), "roboticsnotesd", "EN"],
                     cwd=TARGET, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
for _ in range(28):
    time.sleep(1)
    if os.path.exists(log) and os.path.getsize(log) > 0:
        break
    if p.poll() is not None:
        break
sz = os.path.getsize(log) if os.path.exists(log) else 0
print("  log.txt: %s" % (("%dB ✓" % sz) if sz else "未生成 ✗"))
try:
    p.kill()
except OSError:
    pass
kill()

print()
print("=== 卸载（用新名）→ 回纯净 ===")
# 基线要在**安装前**取（此刻目录里是旧名残留 + 补丁），所以这里不能拿现在当基线 ——
# 改用「补丁专属内容是否全消失」判断：languagebarrier、片段子目录、代理 DLL 都该没了。
ps_run(os.path.join(TARGET, NEWNAME), ["/silent"])
for _ in range(90):
    time.sleep(1)
    if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
        break
time.sleep(2)

left = []
for n in ("languagebarrier", "NOTES DaSH -原版英文 副本 - 副本", "dinput8.dll",
          "dxgi", "d3d9", "VSFilter.dll", "RNDZhLauncher.exe"):
    if os.path.exists(os.path.join(TARGET, n)):
        left.append(n)
# boot.bat 是**游戏自己的文件**，卸载时应"还原"而不是"删除" —— 单独判内容是否与原版一致
bb = os.path.join(TARGET, "boot.bat")
mother = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本"
bb_ok = False
if os.path.exists(bb) and os.path.exists(os.path.join(mother, "boot.bat")):
    with open(bb, "rb") as f1, open(os.path.join(mother, "boot.bat"), "rb") as f2:
        bb_ok = f1.read() == f2.read()
print("  补丁痕迹: %s" % (left if left else "无 ✓"))
print("  boot.bat : %s" % ("已还原成游戏原版 ✓" if bb_ok else "内容不对 ✗"))

print()
ok = has_new and not has_old and sz > 0 and not left and bb_ok
print("★ 升级路径: %s" % ("通过 ✓（新名就位、旧名清除、补丁生效、卸载干净）"
                          if ok else "未通过 ✗"))
kill()
