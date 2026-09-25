# -*- coding: utf-8 -*-
"""把 `临时/cn/汉化好的/` 的成品图同步到「镜像」与「补丁包」两处。

图片的唯一同步源是 `临时/cn/汉化好的/{bg,system,manual}/`（用户交成品的地方）。
每次改图后跑本脚本，三处自动对齐：

    临时/cn/汉化好的/  →  成品ing/图片汉化/  （镜像，带 _zh 后缀）
                       →  成品ing/补丁包/languagebarrier/c0data/  （实际发布，原名）

命名规则：`c0data.cls` 用游戏原始资源名（`rnd_ibg059b.png`），镜像里用带 `_zh`
后缀的名字（`rnd_ibg059b_zh.png`）。`废弃/` 子目录是用户明确不要的，不参与同步。

判据是 **md5 对比 c0data 现状**，不是比 mtime —— 只有内容真的变了才动文件。
已存在的目标文件先备份到 `成品ing/_backup/image_sync_<时间戳>/`。

    python scripts/sync_images.py            # 同步
    python scripts/sync_images.py --dry-run  # 只看会改什么
"""
import argparse
import datetime
import hashlib
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "临时", "cn", "汉化好的")
MIRROR = os.path.join(ROOT, "成品ing", "图片汉化")
PKG = os.path.join(ROOT, "成品ing", "补丁包", "languagebarrier")
C0DATA = os.path.join(PKG, "c0data")
BAKROOT = os.path.join(ROOT, "成品ing", "_backup")

CATS = ("bg", "system", "manual")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_name(stem):
    """镜像里的 stem -> c0data.cls 里的原始资源名（不含 .png）"""
    for suf in ("重做", "_zh"):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
    # manual/system 与 bg 三处共享同一张图，c0data 里只存一份、名字不同
    return ALIAS.get(stem, stem)


# 镜像名 -> c0data 里的原始资源名（stripping 后仍对不上的，在这里补）
#   control_pc/keyboard_pc  在 system 与 manual 两个归档里各有一份
#   guid_pc 的原始资源名带 _jp 后缀
ALIAS = {
    "control_pc": "RND_PC_controller_jp",
    "keyboard_pc": "RND_PC_keyboard_jp",
    "guid_pc": "guid_pc_jp",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(C0DATA):
        sys.exit("找不到 c0data：%s" % C0DATA)

    cls_path = os.path.join(PKG, "c0data.cls")
    cls = [l.strip() for l in io.open(cls_path, encoding="utf-8-sig").read().splitlines()
           if l.strip()]
    live = {n: os.path.join(C0DATA, n) for n in os.listdir(C0DATA)
            if n.lower().endswith(".png")}

    plan = []
    for cat in CATS:
        d = os.path.join(SRC, cat)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(".png"):
                continue
            src = os.path.join(d, f)
            if not os.path.isfile(src):
                continue
            # Mirror name = the source's own name normalised to `*_zh.png`. Note
            # `stem` below is the *c0data* name (suffix stripped, aliases applied
            # -- guid_pc -> guid_pc_jp), so it must NOT be reused for the mirror:
            # the mirror keeps the source stem, only re-suffixed.
            src_stem = os.path.splitext(f)[0]
            for suf in ("重做", "_zh"):
                if src_stem.endswith(suf):
                    src_stem = src_stem[: -len(suf)]
            stem = archive_name(os.path.splitext(f)[0])
            # movie 帧在 c0data 里带 _last
            arc = None
            for cand in (stem + ".png", stem + "_last.png"):
                if cand in live:
                    arc = cand
                    break
            if arc is None:
                print("  跳过（c0data 无对应项）: %s/%s" % (cat, f))
                continue
            # A file needs syncing if EITHER destination is out of date. Checking
            # only c0data hides a stale mirror: if c0data is updated by hand (or
            # by a tool), source == c0data and the mirror is silently left behind
            # -- the run reports "nothing to do" while the two published copies
            # disagree. That happened on 2026-09-25 (extra_chip + extra_chip_en).
            mirror_path = os.path.join(MIRROR, cat, src_stem + "_zh.png")
            s_md5 = md5(src)
            live_stale = s_md5 != md5(live[arc])
            mirror_stale = (not os.path.exists(mirror_path)
                            or s_md5 != md5(mirror_path))
            if not live_stale and not mirror_stale:
                continue
            why = ("两处都旧" if live_stale and mirror_stale
                   else "c0data 旧" if live_stale else "镜像旧")
            plan.append({"cat": cat, "arc": arc, "src": src,
                         "mirror": mirror_path,
                         "live": live[arc], "why": why})

    print("待同步 %d 个文件：" % len(plan))
    for x in plan:
        print("  %-8s %-26s [%s] -> %s"
              % (x["cat"], x["arc"], x.get("why", "?"),
                 os.path.relpath(x["mirror"], ROOT)))

    if not plan:
        print("已全部一致，无需改动")
        return
    if args.dry_run:
        print("\n[dry-run] 未写入")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(BAKROOT, "image_sync_%s" % stamp)
    os.makedirs(bak, exist_ok=True)
    for x in plan:
        rel = os.path.join(x["cat"], x["arc"])
        b = os.path.join(bak, rel)
        os.makedirs(os.path.dirname(b), exist_ok=True)
        shutil.copy2(x["live"], b)
        if os.path.exists(x["mirror"]):
            b2 = os.path.join(bak, "_mirror_" + rel)
            os.makedirs(os.path.dirname(b2), exist_ok=True)
            shutil.copy2(x["mirror"], b2)
        # 两处都写
        os.makedirs(os.path.dirname(x["mirror"]), exist_ok=True)
        shutil.copy2(x["src"], x["mirror"])
        shutil.copy2(x["src"], x["live"])

    with io.open(os.path.join(bak, "_plan.json"), "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in x.items()} for x in plan], f,
                  ensure_ascii=False, indent=1)

    print("\n已同步 %d 个（镜像 + c0data）" % len(plan))
    print("旧版备份：%s" % os.path.relpath(bak, ROOT))
    print("\n接下来：python scripts/gen_pkg_manifest.py && "
          "cd 成品ing/setup/build && python build_installer.py")


if __name__ == "__main__":
    main()
