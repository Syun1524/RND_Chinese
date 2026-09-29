# -*- coding: utf-8 -*-
"""负向自测：故意把 check_fileid0_guard.py 的三条检查各自破坏一次，
确认门禁报 FAIL（好输入 PASS）。

教训（AGENTS 里记过两次）：**门禁必须先在「故意做错」的输入上验证会 FAIL**，
否则等于没有 —— 曾做出过只采样「已登记矩形」的死门禁，三种错误全部漏过。

用法：python scripts/negtest_fileid0_guard.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import check_fileid0_guard as gate  # noqa: E402

TMP = tempfile.mkdtemp(prefix="negtest_fileid0_")


def run_check_dll(path):
    return gate.check_dll(path)


def run_check_source(path):
    return gate.check_source(path)


def run_check_patchdef(lb):
    return gate.check_patchdef(lb)


def case(name, fn, expect_fail=True):
    errs = fn()
    got_fail = bool(errs)
    ok = (got_fail == expect_fail)
    print("  [%s] %-46s -> %s" % ("CAUGHT" if got_fail else "passed", name,
                                  "FAIL" if got_fail else "PASS"))
    if got_fail:
        for e in errs[:2]:
            print("        %s" % e)
    return ok


def main():
    print("=== negtest: fileId 0 守卫门禁 ===")
    results = []

    # ---------- 好输入必须 PASS ----------
    print("\n[1] 好输入（当前实际文件）应 PASS")
    results.append(case("真实 DLL（补丁包）", lambda: run_check_dll(gate.PKG_DLL),
                        expect_fail=False))
    results.append(case("真实 Game.cpp", lambda: run_check_source(gate.REPO_SRC),
                        expect_fail=False))
    results.append(case("真实 patchdef.json", lambda: run_check_patchdef(gate.PKG_LB),
                        expect_fail=False))

    # ---------- A. 源码守卫改回 > 0 ----------
    print("\n[2] 源码守卫改回 `> 0` 应 CAUGHT")
    src = io.open(gate.REPO_SRC, encoding="utf-8-sig", errors="replace").read()
    broken = src.replace("fileId >= 0", "fileId > 0")
    assert broken != src, "测试用例没生效：源码里没有 `fileId >= 0`"
    p = os.path.join(TMP, "Game_broken.cpp")
    io.open(p, "w", encoding="utf-8").write(broken)
    results.append(case("Game.cpp: fileId > 0（原 bug）",
                        lambda: run_check_source(p)))

    # ---------- B. DLL 守卫退回 jg ----------
    print("\n[3] DLL 守卫退回 jg 应 CAUGHT")
    data = bytearray(open(gate.PKG_DLL, "rb").read())
    off = bytes(data).find(gate.GUARD_JNS)
    assert off >= 0, "找不到 jns 守卫，测试用例失效"
    data[off + 10] = 0x7f                      # jns -> jg
    p = os.path.join(TMP, "dinput8_jg.dll")
    open(p, "wb").write(bytes(data))
    results.append(case("DLL: 守卫退回 jg（fileId > 0）",
                        lambda: run_check_dll(p)))

    # ---------- B2. DLL 守卫被抹成恒真/恒假 ----------
    print("\n[4] DLL 守卫被改成 nop 应 CAUGHT")
    data = bytearray(open(gate.PKG_DLL, "rb").read())
    off = bytes(data).find(gate.GUARD_JNS)
    data[off + 10] = 0x90                      # jns -> nop
    p = os.path.join(TMP, "dinput8_nop.dll")
    open(p, "wb").write(bytes(data))
    results.append(case("DLL: 守卫改成 nop", lambda: run_check_dll(p)))

    # ---------- C. patchdef 去掉 key "0" ----------
    print("\n[5] patchdef 去掉 key \"0\" 应 CAUGHT")
    lb = os.path.join(TMP, "lb")
    os.makedirs(lb, exist_ok=True)
    shutil.copy2(os.path.join(gate.PKG_LB, "c0data.cls"), os.path.join(lb, "c0data.cls"))
    d = json.load(io.open(os.path.join(gate.PKG_LB, "patchdef.json"),
                          encoding="utf-8-sig"))
    for arch, m in d["base"]["fileRedirection"].items():
        if isinstance(m, dict):
            m.pop("0", None)
    io.open(os.path.join(lb, "patchdef.json"), "w", encoding="utf-8").write(
        json.dumps(d, ensure_ascii=False, indent=2))
    results.append(case("patchdef: 无 key \"0\" 重定向",
                        lambda: run_check_patchdef(lb)))

    # ---------- C2. key "0" 指向越界/非 png ----------
    print("\n[6] key \"0\" 指向坏索引应 CAUGHT")
    d = json.load(io.open(os.path.join(gate.PKG_LB, "patchdef.json"),
                          encoding="utf-8-sig"))
    d["base"]["fileRedirection"]["manual"]["0"] = 9999
    io.open(os.path.join(lb, "patchdef.json"), "w", encoding="utf-8").write(
        json.dumps(d, ensure_ascii=False, indent=2))
    results.append(case("patchdef: manual/0 -> 越界索引",
                        lambda: run_check_patchdef(lb)))

    # ---------- 汇总 ----------
    missed = sum(1 for r in results if not r)
    print("\n=== 汇总 ===")
    print("  用例 %d 个，CAUGHT %d，MISSED %d"
          % (len(results), sum(1 for r in results if r), missed))
    print("RESULT: %s" % ("ALL CAUGHT" if missed == 0 else "★ 有 %d 个漏判" % missed))
    return 0 if missed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
