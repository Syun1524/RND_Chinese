# -*- coding: utf-8 -*-
"""Create ASCII junction entry points for the game folders.

用途：给这些目录提供**纯 ASCII 的入口路径**，方便命令行/自动化操作。
**与补丁能不能加载无关** —— 分号路径的问题已由安装器自动解决（见下）。

分号目录的真实机制（2026-09-12 定死，见 scripts/diagnostics/）：
  目录名含 `;` 时，Windows 加载器把目录路径**按 `;` 切开**，把分号后面每一段
  当成**相对目录名**（相对游戏目录）再搜一遍；本地 dinput8.dll 只有在那个
  子目录存在、且里面放了 DLL 时才会被加载。

  实测（predict_mechanism.py，三条可证伪预测全部命中）：
      目录名 RNDt                      → 无片段         → 本地 ✓
      目录名 RND;t（无 t\\ 子目录）      → 片段 t 不存在  → 系统 ✗
      目录名 RND;t（建了 t\\ 放 DLL）    → 片段 t 存在    → 本地 ✓
      RND;NOTES DaSH（NOTES DaSH 已存在）→              本地 ✓

  **长度和中文都不是变量**（早先"长路径""中文"两个结论来自混了变量的样本，都是错的）。
  CoZ 原版补丁正是因为这样才在 payload 里带一个写死名字的 `NOTES DaSH\\`。

现在的解决办法（安装器内置，玩家不用管）：
  安装器按游戏目录名**实时算**出分号后每一段，自动建同名子目录并把代理 DLL
  复制进去（`SemicolonFragments()`）。所以本脚本**不再是补丁生效的必需品**。

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
    ("RND_EN_copy2",      os.path.join(COMMON, "ROBOTICS;NOTES DaSH -原版英文 副本 - 副本")),
]
# 这些入口现在只是**操作便利**（纯 ASCII 路径，命令行/自动化好写），
# 不再影响补丁加载。四个入口都保留，是因为历史脚本和人工排查时都用惯了这些名字。
#
# 下面这段曾经的"为什么必需"（含分号+长度阈值）是**误判**，已作废：
#   触发条件从来不是长度，也不是中文 —— 唯一变量是分号，且机制是
#   "分号后的片段被当相对目录搜"。完整实测见文件头与
#   scripts/diagnostics/predict_mechanism.py。


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
