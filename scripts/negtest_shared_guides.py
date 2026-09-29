# -*- coding: utf-8 -*-
"""负向自测：故意破坏 check_shared_guides.py 的每条检查，确认会 FAIL。

教训（AGENTS 记过三次）：**门禁必须先在「故意做错」的输入上验证会 FAIL**，
否则等于没有。

用法：python scripts/negtest_shared_guides.py
"""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TMP = tempfile.mkdtemp(prefix="negtest_shared_")


def make_case(mutate):
    """把真实 patch 目录复制一份到 TMP，用 mutate(root) 破坏它，返回新 root。"""
    root = tempfile.mkdtemp(dir=TMP)
    lb = os.path.join(root, "成品ing", "补丁包", "languagebarrier")
    os.makedirs(os.path.dirname(lb), exist_ok=True)
    shutil.copytree(gate.LB, lb)
    mutate(root)
    return root


def run_gate(root):
    """在给定的 root 下跑门禁，返回 (rc, output)。

    root == 真实工作区时直接用现有脚本（别复制到自己身上，Windows 会拒绝）；
    临时 root 才需要把脚本放进去。
    """
    import subprocess
    script_dir = os.path.join(root, "scripts")
    os.makedirs(script_dir, exist_ok=True)
    dst = os.path.join(script_dir, "check_shared_guides.py")
    if os.path.abspath(root) != os.path.abspath(ROOT) and not os.path.exists(dst):
        shutil.copy2(os.path.join(HERE, "check_shared_guides.py"), dst)
    p = subprocess.run([sys.executable, dst],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=root)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


sys.path.insert(0, HERE)
import check_shared_guides as gate  # noqa: E402


def case(name, mutate, expect_fail=True):
    root = make_case(mutate)
    rc, out = run_gate(root)
    failed = (rc != 0)
    ok = (failed == expect_fail)
    print("  [%s] %-42s -> %s" % ("CAUGHT" if failed else "passed", name,
                                  "FAIL" if failed else "PASS"))
    if failed:
        for line in out.splitlines():
            if line.strip().startswith("- "):
                print("        %s" % line.strip())
    return ok


# ---------- 破坏手法 ----------
def break_split_back(root):
    """把共享关系拆开：system/33 指回另一份（模拟「又变回两份」）。"""
    lb = os.path.join(root, "成品ing", "补丁包", "languagebarrier")
    p = os.path.join(lb, "patchdef.json")
    s = io.open(p, encoding="utf-8-sig").read()
    s = s.replace('        "33": 61,', '        "33": 62,')   # 指到键盘那份
    io.open(p, "w", encoding="utf-8", newline="").write(s)


def break_duplicate_file(root):
    """把一份图复制成另一个名字，制造内容重复。

    ⚠ 文件名从 gate.ORPHANS 取，**不要写死** —— 2026-09-30 图集改名时，
    这里写死的旧名让本测试直接 FileNotFoundError（测试自己坏了，
    而不是门禁抓到了错）。凡是「故意做错的输入」也要跟着真实数据走。
    """
    lb = os.path.join(root, "成品ing", "补丁包", "languagebarrier")
    c0 = os.path.join(lb, "c0data")
    shared = "control_pc.png"
    orphan = gate.ORPHANS[0]
    shutil.copy2(os.path.join(c0, shared), os.path.join(c0, orphan))


def break_orphan_in_cls(root):
    """把已合并掉的旧名加回 cls（末尾追加）。"""
    lb = os.path.join(root, "成品ing", "补丁包", "languagebarrier")
    p = os.path.join(lb, "c0data.cls")
    s = io.open(p, encoding="utf-8-sig").read()
    io.open(p, "w", encoding="utf-8", newline="").write(
        s.rstrip("\r\n") + "\r\n" + gate.ORPHANS[0] + "\r\n")


def break_dup_name_in_cls(root):
    """制造重名条目（把共享的那份名字再追加一行）。

    ⚠ 名字要从 cls 里**按下标取**：MUST_SHARE 里存的第 2 个元素是
    **fileId（如 "33"）**，不是文件名 —— 直接拿它拼 cls 会追加一行 "33"，
    既不是重名也不是图片，门禁当然抓不到（本测试曾因此假绿一次）。
    """
    lb = os.path.join(root, "成品ing", "补丁包", "languagebarrier")
    cls_p = os.path.join(lb, "c0data.cls")
    cls2 = [l.strip() for l in io.open(cls_p, encoding="utf-8-sig").read().splitlines() if l.strip()]
    fr = json.load(io.open(os.path.join(lb, "patchdef.json"), encoding="utf-8-sig"))["base"]["fileRedirection"]
    v = fr["system"]["33"]
    v = v["jp"] if isinstance(v, dict) else v
    io.open(cls_p, "w", encoding="utf-8", newline="").write(
        "\r\n".join(cls2) + "\r\n" + cls2[v] + "\r\n")


def break_missing_file(root):
    """把共享的那份文件删掉（下标还在，但磁盘没有）。"""
    lb = os.path.join(root, "成品ing", "补丁包", "languagebarrier")
    cls_p = os.path.join(lb, "c0data.cls")
    cls2 = [l.strip() for l in io.open(cls_p, encoding="utf-8-sig").read().splitlines() if l.strip()]
    fr = json.load(io.open(os.path.join(lb, "patchdef.json"), encoding="utf-8-sig"))["base"]["fileRedirection"]
    v = fr["system"]["33"]
    v = v["jp"] if isinstance(v, dict) else v
    os.remove(os.path.join(lb, "c0data", cls2[v]))


def main():
    print("=== negtest: 共享图集门禁 ===")
    results = []

    print("\n[1] 好输入（当前真实补丁包）应 PASS")
    rc, out = run_gate(ROOT)
    ok = (rc == 0)
    print("  [%s] 真实补丁包%s -> %s" % ("passed" if ok else "CAUGHT",
                                          "", "PASS" if ok else "FAIL"))
    if not ok:
        for line in out.splitlines():
            if line.strip().startswith("- "):
                print("        %s" % line.strip())
    results.append(ok)

    print("\n[2] 故意破坏应 CAUGHT")
    results.append(case("共享关系被拆开（system/33 指别处）", break_split_back))
    results.append(case("内容重复（多出一份同名副本）", break_duplicate_file))
    results.append(case("孤儿名回到 cls", break_orphan_in_cls))
    results.append(case("cls 出现重名条目", break_dup_name_in_cls))
    results.append(case("共享的那份文件被删", break_missing_file))

    missed = sum(1 for r in results if not r)
    print("\n=== 汇总 ===")
    print("  用例 %d 个，CAUGHT %d，MISSED %d"
          % (len(results), sum(1 for r in results if r), missed))
    print("RESULT: %s" % ("ALL CAUGHT" if missed == 0 else "★ 有 %d 个漏判" % missed))
    return 0 if missed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
