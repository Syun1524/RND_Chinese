# -*- coding: utf-8 -*-
"""把共享图集改回 `control_pc.png` / `keyboard_pc.png`（去掉 `_jp` 后缀）。

背景（2026-09-30，用户指定）
----------------------------
操作说明图在日文原版 `system.cpk` 与 `manual.cpk` 里各存一份（内容逐字节相同）：

| 归档 | 原始资源名 |
|---|---|
| `system` | `control_pc.png` / `keyboard_pc.png` |
| `manual` | `RND_PC_controller_jp.png` / `RND_PC_keyboard_jp.png` |

合并成一份时，之前保留了 `manual` 侧那个带 `_jp` 的名字。用户指出：
**`control_pc.png` 才是我们自己的命名风格**，`_jp` 是跟着归档原名走的。
所以保留 `control_pc.png` / `keyboard_pc.png`，改掉另一份。

★ 这是**纯改名**，不是重排下标：
  `fileRedirection` 存的是数组下标，而这里下标**一个都不动**（还是 61 / 62），
  只把 cls 里那两行的**文件名**换掉。所以 `patchdef.json` **零改动**。

★ 连带要改的（脚本会提示，不代劳）：
  `成品ing/setup/src/RNDZhSetup.cpp` 的 `orphanAtlases[]` —— 它现在删的是
  `control_pc.png` / `keyboard_pc.png`，改名后那正是**要用的文件**，必须改成
  删 `RND_PC_*`（旧名），否则安装器会把补丁自己的图删掉。

用法
----
    python scripts/rename_guide_atlases.py --dry-run
    python scripts/rename_guide_atlases.py
"""
import argparse
import datetime
import hashlib
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG = os.path.join(ROOT, "成品ing", "补丁包", "languagebarrier")
CLS = os.path.join(PKG, "c0data.cls")
PATCH = os.path.join(PKG, "patchdef.json")
C0 = os.path.join(PKG, "c0data")

# 旧名 -> 新名（内容相同，只换名字）
RENAME = {
    "RND_PC_controller_jp.png": "control_pc.png",
    "RND_PC_keyboard_jp.png": "keyboard_pc.png",
}

# 两个归档必须继续共享同一条目（下标不变，仅名字变）
MUST_SHARE = [("system", "33", "manual", "0"), ("system", "35", "manual", "1")]


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    raw_cls = io.open(CLS, encoding="utf-8-sig").read()
    cls = [l.strip() for l in raw_cls.splitlines() if l.strip()]

    # ---------- 前置校验 ----------
    print("=== 前置校验 ===")
    for old, new in RENAME.items():
        if old not in cls:
            sys.exit("★ 旧名 %s 不在 c0data.cls 里，脚本前提已变" % old)
        if new in cls:
            sys.exit("★ 新名 %s 已经在 cls 里了，不能改名（会重名）" % new)
        po, pn = os.path.join(C0, old), os.path.join(C0, new)
        if not os.path.exists(po):
            sys.exit("★ 文件缺失：%s" % po)
        if os.path.exists(pn):
            sys.exit("★ 目标名已存在：%s" % pn)
        print("  %-28s -> %-20s %s" % (old, new, md5(po)[:16]))

    # 旧名在 cls 里的位置（改名后位置不变，这正是「纯改名」的判据）
    idx_before = {n: cls.index(n) for n in RENAME}
    print("\n=== 下标（改名前）===")
    for old, i in idx_before.items():
        print("  [%2d] %s" % (i, old))

    # ---------- 新 cls（就地换名，顺序与长度都不变）----------
    new_cls = [RENAME.get(n, n) for n in cls]
    assert len(new_cls) == len(cls), "行数变了，这不是纯改名"
    idx_after = {n: new_cls.index(n) for n in RENAME.values()}
    print("\n=== 下标（改名后，必须与改名前相同）===")
    for old, new in RENAME.items():
        same = idx_before[old] == idx_after[new]
        print("  [%2d] %s  %s" % (idx_after[new], new, "✓ 位置未变" if same else "★ 位置变了"))
        if not same:
            sys.exit("★ 位置发生变化，说明不是纯改名，中止")

    # ---------- patchdef 必须零改动 ----------
    patch_before = open(PATCH, "rb").read()
    print("\n=== patchdef.json：无需改动（下标不变）===")
    print("  %d 字节  md5 %s" % (len(patch_before), hashlib.md5(patch_before).hexdigest()[:16]))

    if args.dry_run:
        print("\n[dry-run] 未写入")
        return

    # ---------- 执行 ----------
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(ROOT, "成品ing", "_backup", "rename_guides_%s" % stamp)
    os.makedirs(bak, exist_ok=True)
    shutil.copy2(CLS, bak)
    for old in RENAME:
        shutil.copy2(os.path.join(C0, old), bak)
    print("\n备份 -> %s" % bak)

    for old, new in RENAME.items():
        os.rename(os.path.join(C0, old), os.path.join(C0, new))
        print("  改名 %s -> %s" % (old, new))

    with open(CLS, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(new_cls) + "\r\n")
    print("  c0data.cls 已更新（%d 行）" % len(new_cls))

    # ---------- 写后复核 ----------
    print("\n=== 写后复核 ===")
    after_cls = [l.strip() for l in io.open(CLS, encoding="utf-8-sig").read().splitlines() if l.strip()]
    print("  cls 行数: %d %s" % (len(after_cls), "✓" if len(after_cls) == len(cls) else "★"))
    for old, new in RENAME.items():
        print("  %-28s 在 cls: %-5s 在磁盘: %-5s | %-20s 在 cls: %-5s 在磁盘: %s"
              % (old, old in after_cls, os.path.exists(os.path.join(C0, old)),
                 new, new in after_cls, os.path.exists(os.path.join(C0, new))))

    # patchdef 逐字节未变
    patch_after = open(PATCH, "rb").read()
    print("  patchdef.json 未改动: %s" % ("✓" if patch_after == patch_before else "★ 变了"))

    # 共享关系仍然成立
    import json
    fr = json.load(io.open(PATCH, encoding="utf-8-sig"))["base"]["fileRedirection"]
    print("\n=== 共享关系复核 ===")
    for a1, f1, a2, f2 in MUST_SHARE:
        v1, v2 = fr[a1][f1], fr[a2][f2]
        v1 = v1["jp"] if isinstance(v1, dict) else v1
        v2 = v2["jp"] if isinstance(v2, dict) else v2
        print("  %s/%s=[%d] %s | %s/%s=[%d] %s  %s"
              % (a1, f1, v1, after_cls[v1], a2, f2, v2, after_cls[v2],
                 "✓ 同一份" if v1 == v2 else "★"))

    print("""
★ 别忘了同步这几处（脚本不代劳，因为它们是「引用旧名」的代码/配置）：
   1. 成品ing/setup/src/RNDZhSetup.cpp 的 orphanAtlases[] —— 改成删 RND_PC_*（旧名）
   2. scripts/sync_images.py 的 ALIAS —— control_pc/keyboard_pc 两条可以删掉（现在是同名）
   3. scripts/apply_ui_redirect.py 的 SPEC —— 原资源名改成 control_pc.png / keyboard_pc.png
   4. scripts/check_shared_guides.py 的 ORPHANS —— 改成 RND_PC_*
   5. 仓库 补丁数据/运行时配置/c0data.cls
""")


if __name__ == "__main__":
    main()
