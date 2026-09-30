# -*- coding: utf-8 -*-
"""增量更新端到端测试（启动器 v1.6 --selftest-update 通道）。

本地起 HTTP 服务伪造 GitHub 的 latest/download 目录，把一个**合成**的假游戏目录
（目录名故意带分号 → 动态片段子目录）从 v1.5 态用启动器自身增量到 v1.6 态，
再跑三个负向用例。全程不碰真实游戏目录。

用例：
  P1 正向：5 个变化文件（含启动器本体）+ 1 个删除 → 全部落位、version.txt=1.6、
     动态片段(FragT)与硬编码片段(NOTES DaSH)的 dinput8.dll 同步、boot.bat 逐字节未动、
     RNDZhLauncher.new.exe 已消失
  N1 增量包 md5 篡改 → 拒绝应用，游戏目录零改动
  N2 Game.exe 进程在跑 → 拒绝更新
  N3 delete 清单带 ../ 越界路径 → 该条被跳过（不越界删文件），其余正常应用

    python scripts/diagnostics/verify_delta_update.py
"""
import hashlib
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LAUNCHER = r"D:\DATA\tran\agent tran\GitHub\RND_Chinese\tools\RNDZhLauncher.exe"
SEVENZR = os.path.join(ROOT, "成品ing", "setup", "build", "sdk", "7zr.exe")
RESULT = os.path.join(os.environ["TEMP"], "rndzh_upd_selftest.json")

OLD_DINPUT8 = b"OLD-DINPUT8"
NEW_DINPUT8 = b"NEW-DINPUT8"
BOOT_BAT = "start launcher.exe EN\r\n"


def md5b(b):
    return hashlib.md5(b).hexdigest()


