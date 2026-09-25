# -*- coding: utf-8 -*-
"""验证「一份字体缓存同时服务 JP 与 EN」这项修复真的生效。

为什么需要这个脚本 —— final_accept.py 覆盖不到这件事：
  · 它的 snap() 把 fonts/ 排除在比对之外（字体缓存按语言重建，历来不比对）；
  · 它统计错误只数 "error" / "exception" 两个词，而 lang 校验失败写的是
    "Font cache language mismatch, clearing font cache" —— 两个词都不含。
  → 于是「缓存被整份丢掉重烘」在验收里既不算多余、也不算错误，是盲区。

★ 为什么直接翻转 fontData.bin 里的 lang 字节，而不是想办法让游戏跑 EN：
  `Game.exe roboticsnotesd EN` 直启时语言标志仍是 JP（实测：lang=0 的缓存
  没被判定为错配）。要真进 EN 模式得经 launcher.exe 传参，链路更长、变量更多。
  而这两版缓存的字形数据**已实测逐字节相同**，唯一差别就是那个 lang 字节，
  所以「翻转该字节」与「JP 烘的缓存 + EN 版游戏」在本题上等价，且只动一个变量。

三段测试（含阳性对照，避免做成死门禁）：
  [1] 阳性对照：新 DLL + 故意损坏 charsetHash
      → 必须清空缓存。证明 ①loadCache 真的跑了 ②charset 守卫没被误伤。
  [2] 反向对照：旧 DLL + lang 翻转
      → 必须清空缓存。证明 lang 守卫在旧版里是活的（本测试有能力发现差异）。
  [3] 修复效果：新 DLL + lang 翻转
      → 必须不清空、fontData.bin 逐字节不变。

跑完会把日语副本的 fonts/ 与 dinput8.dll 还原。

用法:
    python scripts/diagnostics/verify_lang_cache_shared.py
"""
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

GAME = r"D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -原版日语 副本"
FONTS = os.path.join(GAME, "languagebarrier", "fonts")
LOG = os.path.join(GAME, "languagebarrier", "log.txt")
# ★ 目录名含 ';' 时，Windows 加载器按 ';' 切分并把片段当相对目录名搜 DLL，
#   实际加载的是【片段子目录】里那份，根目录那份压根不在搜索路径里。
#   只改根目录 = 改了个寂寞（AGENTS 记过这个坑；本脚本第一版又踩了一次，
#   症状是「换旧 DLL 却仍然不报 mismatch」——因为跑的一直是新 DLL）。
FRAG = os.path.join(GAME, "NOTES DaSH -原版日语 副本")
DLL_TARGETS = [os.path.join(GAME, "dinput8.dll"),
               os.path.join(FRAG, "dinput8.dll")]
NEW_DLL = (r"D:\DATA\tran\agent tran\GitHub\RND_Chinese\LanguageBarrier_rndchs"
           r"\LanguageBarrier\dinput8-Release\dinput8.dll")
OLD_DLL = (r"D:\DATA\tran\agent tran\9.6文本外工作\成品ing\_backup"
           r"\fontseed_20260925_231408\dinput8.dll")
BAK = (r"D:\DATA\tran\agent tran\9.6文本外工作\成品ing\_backup"
       r"\langtest_fonts_20260925_232240")

MISMATCH = "Font cache language mismatch"
CHARSET = "different charset"


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def kill_game():
    ps = ("Get-Process Game.exe -ErrorAction SilentlyContinue | "
          "Where-Object { $_.Path -like '%s*' -or $_.Path -like '%s*' } | "
          "Stop-Process -Force" % (GAME, os.path.realpath(GAME)))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True)
    time.sleep(2)


