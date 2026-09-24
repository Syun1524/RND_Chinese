# 交接文档 — RND 简体中文补丁（字体/文本渲染方向）

> 最后更新：2026-09-11
> 本文件面向"接手继续开发"的人（包括未来的自己），目标是**不必重新推导已查明的结论**。

---

## 0. 一分钟速览

| 项 | 内容 |
|---|---|
| 项目 | ROBOTICS;NOTES DaSH 简体中文补丁 |
| 基础 | Committee of Zero (CoZ) 的英文优化补丁（LanguageBarrier 运行时） |
| 仓库 | `D:\DATA\tran\agent tran\GitHub\RND_Chinese` |
| 远程 | `https://github.com/Syun1524/RND_Chinese.git`（origin，无 upstream） |
| 分支 | `main` |
| 游戏目录 | `D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH` |
| 已修 | 5 项（4 代码级 + 1 数据级），均已在游戏内验证 |
| 待修 | 无（数字 `9` 已修，见 §5） |
| 待评估 | 来电人名无滚动动效（见 §6，属 CoZ 功能缺失，非 bug） |

---

## 1. 目录与关键路径

```
仓库 D:\DATA\tran\agent tran\GitHub\RND_Chinese\
├── LanguageBarrier_rndchs\LanguageBarrier\      ← C++ 源码（改了 4 个文件）
│   ├── GameText.cpp / GameText.h                ← ruby 撞码修复
│   ├── TextRendering.cpp / TextRendering.h      ← 缓存指纹校验
│   └── dinput8-Release\dinput8.dll              ← 编译产物（发布必需）
├── sc3tools_rndchs\                             ← CN 字符集提取/回写工具
│   ├── resources\rnd\charset.utf8               ← CN 字符表（必须与运行时一致）
│   └── target\release\sc3tools.exe              ← 发布必需
├── sc3tools_jp\                                 ← JP 字符集工具（合作者 Kurashift 添加）
├── docs\                                        ← 本目录（修复记录 + 本文档）
└── .gitignore                                   ← 排除构建产物

游戏目录 D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH\
├── NOTES DaSH\dinput8.dll                       ← 实际生效的补丁 DLL（注意在子目录！）
├── languagebarrier\
│   ├── patchdef.json                            ← 运行时配置（字符表/字体/重定向）
│   ├── enscript\*.msb                           ← 译文（323 个）
│   ├── fonts\                                   ← 字体 + 烘焙缓存
│   ├── c0data\                                  ← 烤字图集（UI）
│   ├── subs\                                    ← 影片字幕 ASS
│   └── log.txt                                  ← 运行日志
└── languagebarrier\enscript_backup_swap_*\      ← 字符集搬运前的 msb 全量备份
```

工作区（非仓库）：
```
D:\DATA\tran\agent tran\9.6文本外工作\
├── 临时\                                        ← 排查脚本、备份（可清理）
│   └── swap_charset_slot.py                     ← 字符位交换工具（见 §7）
├── RND补丁汉化隔壁成品\                          ← 隔壁方案（CHDTevior/RNDash_CN）
└── RND补丁汉化隔壁的源代码\                      ← 隔壁的脚本与术语表（有参考价值）
```

---

## 2. 构建环境与命令

| 项 | 值 |
|---|---|
| 编译器 | MSBuild（VS2022 安装目录 `C:\VS2022BT`） |
| 工具集 | **v142（VS2019）**，需 14.29 版本 |
| **配置名** | **`dinput8-Release`**（注意：不是 `Release`！） |
| 平台 | `Win32`（x86） |

**编译 DLL**：
```bash
cd "D:/DATA/tran/agent tran/GitHub/RND_Chinese/LanguageBarrier_rndchs/LanguageBarrier"
MSYS_NO_PATHCONV=1 "C:/VS2022BT/MSBuild/Current/Bin/MSBuild.exe" \
  LanguageBarrier.vcxproj -p:Configuration=dinput8-Release -p:Platform=Win32 \
  -v:minimal -nologo
# 产物: dinput8-Release/dinput8.dll
# 部署: 复制到 游戏目录/NOTES DaSH/dinput8.dll
```
> Git Bash 下必须加 `MSYS_NO_PATHCONV=1`，否则 `/p:` 会被路径转换。

**编译 sc3tools（改了字符集后必须重编！）**：
```bash
cd "D:/DATA/tran/agent tran/GitHub/RND_Chinese/sc3tools_rndchs"
cargo build --release --offline
```
> ⚠️ 该工具用 `rust-embed` **编译期嵌入**字符集。只改 `resources/rnd/charset.utf8`
> 而不重编 = 工具仍是旧字符表 → 与运行时不一致 → 乱码。

---

## 3. 已完成的工作（已验证）

详细内容见 `docs/CHANGES-字体与文本渲染修复.md` 与 `docs/CHANGES-运行时数据与配置.md`。
此处只列摘要：

### 3.1 代码级

