# -*- coding: utf-8 -*-
"""门禁：增量包与 update.json 不得包含受保护文件（启动器永不覆盖/删除的那批）。

背景（2026-10-03 实机事故）：
  `卸载汉化.exe` 被算进 v1.6→v1.8 差量，v1.6 启动器在 ApplyPayload 里逐条过
  SafeRelPath()，命中受保护名单就整包拒收 —— 玩家看到
  「增量更新失败：增量元数据含非法路径： 卸载汉化.exe」。
  根因是 build_delta.py 的排除清单与启动器 SafeRelPath() 的名单不一致
  （打包端只排除了 boot.bat / RNDZhSetup.exe / version.txt）。

本门禁检查四件事：
  A. 打包端 FORBID 与启动器 SafeRelPath() 的名单**完全一致**（两边不许各写一份）；
  B. update.json 的每个 delta：files[] / delete[] 都不含受保护文件；
  C. 实际 .7z 里的条目（用 7zr l -slt 读真实内容）也不含受保护文件；
  D. update.json 里各 delta 的 file/md5/size 与磁盘上的 .7z 一致。

负向自测（negtest_delta_metadata.py）会故意破坏每种情形，确认本脚本报 FAIL。

用法：
    python scripts/check_delta_metadata.py                     # 查成品ing/ 下全部
    python scripts/check_delta_metadata.py --dir <目录>        # 只查某目录
"""
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEVENZR = os.path.join(ROOT, '成品ing', 'setup', 'build', 'sdk', '7zr.exe')
BUILD_DELTA = os.path.join(ROOT, '成品ing', 'setup', 'build', 'build_delta.py')
LAUNCHER_CPP = os.path.join(ROOT, 'launcher', 'RNDZhLauncher.cpp')

# 除受保护文件外，另有三个「永不进增量」的条目（不是启动器安检，是设计约定）：
#   boot.bat（语言 token 按安装而异）、languagebarrier/version.txt（启动器自己写）
#   —— 它们同样不该出现在任何增量里。
NEVER_IN_DELTA = {'boot.bat', 'languagebarrier/version.txt'}


def md5f(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def parse_cpp_protected(path):
    """从启动器源码里抽出 SafeRelPath() 的 prot[] 名单。"""
    text = io.open(path, encoding='utf-8-sig', errors='replace').read()
    m = re.search(r'static const wchar_t\* prot\[\]\s*=\s*\{(.*?)\};', text, re.S)
    if not m:
        return None
    return [s.strip().strip('L"') for s in m.group(1).split(',') if s.strip()]


def parse_build_delta_forbid(path):
    """从 build_delta.py 里抽出 FORBID 集合。"""
    text = io.open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'^FORBID\s*=\s*\{(.*?)\}', text, re.S | re.M)
    if not m:
        return None
    return set(re.findall(r"'([^']*)'", m.group(1)))


def list_7z(arc):
    """用 7zr 列出归档内的文件（相对路径，POSIX 分隔）。目录条目被过滤掉。"""
    r = subprocess.run([SEVENZR, 'l', '-slt', '-sccUTF-8', arc], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('7zr l 失败: %s' % r.stderr.decode('utf-8', 'replace')[:300])
    out = r.stdout.decode('utf-8', 'replace')
    cur, files, in_entries = None, [], False
    for line in out.splitlines():
        if line.startswith('----------'):
            in_entries = True
            continue
        if not in_entries:
            continue
        if line.startswith('Path = '):
            cur = line[7:].replace('\\', '/')
        elif line.startswith('Attributes = ') and cur:
            if 'D' not in line[13:]:
                files.append(cur)
            cur = None
    return files


def check(out_dir):
    """返回 (errs, info)。"""
    errs = []
    info = []

    # A. 两边名单必须一致
    cpp = parse_cpp_protected(LAUNCHER_CPP)
    forbid = parse_build_delta_forbid(BUILD_DELTA)
    if cpp is None:
        errs.append('读不到启动器 SafeRelPath() 的 prot[] 名单：%s' % LAUNCHER_CPP)
    if forbid is None:
        errs.append('读不到 build_delta.py 的 FORBID 集合：%s' % BUILD_DELTA)
    if cpp is not None and forbid is not None:
        # 启动器名单里的文件必须全部被打包端排除
        miss = sorted(set(cpp) - forbid)
        if miss:
            errs.append('打包端 FORBID 漏了启动器受保护文件：%s（会重演 2026-10-03 事故）' % miss)
        # 打包端额外排除的（boot.bat / version.txt）是设计约定，允许
        extra = sorted(forbid - set(cpp))
        info.append('受保护名单（启动器 %d 项 / 打包端 %d 项，额外 %s）'
                    % (len(cpp), len(forbid), extra or '无'))
    protected = set(cpp or []) | NEVER_IN_DELTA

    # B/C/D. update.json + 各增量包
    upd_path = os.path.join(out_dir, 'update.json')
    if not os.path.exists(upd_path):
        errs.append('缺少 update.json：%s' % upd_path)
        return errs, info
    meta = json.load(io.open(upd_path, encoding='utf-8-sig'))
    deltas = meta.get('deltas', [])
    if not deltas:
        errs.append('update.json 里没有任何 delta')
    for d in deltas:
        arc = os.path.join(out_dir, d['file'])
        if not os.path.exists(arc):
            errs.append('update.json 指向的增量包不存在：%s' % d['file'])
            continue
        # B. 元数据层面
        bad_f = [f['path'] for f in d.get('files', []) if f['path'] in protected]
        bad_d = [p for p in d.get('delete', []) if p in protected]
        if bad_f:
            errs.append('%s：files[] 含受保护文件 %s' % (d['file'], bad_f))
        if bad_d:
            errs.append('%s：delete[] 含受保护文件 %s' % (d['file'], bad_d))
        # C. 真实包内容层面
        try:
            inside = list_7z(arc)
        except RuntimeError as e:
            errs.append('%s：读包失败 %s' % (d['file'], e))
            continue
        bad_in = sorted(p for p in inside if p in protected)
        if bad_in:
            errs.append('%s：包内实际含受保护文件 %s（启动器会整包拒收）'
                        % (d['file'], bad_in))
        # files[] 与包内容必须一一对应（多/少都是元数据漂移）
        declared = sorted(f['path'] for f in d.get('files', []))
        if sorted(inside) != declared:
            errs.append('%s：包内文件与 update.json 的 files[] 不一致（包 %d 条 / 元数据 %d 条）'
                        % (d['file'], len(inside), len(declared)))
        # D. md5/size 与磁盘一致
        if md5f(arc) != d.get('md5'):
            errs.append('%s：md5 与磁盘不符（先重跑 build_delta.py）' % d['file'])
        if os.path.getsize(arc) != d.get('size'):
            errs.append('%s：size 与磁盘不符（%d vs %d）'
                        % (d['file'], os.path.getsize(arc), d.get('size')))
        info.append('%s：%d 文件，受保护 %d 条，md5/size 一致'
                    % (d['file'], len(inside), len(bad_in)))

    return errs, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=os.path.join(ROOT, '成品ing'),
                    help='含 update.json 与增量包的目录（默认 成品ing/）')
    args = ap.parse_args()

    print('=== 增量元数据门禁 ===')
    errs, info = check(args.dir)
    for s in info:
        print('  · %s' % s)
    if errs:
        print('\n问题:')
        for e in errs:
            print('  - %s' % e)
    print('\nRESULT: %s' % ('PASS' if not errs else 'FAIL'))
    return 0 if not errs else 1


if __name__ == '__main__':
    sys.exit(main())
