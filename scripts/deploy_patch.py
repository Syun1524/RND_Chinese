# -*- coding: utf-8 -*-
"""Deploy the patch package into a game install, then verify the result.

`patchdef.json` and `c0data.cls` are a **matched pair**: fileRedirection stores c0data
array indices, so the .cls line order is part of the patch data. Copying one without the
other silently repoints every redirect — a real incident where a stale Steam .cls kept
ten trailing `.lkm` lines, shifting `title_chip_pc.png` from index 87 to 97 and leaving
the game's whole title-menu UI blank (the redirect resolved to a character model).

So: copy both, then re-resolve every redirect against the deployed .cls and report any
entry that lands on a differently-typed file than intended (image vs model).

    python scripts/deploy_patch.py --dry-run          # 只校验现有安装
    python scripts/deploy_patch.py                    # 部署 + 校验（两个游戏）
"""
import argparse
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

GAMES = [
    r"D:/Ruanjian/Steam/steamapps/common/ROBOTICS;NOTES DaSH",
    r"D:/ZZGAME/ROBOTICS NOTES DaSH",
]
SRC = os.path.join(ROOT, "成品ing", "补丁包", "languagebarrier")

# 每个归档里被重定向的文件应当是什么类型（用来抓"索引错位指向别的文件"）
EXPECT_EXT = {"bg": ".png", "manual": ".png", "system": ".png", "model": ".lkm"}


def resolve(cls, idx):
    return cls[idx] if isinstance(idx, int) and 0 <= idx < len(cls) else None


def verify(lb, tag, verbose=True):
    """Returns (ok, errors). Checks .cls ↔ c0data/ ↔ fileRedirection consistency."""
    errs = []
    cls_p = os.path.join(lb, "c0data.cls")
    patch_p = os.path.join(lb, "patchdef.json")
    data_d = os.path.join(lb, "c0data")
    for p in (cls_p, patch_p, data_d):
        if not os.path.exists(p):
            return False, ["缺少 %s" % p]

    cls = [l.strip() for l in
           io.open(cls_p, encoding="utf-8-sig").read().splitlines() if l.strip()]
    patch = json.load(io.open(patch_p, encoding="utf-8-sig"))
    present = {f for f in os.listdir(data_d) if not f.startswith("_bak")}

    missing = [n for n in cls if n not in present]
    if missing:
        errs.append("cls 指向但 c0data/ 缺失: %s" % missing[:5])
    extra = sorted(present - set(cls))
    if extra:
        errs.append("c0data/ 有 cls 未列的残留文件: %s" % extra[:5])

    fr = patch.get("base", {}).get("fileRedirection", {})
    for arch, m in fr.items():
        want = EXPECT_EXT.get(arch)
        for k, v in sorted(m.items(), key=lambda x: int(x[0])):
            name = resolve(cls, v)
            if name is None:
                errs.append("%s fileId %s -> 越界索引 %r" % (arch, k, v))
            elif want and not name.lower().endswith(want):
                errs.append("%s fileId %s -> %s（期望 %s 类型）"
                            % (arch, k, name, want))

    if verbose:
        print("  %s: cls %d 行 / c0data %d 文件 / %s"
              % (tag, len(cls), len(present),
                 "OK" if not errs else "★ %d 个问题" % len(errs)))
        for e in errs:
            print("     - %s" % e)
    return not errs, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只校验，不复制")
    args = ap.parse_args()

    print("== 源（补丁包）==")
    ok_src, _ = verify(SRC, "补丁包")
    if not ok_src:
        sys.exit("补丁包自身校验失败，先修包再部署")

    rc = 0
    for g in GAMES:
        lb = os.path.join(g, "languagebarrier")
        if not os.path.isdir(lb):
            print("\n== %s ==\n  跳过（不存在）" % g)
            continue
        print("\n== %s ==" % g)
        if not args.dry_run:
            # 必须成对复制：patchdef 的索引依赖 cls 的行序
            for rel in ("c0data.cls", "patchdef.json", "gamedef.json"):
                s, d = os.path.join(SRC, rel), os.path.join(lb, rel)
                if os.path.exists(s):
                    shutil.copy2(s, d)
                    print("  复制 %s" % rel)
            # c0data/ 内容同步（多了会残留、少了会缺图，两边都校验）
            sd, dd = os.path.join(SRC, "c0data"), os.path.join(lb, "c0data")
            os.makedirs(dd, exist_ok=True)
            n = 0
            for f in os.listdir(sd):
                s = os.path.join(sd, f)
                d = os.path.join(dd, f)
                if not os.path.exists(d) or open(s, "rb").read() != open(d, "rb").read():
                    shutil.copy2(s, d)
                    n += 1
            print("  c0data/ 更新 %d 个文件" % n)
        ok, _ = verify(lb, "部署后")
        if not ok:
            rc = 1

    print()
    print("全部通过" if rc == 0 else "★ 有问题，见上")
    return rc


if __name__ == "__main__":
    sys.exit(main())
