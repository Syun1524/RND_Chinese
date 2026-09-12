# -*- coding: utf-8 -*-
r"""端到端验证「分号路径自动兼容」：真实失败目录 装 → 确认补丁加载 → 卸载 → 回纯净。

背景：机制已由 predict_mechanism.py 三条预测锁死（分号把搜索路径切开，片段被当
相对子目录），characterize_fix.py 量清了实现细节，validate_fix_real.py 在真实失败
目录上手工建子目录验证过有效。本脚本验证的是**改完代码的安装器**能自动做到这件事。

为什么不能直接跑发布版 exe：
  两个程序都带 requireAdministrator 清单，提权窗口 UIPI 会挡住自动化。
  所以另编一份**去掉清单**的版本；文件名还必须避开 setup/install ——
  Windows 的"安装程序启发式"会照样要求提权（WinError 740）。
  发布版不受影响（它本来就该提权），这只是测试手段。

为什么卸载器要从游戏目录里跑：
  卸载器用**自身所在目录**当游戏目录（ExeDir()），不是命令行传参。

判定用快照（路径 + 大小 + md5）逐文件比对，不用"进程还活着"之类的弱信号。
"""
import hashlib
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

TARGET = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本"
FRAG = "NOTES DaSH -原版英文 副本 - 副本"      # 目录名里分号后面那一段

TMP = os.environ.get("TEMP", r"C:\Windows\Temp")
BUILD = os.path.join(TMP, "rnd_frag_build")    # 编译产物
STAGE = os.path.join(TMP, "rnd_frag_payload")  # 安装器 + 补丁包内容

# 测试专用文件名：不能含 setup / install / uninst ——
# Windows 的"安装程序启发式"只看名字，哪怕清单里没有 requireAdministrator
# 也会照要求提权（实测：ui_uninst.exe 被挡 WinError 740，ui_rm.exe 正常）。
INST = "ui_probe.exe"        # 安装器（无清单版）
UNINST = "ui_rm.exe"         # 卸载器（无清单版）

# 安装器会把"自己所在目录"整个当 payload，所以测试用的 ui_probe.exe / ui_rm.exe
# 也会被拷进游戏目录。它们不是补丁内容、卸载器也不认它们，比对时排除。
TEST_ARTIFACTS = {INST, UNINST}


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def snap(root):
    """{相对路径: (大小, md5)}；跳过备份目录（每次安装时间戳都不同，无法比对）"""
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


def kill_game():
    subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "launcher.exe"], capture_output=True)


