# -*- coding: utf-8 -*-
"""决定性诊断：路径含分号时，游戏到底加载了哪个 dinput8.dll？

两种可能，修法完全不同：
  A) 加载器跳过了本地 DLL（用了 System32 那份）→ LanguageBarrier 从未启动
  B) 本地 DLL 加载了，但 LanguageBarrier 初始化失败（比如相对路径打不开日志）

用 modscan32 扫描运行中游戏进程的已加载模块，看 dinput8.dll 的**完整路径**即可区分。
（tasklist /m 对 32 位游戏进程静默返回空，64 位 PowerShell 也枚举不了，所以必须用它。）
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

MODSCAN = r"D:\DATA\tran\agent tran\9.6文本外工作\scripts\diagnostics\modscan32.exe"
TARGET = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本"
COMMON = r"D:\Ruanjian\Steam\steamapps\common"

CASES = [
    ("无分号(junction)", os.path.join(COMMON, "RND_probe_noSemi")),
    ("含分号(junction)", os.path.join(COMMON, "RND_probe;Semi")),
]


def mk(link):
    if os.path.exists(link):
        subprocess.run(["cmd", "/c", "rmdir", link], capture_output=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", link, TARGET], capture_output=True)
    return os.path.isdir(link)


def run(path, label):
    log = os.path.join(TARGET, "languagebarrier", "log.txt")
    if os.path.exists(log):
        os.remove(log)
    subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
    time.sleep(2)
    p = subprocess.Popen([os.path.join(path, "Game.exe"), "roboticsnotesd", "EN"],
                         cwd=path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(12)
    r = subprocess.run([MODSCAN, str(p.pid), "dinput"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    mods = [l.strip() for l in (r.stdout or "").splitlines() if not l.startswith("#")]
    got = os.path.exists(log) and os.path.getsize(log) > 0
    print("=== %s ===" % label)
    print("  路径: %s" % path)
    print("  加载的 dinput8: %s" % (mods[0].split("\t")[-1] if mods else "(未找到)"))
    print("  log.txt: %s" % ("✓ 生成 %d B" % os.path.getsize(log) if got else "✗ 未生成"))
    p.kill()
    subprocess.run(["taskkill", "/F", "/IM", "Game.exe"], capture_output=True)
    time.sleep(1)
    return mods, got


print("目标目录（真实路径，含分号）: %s" % TARGET)
print()
for label, link in CASES:
    if mk(link):
        run(link, label)
    else:
        print("=== %s === junction 建立失败" % label)
    print()

subprocess.run(["cmd", "/c", "rmdir", CASES[0][1]], capture_output=True)
subprocess.run(["cmd", "/c", "rmdir", CASES[1][1]], capture_output=True)
print("（已清理测试 junction）")