| # | 问题 | 根因 | 状态 |
|---|---|---|---|
| 1 | `A`/`8`/`9` 静默消失（如 `PHASE NAE`→`PHSE NE`） | 见 §5：本分支自行加入的 `0x80 0x09/0A/0B` 判断把字形对误当 ruby 标记吞掉 | ✅ 已修（见 §5） |
| 2 | 改字符集后旧字体缓存不失效 | `loadCache()` 只校验语言不校验字符集 | ✅ 已修（加 `charsetHash` 指纹） |
| 3 | 缓存撕裂（修复 2 的回归） | DDS 缺失时残留索引；saveCache 未删图集 | ✅ 已修 |
| 4 | 数字 `9` 不显示 | 同上：`0x80 0x0A` 被无条件当 ruby 标记 | ✅ 已修（`RUBY_MARKERS_ENABLED` 默认关，见 §5） |

修复 1+4 的具体做法：把 3.1 里本分支自行加入的 ruby 判断彻底关掉——
配置项 `patch.rubyMarkers`（默认 **false**），三处判断
（`GameText.cpp:1422 / 2594 / 2773`）加条件
`(RUBY_MARKERS_ENABLED && (sc3string[1] == 10 || insideRubyText))`。
默认下该分支永不触发，`0x80 0x09/0x0A/0x0B` 一律按普通字形渲染，
`8`/`9`/`A`（尤其数字 9）恢复正常。详见 §5 根因。

### 3.2 数据级

| 项 | 内容 |
|---|---|
| 字体更换 | `noto.ttc`(JP) → **`NotoSansCJKsc-Regular.otf`**（简中黑体，SIL OFL 可分发） |
| 高位字形搬运 | 索引 ≥4096 的 336 个字搬入低位空槽（见 §4），重映射 7389 处 msb 引用 |
| 缓存清理 | 多次（换字体/改字符集后必须清，见 §8） |
| sc3tools 重编 | 字符集变更后重编，并用官方工具验证提取正确 |

### 3.3 仓库整理

- 新增 `.gitignore`（排除构建产物，保留发布必需的 dll/exe）
- 移除误提交的构建产物共 **932 个**（CN 466 + JP 466）
- 提交：`e34114b`（修复）、`018739f`、`3719b06`（清理），均已推送

**安全点（可回档）**：
```
分支: backup-before-cleanup / backup-before-jp-cleanup
tag : cleanup-safe-20260909_025921 / cleanup-jp-20260909_030957
```
回档示例：`git reset --hard 727cfd7`（推送前）或 `git reset --hard backup-before-cleanup`

---

## 4. 关键机制：4096 分界线（重要！）

**游戏原生字体系统只支持 4096 个字形槽位。**

- 原版 CoZ RND 字符集 = **4096** 项
- 本补丁扩展后 = **4499** 项（多 403 个）
- 索引 ≥4096 的字形：
  - **对话**（LB 接管绘制）→ 正常显示
  - **口袋电脑/存档/TIPS 等**（游戏原生绘制）→ **静默消失**（零宽度空精灵）

这就是「汐」在对话正常、在口袋电脑消失的原因。

**已做的修复**：把"索引 ≥4096 且被 msb 使用"的 336 个字搬入**低位空槽**。
- 工具：`临时/swap_charset_slot.py --pairs a:b,c:d --apply`
- 必须同步更新三处：`patchdef.json` 的 charset、`sc3tools_rndchs/.../charset.utf8`、所有 msb 引用
- 搬运后必须清字体缓存

**⚠️ 遗留缺陷**：该工具用"**交换**"而非"单向移动"，会把低位原有的字符换到高位。
已确认目前**无害**（被换上去的字符如 `*` `+` `$` `"` 在 msb 中实际使用 0 次），
但若将来新增文本用到这些符号，它们会消失。**建议改进为单向移动**。

**当前状态**：msb 中使用的 3986 个字符，**全部在 4096 以下**（已校验）。

---

## 5. 【已修】数字 `9` 不显示

### 现象
TIPS 等界面里所有数字 `9` 消失（如 `2010年9月11日` → `2010年 月11日`）。

### 根因（2026-09-11 更正）
原文档把根因写反了。真正的机制是 **控制码与字形在不同字节宽度上，根本不冲突**：

| 类型 | 编码 | 说明 |
|---|---|---|
| 单字节控制码 | `09` / `0A` / `0B` | ruby 基/注音起/注音止，**只有 1 字节** |
| 两字节字形 | `80 09` / `80 0A` / `80 0B` | 字符集索引 9/10/11 = `8`/`9`/`A`，**高字节含 0x80** |

即 SC3 流里：低字节（<0x80）= 控制码；高字节带 0x80 = 字形两字节。
ruby 是单字节 `0A`，数字 `9` 是两字节 `80 0A` —— **二者可区分**。