def patch_fontdata(src, dst, mode):
    """按 mode 改写 fontData.bin 的副本。

    mode='flip_lang'    : 每个条目的 lang 字节 0<->1（制造语言错配）
    mode='break_charset': 每个条目的 charsetHash 翻转一位（制造码表失配）
    其余字节原样，保证只动一个变量。
    """
    b = bytearray(open(src, "rb").read())
    off = 0
    n = struct.unpack_from("<Q", b, off)[0]
    off += 8
    for _ in range(n):
        off += 2                       # key (uint16)
        if mode == "flip_lang":
            b[off] = 1 if b[off] == 0 else 0
        off += 1                       # lang
        if mode == "break_charset":
            b[off] ^= 0x01             # hash 最低位翻转
        off += 4                       # charsetHash
        for _ in range(2):             # glyphMap + outlineMap
            c = struct.unpack_from("<Q", b, off)[0]
            off += 8
            off += c * 24              # gid(2) + FontGlyph(22)
    if off != len(b):
        raise RuntimeError("fontData.bin 解析长度不符: %d/%d" % (off, len(b)))
    open(dst, "wb").write(bytes(b))


def restore_fonts():
    for n in os.listdir(FONTS):
        os.remove(os.path.join(FONTS, n))
    for n in os.listdir(BAK):
        shutil.copy2(os.path.join(BAK, n), os.path.join(FONTS, n))


