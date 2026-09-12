# -*- coding: utf-8 -*-
"""分隔变量实验：到底是【分号】【长度】【中文】还是【别的】让本地 dinput8.dll 不被加载？

背景：以前的实验一次改好几个变量（verify_shortname.py 把 长+分号+中文 一次换成 短+无分号+ASCII），
所以只能得出"改短就好"，说不清是谁的锅；而且中途有几次结论互相矛盾
（AGENTS.md 里先写"中文导致"，后改口"分号+长度"，两次都是从一个混了变量的样本推的）。

这次的做法：拿**同一个已装补丁的真实目录**，只改目录名，一次只动一个变量。

两个信号，互相独立，避免单一测量方式的偏差：
  1. log.txt 是否生成（AGENTS.md 认定的正向信号：LB 一启动必写）—— 二进制、无编码问题
  2. modscan32 扫描运行中进程实际加载的 dinput8.dll 全路径 —— 用 "steamapps" 子串判本地
     （不能用中文子串匹配：wprintf 走管道时按 ANSI 代码页转换，中文会变成 '?'）

每轮之间名字严格还原，全程 try/finally。
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

COMMON = r"D:\Ruanjian\Steam\steamapps\common"
SAMPLE = "ROBOTICS;NOTES DaSH -副本"        # 装了补丁，名字短、无中文，做样本最干净
MODSCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modscan32.exe")

# 名字设计：短/长 × 有/无分号 × 纯ASCII/含中文，外加两个真实世界的名字
CASES = [
    ("A 短 ASCII 无分号",     "RNDt"),                      # 对照基线
    ("B 短 ASCII 有分号",     "RND;t"),                     # 与 A 只差一个分号、同长度附近
    ("C 长 ASCII 无分号",     "RNDt_" + "a" * 33),          # 与 D 只差分号
    ("D 长 ASCII 有分号",     "RND;t_" + "a" * 32),         # 与 C 只差分号
    ("E 短 中文 无分号",      "RND测试"),                    # 与 A 只差"是否中文"
    ("F 长 中文 无分号",      "RND_测试" * 6),               # 与 C 长度相近
    ("G 真实:Steam正本名",    "ROBOTICS;NOTES DaSH"),        # 短 + 有分号（实际能用）
    ("H 同G长度 无分号",      "ROBOTICS!NOTES DaSH"),        # 与 G 同长，换个标点
]


def kill_game():
    subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
    # 加载失败会弹模态框，进程照样活着；一并清掉免得干扰下一轮
    subprocess.run(["taskkill", "/F", "/IM", "launcher.exe"], capture_output=True)


def probe(path):
    """返回 (实际加载的 dinput8 全路径, log 字节数)"""
    log = os.path.join(path, "languagebarrier", "log.txt")
    if os.path.exists(log):
        try:
            os.remove(log)
        except OSError:
            pass
    kill_game()
    time.sleep(2)
    try:
        p = subprocess.Popen([os.path.join(path, "Game.exe"), "roboticsnotesd", "EN"],
                             cwd=path, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    except OSError as e:
        return "(启动失败: %s)" % e, 0

    for _ in range(30):
        time.sleep(1)
        if os.path.exists(log) and os.path.getsize(log) > 0:
            break
        if p.poll() is not None:
            break

    alive = p.poll() is None
    r = subprocess.run([MODSCAN, str(p.pid), "dinput"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    mods = [l.strip() for l in (r.stdout or "").splitlines()
            if not l.startswith("#")]
    dll = mods[0].split("\t")[-1] if mods else "(扫不到)"
    sz = os.path.getsize(log) if os.path.exists(log) else 0
    if not alive:
        dll += "  [进程已退出]"
    try:
        p.kill()
    except OSError:
        pass
    kill_game()
    time.sleep(1.5)
    return dll, sz


def verdict(dll, sz):
    """两个独立判据：log.txt 出现 = 补丁跑了；dll 路径含 steamapps = 加载的是本地那份"""
    if dll == "(扫不到)":
        return "? 扫不到"
    # 管道里 wprintf 按 ANSI 转换，中文变 '?'，所以只认 ASCII 的 steamapps 子串
    dll_local = "steamapps" in dll.lower()
    log_ok = sz > 0
    if dll_local and log_ok:
        return "✓ 本地"
    if not dll_local and not log_ok:
        return "✗ 系统"
    return "! 矛盾(dll=%s,log=%dB)" % ("本地" if dll_local else "系统", sz)


orig = os.path.join(COMMON, SAMPLE)
if not os.path.isfile(os.path.join(orig, "dinput8.dll")):
    sys.exit("样本没装补丁：%s" % orig)

print("样本目录: %s   （内容一律不动，只改目录名）" % SAMPLE)
print("前缀长度: %d" % (len(COMMON) + 1))
print()
print("%-20s %-5s %-9s %-7s %s" % ("标签", "路径长", "判定", "log", "实际加载的 dinput8.dll"))
print("-" * 108)

cur = SAMPLE
try:
    for label, name in CASES:
        target = os.path.join(COMMON, name)
        src = os.path.join(COMMON, cur)
        if os.path.normcase(src) != os.path.normcase(target):
            if os.path.exists(target):
                print("%-20s 跳过（名字被占用）: %s" % (label, name))
                continue
            os.rename(src, target)
            cur = name
        dll, sz = probe(target)
        print("%-20s %-5d %-9s %-7s %s"
              % (label, len(target), verdict(dll, sz),
                 ("%dB" % sz) if sz else "-", dll))
finally:
    if cur != SAMPLE:
        back = os.path.join(COMMON, SAMPLE)
        if os.path.exists(back):
            print("\n!! 原名被占用，停在: %s" % cur)
        else:
            os.rename(os.path.join(COMMON, cur), back)
            cur = SAMPLE
    print()
    print("已恢复原名: %s  存在=%s" % (SAMPLE, os.path.isdir(orig)))