**Bug 来源**：本分支（CN fork）在 `semiTokeniseSc3String` / `processSc3TokenList` /
`getSc3StringDisplayWidthHook` 三处**自行加入了** `0x80 && 0x09..0x0B` 的判断，
把**字形对** `80 09/0A/0B` 误当 ruby 标记吞掉。上游 CoZ（`LanguageBarrier_original`）
这三处**没有该判断**，所以英文版数字 9 正常。该判断是 CN 分支引入的回归。

### 实测数据（2026-09-11，权威 tokenizer + sc3tools 交叉验证）
```
两字节字形 80 09/0A/0B : 349 / 460 / 5785 处（= '8'/'9'/'A' 字面字）
单字节 ruby 三元组 09..0A..0B: 97 处（真注音，全部单字节）
```
真 ruby 存在（`vc_*.msb` 等），但都是**单字节** `0A`，从未被那个两字节判断匹配到；
被吞的全是字形 `80 0A`。故修数字 9 **不会**影响任何真 ruby。

### 修复（已实施）
- 配置项改名 `safeRubyMarkers` → `patch.rubyMarkers`，默认 **false**
  （`GameText.cpp:623`；`GameText.h` 注释同步更正）。
- 三处判断改为 `(RUBY_MARKERS_ENABLED && (sc3string[1] == 10 || insideRubyText))`
  —— 默认下永不触发，`80 09/0A/0B` 一律当普通字形。
- 等价于**恢复上游 CoZ 行为**：真 ruby 交回游戏原生渲染（上游即如此）。
- DLL 已重建并部署到 CN 运行时（Steam 安装 `NOTES DaSH\dinput8.dll`，留 `.bak_prev_*`）。
- 提交：`0e751ce`。

> 早先设想的「方案 A 搬字符槽」不再需要：问题不在字符槽，而在多出来的那个判断。
> `swap_charset_slot.py` 也未再使用于本问题。

### 验证
- 离线：权威 tokenizer 确认字形/控制码可区分；真 ruby 全为单字节。
- 构建：MSBuild `dinput8-Release/Win32` 通过，产物 md5 `2e136742b7c84a63095e756d231d0dbb`。
- **待实机确认**：TIPS/日期中的 `9` 与 `vc_*` 对话里的真注音各走一遍。

---

## 6. 【待评估】来电人名无滚动动效

### 现象
口袋电脑主屏左上角来电人名，原版是滚动文字，汉化后"像图片粘在那"。

### 已查明
- **LB 源码中没有任何滚动/逐字动画实现**（已全量搜索）
- `sghdDrawInteractiveMailHook`（`GameText.cpp:2834`）**一次性画完所有字符**：
  ```cpp
  for (int i = 0; i < str.length; i++) gameExeDrawGlyph(...);
  ```
- 该 hook 替换了游戏原生绘制函数（`GameText.cpp:986`），但**未复刻动画**
- hook 签名含 `lineSkipCount` / `lineDisplayCount`，疑为原版滚动参数，但 LB 把它们当作
  "行数范围"使用而非动画偏移

### 结论
**这是 CoZ 补丁的功能缺失**（优先保证文字显示，动画未移植），非 bug，也不是本次改动造成的。

### 若要恢复
需要逆向定位"当前滚动位置"变量（可能在 ScrWork 或全局），再在 hook 内按时间计算偏移。
工作量大、有风险，建议**优先级低于 §5**。

---

## 7. 工具用法

### sc3tools（官方提取/回写）
```bash
# 提取（CN 文本用 rndchs 工具）
sc3tools_rndchs/target/release/sc3tools.exe extract-text <file.msb> rnd
#   → 输出到 txt/<file>.msb.txt

# 回写
sc3tools_rndchs/target/release/sc3tools.exe replace-text <file.txt> rnd
```

> ⚠️ **CN 与 JP 工具不可混用**：
> - `sc3tools_rndchs` = CN 字符集（4499 项）→ 处理**译文**
> - `sc3tools_jp` = JP 字符集（3020 项）→ 处理**日文原文提取**
> 混用会导致字符表不匹配 → 乱码。

### 字符位交换工具（自研，慎用）
```bash
python 临时/swap_charset_slot.py --pairs 4202:92            # 空跑预览
python 临时/swap_charset_slot.py --pairs 4202:92 --apply    # 落盘
```
自动备份 patchdef / charset.utf8 / 全部 msb 到 `enscript_backup_swap_<时间戳>/`。

**已知限制**：无差别重写 msb 引用；不涉及 0x0A 歧义（该歧义已证不存在，见 §5）。

### msb 格式（自研脚本解析用）
```
0x00: b'MES\0'
0x04: u32, 0x08: u32          （未用）
0x0C: u32  idx_end            （索引区结束位置）
0x10: 索引区起点，每项 8 字节 (u32 id, u32 offset)
idx_end + offset              （字符串数据地址）
```
字形流：
- 字形 = 2 字节 `(0x80|(id>>8)), (id&0xFF)`，**低字节可以 < 0x80**（易踩坑）
- `0x03` = 1 字节控制码（cnscript 显示为 `[%p]`）
- `0xFF` = 字符串结束
- 其余 `<0x80` 为控制码（长度依命令而定，`0x04` 为 2 字节）

