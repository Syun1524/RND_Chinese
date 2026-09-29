# -*- coding: utf-8 -*-
"""门禁：共享图集必须只存一份，且两个归档指向同一条目。

背景（2026-09-29）：
  操作说明图在日文原版 `system.cpk` 与 `manual.cpk` 里各存一份（内容逐字节相同）。
  CoZ 上游让两个归档**指向同一个 c0data 槽位**，也就是「一张图、两条路径」。
  我们这边 `rebuild_c0data.py` 的去重按「归档里的原始文件名」比对，而两个归档里
  同一张图**名字不同**（`control_pc.png` vs `RND_PC_controller_jp.png`），
  于是留成了两份。

  ★ 为什么这是真问题而不只是冗余：`sync_images.py` 的同步源是
  两份里只有一份在同步管线上，另一份没有源文件映射 —— 那是孤儿副本。
  两份内容恰好相同时看不出问题，一改图，`system/33` 这条路径就会静默停在旧图上
  （同 2026-09-25 extra_chip 漏同步）。现合并成一份，名字与源图同名
  （`control_pc.png` / `keyboard_pc.png`）。

本门禁检查：
  A. `c0data.cls` 里没有重名条目；
  B. `c0data/` 里没有「内容逐字节相同」的两份（去重没做干净）；
  C. 下列配对必须指向**同一个** c0data 下标：
       system/33 ↔ manual/0   (手柄操作图)
       system/35 ↔ manual/1   (键盘操作图)
  D. 被删的孤儿名（control_pc.png / keyboard_pc.png）不得回到 cls 里。

用法：
    python scripts/check_shared_guides.py
"""
import collections
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LB = os.path.join(ROOT, "成品ing", "补丁包", "languagebarrier")
CLS = os.path.join(LB, "c0data.cls")
PATCH = os.path.join(LB, "patchdef.json")
C0 = os.path.join(LB, "c0data")

# 必须共享同一条目的配对：(归档A, fileId, 归档B, fileId, 说明)
MUST_SHARE = [
    ("system", "33", "manual", "0", "手柄操作图"),
    ("system", "35", "manual", "1", "键盘操作图"),
]

# 已合并掉的旧名，不得回来（现在用 control_pc.png / keyboard_pc.png）
ORPHANS = ["RND_PC_controller_jp.png", "RND_PC_keyboard_jp.png"]

# 允许「内容相同」的例外（目前没有）。键为排序后的文件名元组。
DUP_ALLOWLIST = set()


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def main():
    errs = []
    if not os.path.exists(CLS):
        print("RESULT: FAIL")
        print("  找不到 %s" % CLS)
        return 1

    cls = [l.strip() for l in io.open(CLS, encoding="utf-8-sig").read().splitlines()
           if l.strip()]
    patch = json.load(io.open(PATCH, encoding="utf-8-sig"))
    fr = patch.get("base", {}).get("fileRedirection", {})

    # A. cls 无重名
    dups = [n for n, c in collections.Counter(cls).items() if c > 1]
    if dups:
        errs.append("c0data.cls 有重名条目：%s" % dups)

    # B. c0data/ 无内容重复
    files = [f for f in sorted(os.listdir(C0)) if f.lower().endswith(".png")]
    by_hash = collections.defaultdict(list)
    for f in files:
        by_hash[md5(os.path.join(C0, f))].append(f)
    for h, names in sorted(by_hash.items()):
        if len(names) < 2:
            continue
        if tuple(sorted(names)) in DUP_ALLOWLIST:
            continue
        errs.append("c0data/ 内容重复（应合并成一份）：%s  [%s]" % (", ".join(names), h[:16]))

    # C. 配对必须共享同一条目
    for a1, f1, a2, f2, what in MUST_SHARE:
        if a1 not in fr or f1 not in fr.get(a1, {}):
            errs.append("%s/%s 不在 fileRedirection 里" % (a1, f1))
            continue
        if a2 not in fr or f2 not in fr.get(a2, {}):
            errs.append("%s/%s 不在 fileRedirection 里" % (a2, f2))
            continue
        v1, v2 = fr[a1][f1], fr[a2][f2]
        v1 = v1["jp"] if isinstance(v1, dict) else v1
        v2 = v2["jp"] if isinstance(v2, dict) else v2
        if v1 != v2:
            n1 = cls[v1] if 0 <= v1 < len(cls) else "越界"
            n2 = cls[v2] if 0 <= v2 < len(cls) else "越界"
            errs.append("%s（%s/%s 与 %s/%s）没共享同一条目：[%d]=%s vs [%d]=%s"
                        % (what, a1, f1, a2, f2, v1, n1, v2, n2))
        else:
            # 指向的那份必须真的在磁盘上
            if not (0 <= v1 < len(cls)):
                errs.append("%s/%s -> 越界下标 %d" % (a1, f1, v1))
            elif not os.path.exists(os.path.join(C0, cls[v1])):
                errs.append("%s/%s -> %s 在 c0data/ 里不存在" % (a1, f1, cls[v1]))

    # D. 孤儿名不得回来
    for name in ORPHANS:
        if name in cls:
            errs.append("孤儿副本 %s 又回到 c0data.cls 了（应只保留共享的那一份）" % name)
        if os.path.exists(os.path.join(C0, name)):
            errs.append("孤儿副本 %s 又出现在 c0data/ 里" % name)

    print("=== 共享图集门禁 ===")
    print("  cls 行数: %d   c0data png: %d" % (len(cls), len(files)))
    for a1, f1, a2, f2, what in MUST_SHARE:
        if a1 in fr and f1 in fr[a1] and a2 in fr and f2 in fr[a2]:
            v = fr[a1][f1]
            v = v["jp"] if isinstance(v, dict) else v
            nm = cls[v] if 0 <= v < len(cls) else "越界"
            same = fr[a2][f2]
            same = same["jp"] if isinstance(same, dict) else same
            print("  %-10s %s/%s = %s/%s = [%d] %s  %s"
                  % (what, a1, f1, a2, f2, v, nm, "✓" if v == same else "★"))
    if errs:
        print("\n问题:")
        for e in errs:
            print("  - %s" % e)
    print("\nRESULT: %s" % ("PASS" if not errs else "FAIL"))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
