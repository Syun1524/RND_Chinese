# -*- coding: utf-8 -*-
"""mv_rnd_prologue 覆盖字幕生成器（单一数据源 → 三份产物）。

为什么需要三个版本：
  game  PlayRes 1920x1088 —— 游戏渲染面高度就是 1088（现有歌词字幕同规格），
        LB 把字幕画在 surface 210 上，尺寸取自 SurfaceWrapper::height。
  pr    PlayRes 1920x1080 —— PR 时间线是 1080。若直接拿 game 版进 PR，
        1088→1080 的 0.74% 垂直缩放会让底部元素偏 ~8px。
  srt   纯文本，PR 原生导入格式（PR 不解析 ASS 的 \\pos）。

排版参数全部来自本片画面实测（见每个常量后的注释），不引用外部来源。
运行：python build_prologue_subs.py          # 打印将写出的内容
     python build_prologue_subs.py --write  # 实际写出三份产物
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- 实测常量 -----------------------------------------------------------
GAME_H = 1088          # 游戏渲染面高（与 subs/*.ass 现有 PlayResY 一致）
VIDEO_H = 1080         # 视频实际高
S = VIDEO_H / GAME_H   # 1088 坐标 → 1080 坐标的换算系数 0.99265

QUOTE_LINES = ["很难说什么是不可能的，", "因为昨天的梦想", "就是今天的希望，与明天的现实。"]
# 行距 66：★ 原画整段有推近运镜，英文行距从 93px 一路收到 65px（逐帧实测）。
# 中文是静止层，取「用户截图那一帧（t≈6.0，英文 66px）」对齐。
# 位置：用户反馈「离原文太近、且可再往下一点」（2026-09-28 第二次调整）——
#   英文署名底(y≈659) 到中文首行顶，由原来的 ≈64px 拉到 ≈105px，整块下移 42px。
QUOTE_Y = [790, 856, 922]
QUOTE_FS = 54                 # 标定：渲染比 0.64，故中文墨高 ≈40px
SIGN_TEXT = "——罗伯特·H·戈达德"
# 署名：★ 原画署名紧跟引文块下方、右对齐到引文右缘。
# 用户反馈原先贴画面右下角「太角落」→ 上移到紧贴文本块；
# 随中文块下移 42px 后同步下移，保持与末行的相对间距。
SIGN_X, SIGN_Y = 1260, 1015
SIGN_FS = 38
# 标题卡：中文夹住原画英文两行（用户指定排版）。
# 原画英文在视频坐标里占 y460-490（小字）与 y514-562（主标题），
# 中文放其上/其下，四行形成「中-英-英-中」的对称块，行间视觉间隙 ≈25px。
TITLE_SUB = "科学ADV系列"
# 字号提到 48 后墨高变 30，底边随之下移；y 从 423 上移到 418，
# 使四行间隙仍统一在 25px（实测 20px → 调整后 25px）。
TITLE_SUB_Y = 418
# ★ 字号 48（原为 34）：实测 fs34 墨高仅 21px，原画小字是 30px，用户反馈「太小」。
# 按原画「小字/主标题 = 30/46」的比例，配主标题 74 应为 48（墨高 30）。
TITLE_SUB_FS = 48
TITLE_MAIN = "机器人笔记 DaSH"
TITLE_MAIN_Y = 615            # 1088 空间 → 视频 ≈610；与上方间隙对齐到 25px
TITLE_MAIN_FS = 74            # 对齐原画主标题 cap height 46px

# ---- 时间点 -------------------------------------------------------------
# 引文与署名：用户提供，已与画面实测核对
T_QUOTE = ("0:00:00.93", "0:00:06.33")   # 实测淡入 0.93→2.5、淡出 6.03→6.4
T_SIGN = ("0:00:01.03", "0:00:07.10")    # 单独一条，比引文晚出、晚收
# 标题卡两段：★ 逐帧实测（2026-09-28）。
# 测量法：文字蒙版内像素的「相对无字基准帧增量」求和 = 与 alpha 线性对应的能量；
# 再取 5%/95% 分位点作为起止。淡出段背景已纯黑，能量即文字亮度。
#   ★ 不要用「偏白像素计数」测淡出 —— 该判据在 alpha≈0.5 就归零，
#     会把淡出后半段整段漏掉（我第一版就是这么错的，导致"时间对不上"）。
#   上行：淡入 20.25→20.60；淡出 24.55→26.05
#   下行：淡入 20.55→21.30；淡出 25.55→27.55（比上行晚 1.0s 起，更长）
# ★ 两行是「重叠」淡出，不是先后接替 —— 实测上行淡出期间下行仍在，
#   下行从 25.55 才开始降。别按"第一阶段/第二阶段"去设。
T_SUB = ("0:00:20.25", "0:00:26.05")     # 上行：\fad(350, 1500)
T_MAIN = ("0:00:20.55", "0:00:27.55")    # 下行：\fad(750, 2000)
FAD_QUOTE = "fad(1500,400)"
FAD_SIGN = "fad(1300,600)"
FAD_SUB = "fad(350,1500)"
FAD_MAIN = "fad(750,2000)"

HEADER = """[Script Info]
; ROBOTICS;NOTES DaSH — mv_rnd_prologue（movie.cpk ID 51）简体中文覆盖字幕
; 本文件由 build_prologue_subs.py 生成，勿手改（改脚本后重跑）。
; 排版依据（均取自本片画面逐帧实测）：
;   引文三行居中，行距 {qgap}px（原画英文行距随推近从 93 收到 65，取用户截图帧的 66）
;   引文字号 {qfs}（渲染比 0.64，故中文墨高约 35px）
;   署名紧跟引文块下方、右缘对齐中文块右缘（原画署名即紧贴引文，不沉到画面角落）
;   标题卡两行居中；主标题字号 {mfs} 对齐原画 cap height 46px
; 可读性：明亮背景段用半透明柔边描边（非实心黑框），避免"贴纸感"
; 时间点：引文 {tq0}~{tq1}、署名 {ts0}~{ts1}、上行 {tb0}~{tb1}、下行 {tm0}~{tm1}
; 淡入淡出：原画是普通统一 alpha 渐变（非擦除/遮挡，已用「暗底先显、亮底后显」
;   的对比度差异证实），故用 \\fad 精确复刻。
"""

STYLES = """[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Quote,RND Serif SC,{qfs},&H00FFFFFF,&H000000FF,&H96000000,&H00000000,0,0,0,0,100,100,1,0,1,3,0,5,40,40,40,1
Style: Signature,RND Serif SC,{sfs},&H00FFFFFF,&H000000FF,&H96000000,&H00000000,0,0,0,0,100,100,1,0,1,3,0,3,40,78,40,1
Style: TitleSub,RND Title SC,{tfs},&H00FFFFFF,&H000000FF,&H8C000000,&H00000000,0,0,0,0,100,100,2,0,1,3,0,5,40,40,40,1
Style: TitleMain,RND Title SC,{mfs},&H00FFFFFF,&H000000FF,&H8C000000,&H00000000,0,0,0,0,100,100,3,0,1,3,0,5,40,40,40,1
"""


def build_ass(play_res_y):
    """生成一份 .ass。y 坐标按 play_res_y 缩放（x 恒为 1920，不缩放）。"""
    k = play_res_y / GAME_H

    def y(v):
        return int(round(v * k))

    out = [HEADER.format(qfs=QUOTE_FS, qgap=QUOTE_Y[1] - QUOTE_Y[0], mfs=TITLE_MAIN_FS,
                         tq0=T_QUOTE[0], tq1=T_QUOTE[1], ts0=T_SIGN[0], ts1=T_SIGN[1],
                         tb0=T_SUB[0], tb1=T_SUB[1], tm0=T_MAIN[0], tm1=T_MAIN[1])]
    out.append("ScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
               "YCbCr Matrix: TV.601\nPlayResX: 1920\nPlayResY: %d\n\n" % play_res_y)
    out.append(STYLES.format(qfs=QUOTE_FS, sfs=SIGN_FS, tfs=TITLE_SUB_FS, mfs=TITLE_MAIN_FS))
    out.append("\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
               "MarginV, Effect, Text\n")
    for text, yy in zip(QUOTE_LINES, QUOTE_Y):
        out.append("Dialogue: 0,%s,%s,Quote,,0,0,0,,{\\pos(960,%d)\\%s\\blur1}%s\n"
                   % (T_QUOTE[0], T_QUOTE[1], y(yy), FAD_QUOTE, text))
    out.append("Dialogue: 0,%s,%s,Signature,,0,0,0,,{\\an3\\pos(%d,%d)\\%s\\blur1}%s\n"
               % (T_SIGN[0], T_SIGN[1], SIGN_X, y(SIGN_Y), FAD_SIGN, SIGN_TEXT))
    out.append("Dialogue: 0,%s,%s,TitleSub,,0,0,0,,{\\pos(960,%d)\\%s\\blur1}%s\n"
               % (T_SUB[0], T_SUB[1], y(TITLE_SUB_Y), FAD_SUB, TITLE_SUB))
    out.append("Dialogue: 0,%s,%s,TitleMain,,0,0,0,,{\\pos(960,%d)\\%s\\blur1}%s\n"
               % (T_MAIN[0], T_MAIN[1], y(TITLE_MAIN_Y), FAD_MAIN, TITLE_MAIN))
    return "".join(out)


def build_srt():
    """PR 原生导入用。SRT 无定位信息，位置由 PR 里手工设定（见 PR 操作说明）。"""
    cues = [
        (T_QUOTE[0], T_QUOTE[1], "\n".join(QUOTE_LINES)),
        (T_SIGN[0], T_SIGN[1], SIGN_TEXT),
        (T_SUB[0], T_SUB[1], TITLE_SUB),
        (T_MAIN[0], T_MAIN[1], TITLE_MAIN),
    ]

    def ms(t):
        h, m, rest = t.split(":")
        s, cs = rest.split(".")
        return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(cs) * 10

    def ts(v):
        h, rem = divmod(v, 3600000)
        m, rem = divmod(rem, 60000)
        s, msec = divmod(rem, 1000)
        return "%02d:%02d:%02d,%03d" % (h, m, s, msec)

    parts = []
    for i, (a, b, text) in enumerate(cues, 1):
        parts.append("%d\n%s --> %s\n%s\n\n" % (i, ts(ms(a)), ts(ms(b)), text))
    return "".join(parts)


def main():
    write = "--write" in sys.argv
    ass_game = build_ass(GAME_H)
    ass_pr = build_ass(VIDEO_H)
    srt = build_srt()

    targets = [
        ("mv_rnd_prologue.ass", ass_game, "utf-8", "\n"),
        ("mv_rnd_prologue_pr1080.ass", ass_pr, "utf-8", "\n"),
        ("mv_rnd_prologue.srt", srt, "utf-8-sig", "\r\n"),   # PR 认 BOM
    ]
    for name, content, enc, nl in targets:
        path = os.path.join(HERE, name)
        if write:
            io.open(path, "w", encoding=enc, newline=nl).write(content)
            print("wrote %-32s %5d bytes" % (name, os.path.getsize(path)))
        else:
            print("--- %s (%d bytes) ---" % (name, len(content.encode(enc))))
            print(content[:400])
    if not write:
        print("\n(dry run — 加 --write 才写文件)")


if __name__ == "__main__":
    main()