> **踩坑记录**：若把低字节 `<0x80` 误判为控制码并只跳 1 字节，会导致整串错位，
> 产生大量**虚假的"越界字形 id"**。排查期间因此多次误判，务必用 2 字节对齐解析。

---

## 8. 字体缓存规则（必须遵守）

1. **换字体 / 改字符集后必须清缓存**：
   ```
   删除 languagebarrier/fonts/ 下：
     font_*.dds  outline_*.dds  fontData.bin
   ```
   （`charsetHash` 只覆盖字符集，**不含字体路径**，换字体不会自动失效）

2. **多进界面才能烤全字号**：LB 只在游戏实际用到某字号时才烘焙。
   已观测字号：16 18 24 25 27 28 30 31 32 34 36 37 39 40 42 43 45 46 48 56 61 63
   （56/61 来自 `BacklogTextSize[...] * 1.5f` 等动态计算，属正常）

3. **必须正常退出游戏**：`saveCache()` 在 `closeAllSystemsHook` 里调用；
   强杀进程会导致本次烘焙丢失（曾出现 `fontData.bin` 缺失）。

4. 首次启动较慢属正常（重新烘焙）。

---

## 9. 发布前检查清单

- [ ] **字体**：打包 `NotoSansCJKsc-Regular.otf`（SIL OFL，可分发）
      —— **不要**打包 `simhei.ttf`（Windows 系统字体）或 `noto.ttc`（日文且非必需）
- [ ] **不要预置字体缓存**（`font_*.dds` / `fontData.bin`），让用户本地生成，
      可从机制上避免"生成时字符集 ≠ 运行时字符集"
- [ ] **保留 CoZ 许可**：`LICENSE`、`THIRDPARTY.LB.txt`
- [ ] **标注游戏版本**：DLL 内含 `SigScan` 特征码，硬编码游戏 exe 版本；
      Steam 更新后可能失效
- [ ] **标注分支来源**：基于 CoZ LanguageBarrier，注明本分支修改内容
- [x] §5 的 `9` 问题已修（`RUBY_MARKERS_ENABLED` 默认关，提交 `0e751ce`）
- [ ] 实机回归：对话、口袋电脑、存档读档、TIPS、邮件、地图各走一遍
      （重点：TIPS/日期中的 `9`，以及 `vc_*` 对话中的真注音）

---

## 10. 已知未修 / 待观察

| # | 问题 | 状态 |
|---|---|---|
| 1 | 数字 `9` 不显示 | ✅ **已修**（`RUBY_MARKERS_ENABLED` 默认关，提交 `0e751ce`；待实机回归） |
| 2 | 来电人名无滚动动效 | CoZ 功能缺失，非 bug（§6） |
| 3 | 30 个 PUA 图标字（U+E001–E01E）不显示 | 字体无此字形，被过滤。隔壁方案用 1044 个 PUA 槽参考 `Build-RNDZhNativeMapFont.ps1` |
| 4 | 偶发 Runtime Error 崩溃 | ✅ **根因已定位并修复**（2026-09-11）：码表有、字体无字形的字符被排除出 `glyphMap`，`getGlyphInfo` 的 `map::at` 命中即抛异常。见 §12.1 |
| 5 | 离线扫描仍报约 980 处"越界字形" | 大概率是扫描器对控制码长度处理不准的假象；其中 344 处集中在废弃文件 `rnd_01_01_00-.msb`（patchdef/gamedef 中零引用） |

---

## 11. 排查经验（避免重复踩坑）

1. **不要用视觉判断字符集问题** —— 用脚本解码 msb 看实际字节。多次因"看起来像"而误判。
2. **解析 msb 必须 2 字节严格对齐**，低字节可 `<0x80`。否则产生大量虚假越界。
3. **区分"数据问题"与"渲染问题"**：若同一字符在对话正常、某界面消失，
   先怀疑**渲染路径差异**（LB 接管 vs 游戏原生），而非字体数据。
4. **离线渲染验证**：用游戏真实 `fontData.bin` + DDS 图集离线拼出字符串图像，
   可确认数据链路是否健康，快速缩小范围。
5. **改字符集是"换门牌号"**：msb 存的是索引不是字符，所以必须同步重写 msb 引用。

---

## 12. 2026-09-11 追加（本轮新增结论）

### 12.1 字体兜底：偶发崩溃已定位（提交 `c45dcb9`）

**根因**：`forceIncludeHan=true` 只让"字体里有字形"的字进图集；**码表里有、字体里没有**的字
（实测 **31 个**：U+02DC 与 30 个 PUA）仍被排除出 `glyphMap`。而 `FontData::getGlyphInfo()`
用 `std::map::at()` 取值 —— 命中即抛 `std::out_of_range`，**抛在游戏渲染线程 = 崩溃**。

