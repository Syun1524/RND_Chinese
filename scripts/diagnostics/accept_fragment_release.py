# -*- coding: utf-8 -*-
r"""发布版安装包最终验收：含分号目录 装→中文→卸载→回纯净。

与 test_fragment_fix.py 的区别：
    那个用**无清单版**（测试手段，非提权），验证的是代码逻辑；
    这个用**真正的发布 exe**（带 requireAdministrator，走 Start-Process -Verb RunAs），
    验证的是玩家实际拿到的那条路径 —— 包括 SFX 解包、参数透传、提权。

目标目录特意选名字里带分号的副本：这正是过去"装了却没反应"的典型场景。

路径必须加引号：`-ArgumentList @('D:\a b\c','/silent')` 生成的命令行不带引号，
CommandLineToArgvW 会在空格处切断，argv[1] 变成半个路径
（安装器现在对此明确失败并返回 2，不再静默回退）。
"""
import hashlib
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

WS = r"D:\DATA\tran\agent tran\9.6文本外工作"
SETUP = os.path.join(WS, "成品ing", "RNDZh-Setup-v0.1.exe")
MODSCAN = os.path.join(WS, "scripts", "diagnostics", "modscan32.exe")

TARGET = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本"
# 可选：命令行传目标目录。Steam 正本（`ROBOTICS;NOTES DaSH`）要专门测 ——
# 它的分号片段算出来正好等于硬编码那条 `NOTES DaSH`，走的是**去重**分支，
# 是最容易出错的一条路径（重复处理会把刚恢复的文件又删一遍）。
if len(sys.argv) > 1:
    TARGET = sys.argv[1]


def frag_of(path):
    """目录名里分号后的片段（与安装器 SemicolonFragments 同规则）"""
    name = os.path.basename(path.rstrip("\\/"))
    out = []
    for p in name.split(";")[1:]:
        p = p.rstrip(" .")
        if p:
            out.append(p)
    return out


FRAG = frag_of(TARGET)[0] if frag_of(TARGET) else ""

# 安装/卸载工具自身会留在游戏目录（设计如此），比对时排除
ALLOW = {"RNDZhLauncher.exe", "RNDZhUninstall.exe", "RNDZhSetup.exe",
         "RNDZh-Setup-v0.1.exe"}


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
            rel = os.path.relpath(p, root)
            try:
                out[rel] = (os.path.getsize(p), md5(p))
            except OSError:
                out[rel] = (-1, "?")
    return out


def killall():
    for exe in ("Game.exe", "launcher.exe", "RNDZhSetup.exe", "RNDZhUninstall.exe",
                "RNDZh-Setup-v0.1.exe", "setup.tmp"):
        subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)


def ps_run(args, wait_timeout=300, exe=None):
    """用 Start-Process -Verb RunAs 提权运行（路径带引号！）

    exe 省略时用安装包（SETUP）；卸载要传游戏目录里的 RNDZhUninstall.exe ——
    卸载器用**自身所在目录**当游戏目录。
    """
    target_exe = exe or SETUP
    parts = ",".join("'\"%s\"'" % a if (" " in a or ";" in a) else "'%s'" % a
                     for a in args)
    cmd = ("$p=Start-Process -FilePath '%s' -ArgumentList %s -PassThru "
           "-Verb RunAs; $p|Wait-Process -Timeout %d -EA SilentlyContinue; "
           "$p.ExitCode" % (target_exe, parts, wait_timeout))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=wait_timeout + 60)
    return (r.stdout or "").strip(), (r.stderr or "").strip()


