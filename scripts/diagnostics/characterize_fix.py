# -*- coding: utf-8 -*-
r"""把机制量清楚，供安装器实现"自动修好"用。

已证实的经验规则（predict_mechanism.py 三条预测全中）：
    目录名含 `;` 时，加载器把目录路径按 `;` 切开，
    分号**后面那些片段**被当作【相对目录名】，相对某个锚点去搜；
    本地 DLL 只有在那个相对目录存在且放了 DLL 时才被加载。

这个脚本回答 4 个实现相关的问题：

  T1  多个分号时，只建【最后一个】片段同名子目录 —— 能不能加载？
  T2  多个分号时，只建【第一个】片段同名子目录 —— 能不能加载？
  T3  锚点是谁？相对目录是相对【游戏目录】(CWD) 还是相对【分号前那段的父目录】？
      （在游戏目录外建一个同名目录，只在那一处放 DLL，看会不会被加载）
  T4  片段子目录里只放 dinput8.dll（不放 dxgi/d3d9/VSFilter）够不够？

T1/T2 决定"要建几个子目录"，T3 决定"建在哪"，T4 决定"放哪些文件"。
"""
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

COMMON = r"D:\Ruanjian\Steam\steamapps\common"
SAMPLE = "ROBOTICS;NOTES DaSH -副本"
MODSCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modscan32.exe")

DLLS = ["dinput8.dll", "d3d9", "d3d10", "d3d10_1", "d3d10core", "d3d11", "dxgi",
        "VSFilter.dll"]


def kill_game():
    subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "launcher.exe"], capture_output=True)


def probe(path, cwd=None):
    """返回 (loaded_dll_path, log_bytes, ok)"""
    log = os.path.join(path, "languagebarrier", "log.txt")
    if os.path.exists(log):
        try:
            os.remove(log)
        except OSError:
            pass
    kill_game()
    time.sleep(2)
    p = subprocess.Popen([os.path.join(path, "Game.exe"), "roboticsnotesd", "EN"],
                         cwd=cwd or path, stdout=subprocess.DEVNULL,
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
    kill_game()
    time.sleep(1.5)
    return dll, sz, ("steamapps" in dll.lower()) and sz > 0


def put(dst_dir, names):
    os.makedirs(dst_dir, exist_ok=True)
    for n in names:
        s = os.path.join(os.path.join(COMMON, CUR), n)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst_dir, n))


def line(tag, note, dll, sz, ok):
    print("%-6s %-40s %-7s %-7s %s"
          % (tag, note, "成功" if ok else "失败", ("%dB" % sz) if sz else "-", dll))


orig = os.path.join(COMMON, SAMPLE)
if not os.path.isfile(os.path.join(orig, "dinput8.dll")):
    sys.exit("样本没装补丁：%s" % orig)

CUR = SAMPLE
extra_outside = None
made = []
print("样本: %s" % SAMPLE)
print()

try:
    # ---------- T1 / T2：多分号，分别只建最后一个 / 第一个片段 ----------
    for tag, name, build in [
        ("T1", "RND;A1;B2", ["B2"]),      # 只建最后一个片段
        ("T2", "RND;A1;B2", ["A1"]),      # 只建第一个片段
    ]:
        cur_path = os.path.join(COMMON, CUR)
        tgt = os.path.join(COMMON, name)
        if os.path.exists(tgt) and name != CUR:
            print("%s 跳过：名字被占用 %s" % (tag, name))
            continue
        if name != CUR:
            os.rename(cur_path, tgt)
            CUR = name
        game = os.path.join(COMMON, CUR)
        # 先清掉这个实验可能残留的片段目录
        for seg in ("A1", "B2"):
            shutil.rmtree(os.path.join(game, seg), ignore_errors=True)
        for seg in build:
            put(os.path.join(game, seg), DLLS)
            made.append(os.path.join(game, seg))
        dll, sz, ok = probe(game)
        line(tag, "%s 只建片段目录 %s\\" % (name, "+".join(build)), dll, sz, ok)

    # ---------- T3：锚点 —— 只在游戏目录【外】建同名目录 ----------
    name = "RND;anchortest"
    tgt = os.path.join(COMMON, name)
    if os.path.exists(tgt) and name != CUR:
        print("T3 跳过：名字被占用")
    else:
        if name != CUR:
            os.rename(os.path.join(COMMON, CUR), tgt)
            CUR = name
        game = os.path.join(COMMON, CUR)
        shutil.rmtree(os.path.join(game, "anchortest"), ignore_errors=True)
        extra_outside = os.path.join(COMMON, "anchortest")   # ← 游戏目录【外】
        put(extra_outside, DLLS)
        dll, sz, ok = probe(game)
        line("T3", "只在游戏目录外 %s\\ 放 DLL" % "..\\anchortest", dll, sz, ok)

    # ---------- T4：片段目录里只放 dinput8.dll ----------
    name = "RND;donly"
    tgt = os.path.join(COMMON, name)
    if os.path.exists(tgt) and name != CUR:
        print("T4 跳过：名字被占用")
    else:
        if name != CUR:
            os.rename(os.path.join(COMMON, CUR), tgt)
            CUR = name
        game = os.path.join(COMMON, CUR)
        shutil.rmtree(os.path.join(game, "donly"), ignore_errors=True)
        put(os.path.join(game, "donly"), ["dinput8.dll"])   # 只放一个
        made.append(os.path.join(game, "donly"))
        dll, sz, ok = probe(game)
        line("T4", "片段目录只放 dinput8.dll", dll, sz, ok)

finally:
    kill_game()
    time.sleep(1)
    game = os.path.join(COMMON, CUR)
    for d in made:
        shutil.rmtree(d, ignore_errors=True)
    if extra_outside:
        shutil.rmtree(extra_outside, ignore_errors=True)
    back = os.path.join(COMMON, SAMPLE)
    if CUR != SAMPLE:
        curp = os.path.join(COMMON, CUR)
        if os.path.exists(back):
            print("\n!! 原名被占用，停在: %s" % CUR)
        else:
            os.rename(curp, back)
            CUR = SAMPLE
    print()
    print("已恢复原名: %s  存在=%s" % (SAMPLE, os.path.isdir(back)))
    for d in ("A1", "B2", "anchortest", "donly", "q7tail"):
        p = os.path.join(back, d)
        if os.path.isdir(p):
            print("  !! 残留子目录: %s" % d)
    print("  片段子目录已清理")