**实测**：31 个缺字形字符中，被**活跃 msb 引用**的只有 `U+02DC '˜'`，共 **8 次**
（`_twipo_00.msb` 4 条帖子的颜文字 `((((;゜Д゜))))˜˜发抖发抖`）。这就是 §10 #4 的病因。

**修复**：`getGlyphInfo` 改 `find()` + `missingGlyph` 兜底（`width=0`，画出来为空）；
新增 `getCharForGlyphId()` 把越界 id 映射为空格。取自已存在于本机备份仓库
（CoZ upstream）工作区中一份**未提交**的修法。**已部署实机**。

> 该修复能覆盖**任何**未来的缺字（换字体/改码表/新译文），是通用安全网。

### 12.2 波浪号 `˜` → `～`（提交 `e060c52`）

`U+02DC` 不在 `NotoSansCJKsc` 字形集中。已把 `_twipo_00.msb` 那 8 处改用码表内已有的
**全角波浪 `U+FF5E`（索引 228）**，字形存在、视觉等价。同步改了 `cnscript` 译稿源。
> 教训：`cnscript`（译稿）与 `charset.utf8` 必须能对上；译文用到"码表不含"或"字体不含"的字都会出问题。

### 12.3 `redoDialogueWordwrap` 必须保持 `false`

关掉的是 CoZ 自己重写的换行（英文思维：按"单词"断行）。中文下**必须关**：
`DialogueWordwrap.cpp` 的 `is_letter(c) = c<0x8000 && 非标点` 把连续汉字当成**一个词**
（实测一句话被切成最长 15 字的不可断块），导致长句无法换行。
- 代价：`type1Punctuation` / `type2Punctuation` 两串配置**失活**（仅在该开关为 true 时读取）。
- 若日后要"数字/英文不断行"，需改 C++ 让 `next_word` 对 CJK 按单字断，属独立小工程。

### 12.4 `appdatadir` 空值 = 启动器开关失效（⚠ 发布前必改）

- CoZ 原值 `Committee of Zero\RNDSteam`；**当前 CN 实机值是空串** → LB 读 `%LOCALAPPDATA%\config.json`
- 而 `LauncherC0.exe` 写的是 `%LOCALAPPDATA%\Committee of Zero\RNDSteam\config.json` → **两者不通**
- 后果：**启动器里所有开关（泳装/鼠标/卡拉OK…）对 CN 补丁无效**
- 修复：把 `patchdef.json` 的 `appdatadir` 设回 `Committee of Zero\RNDSteam`，
  或自研启动器读写自己的目录。详见 `docs/打包清单.md` §4.3。

### 12.5 白烤 ≠ 崩溃源

实测各字号**无字形溢出**（size63 格 83px，最大墨迹 65px）；代码里 4 处
`if (rows>cellSize||width>cellSize) { }` 的空块**上游 CoZ 原本就是空的**，非本分支删改。

### 12.6 码表精简：只有 284 字可安全移除

714 个未使用索引中，再排除"`cnscript` 里有用到"的，只剩 **284 个**可安全中和
（图集 69 行 → 65 行，省 6.5%，约 417MB → 390MB）。需三处同步 + 全量重烤，**建议出正式包再做**。
> 注意：不能按"未使用"直接删——删掉 `cnscript` 用到的字，`sc3tools` 重建会报 `CharNotInCharset`。

### 12.7 其他工具经验

- `sc3tools` 的 `extract-text` 默认会把**全角标点改半角**；往返前务必加 **`--preserve-fullwidth`**，
  否则往返会失真（实测 `，`→`,`）。加了才是逐字节可控。
- 仓库内 sc3tools 基线比上游旧（上游已改 JSON 驱动 gamedef），**不要直接 pull 上游**。

### 12.8 相关文档

- `docs/打包清单.md` —— 自研安装包的**包体清单**（含必须排除项、配置项、泳装模式）
- `docs/补丁说明.md` —— 面向玩家的补丁说明（替换 CoZ 英文 `RNDPatch-README.txt`）

## 13. 2026-09-11 追加（换装核对体系）

要弄清"哪个变体是哪套服装"。游戏把每套服装存成独立 `.lkm`，但**文件名/内容里没有服装名**。

### 13.1 已排除的名称来源（不要再重复查）

| 来源 | 结论 |
|---|---|
| `.lkm` 二进制 | 网格 + 内嵌贴图，无名称串 |
| `.scx` 脚本 | 压缩，全文无 `c0NN_MMM` 引用 |
| `.lka` 动作 | 只有动画名（`stand`/`walk_loop`） |
| 游戏文本 | 只有通用词汇（水着/体操服/ブルマ/メイド/猫耳/浴衣） |
| `_system_00.msb` | **游戏根本没有换装菜单** —— 这正是 CoZ 用 fileIdRemap 硬改的原因 |
| CoZ 原版 | `swimsuitPatch` 只点名 10 个泳装模型，无描述 |
| 邻接补丁 glossary | 只有泛化术语，无按模型映射 |
| **`.lkm` 内嵌贴图** | **可解出，是唯一可行的离线线索**（见 13.3） |

