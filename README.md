# （测试中）ROBOTICS;NOTES DaSH 简体中文 AI 人工精校

**ROBOTICS;NOTES DaSH**（MAGES/5pb，Steam 版）的简体中文汉化补丁。
译文以**日语原文**为准，gemini3.0flash + 人工精校。

- 当前版本：**v1.3**
- 技术基础：Committee of Zero 的英文优化补丁（LanguageBarrier 运行时），在其框架上替换为中文码表、字体、译文与图集
- 适用：Steam 正版与免 DVD 版通用，装完保持游戏原有语言设定

---

# 第一部分：给玩家

## 装完会变成什么样

| | 内容 |
|---|---|
| **对白 / 旁白** | 全中文，人名地名等术语全套统一 |
| **正文界面** | 菜单、TIPS、系统消息、Twipo / 邮件等界面文本全中文 |
| **CG / 系统图片** | 标题菜单、选项界面、系统菜单、CG 库 / 音乐库标签、自动存档提示等全部汉化并手工嵌入图集 |
| **影片** | MV 有中文卡拉OK字幕（逐字高亮 + 翻译轨，可在启动器开关）；1 段剧情影片替换 |
| **启动器** | 中文启动器，提供鼠标操作、滚轮推进文本、cosplay 换装模式等开关 |

## 怎么装

1. **先完全退出游戏**（进程会锁住补丁文件）。
2. 双击 `RNDZh-Setup-v1.3.exe`，安装器会自动找到游戏目录（Steam 库或免 DVD 目录都能认）。
3. 点「安装」。装完点「RNDZhLauncher.exe」启动即可。

卸载：运行游戏目录里的 `卸载汉化.exe`，会还原到装补丁前的状态。

---

# 第二部分：和 Committee of Zero 英文补丁的区别

本补丁基于 CoZ 英文优化补丁的运行时（LanguageBarrier）——它提供改写游戏文本与资源的
机制；本补丁在其上替换了码表、字体、全部译稿与图集，并配有独立的启动器与安装器。

| 维度 | CoZ 英文补丁 | 本补丁 |
|---|---|---|
| 语言 | 英文 | **简体中文**（译文以日语原文为准） |
| 正文字体 | Noto 合并 TTC | **思源黑体简中**（`NotoSansCJKsc-Regular.otf`） |
| 文本重定向 | 仅 `MES01` | `MES00` **+** `MES01`（TIPS / 系统消息等一并接管） |
| 图片重定向 | bg 18 / system 5 | **bg 64 / system 12 / movie 1** |
| 影片字幕 | 英文卡拉OK | **中文逐字卡拉OK + 翻译轨**（三种模式可开关） |
| 启动器 | `LauncherC0.exe`（Qt5，需十余个 DLL） | `RNDZhLauncher.exe`（单文件，无 Qt 依赖） |
| 换装 | `swimsuitPatch`（只切泳装） | `fileIdRemap` 保留LB重定向内部资源，同归档引用，含 cosplay 模式（和服 / 泳装 / 体操服 / 猫耳） |
| 安装 / 卸载 | `nguninstall.exe` | 安装器 / 卸载器，**自动兼容含分号的目录名** |
| 字体 | 运行时逐档烘焙（首次进各界面会卡） | **预置 12 档字形种子**（首次进界面不卡，且绕开写盘权限问题） |
| 补丁体积 | 356 MB | **安装包 171.9 MB**（补丁包本体 424.7 MB，含 227 MB 字形种子） |

相同之处：两者的运行时内核、`patchdef.json` 结构、图形 / 影片重定向机制是同源的
（MIT 许可的 LanguageBarrier）。CoZ 原版的许可文件在补丁包里原样保留。

---

# 第三部分：相对 CoZ 的技术差异

## 运行时（LanguageBarrier 源码）

改动集中在 10 处，都在 `LanguageBarrier_rndchs/LanguageBarrier/`：

