# -*- coding: utf-8 -*-
r"""盘点四个安装目录：补丁加载没有？分号片段子目录在不在？

分号机制的结论（predict_mechanism.py 已验证）意味着：目录名含分号时，
补丁是否生效完全取决于「分号后片段同名子目录」存不存在、里面有没有代理 DLL。
这个脚本把四个真实安装逐个过一遍，给出「能/不能」以及原因，
用来确认新版安装器需要修哪几个、以及老安装留下的现状。

只看两条硬证据：log.txt 是否生成 + modscan32 报的 dinput8 全路径。
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

MODSCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modscan32.exe")

INSTALLS = [
    ("Steam 正本",       r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH"),
    ("日文副本入口",     r"D:\Ruanjian\Steam\steamapps\common\RND_DaSH_jp_copy"),
    ("英文副本入口",     r"D:\Ruanjian\Steam\steamapps\common\RND_EN_copy2"),
    ("盗版英文(旧版)",   r"D:\ZZGAME\ROBOTICS NOTES DaSH"),
]


def frags_of(path):
    """目录名按分号切开后，除第一段外的片段（加载器当相对目录搜的那几个）"""
    name = os.path.basename(path.rstrip("\\/"))
    parts = name.split(";")
    out = []
    for p in parts[1:]:
        p = p.rstrip(" .")
        if p:
            out.append(p)
    return out


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
    exe = os.path.join(path, "Game.exe")
    if not os.path.isfile(exe):
        return "(无 Game.exe)", 0, None
    p = subprocess.Popen([exe, "roboticsnotesd", "EN"], cwd=path,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    return dll, sz, ("steamapps" in dll.lower()) or ("ZZGAME" in dll.upper()) or \
                    ("Ruanjian" in dll) or ("\\\\" not in dll and dll != "(扫不到)" and
                                            "SYSTEM32" not in dll.upper())


for label, path in INSTALLS:
    print("=" * 96)
    print("%s\n  %s" % (label, path))
    if not os.path.isdir(path):
        print("  目录不存在")
        continue
    installed = os.path.isdir(os.path.join(path, "languagebarrier"))
    print("  补丁已装: %s" % ("是" if installed else "否"))
    fg = frags_of(path)
    print("  分号片段: %s" % (fg if fg else "（无）"))
    for f in fg:
        sub = os.path.join(path, f)
        has = os.path.isdir(sub)
        dll = os.path.isfile(os.path.join(sub, "dinput8.dll")) if has else False
        print("    子目录「%s」: %s%s" % (f, "存在" if has else "不存在",
                                        "（有 dinput8.dll ✓）" if dll else
                                        "（无 dinput8.dll）" if has else ""))
    if installed:
        dll, sz, ok = probe(path)
        print("  实测加载: %s" % dll)
        print("  log.txt : %s" % (("%dB" % sz) if sz else "未生成"))
        print("  结论    : %s" % ("✓ 补丁生效" if ok else "✗ 补丁没跑"))
    print()