### 13.2 已确认的 10 套（CoZ 泳装，100% 可信）

CoZ 把泳装模型作为**新文件**放进 c0data，`c0data.cls` 里的文件名与
`settings.swimsuitPatch.setters.fileRedirection.model` 的目标索引一一对应：

| 角色 | 变体 | fileId | 角色 | 变体 | fileId |
|---|---|---|---|---|---|
| c001 | 070 | 469 | c006 | 090 | 509 |
| c002 | 100 | 474 | c008 | 030 | 512 |
| c003 | 090 | 485 | c012 | 020 | 518 |
| c004 | 120 | 496 | c017 | 040 | 524 |
| c005 | 080 | 502 | c019 | 020 | 531 |

规模：**19 角色 / 69 套**（多变体角色 11 个共 61 套需核对，其中 10 套已确认）。
69 套两两 md5 全不同，无重复可合并。

### 13.3 `.lkm` 内嵌贴图（离线认服装的关键）

每个 `.lkm` 是分块容器，内嵌若干 DDS：

```
<uint32 大小> "DDS " <124 字节头> <压缩像素>
```
`大小` 从 `"DDS "` 起算（= 128 + 像素数据）。实测 2048×2048 DXT1 = 0x00200080 = 2097280 字节。
Pillow 可直接 `Image.open(BytesIO(blob))` 解出。

**关键坑**：贴图**槽位顺序跨变体不稳定**（c004_070 把脸部贴图排最前，c004_010 排最后），
所以必须**按内容哈希匹配**，不能按索引。按哈希统计后发现：
每个变体只有 **3~10 张贴图是它独有的**（其余十几张是全变体共用的脸/眼睛/身体），
**那些独有贴图就是服装本体** —— 这是离线辨认的可行路径。

### 13.4 核对机制：每角色一个 bool（不改 LB 源码）

`Config.cpp` 的 `bool`/`choice` 两种类型都会把 payload **深合并**进 `config["patch"]`
（Config.cpp:39-55），所以整件事 **LanguageBarrier 零改动**。
实现用**每个角色×变体一个 bool**：

```
"zz_c002_100": { "type": "bool", "setters": { "fileIdRemap": { "model": {
    "470":474, "471":474, ..., "474":474 } } }
```

**为什么不是单个 choice**：`choice` 一次只能表达一个键（一个选择 = 一个角色的重定向），
而核对需要**同时固定多个角色**（一次进游戏看多个，把 61 次启动压到十几次）。
bool 方案只把选中的键写进 config.json，任意多个角色可同时生效。

两条**必须遵守**的约束（都会**静默失效**）：

1. **每个变体都要映射，包括目标自身**。`swimsuitPatch` 把该角色每个变体（含目标本身）
   都指向泳装，而 `json_merge` 是**递归覆盖、删不掉键** —— 漏掉自身映射的那套会被覆盖回泳装。
2. **键名必须以 `zz_` 开头**（settings 按 std::map = 字典序迭代，保证排在 `swimsuitPatch`
   之后 → 核对胜出）。改成排在前面的名字会先合并、再被泳装覆盖。

`fileIdRemap` 由 `mgsFileOpenHook` **无条件**读取（Game.cpp:748-768），命中即 `return`
（不会落到 `fileRedirection`），所以**核对不依赖泳装模式**：开着时其它角色是泳装，
关着时其它角色是原版默认服，两种都能核对。

（早期版本用单个 `choice` `zzOutfitOverride`，一次只能核对一个角色，已被 bool 方案取代；
`add_outfit_choices.py` 会自动清掉该残留键。）

### 13.6 工具与素材

```
scripts/build_outfit_diff_sheets.py   # ★ 服装对比_<角色>.png：只显示独有贴图 + 填名栏
scripts/build_outfit_sheets.py        # 单套图 + 横排对照 + 分变体 index.html
scripts/add_outfit_choices.py         # 生成 patchdef 的 61 个核对项（--names 可带中文名）
scripts/gen_outfit_table.py           # 生成 tools/outfit_table.h
tools/RNDZhLauncher.cpp               # 玩家启动器源码
tools/RNDZhOutfitTool.cpp             # 核对工具源码
docs/服装核对.md                       # 核对手册（给使用者看）
docs/服装映射表.json                   # 角色 → 变体 → fileId
```

待办：51 套待认名 → 填 `服装名称表.json` → 回填 tooltip/启动器显示名。

### 13.7 构建注意

`launcher/build_launcher.bat` 与 `build_outfit_tool.bat` 内的注释**必须保持 ASCII** ——
cmd 按 OEM 代码页解析 REM 行，非 ASCII 会被截断成乱码命令（实测 `'DI+锛屼笉渚濊禆' 不是
内部或外部命令`）。


## 14. 2026-09-12 追加：目录名含分号导致补丁静默失效（已修复）

### 14.1 症状与根因

