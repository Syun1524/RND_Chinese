# 字体与文本渲染修复记录

本文件记录 2026-09-08 对 LanguageBarrier（RND 简体中文分支）所做的**代码级修复**。
每一项都包含：症状、根因、改法、验证方式。便于后续提交/发布时追溯出处。

相关源文件（均在本仓库 `LanguageBarrier_chs/LanguageBarrier/` 下）：

- `TextRendering.h` / `TextRendering.cpp`
- `GameText.h` / `GameText.cpp`

---

## 修复 1：'A'、'8'、'9' 在游戏中静默消失（ruby 标记与字形撞码）

### 症状

- 读档界面存档标题 `PHASE NAE` 显示为 `PHSE NE` —— **两个 A 被精确删除**，
  既不留空格、也不乱码。
- 口袋电脑等界面的 `8`、`9` 也有类似丢失。
- 正文对话框**不受影响**。

### 根因

SC3 文本流没有转义机制，字节对 `0x80 0x09 / 0x0A / 0x0B` 存在二义性：

| 字节对 | 作为控制码 | 作为字形 id（字符集索引） |
|---|---|---|
| `80 09` | ruby 注音相关 | index 9 = **`8`** |
| `80 0A` | ruby 注音**开始** | index 10 = **`9`** |
| `80 0B` | ruby 注音**结束** | index 11 = **`A`** |

在中文字符集中，index 9 / 10 / 11 正好是 `8`、`9`、`A`。

`GameText.cpp` 中三处代码**无条件**把这三个字节对当作 ruby 控制码消费掉
（只 `sc3string += 2`，不渲染任何字形）：

- `GameText.cpp:1421`（`semiTokeniseSc3String`）
- `GameText.cpp:2593`（`processSc3TokenList` 内）
- `GameText.cpp:2771`（`getSc3StringDisplayWidthHook`）

### 改法

新增可配置开关 `safeRubyMarkers`（默认开启），三处判断统一改为：

```cpp
if ((uint8_t)c == 0x80 && sc3string[1] >= 9 && sc3string[1] <= 11 &&
    (!SAFE_RUBY_MARKERS || sc3string[1] == 10 || insideRubyText)) {
```

逻辑：

- `0x0A`（ruby 开始）仍被识别为控制码 —— 真 ruby 总是"先开后关"，不受影响；
- `0x0B` / `0x09` 只有在**已处于 ruby 中**时才当结束/相关标记；
- 孤立的 `0x0B` 正常渲染为字符 `A`。

配置读取（`GameText.cpp:623-625`）：

```cpp
SAFE_RUBY_MARKERS = true;
if (config["patch"].count("safeRubyMarkers") == 1)
  SAFE_RUBY_MARKERS = config["patch"]["safeRubyMarkers"].get<bool>();
```

声明位于 `GameText.h:69`。

### 为什么正文对话的 ruby 不受影响

对话 ruby 走**独立代码路径**：`GameText.cpp:2091-2099` 从 `BacklogText[]`
（UTF-16 数组）读取，直接判断 `v16 == 9/10/11`，**不解析 `0x80 0x0B` 字节流**。
因此本次改动不影响正文注音显示。

### 验证

用真实 `.msb` 语料对比新旧逻辑：

| 字符 | 旧逻辑被吞次数 | 新逻辑被吞次数 |
|---|---|---|
| `A` | 1846 | 51 |
| `8` | 334 | 63 |
| `9` | 445 | 445 |

修复实例：

```
'PHASE NAE'    → A 恢复
'我是iLY'      → '我是AiLY'
'2020年月16日'  → '2020年8月16日'
'血型:型'      → '血型:A型'
```

### 已知残留

`9`（index 10）仍会被当作 ruby 开启标记，这是字节二义性的固有限制 ——
单看 `0x0A` 无法区分它是字符 `9` 还是"ruby 开始"。
若需彻底解决，须调整字符集让 9/10/11 不落在危险区，但那会触发缓存重建
并需要重编码全部 `.msb`，风险较高，故未采用。

---

## 修复 2：陈旧字体缓存不会被自动丢弃（字符集指纹校验）

### 症状

修改 `patchdef.json` 的 `base.charset` 后，旧的烘焙缓存（`font_NN.dds` +
`fontData.bin`）仍被加载使用，导致字形与坐标表不匹配。

### 根因

`TextRendering::loadCache()` 原本**只校验语言**（`lang`），不校验字符集：

```cpp
if (it->second.lang != TextRendering::Get().language) { ... 清空 ... }
```

字符集变更不会被察觉。

### 改法

1. `TextRendering.h:127` — `FontData` 增加字段并纳入序列化：

```cpp
uint32_t charsetHash = 0;
...
ar(lang, charsetHash, glyphData);
```