def md5f(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def build_v15_game(tmp):
    """合成 v1.5 态游戏目录。返回游戏目录路径。"""
    game = os.path.join(tmp, "RND;FragT")        # 分号 → 动态片段子目录 FragT
    lb = os.path.join(game, "languagebarrier")
    os.makedirs(os.path.join(lb, "c0data"))
    os.makedirs(os.path.join(game, "NOTES DaSH"))
    os.makedirs(os.path.join(game, "FragT"))
    with open(os.path.join(game, "Game.exe"), "wb") as f:
        f.write(b"MZ-fake-game")
    with open(os.path.join(game, "boot.bat"), "w", encoding="utf-8", newline="") as f:
        f.write(BOOT_BAT)
    shutil.copy(LAUNCHER, os.path.join(game, "RNDZhLauncher.exe"))
    for p in (os.path.join(game, "dinput8.dll"),
              os.path.join(game, "NOTES DaSH", "dinput8.dll"),
              os.path.join(game, "FragT", "dinput8.dll")):
        with open(p, "wb") as f:
            f.write(OLD_DINPUT8)
    with open(os.path.join(lb, "version.txt"), "w", encoding="utf-8", newline="") as f:
        f.write("1.5\r\n")
    shutil.copy(SEVENZR, os.path.join(lb, "7zr.exe"))
    with open(os.path.join(lb, "patchdef.json"), "wb") as f:
        f.write(b"OLD-PATCHDEF")
    with open(os.path.join(lb, "c0data", "a.png"), "wb") as f:
        f.write(b"OLD-A")
    with open(os.path.join(lb, "c0data", "obsolete.png"), "wb") as f:
        f.write(b"OBSOLETE")
    return game


def pack_delta(serve_dir, payload, delete, corrupt_md5=False):
    """按补丁包布局打包增量 + 写 update.json，返回 (base_url, update.json dict)。"""
    stage = os.path.join(serve_dir, "_stage")
    shutil.rmtree(stage, ignore_errors=True)
    for rel, data in payload.items():
        dst = os.path.join(stage, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
    arc = os.path.join(serve_dir, "RNDZh-Update-v1.5_to_v1.6.7z")
    if os.path.exists(arc):
        os.remove(arc)
    r = subprocess.run([SEVENZR, "a", "-t7z", "-mx=5", arc,
                        os.path.join(stage, "*")], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    shutil.rmtree(stage, ignore_errors=True)
    arc_md5 = md5f(arc)
    if corrupt_md5:
        arc_md5 = ("0" if arc_md5[0] != "0" else "1") + arc_md5[1:]
    upd = {
        "version": "1.6", "date": "2026-09-30",
        "setup": {"name": "RNDZh-Setup-v1.6.exe", "size": 0},
        "deltas": [{
            "from": "1.5", "file": "RNDZh-Update-v1.5_to_v1.6.7z",
            "size": os.path.getsize(arc), "md5": arc_md5,
            "delete": delete,
            "files": [{"path": p, "md5": md5b(d)} for p, d in sorted(payload.items())],
        }],
    }
    with open(os.path.join(serve_dir, "update.json"), "w", encoding="utf-8") as f:
        json.dump(upd, f, ensure_ascii=False, indent=2)
    return upd


class Quiet(SimpleHTTPRequestHandler):
    hits = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Quiet.hits.append(self.path)
        return SimpleHTTPRequestHandler.do_GET(self)


def run_launcher(game, port):
    r = subprocess.run([os.path.join(game, "RNDZhLauncher.exe"),
                        "--update-base", "http://127.0.0.1:%d/" % port,
                        "--selftest-update"],
                       capture_output=True, timeout=120)
    if not os.path.exists(RESULT):
        raise AssertionError("自测结果文件未生成 rc=%s out=%s err=%s"
                             % (r.returncode, r.stdout[-300:], r.stderr[-300:]))
    return json.load(open(RESULT, encoding="utf-8-sig"))


def read(p):
    return open(p, "rb").read()


def case_positive(server):
    tmp = tempfile.mkdtemp(prefix="rndupd_pos_")
    game = build_v15_game(tmp)
    payload = {
        "RNDZhLauncher.exe": read(os.path.join(game, "RNDZhLauncher.exe")) + b";PATCHED",
        "dinput8.dll": NEW_DINPUT8,
        "languagebarrier/patchdef.json": b"NEW-PATCHDEF",
        "languagebarrier/c0data/a.png": b"NEW-A",
        "languagebarrier/new_sub/newfile.bin": b"NEWFILE",
    }
    delete = ["languagebarrier/c0data/obsolete.png"]
    pack_delta(server["dir"], payload, delete)
    res = run_launcher(game, server["port"])
    ok, why = True, []
    if not res.get("ok"):
        ok, why = False, ["ok=false err=%r" % res.get("err")]
    for k, want in (("check_status", 3), ("delta_found", 1), ("selfUpdated", True)):
        if res.get(k) != want:
            ok = False
            why.append("%s=%r 应为 %r" % (k, res.get(k), want))
    lb = os.path.join(game, "languagebarrier")
    checks = [
        (os.path.join(lb, "version.txt"), b"1.6\r\n"),
        (os.path.join(lb, "patchdef.json"), b"NEW-PATCHDEF"),
        (os.path.join(lb, "c0data", "a.png"), b"NEW-A"),
        (os.path.join(lb, "new_sub", "newfile.bin"), b"NEWFILE"),
        (os.path.join(game, "dinput8.dll"), NEW_DINPUT8),
        (os.path.join(game, "FragT", "dinput8.dll"), NEW_DINPUT8),
        (os.path.join(game, "NOTES DaSH", "dinput8.dll"), NEW_DINPUT8),
        (os.path.join(game, "boot.bat"), BOOT_BAT.encode("utf-8")),
        (os.path.join(game, "RNDZhLauncher.exe"),
         read(os.path.join(game, "RNDZhLauncher.exe"))),  # 占位，下面单独比
    ]
    for p, want in checks[:-1]:
        if not os.path.exists(p):
            ok, why = False, why + ["缺文件 %s" % p]
        elif read(p) != want:
            ok, why = False, why + ["内容不符 %s" % os.path.relpath(p, game)]
    if read(os.path.join(game, "RNDZhLauncher.exe"))[-8:] != b";PATCHED":
        ok, why = False, why + ["启动器本体未换成新内容"]
    if os.path.exists(os.path.join(game, "RNDZhLauncher.new.exe")):
        ok, why = False, why + ["RNDZhLauncher.new.exe 残留"]
    if os.path.exists(os.path.join(lb, "c0data", "obsolete.png")):
        ok, why = False, why + ["删除清单未生效（obsolete.png 还在）"]
    shutil.rmtree(tmp, ignore_errors=True)
    return ok, why


def case_bad_md5(server):
    tmp = tempfile.mkdtemp(prefix="rndupd_md5_")
    game = build_v15_game(tmp)
    payload = {"languagebarrier/patchdef.json": b"NEW-PATCHDEF"}
    pack_delta(server["dir"], payload, [], corrupt_md5=True)
    res = run_launcher(game, server["port"])
    ok = (not res.get("ok")) and "md5" in res.get("err", "")
    why = [] if ok else ["应因 md5 失败且提示含 md5：%r" % res]
    if os.path.exists(os.path.join(game, "languagebarrier", "patchdef.json")):
        if read(os.path.join(game, "languagebarrier", "patchdef.json")) != b"OLD-PATCHDEF":
            ok, why = False, why + ["拒绝后游戏目录竟被改动"]
    if read(os.path.join(game, "languagebarrier", "version.txt")).strip() != b"1.5":
        ok, why = False, why + ["拒绝后 version.txt 被改"]
    shutil.rmtree(tmp, ignore_errors=True)
    return ok, why


def case_game_running(server):
    tmp = tempfile.mkdtemp(prefix="rndupd_run_")
    game = build_v15_game(tmp)
    payload = {"languagebarrier/patchdef.json": b"NEW-PATCHDEF"}
    pack_delta(server["dir"], payload, [])
    # 把 python.exe 拷成 Game.exe 挂起运行 —— 进程表里就有 Game.exe
    exe = os.path.join(game, "Game.exe")
    shutil.copy(sys.executable, exe)
    proc = subprocess.Popen([exe, "-c", "import time; time.sleep(30)"],
                            cwd=game, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        res = run_launcher(game, server["port"])
    finally:
        proc.kill()
        proc.wait()
    ok = (not res.get("ok")) and "游戏正在运行" in res.get("err", "")
    why = [] if ok else ["应因游戏运行被拒绝：%r" % res]
    shutil.rmtree(tmp, ignore_errors=True)
    return ok, why


def case_traversal(server):
    tmp = tempfile.mkdtemp(prefix="rndupd_trav_")
    game = build_v15_game(tmp)
    outside = os.path.join(tmp, "outside_target.txt")
    with open(outside, "wb") as f:
        f.write(b"DONT-TOUCH")
    payload = {"languagebarrier/patchdef.json": b"NEW-PATCHDEF"}
    delete = ["languagebarrier/../../outside_target.txt",
              "languagebarrier/c0data/obsolete.png"]
    pack_delta(server["dir"], payload, delete)
    res = run_launcher(game, server["port"])
    ok, why = True, []
    if not res.get("ok"):
        ok, why = False, ["越界条目应被跳过而非中断：%r" % res]
    if read(outside) != b"DONT-TOUCH":
        ok, why = False, why + ["越界路径把门外文件删了！"]
    if read(os.path.join(game, "languagebarrier", "version.txt")).strip() != b"1.6":
        ok, why = False, why + ["合法删除条目未生效（version.txt 未更新）"]
    if os.path.exists(os.path.join(game, "languagebarrier", "c0data", "obsolete.png")):
        ok, why = False, why + ["合法删除条目未生效"]
    shutil.rmtree(tmp, ignore_errors=True)
    return ok, why


def main():
    if not os.path.exists(LAUNCHER):
        sys.exit("缺少启动器：%s" % LAUNCHER)
    serve_dir = tempfile.mkdtemp(prefix="rndupd_serve_")
    # ⚠ SimpleHTTPRequestHandler 默认伺服**进程 cwd**，不是 serve_dir ——
    #   必须显式传 directory，否则启动器拿到的是 404（首轮测试踩过：现象是
    #   「永远走 GitHub 兜底」，与服务器无关，极难排查）。
    httpd = HTTPServer(("127.0.0.1", 0),
                       functools.partial(Quiet, directory=serve_dir))
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    server = {"dir": serve_dir, "port": port}
    try:
        cases = [("P1 正向更新", case_positive),
                 ("N1 md5 篡改", case_bad_md5),
                 ("N2 游戏运行中", case_game_running),
                 ("N3 越界路径", case_traversal)]
        n_fail = 0
        for name, fn in cases:
            Quiet.hits.clear()
            try:
                ok, why = fn(server)
            except Exception as e:                     # noqa
                ok, why = False, ["异常: %r" % e]
            print("%s  %s%s%s" % ("✓" if ok else "✗", name,
                                  ("  |  " + "; ".join(why)) if why else "",
                                  ("  [服务器命中: %s]" % Quiet.hits) or ""))
            n_fail += 0 if ok else 1
    finally:
        httpd.shutdown()
        shutil.rmtree(serve_dir, ignore_errors=True)
    print()
    print("结果: %s（%d 失败）" % ("ALL PASS" if n_fail == 0 else "FAIL", n_fail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
