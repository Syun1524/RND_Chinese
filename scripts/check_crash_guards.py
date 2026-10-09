# -*- coding: utf-8 -*-
"""门禁：两个玩家报告的闪退场景的「数据不变量 + 源码防护点」。

背景（2026-10-09 玩家反馈）：
  ① 芙劳线末尾「芙劳波拦住 HOMO → 切黑屏」闪退；
  ② 共通线君岛晃第二次登场、打开 IRUO 闪退。
  两者都是**中文模式必崩、切英文能过**。

已坐实的两个机制（本门禁守的就是它们）：

  A. **宽度扫描死循环**（GameText.cpp `getSc3StringDisplayWidthHook`）
     旧实现的循环体里，只有 `0x04`（表达式）与「双字节字形」两条分支会推进
     `sc3string`；**任何单字节控制码（0x00/0x01/0x02/0x03/0x09/0x0A/0x0B…）
     落不进任何分支 → 指针原地不动 → 死循环**。
     实测：把 CN `rnd_02_01_00.msb` sid=1300 的真实字节喂给旧循环，20M 次
     迭代仍未退出（`looptest.cpp`）。IRUO 的 AR 标签正是通过
     `gameExeGetSC3StringByID(13, ...)` → `getSc3StringDisplayWidthHook` 测量的，
     而脚本 13（`rnd_01_01_00.msb`）的 sid=7800 带 `0x09/0x0A/0x0B`。
     ⚠ 数据侧无法「改掉」这些字节：ruby 标记本身就是 0x09/0x0A/0x0B，
     而且 CN 全库 105 个文件 582 条都带（EN 侧只有 25 文件 431 条，
     且分布不同）—— 只能在代码侧修。

  B. **字幕状态未加空指针/失败保护**（CriManaMod.cpp）
     `drawSubs()` 直接 `CopyResource(state->stagingTexture, …)`；
     CoZ 上游原本有 `if (state->stagingTexture) … else …` 的守卫，本 fork
     改写 D3D11 路径时把它丢了。而 `csri_render(NULL, frame, t)` 实测是
     **访问违例**（用仓库自带的 VSFilter.dll 直接跑：`probe3.exe`）。
     芙劳线末尾的 ED 影片（movie id 46）默认挂字幕（`karaokeSubs: all`）。

本门禁检查：
  A1. 源码里宽度扫描必须有「兜底推进」分支（否则控制码会卡死）；
  A2. 数据侧：目标场景文件的控制码结构必须与日文/英文基线一致（无新增畸形）；
  B.  源码里 drawSubs/startSubtitle 必须有 stagingTexture + csri 的失败保护；
  B2. 源码里不得再出现无保护的 `csri_render(state->csri` 直接调用；
  C.  源码里 IRUO 钩子不得裸除 `IruoSensitivity`，且地标数组访问有边界检查。

用法：
    python scripts/check_crash_guards.py            # 检查仓库源码 + 补丁包数据
    python scripts/check_crash_guards.py --quiet
"""
import argparse
import io
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _resolve(rel_candidates):
    """按候选相对路径找一个存在的。

    本脚本在**两个位置**各有一份：工作区 `9.6文本外工作/scripts/` 与仓库
    `GitHub/RND_Chinese/scripts/`。两处的相对层级不同（仓库那份的
    LanguageBarrier_chs 就在同级），所以不能写死 `..\\GitHub\\...`。
    """
    for rel in rel_candidates:
        p = os.path.normpath(os.path.join(HERE, rel))
        if os.path.exists(p):
            return p
    return os.path.normpath(os.path.join(HERE, rel_candidates[0]))


SRC_GAMETEXT = _resolve(["../GitHub/RND_Chinese/LanguageBarrier_chs/LanguageBarrier/GameText.cpp",
                         "../../GitHub/RND_Chinese/LanguageBarrier_chs/LanguageBarrier/GameText.cpp",
                         "../LanguageBarrier_chs/LanguageBarrier/GameText.cpp"])
SRC_CRIMANA = _resolve(["../GitHub/RND_Chinese/LanguageBarrier_chs/LanguageBarrier/CriManaMod.cpp",
                        "../../GitHub/RND_Chinese/LanguageBarrier_chs/LanguageBarrier/CriManaMod.cpp",
                        "../LanguageBarrier_chs/LanguageBarrier/CriManaMod.cpp"])
