# -*- coding: utf-8 -*-
"""清理隔离测试留下的 junction，只删链接、绝不删真实目录。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

COMMON = r"D:\Ruanjian\Steam\steamapps\common"

# 隔离测试建的临时 junction（这些名字是测试专用，真实游戏目录不叫这些）
SUSPECTS = [
    "测试",
    "RND_EN_copy_ascii_verylongdirname_0123456789abcdef",
    "ROBOTICS;NOTES DaSH -abcdefgh ijkl - mnop",
    "ROBOTICS NOTES DaSH -原版英文 副本 - 副本",
    "ROBOTICS NOTES DaSH -abcdefgh ijkl - mnop",
    "ROBOTICS NOTES DaSH -abcdefgh ijkl - mno;",
    ";ROBOTICS NOTES DaSH -abcdefgh ijkl - mnop",
]


def link_type(p):
    ps = "(Get-Item -LiteralPath '%s' -Force).LinkType" % p
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "").strip().lower()


print("=== 清理测试 junction ===")
for d in SUSPECTS:
    p = os.path.join(COMMON, d)
    if not os.path.exists(p):
        continue
    lt = link_type(p)
    if lt in ("junction", "symboliclink"):
        subprocess.run(["cmd", "/c", "rmdir", p], capture_output=True)
        print("  已删 junction: %s" % d)
    else:
        print("  ★保留（真实目录，非链接）: %s" % d)

print()
print("=== 当前 ROBOTICS / RND 相关目录 ===")
for d in sorted(os.listdir(COMMON)):
    if "ROBOTIC" in d.upper() or d.upper().startswith("RND"):
        p = os.path.join(COMMON, d)
        lt = link_type(p)
        tag = ("LINK -> " + lt) if lt else "真实目录"
        print("  %-52s %s" % (d, tag))
