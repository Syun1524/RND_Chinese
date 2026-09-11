# -*- coding: utf-8 -*-
"""Generate `zzOutfitOverride` into patchdef.json so any single outfit can be forced.

LanguageBarrier's `settings` block understands two types: `bool` and `choice`.
A `choice` merges its selected entry straight into `config["patch"]` (Config.cpp:47-53),
so a choice carrying `{"fileIdRemap": {...}}` reaches `mgsFileOpenHook` untouched.
That means the whole outfit-verification feature needs **no LanguageBarrier changes at
all** — patchdef just has to enumerate the choices.

Layout of one choice (verifying outfit V of character C):

    "zzOutfitOverride": {
      "type": "choice",
      "choices": {
        "off": {},
        "c002_100": { "fileIdRemap": { "model": { "470":474, "471":474, ... } } }
      }
    }

i.e. every other variant of C is remapped onto V, exactly like the swimsuit patch does.

Ordering note: settings are applied in the order nlohmann::json iterates them, which is
std::map order = lexicographic. "zzOutfitOverride" therefore merges *after*
"swimsuitPatch", which makes the two compose the useful way round: swimsuit for the whole
cast, with one character pinned to an outfit you are checking. Renaming this key to
anything sorting before "swimsuitPatch" would silently break that.

Idempotent. Rewrites patchdef.json in place (UTF-8 no BOM, CRLF, indent=2) after backing
it up to patchdef.json.bak_outfitfit_<stamp>.
"""
import argparse
import io
import json
import os
import shutil
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

KEY = "zzOutfitOverride"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patchdef", default=os.path.join(
        ROOT, "成品ing", "补丁包", "languagebarrier", "patchdef.json"))
    ap.add_argument("--mapping", default=os.path.join(ROOT, "成品ing", "服装映射表.json"))
    ap.add_argument("--names", default=None,
                    help="可选：服装名称表 JSON，形如 {\"c002_100\": \"泳装\"}")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    mapping = json.load(io.open(args.mapping, encoding="utf-8"))
    names = {}
    if args.names and os.path.exists(args.names):
        names = json.load(io.open(args.names, encoding="utf-8"))

    choices = {"off": {}}
    listing = []
    for ch in sorted(mapping):
        entries = sorted(mapping[ch], key=lambda e: e["variant"])
        if len(entries) < 2:
            continue                       # 单变体角色没什么可核验的
        for target in entries:
            tv = target["variant"]
            # 必须把【目标变体自己也映射到自己】。swimsuitPatch 会把本角色的每个变体
            # （含目标本身）都指向泳装模型，而 zzOutfitOverride 排在它后面合并
            # （json_merge 是递归覆盖，删不掉键），所以漏掉自身映射的话，
            # 想核对的那套会被泳装覆盖回泳装。
            remap = {str(o["fileId"]): target["fileId"] for o in entries}
            cid = "%s_%s" % (ch, tv)
            choices[cid] = {"fileIdRemap": {"model": remap}}
            listing.append((cid, ch, tv, target["fileId"], len(remap),
                            names.get(cid, "")))

    raw = io.open(args.patchdef, encoding="utf-8-sig").read()
    doc = json.loads(raw)
    doc.setdefault("settings", {})[KEY] = {"type": "choice", "choices": choices}

    print("核验项：%d 个变体（覆盖 %d 个多变体角色）"
          % (len(listing), len({c for _, c, _, _, _, _ in listing})))
    print("角色   变体   fileId  重定向条数")
    for cid, ch, tv, fid, n, nm in listing:
        print("  %-12s %-5s %7d %6d   %s" % (cid, tv, fid, n, nm))

    if args.dry_run:
        print("\n[dry-run] patchdef.json 未改动")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(args.patchdef, "%s.bak_outfitfit_%s" % (args.patchdef, stamp))

    out = json.dumps(doc, ensure_ascii=False, indent=2).replace("\n", "\r\n")
    with io.open(args.patchdef, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print("\n已写入 %s（备份 .bak_outfitfit_%s）" % (args.patchdef, stamp))


if __name__ == "__main__":
    main()