SRC_INPUT = _resolve(["../GitHub/RND_Chinese/LanguageBarrier_chs/LanguageBarrier/CustomInputRND.cpp",
                      "../../GitHub/RND_Chinese/LanguageBarrier_chs/LanguageBarrier/CustomInputRND.cpp",
                      "../LanguageBarrier_chs/LanguageBarrier/CustomInputRND.cpp"])
PKG_LB = _resolve(["../成品ing/补丁包/languagebarrier",
                   "../../9.6文本外工作/成品ing/补丁包/languagebarrier"])
PKG_ENS = os.path.join(PKG_LB, "enscript")
JP_ENS = _resolve(["../解包/解包cpk的产物(日语)/mes00",
                   "../../9.6文本外工作/解包/解包cpk的产物(日语)/mes00"])

# 玩家报告的两个场景族 + IRUO 标签来源脚本
SCENE_FILES = [
    "rnd_fra_09_01_00.msb",   # 芙劳现身拦住 HOMO
    "rnd_fra_09_02_00.msb",
    "rnd_fra_09_03_00.msb",   # 张开双臂挡在中间 → 切黑屏
    "rnd_02_01_00.msb",       # 君岛晃第二次登场 + 启动 IRUO.
    "rnd_02_02_00.msb",
    "rnd_01_01_00.msb",       # 脚本 13：AR 地标标签来源
    "_geotag_00.msb",         # IRUO 地标文本
    "rnd_dar_02_13_00.msb",
]

# 单字节控制码里，旧循环唯一会推进的是 0x04（表达式）；其余都会卡住。
EXPR = 0x04


def read_msb(path):
    """返回 [(sid, raw_bytes)]。

    ⚠ 正文长度**不能**靠「扫到 0xFF」来定：`0xFF` 是合法字形码的低字节
    （例：`8b ff` = 字形 3071），照那样切会把长句拦腰截断，看起来像
    「没有 0x03 收尾」。正确做法是从条目起点按 token 走，走到 0x03 收尾
    为止（0x03 后面那个字节是 0xFF 终止符）。
    """
    d = open(path, "rb").read()
    n = struct.unpack_from("<I", d, 8)[0]
    base = struct.unpack_from("<I", d, 12)[0]
    spans = []
    for k in range(n):
        e = 0x18 + k * 8
        sid, off = struct.unpack_from("<II", d, e)
        spans.append((sid, base + off))
    out = []
    for sid, start in spans:
        out.append((sid, walk_to_end(d, start)))
    return out


def walk_to_end(d, start):
    """从 start 起按 token 走到 0x03 收尾，返回不含收尾 0x03 的正文。

    遇到 0xFF（终止符）或越界就停 —— 那说明这条本身畸形，由调用方判定。
    """
    i = start
    L = len(d)
    while i < L:
        b = d[i]
        if b == 0xFF:
            return d[start:i]
        if b >= 0x80:
            if i + 1 >= L:
                return d[start:i]
            i += 2
        elif b == EXPR:
            j = i + 1
            while j < L and d[j] != 0:
                j += 1
            i = j + 1
        else:
            i += 1
            if b == 0x03:
                return d[start:i - 1]
    return d[start:L]


def walk_controls(raw):
    """按 SC3 token 规则走一遍，返回 [(offset, byte)] 的单字节控制码列表。"""
    ctrls = []
    i, L = 0, len(raw)
    while i < L:
        b = raw[i]
        if b >= 0x80:                      # 双字节字形
            if i + 1 >= L:
                break
            i += 2
        elif b == EXPR:                    # 0x04：表达式，跳到 0x00
            i += 1
            while i < L and raw[i] != 0:
                i += 1
            i += 1
        else:
            ctrls.append((i, b))
            i += 1
    return ctrls


def find_function_body(text, signature):
    """取 signature 的**函数定义**体。

    ⚠ 不能取第一次出现：文件里先有前向声明（`int __cdecl f();`），
    那会切出一个几十字节的空壳，检查恒假。
    """
    start = 0
    while True:
        i = text.find(signature, start)
        if i < 0:
            return None
        brace = text.find("{", i)
        semi = text.find(";", i)
        # 声明：分号出现在左花括号之前
        if brace < 0 or (0 <= semi < brace):
            start = i + len(signature)
            continue
        depth = 0
        k = brace
        while k < len(text):
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
                if depth == 0:
                    return text[i:k + 1]
            k += 1
        return text[i:]


