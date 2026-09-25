# 正文字体

| 文件 | 说明 |
|---|---|
| `NotoSansCJKsc-Regular.otf` | **补丁的正文字体**（思源黑体简中，15.7 MB）。所有界面文字用它光栅化 |

## 进补丁包时放两处

同一个文件在补丁包里出现**两次**（逐字节相同）：

| 补丁包内路径 | 用途 |
|---|---|
| `languagebarrier/fonts/` | 正文字体：`TextRendering` 用它烘焙全部字形（码表 4550 字符） |
| `languagebarrier/subs/fonts/` | 影片字幕：`patchdef.json → base.fmv.fonts` 点名的 9 个字体之一 |

## 来源

[Noto Sans CJK SC](https://github.com/notofonts/noto-cjk)（SIL Open Font License 1.1，
允许再分发；许可全文见 `subs/fonts/OFL-NotoSansSC.txt`）。

选它是因为**字形覆盖**：本项目码表 4550 字符（含 3930 个汉字 + 拉丁 + 希腊 +
假名 + 各种符号）要求字体能全部渲染。`TextRendering::Init()` 会逐个
`FT_Get_Char_Index` 过滤，字体渲染不出的字符直接不进字形表 —— 换字体前
必须确认覆盖率，否则那些字会**静默不显示**。

## 换字体时的检查

```bash
# 用 fontTools 核对新字体是否覆盖整个码表（本项目历史做法）
python -c "
from fontTools.ttLib import TTFont
import json, io
f = TTFont(r'新字体.otf')
cmap = set()
for t in f['cmap'].tables: cmap |= set(t.cmap.keys())
cs = json.load(io.open(r'补丁数据/运行时配置/patchdef.json', encoding='utf-8-sig'))['base']['charset']
miss = [c for c in set(cs) if ord(c) not in cmap]
print('码表 %d 字符，字体缺 %d 个' % (len(set(cs)), len(miss)))
print('缺失样例:', ''.join(miss[:40]))
"
```

⚠️ 换字体后**必须重烘字体种子**（`docs/字体种子.md`），因为字形位图变了。
