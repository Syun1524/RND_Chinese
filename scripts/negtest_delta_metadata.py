# -*- coding: utf-8 -*-
"""负向自测：故意破坏 check_delta_metadata.py 的每条检查，确认会 FAIL。

教训（AGENTS 记过三次）：**门禁必须先在「故意做错」的输入上验证会 FAIL**，
否则等于没有。

用例（每条对应门禁的一类检查）：
  [好] 合成一份干净的 update.json + 增量包 → 必须 PASS
  [A] 打包端 FORBID 漏掉 卸载汉化.exe（重演事故根因） → CAUGHT
  [B] update.json 的 files[] 含 卸载汉化.exe → CAUGHT
  [B2] delete[] 含 Game.exe → CAUGHT
  [B3] files[] 含 boot.bat（设计约定也永不进增量） → CAUGHT
  [C] 包内实际多出 卸载汉化.exe（元数据干净、包脏） → CAUGHT
  [C2] 包内容与 files[] 不一致（包多一条） → CAUGHT
  [D] 增量包 md5 与 update.json 不符 → CAUGHT
  [D2] 增量包 size 与 update.json 不符 → CAUGHT

用法：python scripts/negtest_delta_metadata.py
"""
import hashlib
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

import check_delta_metadata as gate  # noqa: E402

TMP = tempfile.mkdtemp(prefix="negtest_delta_meta_")


def md5f(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def build_case(stage_files, declared=None, delete=None, corrupt_md5=False,
               corrupt_size=False, extra_in_arc=None):
    """造一份合成 update.json + 7z。

    stage_files: {相对路径: 内容} —— 打进 7z 的
    declared:    写进 update.json files[] 的（默认 = stage_files 的键）
    extra_in_arc: 额外塞进 7z 但**不**写进 files[] 的 {路径: 内容}
    """
    d = tempfile.mkdtemp(dir=TMP)
    stage = os.path.join(d, '_stage')
    os.makedirs(stage, exist_ok=True)
    payload = dict(stage_files)
    if extra_in_arc:
        payload.update(extra_in_arc)
    for rel, data in payload.items():
        dst = os.path.join(stage, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(data)
    arc = os.path.join(d, 'RNDZh-Update-v1.6_to_v1.8.7z')
    r = subprocess.run([gate.SEVENZR, 'a', '-t7z', '-mx=1', arc,
                        os.path.join(stage, '*')], capture_output=True)
    assert r.returncode == 0, r.stderr.decode('utf-8', 'replace')
    keys = sorted(declared if declared is not None else stage_files.keys())
    md5 = md5f(arc)
    size = os.path.getsize(arc)
    if corrupt_md5:
        md5 = ('0' if md5[0] != '0' else '1') + md5[1:]
    if corrupt_size:
        size += 1
    upd = {
        'version': '1.8', 'date': '2026-10-03',
        'setup': {'name': 'RNDZh-Setup-v1.8.exe', 'size': 0},
        'deltas': [{
            'from': '1.6', 'file': os.path.basename(arc),
            'size': size, 'md5': md5,
            'delete': delete or [],
            'files': [{'path': p, 'md5': md5f(os.path.join(stage, p.replace('/', os.sep)))
                       if os.path.exists(os.path.join(stage, p.replace('/', os.sep)))
                       else md5f(arc)} for p in keys],
        }],
    }
    with open(os.path.join(d, 'update.json'), 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(upd, ensure_ascii=False, indent=2))
    return d


def run_gate(out_dir, launcher_cpp=None, build_delta=None):
    """在给定目录跑门禁；可临时替换名单来源文件。"""
    old = (gate.LAUNCHER_CPP, gate.BUILD_DELTA)
    if launcher_cpp:
        gate.LAUNCHER_CPP = launcher_cpp
    if build_delta:
        gate.BUILD_DELTA = build_delta
    try:
        return gate.check(out_dir)
    finally:
        gate.LAUNCHER_CPP, gate.BUILD_DELTA = old


def case(name, out_dir, expect_fail=True, **kw):
    errs, _info = run_gate(out_dir, **kw)
    failed = bool(errs)
    ok = (failed == expect_fail)
    print("  [%s] %-52s -> %s" % ("CAUGHT" if failed else "passed", name,
                                  "FAIL" if failed else "PASS"))
    if failed:
        for e in errs[:2]:
            print("        %s" % e)
    return ok


def main():
    print("=== negtest: 增量元数据门禁 ===")
    results = []

    good_files = {'RNDZhLauncher.exe': b'NEW-LAUNCHER',
                  'languagebarrier/enscript/_system_00.msb': b'NEW-SYS'}

    print("\n[1] 好输入（合成干净增量）应 PASS")
    results.append(case("干净增量包", build_case(good_files), expect_fail=False))

    print("\n[2] 名单不一致应 CAUGHT")
    # A. 打包端 FORBID 漏掉 卸载汉化.exe
    src = io.open(gate.BUILD_DELTA, encoding='utf-8').read()
    broken = src.replace("'Game.exe', '卸载汉化.exe'}", "'Game.exe'}")
    assert broken != src, "测试用例没生效：build_delta.py 的 FORBID 里没有预期串"
    p = os.path.join(TMP, 'build_delta_noprotect.py')
    io.open(p, 'w', encoding='utf-8').write(broken)
    results.append(case("打包端 FORBID 漏 卸载汉化.exe", build_case(good_files),
                        expect_fail=True, build_delta=p))

    print("\n[3] 元数据含受保护文件应 CAUGHT")
    results.append(case("files[] 含 卸载汉化.exe",
                        build_case(good_files, declared=list(good_files) + ['卸载汉化.exe'])))
    results.append(case("delete[] 含 Game.exe",
                        build_case(good_files, delete=['Game.exe'])))
    results.append(case("files[] 含 boot.bat",
                        build_case(good_files, declared=list(good_files) + ['boot.bat'])))

    print("\n[4] 包内实际含受保护文件应 CAUGHT")
    results.append(case("包内多出 卸载汉化.exe（元数据干净）",
                        build_case(good_files, extra_in_arc={'卸载汉化.exe': b'OLD-UNINST'})))
    results.append(case("包内容与 files[] 不一致（包多一条）",
                        build_case(good_files, extra_in_arc={'extra.bin': b'X'})))

    print("\n[5] md5/size 漂移应 CAUGHT")
    results.append(case("增量包 md5 不符", build_case(good_files, corrupt_md5=True)))
    results.append(case("增量包 size 不符", build_case(good_files, corrupt_size=True)))

    missed = sum(1 for r in results if not r)
    print("\n=== 汇总 ===")
    print("  用例 %d 个，CAUGHT %d，MISSED %d"
          % (len(results), sum(1 for r in results if r), missed))
    print("RESULT: %s" % ("ALL CAUGHT" if missed == 0 else "★ 有 %d 个漏判" % missed))
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if missed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