2. `TextRendering.h:173` — `TextRendering` 增加成员与静态函数声明：

```cpp
uint32_t charsetHash = 0;
static uint32_t computeCharsetHash(const std::wstring& charset);
```

3. `TextRendering.cpp` 新增 `computeCharsetHash()`：FNV-1a，按 UTF-16 码元计算。

4. `TextRendering.cpp:72` — `Init()` 中在 `fullCharMap` 构建后计算指纹。

5. `TextRendering.cpp:130` — `buildFont()` 中写入 `fontData->charsetHash`。

6. `TextRendering.cpp:440-449` — `loadCache()` 中在语言检查**之前**加字符集检查，
   不匹配则清空缓存并重新保存。

### 向后兼容

对**旧缓存**（无 hash 字段，值为 0）使用 `charsetHash != 0 &&` 条件，
因此读到 0 时会**保留而非清空**，避免误删用户现有缓存。

### 验证

Python 复刻该哈希做单元测试，6/6 通过：

| 场景 | 是否触发清空 |
|---|---|
| 加前导 `〓`（历史真实成因） | 触发 |
| 删前导空格 | 触发 |
| 交换前两字符 | 触发 |
| 追加字符 | 触发 |
| 截断末尾 | 触发 |
| 未改动 | 保留 |

当前字符集哈希：`0x7E577241`（4499 字符）。

---

## 修复 3：缓存撕裂 —— 索引残留导致图集缺失（修复 2 引入的回归）

### 症状

应用修复 2 后，`fonts/` 出现**撕裂状态**：`fontData.bin` 完好（12 个字号），
但**一个 DDS 都没有**，导致所有文字不显示。

### 根因

`loadCache()` 中 DDS 加载失败时直接 `return`，索引留在内存；
退出时 `saveCache()` 将其写回磁盘。下次启动 DDS 全缺。

### 改法

1. `TextRendering.cpp` — `loadCache()` 两处 DDS 缺失路径改为清空后调用
   `saveCache()`，不再残留索引：

```cpp
if (g != S_OK) {
  lb::LanguageBarrierLog(
      "Font cache is missing its baked atlas, clearing font cache");
  this->fontData.clear();
  TextRendering::Get().saveCache();
  return;
}
```

（outline 图集同理，日志文案为 `...its baked outline atlas...`）

2. `TextRendering.cpp:418-420` — `saveCache()` 删除索引条目时**同步删除
   对应的图集文件**，从机制上杜绝"索引在、图集不在"：

```cpp
wchar_t atlasName[260];
wsprintf(atlasName, L"languagebarrier/fonts/font_%02d.dds", it->first);
_wremove(atlasName);
wsprintf(atlasName, L"languagebarrier/fonts/outline_%02d.dds", it->first);
_wremove(atlasName);
```

同时补 `#include <cstdio>`（`_wremove` 所需）。

---

## 附：字形不可用时的行为（背景说明，非本次改动）

`TextRendering.cpp:74-82` 会过滤掉字体中不存在的字形：

```cpp
int glyph_index = FT_Get_Char_Index(this->ftFace, fullCharMap[i]);
if (glyph_index && ((!isHan) || language == JP || forceIncludeHan) && ...)
```

`Noto Sans CJK SC` 不含 U+E001–U+E01E（30 个 PUA 图标槽），
`FT_Get_Char_Index` 返回 0 → 被过滤 → **永不显示**。

- 这 30 个槽位在 `.msb` 中被引用约 55 次。
- 运行时表现：`getGlyphInfo` 返回默认构造的 `FontGlyph`（`x=-1`），
  `textureWidth = 0`，画出零宽度空精灵 —— **静默不显示**。
- **尚未修复**。隔壁方案（`RNDash_CN`）用 1044 个 PUA 槽并建立地图中文别名，
  可参考其 `tools/Build-RNDZhNativeMapFont.ps1`。

---

## 编译与部署

- 编译配置：`dinput8-Release | Win32`（**不是** `Release`）
- 工具集：v142（VS2019），装在 VS2022 中
- 命令：

```
MSBuild.exe LanguageBarrier.vcxproj ^
  -p:Configuration=dinput8-Release -p:Platform=Win32 -v:minimal
```

产物：`LanguageBarrier/dinput8-Release/dinput8.dll`
部署位置：游戏目录 `NOTES DaSH/dinput8.dll`（**注意是子目录，不是根目录**）

> 在 Git Bash 下需加 `MSYS_NO_PATHCONV=1`，否则 `/p:` 会被当作路径转换。

---

## 许可提醒

本分支基于 Committee of Zero 的 LanguageBarrier。若分发编译产物：

- 保留 CoZ 署名与 LICENSE / THIRDPARTY 声明；
- 明确标注本分支所做的修改；
- 按 LICENSE 条款提供修改后源码。