| 文件 | 改动 | 为什么 |
|---|---|---|
| `TextRendering.cpp` | 新增 `forceIncludeHan` 开关 | 原逻辑按语言过滤 CJK 字形；中文码表必须烤汉字 |
| `TextRendering.cpp/.h` | 新增 `charsetHash`（FNV-1a 32 位）写入字体缓存 | 码表一变就判定旧缓存失效，自动重烤 |
| `TextRendering.cpp` | 字体缓存自愈（缺 `.dds` 图集 / 哈希不符即清缓存） | 修「缓存说没问题、实际画不出字」 |
| `TextRendering.cpp` | `loadCache` 的语言校验改为**跟随 `forceIncludeHan`** | 开启时 JP/EN 烘出的图集完全相同，该校验只会把好缓存整份丢掉；关掉时自动恢复原行为 |
| `TextRendering.cpp/.h` | `getGlyphInfo` 缺字形返回 `missingGlyph`（宽 0） | 原本 `map::at` 会在游戏渲染线程抛 `out_of_range` |
| `GameText.cpp/.h` | `RUBY_MARKERS_ENABLED`（默认关） | 修 `A`/`8`/`9` 被当成注音标记吃掉 |
| `Game.cpp` | 新增 `fileIdRemap` 分支 | 同归档内改指到另一文件（换装），不随包分发原素材 |
| `Game.cpp` | `fileIdRemap` 查找加 json 守卫 | 修 `type_error.302` 崩溃 |
| `SigScan.cpp` | `pattern` 支持**字符串数组**逐个回退 + `occurrence` | 一个 `gamedef` 兼容游戏多个版本的特征码 |
| `CustomInputRND.cpp` | `kTitleMenuWidthsZh[15]` | 标题菜单鼠标悬停 / 点击宽度跟着中文图集改 |

## 工具链

- `sc3tools_rndchs/src/text.rs`：删掉「半角空格无条件转全角空格 U+3000」的分支——
  中文码表里 U+3000 走汉字字形步进，会让英文术语两侧多出一个汉字宽的间隔。
- `SigScan` 的数组回退（上表最后第二行）配合 `gamedef.json` 里追加的两条备选特征码，
  让补丁不因游戏小版本更新而失效。

## 已修复的问题

1. **字母 `A` / `8` / `9` 静默消失**——SC3 文本流里 0x80 0x09/0x0A/0x0B 既是注音标记又是字形对，
   中文码表下 `A`/`8`/`9` 正好落在那三个位置，被当标记吃掉（`PHASE NAE` 显示成 `PHSE NE`）。
2. **字体缓存陈旧**——换了码表却仍读旧缓存，字形错乱 / 缺字；现在带哈希校验并自愈。
3. **高位字形不显示**——字形 id 解析不到时曾抛异常或画成空白。
4. **英文术语两侧多出汉字宽的空隔**（如 `Mr.　Pleiades`）——全角空格误编码所致。
5. **游戏目录名含分号 → 补丁静默失效**——Windows 加载器把分号后的路径当子目录搜；
   安装器现在按目录名实时算出片段名并自动建子目录，玩家无需改名。
6. **重装后卸载残留 8 个代理 DLL**——安装前按内容比对，避免把自家补丁当「玩家原版文件」备份。
7. **数字 `9` 不显示**、**`json type_error.302` 崩溃**、**缺字形抛异常**——见上表。
8. **安装器点「启动游戏」窗口卡死**——SFX 临时目录的清理挪到窗口关闭之后。
9. **对话历史（backlog）说话人名参差不齐**——游戏把「喇叭图标 + 名字」整块居中，
   名字长短不同就各自偏移。现在名字右对齐到统一列，正文保持游戏原有位置。
   （附带发现：CoZ 上游那段对齐代码从写下就**从未执行过**，因为它是用
   `std::wstring_view` 从裸指针定长搜索，而缓冲里空格字形把它截断了。）
10. **对话框注音（ruby）位置偏**——标注比基字长时（`可靠的右手` ← `Favorite Right Arm`）
    会跑到整行居中、偏出约 150px；比基字短时会截尾。现在按「标注 → 所属词」对照表
    精确居中。
11. **引号「」占满一个全角格、换行后对不齐**——引号的墨只占格子右半边，导致
    引号行视觉上比旁白行缩进 25px，且换行后下一行对着它的空白。现在按半角步进绘制，
    墨贴左缘。
12. **中文没有空格导致长句不换行**——CJK 逐字断行 + 行首/行尾禁则（标点不排行首）。

---

# 第四部分：仓库内容

