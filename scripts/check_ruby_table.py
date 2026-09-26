# -*- coding: utf-8 -*-
"""门禁：检查 RubyBaseTable.inc 是否与已部署的 enscript 保持一致。

`RubyBaseTable.inc` 是 `scripts/gen_ruby_base_table.py` 从
`成品ing/补丁包/languagebarrier/enscript/*.msb` 提取的「标注 -> 基字」对照表，
编译进 dinput8.dll。**只要 enscript 里的 ruby 文本变了、而表没重建，对话框标注
就会悄悄回到错位置**——不报错、不崩，只是偏着显示。本项目已两次踩这类静默失效
（表键曾把空格删掉，导致整条修复完全无效），所以做成门禁而不是靠记忆。

检查 = 「重新生成一份到临时文件 + 逐字节比对」，不碰正式表。

    python scripts/check_ruby_table.py          # 检查（过期则非零退出）
    python scripts/check_ruby_table.py --fix    # 重建表（之后需重编 DLL 并部署）
"""
import argparse
import io
import os
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\DATA\tran\agent tran\9.6文本外工作"
GEN = os.path.join(ROOT, "scripts", "gen_ruby_base_table.py")
REPO_LB = (r"D:\DATA\tran\agent tran\GitHub\RND_Chinese"
           r"\LanguageBarrier_chs\LanguageBarrier")
TABLE = os.path.join(REPO_LB, "RubyBaseTable.inc")


def read(path):
    with io.open(path, encoding="ascii", newline="") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="重建表")
    args = ap.parse_args()

    if args.fix:
        r = subprocess.run([sys.executable, GEN],
                           capture_output=True, text=True, encoding="utf-8")
        print(r.stdout.rstrip())
        if r.returncode != 0:
            print("✗ 生成失败，表未改动")
            return 1
        print("\n✓ 表已重建 —— 还要重新编译 dinput8.dll 并部署，否则游戏里用不到")
        return 0

    if not os.path.exists(TABLE):
        print("✗ 表不存在: %s" % TABLE)
        return 1

    fd, tmp = tempfile.mkstemp(suffix=".inc", prefix="rubytable_")
    os.close(fd)
    try:
        r = subprocess.run([sys.executable, GEN, "--out", tmp],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print(r.stdout.rstrip())
            print("✗ 生成器自检未通过 —— 数据侧就有问题，先修那个")
            return 1
        fresh, current = read(tmp), read(TABLE)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    if fresh == current:
        print("✓ RubyBaseTable.inc 与已部署 enscript 一致")
        return 0

    print("✗ RubyBaseTable.inc 已过期 —— enscript 变过了，表没重建")
    print("  表现：对话框里的标注会偏位（不报错，只是偏）")
    print("  修法：python scripts/gen_ruby_base_table.py")
    print("        然后重新编译 dinput8.dll 并部署到补丁包 + 游戏目录")
    return 1


if __name__ == "__main__":
    sys.exit(main())
