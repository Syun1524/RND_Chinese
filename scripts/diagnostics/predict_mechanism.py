# -*- coding: utf-8 -*-
r"""锁死机制：分号把加载器的搜索路径切开，分号**后面那一段**被当成相对目录去搜。

由 semicolon_decisive.py 观察到的关键事实：真实 Steam 正本 `...\ROBOTICS;NOTES DaSH`
（**含分号**）能加载，而且加载的是 `...\ROBOTICS;NOTES DaSH\NOTES DaSH\DINPUT8.dll`
—— 来自**子目录**，不是根目录。那个 `NOTES DaSH\` 子目录不是游戏原装的
（两份纯净副本里都没有），是以前部署时放进去的。

由此得到的统一解释（能一次解释全部历史观测）：
    目录名 `A;B` 含分号时，加载器把搜索路径字符串按 `;` 切开，
    `B` 作为**相对路径**（相对当前工作目录 = 游戏目录）再搜一遍。
      → `ROBOTICS;NOTES DaSH`     切出 `NOTES DaSH` → 子目录存在（我们放过 DLL）→ 能用
      → `ROBOTICS;NOTES DaSH -副本` 切出 `NOTES DaSH -副本` → 不存在 → 不能用
      → `RND;t`                    切出 `t` → 不存在 → 不能用

本轮做**可证伪的预测测试**，三条预测全部命中才认：

  P1  改名 `RND;q7tail`（切出 `q7tail`，不存在）          预测：✗ 失败
  P2  在目录里建子目录 `q7tail\` 并放一份 dinput8.dll      预测：✓ 成功，且从 `q7tail\` 加载
  P3  改名 `RND;NOTES DaSH`（切出 `NOTES DaSH`，已存在）   预测：✓ 成功，且从 `NOTES DaSH\` 加载

P1→P2 只多了一个子目录，若结果由 ✗ 翻成 ✓，机制即坐实。
最后清掉 P2 建的目录并还原原名。
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


def report(label, path, expect_ok, dll, sz, ok):
    tag = "✓ 预测命中" if ok == expect_ok else "✗ 预测落空"
    print("%-34s 路径长%-4d %-9s %-7s %s" % (label, len(path),
                                             "成功" if ok else "失败",
                                             ("%dB" % sz) if sz else "-", tag))
    print("%-34s   → %s" % ("", dll))


orig = os.path.join(COMMON, SAMPLE)
if not os.path.isfile(os.path.join(orig, "dinput8.dll")):
    sys.exit("样本没装补丁：%s" % orig)

cur = SAMPLE
made_sub = None
print("样本: %s   前缀长度 %d" % (SAMPLE, len(COMMON) + 1))
print()
try:
    # ---- P1: 有分号，切出的段不存在 ----
    p1 = "RND;q7tail"
    src = os.path.join(COMMON, cur)
    if os.path.exists(os.path.join(COMMON, p1)):
        sys.exit("名字被占用: %s" % p1)
    os.rename(src, os.path.join(COMMON, p1))
    cur = p1
    t = os.path.join(COMMON, p1)
    assert not os.path.isdir(os.path.join(t, "q7tail")), "不该有 q7tail 子目录"
    dll, sz, ok = probe(t)
    report("P1  RND;q7tail（无 q7tail 子目录）", t, False, dll, sz, ok)

    # ---- P2: 建一个和分号后那段同名的子目录，只多这一步 ----
    sub = os.path.join(t, "q7tail")
    os.makedirs(sub, exist_ok=True)
    made_sub = sub
    for n in DLLS:
        s = os.path.join(t, n)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(sub, n))
    dll, sz, ok = probe(t)
    report("P2  RND;q7tail（建了 q7tail\\ 放 DLL）", t, True, dll, sz, ok)

    # ---- P3: 切出的段 = 已存在的 NOTES DaSH ----
    p3 = "RND;NOTES DaSH"
    if os.path.exists(os.path.join(COMMON, p3)):
        print("跳过 P3（名字被占用）")
    else:
        os.rename(t, os.path.join(COMMON, p3))
        cur = p3
        t3 = os.path.join(COMMON, p3)
        dll, sz, ok = probe(t3)
        report("P3  RND;NOTES DaSH（子目录已存在）", t3, True, dll, sz, ok)
finally:
    kill_game()
    time.sleep(1)
    # 清掉实验建的子目录
    if made_sub and os.path.isdir(made_sub):
        try:
            shutil.rmtree(made_sub, ignore_errors=True)
        except OSError:
            pass
    target_back = os.path.join(COMMON, SAMPLE)
    if cur != SAMPLE:
        curpath = os.path.join(COMMON, cur)
        if os.path.exists(target_back):
            print("\n!! 原名被占用，停在: %s" % cur)
        else:
            os.rename(curpath, target_back)
            cur = SAMPLE
    print()
    print("已恢复原名: %s  存在=%s" % (SAMPLE, os.path.isdir(target_back)))
    print("实验子目录 q7tail 已清理:", not os.path.isdir(os.path.join(target_back, "q7tail")))