| 目录 | 内容 |
|---|---|
| `cnscript/` | 中文译稿（`.msb.txt`）与中文码表 |
| `jpscript/` | 日文原版脚本（提取用基线） |
| `subs/` | 影片字幕 `.ass` 与歌词字体 |
| `LanguageBarrier_rndchs/` | LanguageBarrier 运行时源码 + 发布用 `dinput8.dll` / `VSFilter.dll`（编译中间产物不入库） |
| `sc3tools_jp/`、`sc3tools_rndchs/` | 日文提取 / 中文回写工具链 |
| `tools/` | 启动器 `RNDZhLauncher.cpp` + 换装核对工具 `RNDZhOutfitTool.cpp` 源码与构建脚本 |
| `setup/` | 安装器 / 卸载器源码（`src/`）与构建脚本（`build/`） |
| `图片汉化/` | **成品中文图集**（`bg/` `system/` `manual/`，与补丁包 `c0data/` 逐字节一致）。其下 `system/data/_archive/` 存**非汉化的原件**（见该目录 README） |
| `废弃图片/` | 已从补丁重定向中撤下的汉化图（仅留存备查，不随补丁分发） |
| `视频汉化/` | 替换用影片（USM 重封说明 + `movie_dar020.usm`） |
| `代理DLL/` | 补丁运行所需的代理 DLL（DXVK 的 `d3d9`/`d3d10`/`d3d10_1`/`d3d10core`/`d3d11`/`dxgi` + `VSFilter.dll`），来自 CoZ 补丁包，**非本项目产出**（见该目录 README） |
| `scripts/` | 构建与部署脚本（`deploy_patch.py`、`sync_images.py`、`gen_pkg_manifest.py` 等） |
| `docs/` | 交接文档、打包清单、设计说明 |

> `图片汉化/` 里的文件名带 `_zh` 后缀（便于与解包原图区分）；进补丁包时按
> `c0data.cls` 的原始资源名（去掉 `_zh`）落位，`scripts/sync_images.py` 负责这件事。
> 撤下已废弃的图用 `scripts/drop_deprecated.py`（会重排 `c0data.cls` 索引）。

> ⚠️ **本仓库不含「可直接打包」的完整补丁包**。安装包由工作区的 `成品ing/补丁包/`
> 组装（`build_installer.py` 从那里取件）。从本仓库重建安装包时，以下内容需要另行生成：
> 编译产物 `enscript/*.msb`（由 `sc3tools_rndchs` + `cnscript` 编出）、
> 字体缓存 `fonts/*.dds`（需实机跑游戏烘焙，见 `docs/字体种子.md`）、
> `c0data` 注入图（由 `scripts/sync_images.py` 从 `图片汉化/` 生成）。
> 代理 DLL、影片、归档原件已在本仓库中，无需外部来源。

## sc3tools 版本说明 (IMPORTANT)

仓库里有两套 sc3tools，源码完全相同，唯一区别是编译时内嵌的 `resources/rnd/charset.utf8` 码表。
**码表是 rust-embed 编译期打进 exe 的，改码表必须重新 `cargo build --release`，改完直接跑旧 exe 无效。**

- `sc3tools_rndchs/` — **中文版**。码表为汉化简体字码表（13K，4499 字，md5 `e62f5ca3...`），
  用于配合 `cnscript/` 译稿做中文回写（replace-text）。
- `sc3tools_jp/` — **日文版**。码表为日文原版码表（8.7K，3020 字，md5 `6040d18f...`，
  即 `charset-.utf8` / `charset-备份.utf8`），用于提取日文原版脚本（extract-text）。

**配对关系：日文包用日文版提取，中文回写用中文版。用错码表会得到大面积错码
（例如 `種子島` → `丽仁亿`，`海翔` → `ΥΦ`）。**

现成的 exe：

- `sc3tools_rndchs/target/release/sc3tools.exe` — 中文版
- `sc3tools_jp/target/release/sc3tools.exe` — 日文版

用法示例（提取日文）：

```
sc3tools_jp/target/release/sc3tools.exe extract-text "mes00.cpk/*.msb" rnd
```

输出会放在输入文件同级的 `txt/` 子目录。

---

## 致谢与许可

- **汉化：Eight_tide × 仓式同学◆**（AI 翻译 Gemini 3.0 Flash · 人工精校 · CG / 系统图手工嵌入）
- 运行时框架 [LanguageBarrier](https://github.com/CommitteeOfZero/LanguageBarrier)
  与英文优化补丁由 **Committee of Zero** 开发（MIT；因含 xy-VSFilter，二进制按 GPLv2 分发）。
- 本补丁基于 CoZ 的工作，译文 / 图集 / 工具为本项目完成。
- 文本编码工具 [sc3tools](https://github.com/CommitteeOfZero/sc3tools)。
- 歌词字体基于 Noto Sans SC（SIL OFL 1.1，随字体分发）。
- 本方为**非官方**汉化，与 MAGES./5pb.、Nitroplus、Steam 及 Committee of Zero 均无隶属关系。
  请支持正版。若认为本仓库内容有不妥之处，请联系作者。
