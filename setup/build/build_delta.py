# -*- coding: utf-8 -*-
"""构建增量更新包（RNDZh-Update-v<基线>_to_v<当前>.7z）与 update.json。

用法（build_installer.py 出全量包之后跑）：
    python build_delta.py --version 1.6 --from 1.5 \
        --base-manifest 成品ing/_releases/v1.5_manifest.json
    # 多基线：--from 与 --base-manifest 按顺序一一对应
    python build_delta.py --version 1.7 --from 1.6 1.5 \
        --base-manifest 成品ing/_releases/v1.6_manifest.json \
                         成品ing/_releases/v1.5_manifest.json

原理：增量 = 「当前补丁包相对基线快照的新增/变化文件」按补丁包布局打包 + 删除清单。
基线快照由 `gen_pkg_manifest.py --snapshot` 生成（路径/size/md5），必须在改动补丁包
内容**之前**固化；发版后同样把当版快照存进 成品ing/_releases/ 供下一版算差量。

产物（输出到 成品ing/）：
    RNDZh-Update-v<基线>_to_v<当前>.7z   每个基线一份
    update.json                          启动器检查更新用的元数据（资产名固定）

排除（绝不进增量/删除清单）：
    boot.bat                     语言 token 按安装而异，安装器重写，增量无权碰
    RNDZhSetup.exe               不进游戏目录
    languagebarrier/version.txt  启动器应用增量后自己写（写进包会固化旧版本号）
    Game.exe / 卸载汉化.exe      ★ 启动器 SafeRelPath 的受保护文件（永不覆盖/删除）
                                 —— 卸载器源码没改，但每次发版重编会改 PE 时间戳、
                                 md5 随变，2026-10-03 就因此被算进差量、被 v1.6
                                 启动器整包拒收（报「增量元数据含非法路径」）。

门禁（任一触发即退出，不写盘）：
    基线快照缺 md5 字段 / 删除清单含受保护文件 / 某基线零差异 /
    受保护文件被算进变化集 / 打包后 `7zr t` 不过 / --version 与补丁包 version.txt 不一致
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP_DIR = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(SETUP_DIR, '..', '..'))   # 9.6文本外工作/
SEVENZR = os.path.join(HERE, 'sdk', '7zr.exe')
DEFAULT_PKG = os.path.join(ROOT, '成品ing', '补丁包')
DEFAULT_OUT = os.path.join(ROOT, '成品ing')

# ★ 受保护文件：必须与启动器 tools/RNDZhLauncher.cpp 的 SafeRelPath() 名单**完全一致**。
#   启动器在应用增量前逐条安检 files[]，命中即整包拒绝（「增量元数据含非法路径」）。
#   名单不一致就会出现「打包端打进去了、玩家端永远装不上」的静默死锁。
#   check_delta_metadata.py 有一道门禁专门核对两边名单。
FORBID = {'boot.bat', 'RNDZhSetup.exe', 'languagebarrier/version.txt',
          'Game.exe', '卸载汉化.exe'}

# 受保护文件里「本该逐版不变」的那些：一旦 md5 变了就该有人看一眼。
#   · Game.exe     —— 游戏本体，不该进包
#   · 卸载汉化.exe —— 源码几乎不动；变了通常是无意重编（2026-10-03 事故的起点）
# 不含 RNDZhSetup.exe：它每版都随版本号重编，告警会退化成噪音。
FORBID_STABLE = ['Game.exe', '卸载汉化.exe']


def log(*a):
    print(*a, flush=True)


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def walk_pkg(pkg):
    """{相对路径(POSIX): md5}"""
    out = {}
    for root, _dirs, files in os.walk(pkg):
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, pkg).replace('\\', '/')] = md5(p)
    return out


def load_snapshot(path):
    snap = json.load(open(path, encoding='utf-8-sig'))
    files = {}
    for e in snap['files']:
        if 'md5' not in e:
            sys.exit('基线快照缺 md5 字段（用新版 gen_pkg_manifest.py --snapshot 重做）: %s' % path)
        files[e['path']] = e['md5']
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True, help='当前版本号（如 1.6）')
    ap.add_argument('--from', dest='bases', nargs='+', required=True, help='基线版本号列表')
    ap.add_argument('--base-manifest', dest='manifests', nargs='+', required=True,
                    help='各基线的快照 JSON，顺序与 --from 一致')
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    ap.add_argument('--out-dir', default=DEFAULT_OUT)
    args = ap.parse_args()

    if len(args.bases) != len(args.manifests):
        sys.exit('--from 与 --base-manifest 数量不一致')
    if not os.path.exists(SEVENZR):
        sys.exit('缺少 7zr.exe: %s' % SEVENZR)

    # 门禁：version.txt 与 --version 一致（build_installer.py 刚写的）
    verfile = os.path.join(args.pkg, 'languagebarrier', 'version.txt')
    if os.path.exists(verfile):
        cur = open(verfile, encoding='utf-8-sig').read().strip()
        if cur != args.version:
            sys.exit('补丁包 version.txt=%s 与 --version %s 不一致（先跑 build_installer.py）'
                     % (cur, args.version))

    cur_all = walk_pkg(args.pkg)                       # 含受保护文件（只用于对比告警）
    cur = {p: h for p, h in cur_all.items() if p not in FORBID}
    log('当前补丁包：%d 文件（不含 %d 个排除项）' % (len(cur), len(cur_all) - len(cur)))

    deltas = []
    for base_ver, mpath in zip(args.bases, args.manifests):
        base_all = load_snapshot(mpath)
        base = {p: h for p, h in base_all.items() if p not in FORBID}
        # 受保护文件变了 → 显式告警。这些文件按设计逐版不变（卸载器/游戏本体），
        # md5 变了通常意味着「发版时顺手重编了」——它进不了增量包（上面已排除），
        # 但也绝不能让它悄悄溜进「变化集」而无人知晓（2026-10-03 事故就是这样开始的）。
        for p in FORBID_STABLE:
            if p in base_all and p in cur_all and base_all[p] != cur_all[p]:
                log('⚠ 受保护文件 %s 与基线 v%s 不同（不进增量包；'
                    '确认是有意重编，或检查是否误改）' % (p, base_ver))
        changed = sorted(p for p in cur if p not in base or base[p] != cur[p])
        deleted = sorted(p for p in base if p not in cur)
        prot = [p for p in deleted if p in FORBID]
        if prot:
            sys.exit('★ 删除清单含受保护文件：%s' % prot)
        bad = [p for p in changed if p in FORBID]
        if bad:
            sys.exit('★ 受保护文件被算进变化集（不该发生，先查 walk/过滤）：%s' % bad)
        if not changed and not deleted:
            sys.exit('基线 v%s 与当前零差异，无需增量包' % base_ver)

        arc_name = 'RNDZh-Update-v%s_to_v%s.7z' % (base_ver, args.version)
        arc_path = os.path.join(args.out_dir, arc_name)
        stage = os.path.join(os.environ.get('TEMP', HERE), 'rnd_delta_stage')
        shutil.rmtree(stage, ignore_errors=True)
        for p in changed:
            dst = os.path.join(stage, p.replace('/', os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(args.pkg, p.replace('/', os.sep)), dst)
        if os.path.exists(arc_path):
            os.remove(arc_path)
        r = subprocess.run([SEVENZR, 'a', '-t7z', '-mx=5', '-ms=on',
                            arc_path, os.path.join(stage, '*')], capture_output=True)
        if r.returncode != 0:
            sys.exit('压缩失败：' + r.stderr.decode('utf-8', 'replace'))
        shutil.rmtree(stage, ignore_errors=True)
        # 门禁：包必须能通过 7z 自测
        r = subprocess.run([SEVENZR, 't', arc_path], capture_output=True)
        if r.returncode != 0:
            sys.exit('增量包 7z t 自测失败：%s' % arc_path)

        deltas.append({
            'from': base_ver,
            'file': arc_name,
            'size': os.path.getsize(arc_path),
            'md5': md5(arc_path),
            'delete': deleted,
            'files': [{'path': p, 'md5': cur[p]} for p in changed],
        })
        log('基线 v%s → v%s：新增/变化 %d，删除 %d → %s（%.1f MB，md5 %s）'
            % (base_ver, args.version, len(changed), len(deleted), arc_name,
               deltas[-1]['size'] / 1048576, deltas[-1]['md5']))
        if changed:
            log('    变化: %s%s' % (', '.join(changed[:8]),
                                    ' …共 %d' % len(changed) if len(changed) > 8 else ''))
        if deleted:
            log('    删除: %s' % ', '.join(deleted[:8]))

    setup_name = 'RNDZh-Setup-v%s.exe' % args.version
    setup_path = os.path.join(args.out_dir, setup_name)
    # ★ 优先读 setup/ 下的新构建：出包流程里「cp 安装包到 out_dir」发生在 build_delta
    #   **之后**，用 out_dir 的文件会把上一版的大小记进 update.json（2026-10-01 实测）。
    fresh = os.path.join(SETUP_DIR, setup_name)
    if os.path.exists(fresh):
        setup_path = fresh
    update = {
        'version': args.version,
        'date': time.strftime('%Y-%m-%d'),
        'setup': {'name': setup_name,
                  'size': os.path.getsize(setup_path) if os.path.exists(setup_path) else 0},
        'deltas': deltas,
    }
    out_json = os.path.join(args.out_dir, 'update.json')
    with open(out_json, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(update, ensure_ascii=False, indent=2).replace('\n', '\r\n'))
    log('已写 %s（deltas %d 份；setup size %s）'
        % (out_json, len(deltas), update['setup']['size'] or '⚠ 全量包不存在'))
    log('')
    log('=== 发布清单（全部要传到 GitHub Release）===')
    log('  %s' % setup_name)
    for d in deltas:
        log('  %s' % d['file'])
    log('  update.json')


if __name__ == '__main__':
    main()
