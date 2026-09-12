# -*- coding: utf-8 -*-
r"""实验：payload 里那个写死名字的 `NOTES DaSH\` 到底还有没有用？

背景（为什么会有这个问题）：
    它本来是 **CoZ 原版补丁的 workaround** —— CoZ 观察到"Steam 正本加载的是
    `NOTES DaSH\DINPUT8.dll`"，就把代理 DLL 全放进一个**写死名字**的 `NOTES DaSH\` 里。
    当时不知道机制，于是把这个 workaround 的产物当成了"游戏要求 DLL 放这儿"。

    机制查清后（分号把搜索路径切开、片段被当相对目录搜）就知道：
    游戏要的不是"叫 NOTES DaSH 的目录"，而是"**分号后片段同名**的目录"。
    对 Steam 正本 `ROBOTICS;NOTES DaSH` 恰好等于 `NOTES DaSH`，
    所以对它**看起来**有用；换个目录名（副本）就对不上了。

现在新安装器会按实际目录名**实时算**片段并建目录（`SemicolonFragments()`），
所以按理说 payload 里那份是冗余的。本脚本用对照实验验证这个推断：

    A 组：payload **含** NOTES DaSH\（现状）
    B 组：payload **不含** NOTES DaSH\
    在同一个 Steam 正本目录上各装一次，比对补丁是否加载。

    C 组：用 B 组 payload 装到**无分号**目录，看会不会多出 NOTES DaSH\（纯垃圾）。

预期：
    A ✓、B ✓  → 说明它对 Steam 正本也冗余，可以移除
    A ✓、B ✗  → 说明它对 Steam 正本仍然必需，必须保留

每组都只动 payload 那一个变量，其余完全相同。
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
MODSCAN = os.path.join(WS, "scripts", "diagnostics", "modscan32.exe")

STEAM = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH"      # 有分号，片段 = NOTES DaSH
NOSEMI = r"D:\ZZGAME\ROBOTICS NOTES DaSH"                              # 无分号

TMP = os.environ.get("TEMP", r"C:\Windows\Temp")
BUILD = os.path.join(TMP, "rnd_q_build")
STAGE_WITH = os.path.join(TMP, "rnd_q_with")      # A 组：含 NOTES DaSH
STAGE_WITHOUT = os.path.join(TMP, "rnd_q_without")  # B 组：不含

INST = "ui_probe.exe"     # 避开 setup/install（否则被启发式要求提权）
UNINST = "ui_rm.exe"

PROXY = ["dinput8.dll", "d3d9", "d3d10", "d3d10_1", "d3d10core", "d3d11", "dxgi",
         "VSFilter.dll"]


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
        r = subprocess.run(["cmd", "/c", bat], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if not os.path.exists(os.path.join(BUILD, out_name)):
            print("!! 编译失败 %s\n%s" % (src_name, (r.stdout or "")[-600:]))
            return False
    return True


def stage(dest, with_notes):
    """搭一份 payload；with_notes 决定要不要放那个 NOTES DaSH\\ 子目录"""
    if os.path.isdir(dest):
        shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    for n in os.listdir(PAYLOAD_SRC):
        s = os.path.join(PAYLOAD_SRC, n)
        if n in ("RNDZhSetup.exe", "RNDZhUninstall.exe", "NOTES DaSH"):
            continue
        d = os.path.join(dest, n)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    if with_notes:
        shutil.copytree(os.path.join(PAYLOAD_SRC, "NOTES DaSH"),
                        os.path.join(dest, "NOTES DaSH"), dirs_exist_ok=True)
    shutil.copy2(os.path.join(BUILD, INST), os.path.join(dest, INST))
    return os.path.join(dest, INST)


def run(exe, args, cwd=None, timeout=300):
    return subprocess.run([exe] + args, capture_output=True, cwd=cwd, timeout=timeout)


def probe_load(target):
    """启动游戏，返回 (dll全路径, log字节, 是否生效)"""
    log = os.path.join(target, "languagebarrier", "log.txt")
    if os.path.exists(log):
        try:
            os.remove(log)
        except OSError:
            pass
    killall()
    time.sleep(2)
    p = subprocess.Popen([os.path.join(target, "Game.exe"), "roboticsnotesd", "EN"],
                         cwd=target, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    for _ in range(28):
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
    try:
        p.kill()
    except OSError:
        pass
    killall()
    time.sleep(1.5)
    return dll, sz, ("steamapps" in dll.lower()) or ("ZZGAME" in dll.upper()) \
        or ("Ruanjian" in dll)


def uninstall(target):
    killall()
    time.sleep(1)
    if os.path.isdir(os.path.join(target, "languagebarrier")):
        shutil.copy2(os.path.join(BUILD, UNINST), os.path.join(target, UNINST))
        run(os.path.join(target, UNINST), ["/silent"], cwd=target)
        for _ in range(90):
            time.sleep(1)
            if not os.path.isdir(os.path.join(target, "languagebarrier")):
                break
        time.sleep(2)
    # 清掉可能残留的碎片目录与测试工具
    for junk in ("NOTES DaSH", "ui_probe.exe", "ui_rm.exe", "RNDZhLauncher.exe",
                 "RNDZhUninstall.exe", "RNDZh-Setup-v0.1.exe"):
        p = os.path.join(target, junk)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def frag_of(path):
    name = os.path.basename(path.rstrip("\\/"))
    return [p.rstrip(" .") for p in name.split(";")[1:] if p.rstrip(" .")]


print("=== 0. 编译无清单版安装器 ===")
if not build():
    sys.exit(1)
EXE_WITH = stage(STAGE_WITH, True)
EXE_WITHOUT = stage(STAGE_WITHOUT, False)
print("  A 组 payload: %s（含 NOTES DaSH\\）" % STAGE_WITH)
print("  B 组 payload: %s（不含）" % STAGE_WITHOUT)
print()

results = {}

# ───────── A 组：含 NOTES DaSH（现状）─────────
print("=" * 92)
print("A) payload 含 NOTES DaSH\\ → 装到 Steam 正本（%s）" % os.path.basename(STEAM))
print("=" * 92)
uninstall(STEAM)
r = run(EXE_WITH, [STEAM, "/silent"], cwd=STAGE_WITH)
print("  安装 rc=%s" % r.returncode)
dll, sz, ok = probe_load(STEAM)
print("  实际加载: %s" % dll)
print("  log.txt : %s" % (("%dB" % sz) if sz else "未生成"))
print("  判定    : %s" % ("✓ 生效" if ok else "✗ 没跑"))
results["A 含 NOTES DaSH"] = ok
print()

# ───────── B 组：不含 NOTES DaSH ─────────
print("=" * 92)
print("B) payload **不含** NOTES DaSH\\ → 装到同一个 Steam 正本")
print("=" * 92)
uninstall(STEAM)
r = run(EXE_WITHOUT, [STEAM, "/silent"], cwd=STAGE_WITHOUT)
print("  安装 rc=%s" % r.returncode)
sub = os.path.join(STEAM, "NOTES DaSH")
print("  安装后 %s\\ 是否存在: %s" % ("NOTES DaSH", "是" if os.path.isdir(sub) else "否"))
if os.path.isdir(sub):
    print("    内含: %s" % sorted(os.listdir(sub)))
dll, sz, ok = probe_load(STEAM)
print("  实际加载: %s" % dll)
print("  log.txt : %s" % (("%dB" % sz) if sz else "未生成"))
print("  判定    : %s" % ("✓ 生效" if ok else "✗ 没跑"))
results["B 不含 NOTES DaSH"] = ok
print()

# ───────── C 组：无分号目录会不会多出 NOTES DaSH ─────────
print("=" * 92)
print("C) payload 含 NOTES DaSH\\ → 装到**无分号**目录（%s）" % os.path.basename(NOSEMI))
print("=" * 92)
uninstall(NOSEMI)
r = run(EXE_WITH, [NOSEMI, "/silent"], cwd=STAGE_WITH)
print("  安装 rc=%s" % r.returncode)
sub = os.path.join(NOSEMI, "NOTES DaSH")
if os.path.isdir(sub):
    print("  ✗ 多出一个 NOTES DaSH\\（该目录名无分号，加载器根本不需要它）")
    print("    内含 %d 个文件: %s" % (len(os.listdir(sub)), sorted(os.listdir(sub))))
    results["C 无分号目录多出该目录"] = False
else:
    print("  ✓ 没有多出 NOTES DaSH\\")
    results["C 无分号目录多出该目录"] = True
dll, sz, ok = probe_load(NOSEMI)
print("  实际加载: %s" % dll)
print("  补丁生效: %s（无分号本就不需要子目录）" % ("✓" if ok else "✗"))
print()

# ───────── 收尾 ─────────
uninstall(STEAM)
uninstall(NOSEMI)
for d in (BUILD, STAGE_WITH, STAGE_WITHOUT):
    shutil.rmtree(d, ignore_errors=True)

print("=" * 92)
print("结论")
print("=" * 92)
print("  A（含 NOTES DaSH）Steam 正本生效 : %s" % ("✓" if results["A 含 NOTES DaSH"] else "✗"))
print("  B（不含）        Steam 正本生效 : %s" % ("✓" if results["B 不含 NOTES DaSH"] else "✗"))
print("  C  无分号目录是否多出垃圾目录    : %s"
      % ("否 ✓（没有垃圾）" if results["C 无分号目录多出该目录"] else "是 ✗（是垃圾）"))
print()
if results["B 不含 NOTES DaSH"] and results["A 含 NOTES DaSH"]:
    print("  ★ 两组都生效 → payload 里那份对 Steam 正本**也是冗余**的：")
    print("    安装器会按目录名实时算出片段 NOTES DaSH 并自己建、自己放 DLL。")
    print("    可以移除；移除后对无分号目录还少一份垃圾。")
elif results["B 不含 NOTES DaSH"] is False:
    print("  ★ B 组失效 → 它对 Steam 正本仍然必需，**必须保留**。")
print()
print("（已清理全部测试安装与暂存目录）")