def build_nomanifest():
    """编译无清单版 安装器/卸载器（自动化才跑得动）"""
    for d in (BUILD, STAGE):
        os.makedirs(d, exist_ok=True)
    shutil.copy2(os.path.join(SETUP_SRC, "game.ico"), os.path.join(BUILD, "game.ico"))
    with open(os.path.join(BUILD, "test.rc"), "w") as f:
        f.write('#include <windows.h>\n101 ICON "game.ico"\n')
    mapping = [("RNDZhSetup.cpp", INST), ("RNDZhUninstall.cpp", UNINST)]
    for src_name, out_name in mapping:
        shutil.copy2(os.path.join(SETUP_SRC, src_name), os.path.join(BUILD, src_name))
        bat = os.path.join(BUILD, "b_%s.bat" % out_name)
        with open(bat, "w", newline="\r\n") as f:
            f.write(
                '@echo off\n'
                'call "C:\\VS2022BT\\VC\\Auxiliary\\Build\\vcvars32.bat" >nul\n'
                'cd /d "%s"\n'
                'rc /nologo /fo test.res test.rc\n'
                'cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE '
                '%s /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup '
                'gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib advapi32.lib '
                'test.res /OUT:%s\n' % (BUILD, src_name, out_name))
        r = subprocess.run(["cmd", "/c", bat], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        exe = os.path.join(BUILD, out_name)
        if not os.path.exists(exe):
            print("!! 编译失败 %s:\n%s" % (src_name, (r.stdout or "")[-900:]))
            return False
        raw = open(exe, "rb").read()
        print("  %-16s requireAdministrator=%s  大小=%d"
              % (out_name, "有(不对)" if b"requireAdministrator" in raw else "无 ✓",
                 len(raw)))
    return True


def stage_payload():
    """补丁包内容 + 无清单版安装器/卸载器 → STAGE（安装器从自身目录取 payload）"""
    for n in os.listdir(PAYLOAD_SRC):
        if n == "RNDZhSetup.exe":
            continue                       # 安装器不会安装它自己（源里也没有）
        s = os.path.join(PAYLOAD_SRC, n)
        d = os.path.join(STAGE, n)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    # 发布版卸载器带清单，自动化跑不了 —— 测试时移走，用无清单版
    pub = os.path.join(STAGE, "RNDZhUninstall.exe")
    if os.path.exists(pub):
        os.remove(pub)
    shutil.copy2(os.path.join(BUILD, UNINST), os.path.join(STAGE, UNINST))
    shutil.copy2(os.path.join(BUILD, INST), os.path.join(STAGE, INST))
    return os.path.join(STAGE, INST)


def run(exe, args, cwd=None, timeout=300):
    return subprocess.run([exe] + args, capture_output=True, cwd=cwd, timeout=timeout)


def probe_load():
    """启动游戏，返回 (dll全路径, log字节, 是否生效)"""
    log = os.path.join(TARGET, "languagebarrier", "log.txt")
    if os.path.exists(log):
        try:
            os.remove(log)
        except OSError:
            pass
    kill_game()
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
    try:
        p.kill()
    except OSError:
        pass
    kill_game()
    time.sleep(1.5)
    return dll, sz, ("steamapps" in dll.lower()) and sz > 0


# ─────────────── 开始 ───────────────
print("目标: %s" % os.path.basename(TARGET))
print("分号片段: %s" % FRAG)
print()

print("=== 0. 编译无清单版安装器/卸载器 ===")
if not build_nomanifest():
    sys.exit(1)
INST_EXE = stage_payload()
print("  payload: %s" % STAGE)
print()

print("=== 1. 先回到纯净状态 ===")
kill_game()
time.sleep(1)
if os.path.isdir(os.path.join(TARGET, "languagebarrier")):
    print("  目录里装着旧版补丁，先用卸载器清掉…")
    shutil.copy2(os.path.join(BUILD, UNINST), os.path.join(TARGET, UNINST))
    r = run(os.path.join(TARGET, UNINST), ["/silent"], cwd=TARGET)
    print("  卸载返回码 %s" % r.returncode)
    for _ in range(90):
        time.sleep(1)
        if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
            break
    time.sleep(2)
# 清掉历史测试可能留下的痕迹
for junk in (FRAG, UNINST, INST, "RNDZh-Setup-v0.1.exe"):
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
    print("=== 2. 安装（/silent）===")
    t0 = time.time()
    r = run(INST_EXE, [TARGET, "/silent"], cwd=STAGE)
    print("  返回码 %s，耗时 %.0f 秒" % (r.returncode, time.time() - t0))

    sub = os.path.join(TARGET, FRAG)
    print("  兼容子目录「%s」: %s" % (FRAG, "已创建 ✓" if os.path.isdir(sub) else "未创建 ✗"))
    if os.path.isdir(sub):
        print("  内含: %s" % sorted(os.listdir(sub)))
    print()

    print("=== 3. 确认补丁真的加载（关键验证）===")
    dll, sz, ok = probe_load()
    print("  实际加载: %s" % dll)
    print("  log.txt : %s" % (("%dB" % sz) if sz else "未生成"))
    print("  判定    : %s" % ("✓ 补丁生效（目录名含分号也能用了）" if ok
                              else "✗ 补丁没跑 —— 修法无效"))
    print()

    print("=== 4. 卸载 ===")
    shutil.copy2(os.path.join(BUILD, UNINST), os.path.join(TARGET, UNINST))
    t0 = time.time()
    r = run(os.path.join(TARGET, UNINST), ["/silent"], cwd=TARGET)
    print("  返回码 %s，耗时 %.0f 秒" % (r.returncode, time.time() - t0))
    for _ in range(90):
        time.sleep(1)
        if not os.path.isdir(os.path.join(TARGET, "languagebarrier")):
            break
    time.sleep(2)

    after = snap(TARGET)
    extra = sorted(set(after) - set(before))
    missing = sorted(set(before) - set(after))
    changed = sorted(k for k in (set(before) & set(after)) if before[k] != after[k])
    real_extra = [e for e in extra if os.path.basename(e) not in TEST_ARTIFACTS]
    print("  多余 %d（其中 %d 个是测试工具自身）| 缺失 %d | 不同 %d"
          % (len(extra), len(extra) - len(real_extra), len(missing), len(changed)))
    for k in real_extra[:15]:
        print("    多余: %s" % k)
    for k in missing[:15]:
        print("    缺失: %s" % k)
    for k in changed[:15]:
        print("    不同: %s" % k)
    frag_left = os.path.isdir(sub)
    print("  兼容子目录: %s" % ("已清掉 ✓" if not frag_left else "仍存在 ✗"))
    print()
    clean = (not real_extra) and (not missing) and (not changed) and (not frag_left)
    if clean:
        print("★ 通过：含分号的目录名也能自动兼容，卸载后逐字节回到纯净。")
    else:
        print("!! 未通过，差异见上。")
finally:
    kill_game()
    # 测试工具会被安装器拷进游戏目录（安装器把自身所在目录当 payload），
    # 跑完必须清掉，否则游戏目录里会多出 ui_probe.exe / ui_rm.exe 这种怪文件。
    for n in (INST, UNINST):
        p = os.path.join(TARGET, n)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    for d in (BUILD, STAGE):
        shutil.rmtree(d, ignore_errors=True)
    print()
    print("已清理测试工具与暂存目录（%s / %s）" % (BUILD, STAGE))