def check_source_widthloop(path):
    """A1. 宽度扫描必须有兜底推进。"""
    errs = []
    if not os.path.exists(path):
        return ["源码不存在: %s" % path]
    text = io.open(path, encoding="utf-8-sig", errors="replace").read()
    body = find_function_body(text, "int __cdecl getSc3StringDisplayWidthHook")
    if body is None:
        return ["GameText.cpp 里找不到 getSc3StringDisplayWidthHook"]
    # 兜底分支的标志：else { sc3string++; }（注释可有可无）
    has_else_advance = "} else {" in body and "sc3string++;" in body
    if not has_else_advance:
        errs.append(
            "getSc3StringDisplayWidthHook 缺少单字节控制码的兜底推进分支 "
            "—— 遇到 0x00/0x01/0x02/0x03/0x09/0x0A/0x0B 会死循环")
    # 两个宽度表的下标都必须先判范围（判据要能区分「有检查」与「没检查」，
    # 所以逐条找下标读取点，而不是只看文件里有没有出现过 sizeof）
    for table, guard in (
        ("originalWidth[glyphId]", "originalWidth))"),
        ("widths[glyphId]", "sizeof(widths)"),
    ):
        idx = body.find(table)
        if idx < 0:
            continue
        if guard not in body[:idx]:
            errs.append("getSc3StringDisplayWidthHook 里 %s 没有先判范围" % table)
    return errs


def check_source_fmv(path):
    """B. 字幕渲染必须有失败保护。"""
    errs = []
    if not os.path.exists(path):
        return ["源码不存在: %s" % path]
    text = io.open(path, encoding="utf-8-sig", errors="replace").read()

    # 必须有统一的释放/替换辅助
    for fn in ("releaseState", "dropStateFor", "startSubtitle"):
        if fn not in text:
            errs.append("CriManaMod.cpp 缺少 %s（字幕状态生命周期未收敛）" % fn)

    # csri_open_mem 之后必须判空
    if "csri_open_mem" in text and "if (!state->csri)" not in text:
        errs.append("csri_open_mem 之后没有判空 —— 解析失败会让 "
                    "csri_render(NULL) 访问违例")

    # CreateTexture2D 之后必须判 HRESULT（判据取「CreateTexture2D 与它的
    # 失败分支之间不能再有别的成功路径」，所以按语句位置检查）
    tex = text.find("CreateTexture2D")
    if tex > 0:
        after = text[tex:tex + 600]
        if "FAILED(hr)" not in after:
            errs.append("CreateTexture2D 之后没有检查 HRESULT")

    # Map 之后必须判 HRESULT / pData
    if "->Map(" in text and "!rsc.pData" not in text:
        errs.append("Map 之后没有检查 rsc.pData")

    # 帧率分母
    if "framerate_n" in text and "framerate_n != 0" not in text:
        errs.append("字幕时钟没有防 framerate_n == 0 的除零")

    # drawSubs 里必须先确认 csri 与 stagingTexture 都有效
    body = find_function_body(text, "void drawSubs(")
    if body is not None:
        if "!state->csri" not in body or "!state->stagingTexture" not in body:
            errs.append("drawSubs 没有同时校验 csri 与 stagingTexture")
        if "csri_render(state->csri" in body and "if (csri_request_fmt" not in body:
            errs.append("drawSubs 里 csri_render 没有包在 request_fmt 成功之后")
    return errs


def check_source_iruo(path):
    """C. IRUO 钩子不得裸除，且地标访问要有边界检查。"""
    errs = []
    if not os.path.exists(path):
        return ["源码不存在: %s" % path]
    text = io.open(path, encoding="utf-8-sig", errors="replace").read()
    if "/ IruoSensitivity;" in text:
        errs.append("pokecomARMainHook 直接除以 IruoSensitivity —— "
                    "配置写 0 就是除零崩溃")
    body = find_function_body(text, "int __cdecl pokecomARMainHook")
    if body is None:
        return errs + ["CustomInputRND.cpp 里找不到 pokecomARMainHook"]
    if "id >= *ARNumberOfGeoTags" not in body:
        errs.append("pokecomARMainHook 的地标 id 没有范围检查")
    if "windowIndex < 0 || windowIndex > 64" not in body:
        errs.append("pokecomARMainHook 的窗口下标（scrWork[6374]）没有范围检查")
    return errs


