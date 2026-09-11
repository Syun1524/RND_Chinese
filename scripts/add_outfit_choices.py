# -*- coding: utf-8 -*-
"""Generate per-character outfit overrides into patchdef.json.

LanguageBarrier's `settings` block understands two types, `bool` and `choice`, and both
merge their payload straight into `config["patch"]` (Config.cpp:39-55). The outfit
verification feature needs to pin **several characters at once** in a single run, which a
`choice` cannot express (one choice = one key), so it uses one *bool* per
character×variant:

    "zz_c002_100": { "type": "bool", "setters": { "fileIdRemap": { "model": {
        "470":474, "471":474, ..., "474":474 } } }

The tool writes only the `true` keys it needs into config.json, so any subset of
characters can be pinned simultaneously — that is what makes a batch verification run
(see several characters' outfits in one launch) possible.

`fileIdRemap` is read unconditionally by `mgsFileOpenHook` (Game.cpp:748-768) and returns
before `fileRedirection` is consulted, so these overrides work with or without the
swimsuit patch enabled.

Two hard constraints, both silent failures if broken:

1. Every variant of the character must be remapped **including the target itself**.
   `swimsuitPatch` points all of a character's variants at the swimsuit model, and
   `json_merge` is a recursive overwrite that cannot delete keys — so leaving the target
   out means the outfit you asked for gets overwritten back to the swimsuit.
2. The key prefix must sort **after** `"swimsuitPatch"` (settings iterate in std::map =
   lexicographic order). `"zz_"` guarantees that; a name sorting earlier is merged first
   and then overwritten, again silently.

Idempotent. Rewrites patchdef.json in place (UTF-8 no BOM, CRLF, indent=2) after backing
up to patchdef.json.bak_outfitfit_<stamp>. Also drops the older single-`choice`
`zzOutfitOverride` block if present.
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

PREFIX = "zz_"            # 必须排在 swimsuitPatch 之后（字典序）
LEGACY_KEY = "zzOutfitOverride"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patchdef", default=os.path.join(
        ROOT, "成品ing", "补丁包", "languagebarrier", "patchdef.json"))
    ap.add_argument("--mapping", default=os.path.join(ROOT, "成品ing", "服装映射表.json"))
    ap.add_argument("--names", default=None,
                    help="可选：服装名称表 JSON，形如 {\"c002_100\": \"泳装\"}（仅用于显示）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    mapping = json.load(io.open(args.mapping, encoding="utf-8"))
    names = {}
    if args.names and os.path.exists(args.names):
        names = json.load(io.open(args.names, encoding="utf-8"))

    raw = io.open(args.patchdef, encoding="utf-8-sig").read()
    doc = json.loads(raw)
    settings = doc.setdefault("settings", {})

    # 清掉旧机制与上次生成的键，保证幂等
    for k in [k for k in settings if k == LEGACY_KEY or k.startswith(PREFIX)]:
        del settings[k]

    added = 0
    table = []
    for ch in sorted(mapping):
        entries = sorted(mapping[ch], key=lambda e: e["variant"])
        if len(entries) < 2:
            continue                     # 单变体角色没有别的服装可切
        for target in entries:
            tv = target["variant"]
            # 该角色【全部】变体（含目标自身）→ 目标
            remap = {str(o["fileId"]): target["fileId"] for o in entries}
            key = "%s%s_%s" % (PREFIX, ch, tv)
            settings[key] = {"type": "bool",
                             "setters": {"fileIdRemap": {"model": remap}}}
            added += 1
            table.append((key, ch, tv, target["fileId"], len(remap),
                          names.get("%s_%s" % (ch, tv), "")))

    print("已生成 %d 个角色×服装开关（%d 个多变体角色）"
          % (added, len({c for _, c, _, _, _, _ in table})))
    print("键名形如 %s<角色>_<变体>，全部排在 swimsuitPatch 之后" % PREFIX)
    print()
    print("角色   变体   fileId  重定向条数  名称")
    for key, ch, tv, fid, n, nm in table:
        print("  %-14s %-5s %7d %6d      %s" % (key, tv, fid, n, nm))

    if args.dry_run:
        print("\n[dry-run] patchdef.json 未改动")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(args.patchdef, "%s.bak_outfitfit_%s" % (args.patchdef, stamp))
    out = json.dumps(doc, ensure_ascii=False, indent=2).replace("\n", "\r\n")
    io.open(args.patchdef, "w", encoding="utf-8", newline="").write(out)
    print("\n已写入 %s（备份 .bak_outfitfit_%s）" % (args.patchdef, stamp))


if __name__ == "__main__":
    main()