def probe_load():
    log = os.path.join(TARGET, "languagebarrier", "log.txt")
    if os.path.exists(log):
        try:
            os.remove(log)
        except OSError:
            pass
    killall()
    time.sleep(2)
    p = subprocess.Popen([os.path.join(TARGET, "Game.exe"), "roboticsnotesd", "EN"],
                         cwd=TARGET, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(1)
        if os.path.exists(log) and os.path.getsize(log) > 0:
            break
        if p.poll() is not None:
            break
    dll = "(扫不到)"
    for _ in range(3):
        r = subprocess.run([MODSCAN, str(p.pid), "dinput"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        mods = [l.strip() for l in (r.stdout or "").splitlines()
                if not l.startswith("#")]
        if mods:
            dll = mods[0].split("\t")[-1]
            break
        time.sleep(1)
    sz = os.path.getsize(log) if os.path.exists(log) else 0
    txt = ""
    if os.path.exists(log):
        try:
            txt = open(log, encoding="utf-8", errors="replace").read()
        except OSError:
            pass
    try:
        p.kill()
    except OSError:
        pass
    killall()
    time.sleep(1.5)
    return dll, sz, ("steamapps" in dll.lower()) and sz > 0, \
        txt.lower().count("error") + txt.lower().count("exception")


print("安装包: %s" % SETUP)
print("  大小 %.1f MB   md5 %s" % (os.path.getsize(SETUP) / 1048576,
                                   md5(SETUP)[:16]))
print("目标: %s" % os.path.basename(TARGET))
print()

print("=== 1. 先回到纯净 ===")
killall()
time.sleep(1)
# 卸载器必须从游戏目录里跑（它用自身所在目录当游戏目录）。
# 干净目录里没有它，那就已经纯净了，跳过卸载。
uninst = os.path.join(TARGET, "RNDZhUninstall.exe")
if os.path.isdir(os.path.join(TARGET, "languagebarrier")):
    print("  已装补丁，先卸载…")
    if not os.path.exists(uninst):
        sys.exit("  装着补丁却没有卸载器，无法自动清理；请手动处理")
    ps_run(["/silent"], exe=uninst)
    for _ in range(90):
        time.sleep(1)
        if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
            break
    time.sleep(2)
else:
    print("  目录已纯净")
for junk in ([FRAG] if FRAG else []) + ["RNDZh-Setup-v0.1.exe"]:
    p = os.path.join(TARGET, junk)
    if os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)
    elif os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass
time.sleep(1)
before = snap(TARGET)
print("  基线 %d 个文件" % len(before))
print()

try:
    print("=== 2. 安装发布版（提权 /silent）===")
    t0 = time.time()
    out, err = ps_run([TARGET, "/silent"])
    print("  退出码 %s，耗时 %.0f 秒" % (out or "(无)", time.time() - t0))
    if err.strip():
        print("  stderr: %s" % err.strip()[:300])

    sub = os.path.join(TARGET, FRAG)
    print("  兼容子目录「%s」: %s" % (FRAG, "已创建 ✓" if os.path.isdir(sub) else "未创建 ✗"))
    if os.path.isdir(sub):
        print("  内含 %d 个文件" % len(os.listdir(sub)))
    print()

    print("=== 3. 补丁是否真的生效 ===")
    dll, sz, ok, errs = probe_load()
    print("  实际加载: %s" % dll)
    print("  log.txt : %s，错误 %d" % ((("%dB" % sz) if sz else "未生成"), errs))
    print("  判定    : %s" % ("✓ 生效（含分号目录也能用了）" if ok else "✗ 没跑"))
    print()

    print("=== 4. 卸载发布版（提权 /silent）===")
    # 卸载器必须从游戏目录里跑（它用自身所在目录当游戏目录）
    t0 = time.time()
    out, err = ps_run(["/silent"], exe=uninst)
    print("  退出码 %s，耗时 %.0f 秒" % (out or "(无)", time.time() - t0))
    for _ in range(120):
        time.sleep(1)
        if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
            break
    time.sleep(2)

    after = snap(TARGET)
    extra = sorted(set(after) - set(before) - ALLOW)
    missing = sorted(set(before) - set(after))
    changed = sorted(k for k in (set(before) & set(after)) if before[k] != after[k])
    print("  多余 %d | 缺失 %d | 不同 %d" % (len(extra), len(missing), len(changed)))
    for k in extra[:12]:
        print("    多余: %s" % k)
    for k in missing[:12]:
        print("    缺失: %s" % k)
    for k in changed[:12]:
        print("    不同: %s" % k)
    frag_left = os.path.isdir(sub)
    print("  兼容子目录: %s" % ("已清掉 ✓" if not frag_left else "仍存在 ✗"))
    print()
    if not extra and not missing and not changed and not frag_left:
        print("★ 发布版验收通过：含分号目录自动兼容 + 卸载回纯净。")
    else:
        print("!! 有差异，见上。")
finally:
    killall()