def launch_and_read_log(max_wait=75, stable=6, min_wait=12):
    """启动游戏，等日志稳定后杀掉，返回 (log文本, 是否拿到日志)。

    loadCache() 在 earlyInitHook 里跑，实测启动后 ~11 秒内已走完（判据：日志
    出现 SetDialoguePageValuesHook 的 sigscan，它排在 loadCache 之后）。
    这里要求日志至少 min_wait 秒、且连续 stable 秒不再增长才收工。
    """
    if os.path.exists(LOG):
        os.remove(LOG)
    p = subprocess.Popen([os.path.join(GAME, "Game.exe"), "roboticsnotesd", "EN"],
                         cwd=GAME, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    t0 = time.time()
    got = False
    last_size, last_change = -1, time.time()
    while time.time() - t0 < max_wait:
        if p.poll() is not None:
            break
        size = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        if size > 0:
            got = True
        if size != last_size:
            last_size, last_change = size, time.time()
        elif (got and (time.time() - last_change) >= stable
              and (time.time() - t0) >= min_wait):
            break
        time.sleep(0.5)
    p.kill()
    kill_game()
    txt = ""
    if os.path.exists(LOG):
        txt = open(LOG, encoding="utf-8", errors="replace").read()
    return txt, got


def install_dll(dll):
    """写入两处（根目录 + 分号片段子目录）—— 后者才是实际被加载的那份。"""
    for t in DLL_TARGETS:
        shutil.copy2(dll, t)


def stage(name, dll, mode, expect_cleared, expect_marker):
    """跑一段测试。返回 (是否通过, 详情)。"""
    print("\n[%s]" % name)
    print("     DLL: %s   缓存改写: %s" % (md5(dll)[:16], mode))
    install_dll(dll)
    ref = os.path.join(BAK, "fontData.bin")
    target = os.path.join(FONTS, "fontData.bin")
    if mode:
        patch_fontdata(ref, target, mode)
    before = os.path.getsize(target), md5(target)

    txt, got = launch_and_read_log()
    marker = expect_marker in txt
    after = os.path.getsize(target), md5(target)
    cleared = after != before

    ok = got and (marker == expect_cleared) and (cleared == expect_cleared)
    print("     拿到日志: %s" % ("是" if got else "★否"))
    print("     日志含 '%s': %-5s （预期 %s）%s"
          % (expect_marker, marker, expect_cleared, "" if marker == expect_cleared else "  ★不符"))
    print("     缓存被清空: %-5s （预期 %s）%s   [%d B -> %d B]"
          % (cleared, expect_cleared,
             "" if cleared == expect_cleared else "  ★不符", before[0], after[0]))
    print("     => %s" % ("✓ 通过" if ok else "★ 未通过"))
    return ok


def main():
    for p in (GAME, FONTS, NEW_DLL, OLD_DLL, BAK):
        if not os.path.exists(p):
            sys.exit("★ 缺少: %s" % p)
    if md5(NEW_DLL) == md5(OLD_DLL):
        sys.exit("★ 新旧 DLL 相同，无法做对照（OLD_DLL 可能已被覆盖）")

    print("=" * 72)
    print(" 字体缓存语言共用 专项验证")
    print("=" * 72)
    print(" 旧 DLL (修复前): %s" % md5(OLD_DLL)[:16])
    print(" 新 DLL (修复后): %s" % md5(NEW_DLL)[:16])
    print(" 缓存备份: %s (%d 文件)" % (os.path.basename(BAK), len(os.listdir(BAK))))

    kill_game()
    restore_fonts()
    results = {}

    # 实测结论（本脚本探针得出，别再凭猜）：
    #   本目录用 `Game.exe roboticsnotesd EN` 直启时，**运行时语言 = EN(1)**。
    #   证据：出厂缓存(lang=0) 被旧 DLL 判为 mismatch 并清空；
    #         lang 翻转为 1 后旧 DLL 反而静默通过。
    #   这正好是真实场景：我们烘的种子来自 JP 目录(lang=0)，发给英文版玩家。

    # [1] 阳性对照：证明 loadCache 真的在跑、charset 守卫还活着
    results["1"] = stage("1] 阳性对照：新 DLL + 损坏 charsetHash（预期清空）",
                         NEW_DLL, "break_charset", True, CHARSET)
    restore_fonts()

    # [2] 反向对照：修复前的真实状态 —— 出厂缓存(lang=0) + 旧 DLL + 英文版游戏
    #     → 必须清空。这是「本测试有能力发现差异」的证明。
    results["2"] = stage("2] 反向对照：旧 DLL + 出厂缓存 lang=0（预期清空）",
                         OLD_DLL, None, True, MISMATCH)
    restore_fonts()

    # [3] 边界：把 lang 翻转成与运行时一致，旧 DLL 也应静默采纳
    #     （说明 [2] 的失败确实来自语言比对，而不是别的什么）
    results["3"] = stage("3] 边界：旧 DLL + lang 翻转为 1（预期保留）",
                         OLD_DLL, "flip_lang", False, MISMATCH)
    restore_fonts()

    # [4] 修复效果：出厂缓存原样 + 新 DLL → 必须采纳，且日志无 mismatch。
    #     这正是「JP 烘的缓存发给 EN 版玩家」要验的场景。
    results["4"] = stage("4] 修复效果：新 DLL + 出厂缓存 lang=0（预期保留）",
                         NEW_DLL, None, False, MISMATCH)

    # 收尾
    install_dll(NEW_DLL)
    restore_fonts()
    final_md5 = md5(os.path.join(FONTS, "fontData.bin"))
    ref_md5 = md5(os.path.join(BAK, "fontData.bin"))
    restored = final_md5 == ref_md5
    print("\n 收尾：已恢复新 DLL 与测试前缓存 %s" % ("✓" if restored else "★不一致"))

    print("\n" + "=" * 72)
    names = {"1": "阳性对照（loadCache 在跑 / charset 守卫在）",
             "2": "反向对照（旧 DLL + 出厂缓存 lang=0，必须清）",
             "3": "边界（旧 DLL + lang 与运行时一致，不该清）",
             "4": "修复效果（新 DLL + 出厂缓存 lang=0，必须留）"}
    for k in ("1", "2", "3", "4"):
        print(" [%s] %-40s %s" % (k, names[k], "✓ 通过" if results[k] else "★ 未通过"))
    ok = all(results.values()) and restored
    print(" 结果: %s" % ("★ 全部通过 —— 一份缓存确实同时服务 JP/EN"
                        if ok else "★ 有问题，见上"))
    print("=" * 72)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
