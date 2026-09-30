# -*- coding: utf-8 -*-
"""用 GitHub API 发布 release 并上传全部资产（泛化版，v1.6 起使用）。

每次发布传三样（build_delta.py 的输出清单）：
    RNDZh-Setup-vX.Y.exe              全量安装包
    RNDZh-Update-v<基线>_to_vX.Y.7z   各基线增量包
    update.json                       启动器检查更新元数据（资产名固定，
                                      走 releases/latest/download/update.json 稳定 URL）

token 从 Windows 凭据管理器取（`git credential fill` 走 PowerShell —— 本机在
非交互 shell 里直接调会返回空，AGENTS 记过这条）。

    python scripts/publish_release.py --tag v1.6 --name "v1.6 —— 应用内增量更新" \
        --asset 成品ing/RNDZh-Setup-v1.6.exe \
        --asset 成品ing/RNDZh-Update-v1.5_to_v1.6.7z \
        --asset 成品ing/update.json \
        --notes 成品ing/_release_v1.6.md
    加 --dry-run 只做检查，不调 API。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

REPO = 'Syun1524/RND_Chinese'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_token():
    ps = ('$in = "protocol=https`nhost=github.com`n`n"; '
          '$out = $in | git credential fill 2>$null; '
          '($out | Select-String "password=(.+)").Matches.Groups[1].Value')
    r = subprocess.run(['pwsh', '-NoProfile', '-Command', ps],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    tok = (r.stdout or '').strip()
    if not tok:
        sys.exit('取不到 GitHub token')
    return tok


def api(url, token, method='GET', data=None, ctype='application/json',
        raw_file=None):
    req = urllib.request.Request(url, method=method)
    req.add_header('Authorization', 'token %s' % token)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', 'RND_Chinese-release')
    if raw_file:
        body = open(raw_file, 'rb').read()
        req.add_header('Content-Type', ctype)
        req.add_header('Content-Length', str(len(body)))
        req.data = body
    elif data is not None:
        req.add_header('Content-Type', ctype)
        req.data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            txt = r.read().decode('utf-8', 'replace')
            return r.status, (json.loads(txt) if txt.strip().startswith(('{', '[')) else txt)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True, help='如 v1.6')
    ap.add_argument('--name', required=True, help='release 标题')
    ap.add_argument('--asset', dest='assets', action='append', required=True,
                    help='资产文件路径，可重复')
    ap.add_argument('--notes', required=True, help='release 说明（markdown 文件）')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    for p in args.assets + [args.notes]:
        if not os.path.exists(p):
            sys.exit('缺少文件 %s' % p)
    import hashlib
    print('release : %s %s' % (args.tag, args.name))
    for p in args.assets:
        print('  资产: %-42s %9.1f MB  md5 %s'
              % (os.path.basename(p), os.path.getsize(p) / 1048576,
                 hashlib.md5(open(p, 'rb').read()).hexdigest()))
    print('notes   : %s' % args.notes)
    # update.json 是启动器的元数据，发布前必须与资产 md5 一致
    upd = next((p for p in args.assets if os.path.basename(p) == 'update.json'), None)
    if upd:
        meta = json.load(open(upd, encoding='utf-8-sig'))
        names = {os.path.basename(p): hashlib.md5(open(p, 'rb').read()).hexdigest()
                 for p in args.assets}
        bad = []
        for d in meta.get('deltas', []):
            if names.get(d['file']) != d['md5']:
                bad.append(d['file'])
        if bad:
            sys.exit('★ update.json 里的 md5 与本地文件不符：%s（先重跑 build_delta.py）' % bad)
        print('  update.json 校验: %d 份增量 md5 全部一致'
              % len(meta.get('deltas', [])))

    if args.dry_run:
        print('\n[dry-run] 未调用 API')
        return

    tok = get_token()
    print('token 已取得 (%d 字符)' % len(tok))
    body = open(args.notes, encoding='utf-8').read()

    st, res = api('https://api.github.com/repos/%s/releases/tags/%s' % (REPO, args.tag), tok)
    if st == 200:
        print('release %s 已存在，更新说明' % args.tag)
        st2, res2 = api('https://api.github.com/repos/%s/releases/%d' % (REPO, res['id']),
                        tok, 'PATCH', {'name': args.name, 'body': body})
        print('  PATCH http=%s' % st2)
        rel = res2
    else:
        st2, res2 = api('https://api.github.com/repos/%s/releases' % REPO, tok, 'POST', {
            'tag_name': args.tag, 'name': args.name, 'body': body,
            'draft': False, 'prerelease': False,
        })
        print('  创建 release http=%s' % st2)
        if st2 not in (200, 201):
            sys.exit('创建失败: %s' % str(res2)[:500])
        rel = res2
    rid = rel['id']
    print('  release id=%s  html=%s' % (rid, rel.get('html_url')))

    st, assets = api('https://api.github.com/repos/%s/releases/%d/assets' % (REPO, rid), tok)
    existing = {a['name']: a['id'] for a in assets} if isinstance(assets, list) else {}

    for p in args.assets:
        name = os.path.basename(p)
        if name in existing:
            st_d, _ = api('https://api.github.com/repos/%s/releases/assets/%d'
                          % (REPO, existing[name]), tok, 'DELETE')
            print('  删除旧资产 %s -> http=%s' % (name, st_d))
        up = ('https://uploads.github.com/repos/%s/releases/%d/assets?name=%s'
              % (REPO, rid, urllib.parse.quote(name)))
        st3, res3 = api(up, tok, 'POST', raw_file=p, ctype='application/octet-stream')
        print('  上传 %s -> http=%s' % (name, st3))
        if st3 not in (200, 201):
            sys.exit('上传失败: %s' % str(res3)[:500])
        print('    id=%s size=%s %s' % (res3.get('id'), res3.get('size'),
                                        res3.get('browser_download_url')))
    print('\n完成。发布后用启动器跑一次真实检查更新做冒烟：')
    print('  RNDZhLauncher.exe --selftest-update   （应报 已是最新 或正常增量）')


if __name__ == '__main__':
    sys.exit(main())
