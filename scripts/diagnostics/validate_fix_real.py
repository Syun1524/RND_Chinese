# -*- coding: utf-8 -*-
r"""在【真实失败目录】上验证修法：建分号片段同名的子目录 → виправить补丁加载。

前面 predict_mechanism.py 用样本目录证明了机制（三条预测全中），
characterize_fix.py 量清了实现细节。本脚本做最后一步：
拿一个**当前真的加载不了**的实例（英文副本-副本，名字里有分号），
按机制建一个子目录，看它是否立刻恢复 —— 这直接验证"安装器可以自动修好"。

子目录名 = 目录名里分号【后面】那一段（加载器就是拿它当相对路径搜的）。
只多建这一个目录，其余原样。
"""
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

TARGET = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本"
MODSCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modscan32.exe")

# 代理 DLL：游戏静态导入 dinput8；dxgi/d3d* 是 DXVK 的，VBFilter 是字幕渲染。
# 片段目录里都放一份，跟补丁包根目录保持一致。
DLLS = ["dinput8.dll", "d3d9", "d3d10", "d3d10_1", "d3d10core", "d3d11", "dxgi",
        "VSFilter.dll"]


def kill_game():
    subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "launcher.exe"], capture_output=True)


def probe(path):
    log = os.path.join(path, "languagebarrier", "log.txt")
    if os.path.exists(log):
        try:
            os.remove(log)
        except OSError:
            pass
    kill_game()
    time.sleep(2)
    p = subprocess.Popen([os.path.join(path, "Game.exe"), "roboticsnotesd", "EN"],
                         cwd=path, stdout=subprocess.DEVNULL,
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
    ok = ("steamapps" in dll.lower()) and sz > 0
    return dll, sz, ok


def fragments(dirname):
    """目录名按分号切开后，除第一段外的所有非空片段（加载器会把它们当相对目录）"""
    parts = [p for p in dirname.split(";")]
    return [p for p in parts[1:] if p.strip()]


name = os.path.basename(TARGET)
frags = fragments(name)
print("目标: %s" % name)
print("分号片段（加载器会当相对目录搜）: %s" % frags)
print()
if not os.path.isdir(TARGET):
    sys.exit("目标不存在: %s" % TARGET)

made = []
try:
    # 修前
    dll, sz, ok = probe(TARGET)
    print("修前: %-6s log=%-7s %s" % ("成功" if ok else "失败",
                                      ("%dB" % sz) if sz else "-", dll))

    # 按机制建子目录
    for f in frags:
        sub = os.path.join(TARGET, f)
        if not os.path.isdir(sub):
            os.makedirs(sub, exist_ok=True)
            made.append(sub)
        for n in DLLS:
            s = os.path.join(TARGET, n)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(sub, n))
        print("已建: %s\\  <- 放了 %d 个代理 DLL" % (f, len(DLLS)))

    # 修后
    dll, sz, ok = probe(TARGET)
    print()
    print("修后: %-6s log=%-7s %s" % ("成功" if ok else "失败",
                                      ("%dB" % sz) if sz else "-", dll))
    if ok:
        print()
        print("★ 结论：只多建一个「分号片段同名子目录」，原本加载不了的目录就恢复 ——")
        print("  这个修法可以写进安装器（用户不用改名、不用 junction）。")
    # 恢复原状：删掉刚建的子目录
    for d in made:
        shutil.rmtree(d, ignore_errors=True)
    print()
    print("已清理新建子目录: %s" % [os.path.basename(d) for d in made])
finally:
    kill_game()