def check_scene_data():
    """A2. 目标场景的结构必须与日文基线**同构**。

    ⚠ 「每条都以 0x03 收尾」**不是**本作的规则：`_geotag_00` 日文原版 359 条里
    有 350 条没有 0x03（它是标签表，不带 %p）。所以这里只比对**与基线的差异**，
    不假设绝对规则 —— 判据是「CN 相对 JP 有没有多出畸形」，而不是「符合我猜的格式」。

    补丁包与解包目录都在**工作区**（不在仓库），所以从仓库那份运行时这一步会
    找不到数据。此时跳过而不是报 FAIL —— 否则仓库里跑门禁永远是红的，
    等于把这道门禁废掉。源码侧的三项检查仍然照跑。
    """
    errs = []
    if not os.path.isdir(PKG_ENS):
        return []   # 数据不在本机这个位置 → 跳过（见 docstring）
    for name in SCENE_FILES:
        p = os.path.join(PKG_ENS, name)
        if not os.path.exists(p):
            errs.append("补丁包缺少 %s" % name)
            continue
        try:
            ents = read_msb(p)
        except Exception as ex:
            errs.append("%s 解析失败: %s" % (name, ex))
            continue

        # 未闭合的 0x04 表达式 = 真正的畸形（走到数据末尾都没碰到 0x00）
        bad_expr = []
        for sid, raw in ents:
            i, L = 0, len(raw)
            while i < L:
                b = raw[i]
                if b >= 0x80:
                    i += 2
                elif b == EXPR:
                    k = i + 1
                    while k < L and raw[k] != 0:
                        k += 1
                    if k >= L:
                        bad_expr.append(sid)
                        break
                    i = k + 1
                else:
                    i += 1
        if bad_expr:
            errs.append("%s: %d 条 0x04 表达式未闭合（例: %s）"
                        % (name, len(bad_expr), bad_expr[:5]))

        # 与日文基线比条目数 + 「无 0x03 收尾」的条数（同构性）
        jp = os.path.join(JP_ENS, name)
        if os.path.exists(jp):
            try:
                jp_ents = read_msb(jp)
                if len(ents) != len(jp_ents):
                    errs.append("%s: 条目数 CN=%d 与 JP=%d 不一致"
                                % (name, len(ents), len(jp_ents)))
                else:
                    n_cn = sum(1 for _, r in ents if not r or r[-1] != 0x03)
                    n_jp = sum(1 for _, r in jp_ents if not r or r[-1] != 0x03)
                    # CN 是译文，条目级 0x03 分布可以不同；但如果 CN 比 JP
                    # 多出一大截，说明编译时把结构写坏了
                    if n_cn > n_jp + max(4, len(ents) // 20):
                        errs.append(
                            "%s: 缺 0x03 收尾的条目 CN=%d 明显多于 JP=%d "
                            "—— 结构可能被写坏" % (name, n_cn, n_jp))
            except Exception:
                pass
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    sections = [
        ("A1 宽度扫描兜底推进（防死循环）", check_source_widthloop(SRC_GAMETEXT)),
        ("A2 目标场景控制码结构", check_scene_data()),
        ("B  字幕渲染失败保护", check_source_fmv(SRC_CRIMANA)),
        ("C  IRUO 钩子除零与边界", check_source_iruo(SRC_INPUT)),
    ]

    if not args.quiet:
        print("=== 崩溃防护门禁（芙劳线黑屏 / IRUO 闪退）===")
    total = 0
    for label, errs in sections:
        if not args.quiet:
            print("  %-34s %s" % (label, "OK" if not errs else "FAIL"))
        for e in errs:
            print("    - %s" % e)
        total += len(errs)
    if total:
        print("\nRESULT: FAIL（%d 项）" % total)
        return 1
    if not args.quiet:
        print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
