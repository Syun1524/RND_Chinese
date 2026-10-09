# -*- coding: utf-8 -*-
"""门禁：mgsFileOpenHook 必须放行 fileId == 0（否则 manual/0 控制器图不汉化）。

背景（2026-09-29 实机 bug）：
  帮助页的「手柄操作图」与「键盘操作图」分别存在 `manual` 归档的 **fileId 0 / 1**。
  CoZ 上游的 mgsFileOpenHook 用 `fileId > 0` 当「确实要开一个文件」的判据，
  于是 **fileId 0 被整条跳过** —— 键盘图（1）汉化正常、手柄图（0）始终是日文原图。
  实测判据：截图里左列标签与日文图集逐像素相关度 1.0，与中文图集 0.185。

本门禁检查三件事：
  A. 源码里那处守卫是 `>= 0`（不是 `> 0`）；
  B. 已发布的 dinput8.dll 里，该守卫编译成 jns/jge（0x79 / 0x7d），而不是 jg（0x7f）；
  C. patchdef 里确实存在 key "0" 的重定向（证明这条路径真的被用到）。

负向自测（negtest_fileid0_guard.py）会故意把三处各自破坏一次，确认本脚本报 FAIL。

用法：
    python scripts/check_fileid0_guard.py                 # 检查补丁包 + 仓库
    python scripts/check_fileid0_guard.py --dll <path>    # 只查某个 DLL
"""
import argparse
import hashlib
import io
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

REPO_SRC = os.path.join(ROOT, "..", "GitHub", "RND_Chinese",
                        "LanguageBarrier_chs", "LanguageBarrier", "Game.cpp")
PKG_DLL = os.path.join(ROOT, "成品ing", "补丁包", "dinput8.dll")
REPO_DLL = os.path.join(ROOT, "..", "GitHub", "RND_Chinese", "LanguageBarrier_chs",
                        "LanguageBarrier", "dinput8-Release", "dinput8.dll")
PKG_LB = os.path.join(ROOT, "成品ing", "补丁包", "languagebarrier")

# 守卫的字节骨架（test ecx,ecx / je / test ebx,ebx / jcc / test esi,esi / je / cmp [esi],0 / je）。
# ⚠ 不要写死 rel32：那是**相对偏移**，随编译器版本与函数长度变化。
#   v142 版发布 DLL 是 `... 85 db 79 11 ...`，v143 重编后同一逻辑是
#   `... 85 db 79 11 ...` 但四条跳转的 rel32 各差 1（bc/b0/a7 → bd/b1/a8）。
#   所以用正则匹配「骨架 + 任意 rel32」，只在 jcc 那个字节上区分 jg / jns / jge。
GUARD_RE = re.compile(
    rb"\x85\xc9\x0f\x84.{4}"          # test ecx,ecx ; je
    rb"\x85\xdb(?P<jcc>[\x7f\x79\x7d])."  # test ebx,ebx ; jg/jns/jge rel8
    rb"\x85\xf6\x0f\x84.{4}"          # test esi,esi ; je
    rb"\x80\x3e\x00\x0f\x84.{4}",     # cmp byte [esi],0 ; je
    re.DOTALL)


def check_source(path):
    """A. Game.cpp 的守卫必须是 >= 0"""
    errs = []
    if not os.path.exists(path):
        return ["源码不存在: %s" % path]
    text = io.open(path, encoding="utf-8-sig", errors="replace").read()
    if "fileId >= 0" not in text:
        errs.append("Game.cpp 里找不到 `fileId >= 0`（守卫可能被改回 `> 0`）")
    if "(fileId > 0 ||" in text:
        errs.append("Game.cpp 里仍有 `(fileId > 0 ||` —— fileId 0 会被跳过")
    return errs


def check_dll(path):
    """B. DLL 里的守卫必须是 jns/jge"""
    errs = []
    if not os.path.exists(path):
        return ["DLL 不存在: %s" % path]
    data = open(path, "rb").read()
    hits = list(GUARD_RE.finditer(data))
    bad = [h for h in hits if h.group("jcc") == b"\x7f"]
    good = [h for h in hits if h.group("jcc") in (b"\x79", b"\x7d")]
    if bad:
        errs.append("%s: 守卫仍是 jg（fileId > 0），共 %d 处 —— fileId 0 会被跳过"
                    % (os.path.basename(path), len(bad)))
    if len(good) != 1:
        errs.append("%s: 期望恰好 1 处 jns/jge 守卫，实际 %d 处（总命中 %d）"
                    % (os.path.basename(path), len(good), len(hits)))
    return errs


def check_patchdef(lb_dir):
    """C. patchdef 里必须有 key \"0\" 的重定向（证明这条路径被用到）"""
    errs = []
    p = os.path.join(lb_dir, "patchdef.json")
    if not os.path.exists(p):
        return ["patchdef.json 不存在: %s" % p]
    d = json.load(io.open(p, encoding="utf-8-sig"))
    fr = d.get("base", {}).get("fileRedirection", {})
    zero = {a: m["0"] for a, m in fr.items() if isinstance(m, dict) and "0" in m}
    if not zero:
        errs.append("patchdef 里没有任何 key \"0\" 的重定向 —— 本门禁失去意义，请核对设计")
    # 顺便核对索引在 cls 范围内、且指向 png
    cls_p = os.path.join(lb_dir, "c0data.cls")
    if os.path.exists(cls_p):
        cls = [l.strip() for l in
               io.open(cls_p, encoding="utf-8-sig").read().splitlines() if l.strip()]
        for a, idx in zero.items():
            if not (isinstance(idx, int) and 0 <= idx < len(cls)):
                errs.append("%s fileId 0 -> 越界索引 %r" % (a, idx))
            elif not cls[idx].lower().endswith(".png"):
                errs.append("%s fileId 0 -> %s（期望 png）" % (a, cls[idx]))
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", action="append", default=None,
                    help="只检查指定 DLL（可多次）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    all_errs = []
    if args.dll:
        for d in args.dll:
            all_errs += check_dll(d)
    else:
        all_errs += check_source(REPO_SRC)
        all_errs += check_dll(PKG_DLL)
        all_errs += check_dll(REPO_DLL)
        all_errs += check_patchdef(PKG_LB)

    if not args.quiet:
        print("=== fileId 0 守卫门禁 ===")
        print("  源码:", "OK" if not check_source(REPO_SRC) else "FAIL")
        for tag, p in (("补丁包 DLL", PKG_DLL), ("仓库 DLL", REPO_DLL)):
            e = check_dll(p)
            print("  %s: %s" % (tag, "OK" if not e else "FAIL"))
        print("  patchdef key\"0\":", "OK" if not check_patchdef(PKG_LB) else "FAIL")
        if all_errs:
            print("\n问题:")
            for e in all_errs:
                print("  - %s" % e)

    print("\nRESULT: %s" % ("PASS" if not all_errs else "FAIL"))
    return 0 if not all_errs else 1


if __name__ == "__main__":
    sys.exit(main())
