# -*- coding: utf-8 -*-
"""Create ASCII junction entry points for the CJK-named game folders.

Root cause (verified with modscan32 on the live process, see tmp_128/):
  A local proxy dinput8.dll is only picked up when the game is reached through a path
  that is pure ASCII. Launching the very same directory via an ASCII junction flips the
  loader back to the local DLL:

     ...\\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本      -> C:\\WINDOWS\\SYSTEM32\\DINPUT8.dll
     D:\\...\\RND_EN_copy_ascii  (junction to it)        -> <game>\\DINPUT8.dll

So each affected folder gets an ASCII junction. Junctions cost no disk space and stay
valid when the target folder is renamed/moved within the same volume.

    python scripts/make_ascii_links.py            # 创建（已存在则跳过）
    python scripts/make_ascii_links.py --remove   # 全部删除
"""
import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMMON = r"D:/Ruanjian/Steam/steamapps/common"

# (ASCII 链接名, 目标目录)
LINKS = [
    ("RND_DaSH_steam",    os.path.join(COMMON, "ROBOTICS;NOTES DaSH")),
    ("RND_DaSH_jp_copy",  os.path.join(COMMON, "ROBOTICS;NOTES DaSH -原版日语 副本 - 副本")),
    ("RND_DaSH_en_copy",  os.path.join(COMMON, "ROBOTICS;NOTES DaSH -原版英文 副本 - 副本")),
]
# 说明：两个「- 副本 - 副本」是原本就带中文名的，需要 ASCII 入口；
#      Steam 正本与盗版(ZZGAME) 路径本来就是 ASCII，不需要。


def run(*args):
    return subprocess.run(list(args), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def is_junction(p):
    if not os.path.isdir(p):
        return False
    r = run("powershell", "-NoProfile", "-Command",
            "(Get-Item -LiteralPath '%s' -Force).LinkType" % p.replace("/", "\\"))
    return (r.stdout or "").strip().lower() in ("junction", "symboliclink")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remove", action="store_true")
    args = ap.parse_args()

    rc = 0
    for name, target in LINKS:
        link = os.path.join(COMMON, name)
        if args.remove:
            if is_junction(link):
                run("cmd", "/c", "rmdir", link.replace("/", "\\"))
                print("  删除 %s" % link)
            continue

        if not os.path.isdir(target):
            print("  %-46s 跳过（目标不存在）" % name)
            continue
        if is_junction(link):
            print("  %-22s 已存在 -> %s" % (name, target))
            continue
        if os.path.exists(link):
            print("  %-22s ★ 已存在同名实体（非链接），跳过" % name)
            rc = 1
            continue
        r = run("cmd", "/c", "mklink", "/J",
                link.replace("/", "\\"), target.replace("/", "\\"))
        ok = is_junction(link) and os.path.exists(os.path.join(link, "Game.exe"))
        print("  %-22s %s -> %s" % (name, "创建成功" if ok else "★ 失败", target))
        if not ok:
            print("      %s" % (r.stdout or r.stderr).strip()[:120])
            rc = 1

    print()
    if args.remove:
        print("已移除全部 ASCII 入口")
    else:
        print("ASCII 入口就绪 —— 请从这些路径启动游戏：")
        for name, _ in LINKS:
            p = os.path.join(COMMON, name)
            if is_junction(p):
                print("   %s" % p)
    return rc


if __name__ == "__main__":
    sys.exit(main())