补丁文件全部就位，游戏却显示原版语言（日/英），`languagebarrier/log.txt` 从不生成。
不崩溃、不报错 —— 完全静默。

**根因（本日定死）**：目录名含分号 `;` 时，Windows 加载器把目录路径**按 `;` 切开**，
把分号后面每一段当成**相对目录名**（相对游戏目录）再搜一遍。本地 `dinput8.dll`
只有在那个子目录存在、且里面放了 DLL 时才会被加载。

实测（`scripts/diagnostics/predict_mechanism.py`，三条可证伪预测全部命中）：

| 目录名 | 分号后的片段 | 片段子目录 | 实际加载的 dinput8 |
|---|---|---|---|
| `RNDt` | （无） | — | 本地 ✓ |
| `RND;t` | `t` | 不存在 | 系统 ✗ |
| `RND;t` + 建了 `t\` 放 DLL | `t` | 存在 | 本地 ✓ |
| `RND;A1;B2` + 只建 `B2\` | `A1`/`B2` | `B2` 存在 | 本地 ✓（任一片段命中即可） |

**长度和中文都不是变量。** 本节早先写过"非 ASCII 导致"、后来又改成"分号+长路径"，
**两次都是错的** —— 各自从一个同时变动了多个变量的样本推出来。
`isolate_mechanism.py` 一次只改一个变量（短/长 ASCII、短/长中文、有无分号），
唯一与成败相关的只有分号。

**这也解释了那个一直没解释的 `NOTES DaSH\` 子目录**：它是 **CoZ 原版补丁的 workaround**
—— CoZ payload 里带着一个**写死名字**的 `NOTES DaSH\`（代理 DLL 全在里面，根目录反而没有），
正是 Steam 正本目录名 `ROBOTICS;NOTES DaSH` 分号后的片段。
把游戏目录改成副本后片段不再是 `NOTES DaSH`，那个目录就白带了 → 补丁静默不加载。
（纯净游戏目录里**没有**这个子目录，两份母本都实测过。）

### 14.2 证据（modscan32 扫描运行中进程的模块）

同一份 Game.exe、同一份 dinput8.dll，只有目录不同：

| 游戏目录 | 进程实际加载的 dinput8.dll |
|---|---|
| `...\common\ROBOTICS;NOTES DaSH`（片段 `NOTES DaSH` 存在） | `...\NOTES DaSH\DINPUT8.dll` ← 补丁 ✓ |
| `...\common\ROBOTICS;NOTES DaSH -原版英文 副本 - 副本`（片段不存在） | `C:\WINDOWS\SYSTEM32\DINPUT8.dll` ← 系统 ✗ |
| `...\common\ROBOTICS;NOTES DaSH -原版日语 副本 - 副本`（片段不存在） | `C:\WINDOWS\SYSTEM32\DINPUT8.dll` ← 系统 ✗ |
| `D:\ZZGAME\ROBOTICS NOTES DaSH`（无分号） | `...\DINPUT8.dll` ← 补丁 ✓ |

> 排查陷阱：`tasklist /m` 对这类 32 位游戏进程**静默返回空**，64 位 PowerShell 也无法
> 枚举 32 位进程模块 —— 两者都会让人误判。必须用自建的 32 位 toolhelp 工具
> （`scripts/diagnostics/modscan32.cpp`，`modscan32.exe <pid> dinput`）。
>
> 另一个陷阱：modscan32 的输出经管道会丢中文（`wprintf` 按 ANSI 代码页转换，
> 中文目录名变成 `?`）。判读时只认 ASCII 子串（如 `steamapps`）。

### 14.3 解决办法：安装器自动建片段子目录（已实现）

**补丁侧是能修的** —— 建一个与「分号后片段」同名的子目录、把代理 DLL 放进去即可。
安装器按游戏目录名**实时算**片段名（`SemicolonFragments()`），装完自动建目录 +
复制 8 个代理文件（`dinput8.dll` / `d3d9/d3d10/d3d10_1/d3d10core/d3d11` / `dxgi` /
`VSFilter.dll`）。Steam 正本、任意副本、玩家改名后的目录全都自动兼容。
**玩家不需要改名，也不需要 junction。**

卸载器同样算出这些片段（`g_fragDirs`），**逐文件**只删我们放进去的那 8 个名字，
目录空了才删、非空保留 —— 绝不整树删（那些目录名来自玩家自己的目录名）。
装完还有自检：片段子目录里没落到 `dinput8.dll` 就明确弹警告。

`python scripts/make_ascii_links.py` 的 ASCII junction **仍可用但不是必需**
（那是给命令行/自动化提供 ASCII 路径的便利，与加载无关）。

### 14.4 另一个 bug：重装后卸载残留代理 DLL（同日修复）

对**已装过补丁**的目录再装一次时，安装器把那里的 `dinput8.dll / d3d9 / dxgi /
VSFilter.dll …` 也当"既有文件"备份了；卸载器看到"备份里有"就按「安装前就存在 → 恢复」
处理，于是把我们自己的补丁文件原样留下。修法：安装前**比对内容**，
与 payload 根目录同名文件一致的（= 上次装的补丁）不备份。
`scripts/diagnostics/test_reinstall_clean.py` 两个方向都测：
装两次再卸载必须干净；外来 `dinput8.dll` 必须被**还原**而非删除。

### 14.5 排查经验（避免重复踩坑）

1. **判断补丁是否加载，看 `languagebarrier/log.txt` 是否生成** —— LB 一启动必写。
   不要用「进程是否还在」判断（加载失败会弹模态框，进程照样活着）。
2. **不要用 `tasklist /m` 判断 32 位进程的模块** —— 会静默返回空。用 modscan32。
3. **不要用 `taskkill /F` 关游戏** —— 字体缓存在正常退出时写回
   （`saveCache()` 在 `closeAllSystemsHook`），强杀会丢失本次烘焙。
4. **`patchdef.json` 与 `c0data.cls` 必须成套替换** —— fileRedirection 存的是数组下标，
   cls 行序一变索引全错位（曾导致标题 UI 整片空白：索引指到了角色模型文件）。
   `python scripts/deploy_patch.py` 成对部署 + 逐条校验重定向类型。
5. **下结论前先隔离变量** —— 这个坑被误判过三次（"中文""长路径""分号+长度"），
   全是因为对照样本一次改了好几个变量。一次只动一个维度，其余保持不变。
6. **验证汉化别只看 OP 动画** —— 片头罗马字来自 `subs/mv_rnd_op001.ass`（CoZ 罗马字歌词轨），
   与汉化是两条独立通路。


## 15. 2026-09-12 晚追加：三个窗口统一 + 启动器修复 + 卸载器改名

### 15.1 真正的"显示有问题"：三个 exe 都没声明 DPI 感知

实测：系统 DPI 120（125%），窗口却报 96 —— Windows 把整个界面位图**拉伸 1.25 倍**
（启动器客户区 1125×775 而逻辑只有 900×620）。后果是**发虚、边缘发糊**。

三个 exe 现在都 `SetProcessDPIAware()` + 按真实 DPI 换算尺寸，绘制用
`ScaleTransform` 缩放坐标系。要点：

- `BltBit` 要用**物理**尺寸 —— 用逻辑值只拷左上角一块（主按钮整片消失，踩过）
- 鼠标坐标要 `unscale()` 回逻辑再命中判定
- **原生子控件是物理坐标**（安装器的 EDIT 目录框）：创建与 `WM_SIZE` 都要乘 S，
  否则"看着对、点不准"

### 15.2 启动器「开始游戏」被切

`StartRect()` 右边界 = 660+250 = **910 > WIN_W 900**，手写死坐标超出窗口。
改为由统一栅格反推（内容右边界 = WIN_W-32），窗口 900×620 → 820×580。

顺带修：下拉列表原先会被随后绘制的「影片字幕」「开始游戏」**盖住**，
现在所有控件画完再画下拉。

### 15.3 卸载器改名 + 专用图标

- 产品名 `RNDZhUninstall.exe` → **`卸载汉化.exe`**（源码文件名不变）
- 图标换成**红底垃圾桶**（`uninstall.ico`，`scripts/make_uninstall_icon.py` 生成）
  —— ⚠ **后已改回**：2026-09-13 用户要求三 exe 同一图标，改用 `game.ico`，
  靠中文文件名区分。实测现役 `卸载汉化.exe` 图标与启动器逐字节相同。
- 配色从深色霓虹改成**纯白极简**（与安装器/启动器同一套常量），主按钮红色

理由：两个 exe 名字太像又并排躺在游戏目录，点错的代价是**把汉化卸了**。

> ★ **中文名不能写在 .bat 里** —— cmd 按 OEM 代码页逐行读批处理，`chcp 65001`
> 只对"还没读到的行"生效，写成 LF 换行也会失效（两种都踩过：
> 报 `'5001' 不是内部或外部命令`）。做法：bat 编译成 ASCII 名，
> 再由 `setup/build/rename_uninstall.py` 改名（Python 处理 Unicode 路径没问题）。

**升级路径**：安装器会清掉 `RNDZhUninstall.exe` 等旧名，否则老玩家升级后
目录里会同时躺着新旧两个卸载器。`test_uninstaller_rename.py` 专测这条。

### 15.4 排查陷阱：截图工具会骗人

`shot.py` 原先按 `GetClientRect` 分配位图，但 **`PrintWindow` 画的是整个窗口**
（含标题栏与边框）→ 底部被裁 → 看起来像"按钮被切了"，**为此白查了一轮 UI**。
现在按窗口尺寸分配、再按客户区偏移裁出来。

判断"控件被裁"之前，先用 `measure_window.py` 把**窗口矩形 / 客户区 / 客户区偏移**
三个值都量出来再换算 —— 只看图像高度会算错一个标题栏（38 px）。

抓图：`python scripts/diagnostics/shot_ui.py [setup|uninstall|launcher]`。
