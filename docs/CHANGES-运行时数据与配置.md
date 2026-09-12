# 运行时数据与配置变更记录

记录 2026-09-08 对**游戏目录内运行时数据 / 配置**所做的改动。
这些不是代码，但会影响实际运行效果，变更时容易被忽略，故单独归档。

游戏目录：`D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH`
配置目录：`languagebarrier/`

---

## 1. 字体更换（日文 → 简体黑体）

### 原因

原 `fontPath` 指向 `languagebarrier/fonts/noto.ttc`。经查该字体 name 表：

```
family: Noto Sans CJK JP Regular
ps:     NotoSansCJKjp-Regular
```

是 **JP（日文）版本**，因此汉字渲染为日文字形。

### 变更

`languagebarrier/patchdef.json`：

```diff
- "fontPath": "languagebarrier/fonts/noto.ttc"
+ "fontPath": "languagebarrier/fonts/NotoSansCJKsc-Regular.otf"
```

字体文件：`languagebarrier/fonts/NotoSansCJKsc-Regular.otf`

- 来源：隔壁方案 `RNDash_CN` 发行包
- 名称：Noto Sans CJK SC Regular（简体中文，无衬线黑体）
- 大小：16,437,364 字节
- 授权：**SIL OFL**，可随补丁自由分发

### 字形覆盖验证

对运行时字符集（4499 项，去重 4414）做覆盖检查：

| 字体 | 缺字 | 说明 |
|---|---|---|
| `NotoSansCJKsc-Regular.otf`（新） | 31 | 全为 PUA 图标（U+E001–U+E01E） |
| `noto.ttc`（原，JP） | 31 | 同上 |
| `simhei.ttf`（曾用） | 50 | 另缺 `ﾟ ﾉ ｷ ﾘ ｯ` 等半角假名 |

→ 新字体**完整覆盖汉字**，且比 simhei 更全；PUA 缺字与原来的 noto.ttc 一致
（属已知未修问题，见代码修复文档附录）。

### 清理

以下字体已从游戏目录移走（备份到工作区 `临时/字体备份_*`）：

- `noto.ttc`（日文，已弃用）
- `simhei.ttf`（Windows 系统字体，**不可随补丁分发**）

---

## 2. 字体缓存清空（多次）

字体缓存必须**与当前字体、字符集同批生成**，否则出现字形错乱或空白。

历次清空及备份位置（均在 `languagebarrier/fonts/cache_backup_*` 或工作区）：

| 时间 | 原因 | 备份目录 |
|---|---|---|
| 09-08 15:42 | 首次排查，清三批混杂缓存 | `cache_backup_before_fix_20260908` |
| 09-08 16:32 | 修复缓存撕裂后重建 | `cache_backup_before_fix_20260908` |
| 09-08 21:03 | 换 Noto Sans SC，旧缓存字体不匹配 | `cache_backup_before_notosc_20260908_210324` |
| 09-08 21:32 | 最终清理：旧图集用 simhei 烤，与 Noto 不符 | 工作区 `临时/旧缓存_20260908_213218` |

**最终状态**（`languagebarrier/fonts/`）：

```
NotoSansCJKsc-Regular.otf      仅此一项，缓存为空
```

游戏启动后会用 Noto Sans SC 按需重建全部字号。

### 重要：换字体/改字符集后必须清缓存

我加的 `charsetHash` 校验**只覆盖字符集，不含字体路径**。
因此**更换字体文件后，必须手动清空**以下文件，否则会沿用旧字体的图集：

```
languagebarrier/fonts/font_*.dds
languagebarrier/fonts/outline_*.dds
languagebarrier/fonts/fontData.bin
```

---

## 3. 关于"按需烘焙"

LanguageBarrier **只在游戏实际用到某字号时才烘焙它**，且 `saveCache()`
在退出时（`closeAllSystemsHook`）才写盘。

因此：

- 首次启动会较慢（烘焙）；
- 需**多进几个界面**才能覆盖全部字号（对话、口袋电脑、存档/读档、设置、
  TIPS、邮件、地图等）；
- 必须**正常退出游戏**，`fontData.bin` 才会保存；
  强杀进程会导致本次烘焙成果丢失（曾因此出现 `fontData.bin` 缺失）。

已观测到的字号：16 18 24 25 27 28 30 31 32 34 36 37 39 40 42 43 56 61
（56/61 来自 `BacklogTextSize[...] * 1.5f` 等动态计算，非异常值）

---

## 4. 字符集来源确认（重要结论）

运行时字符集 = `patchdef.json` 的 `base.charset`，长度 **4499**。

验证结果：

| 文件 | 长度 | 与运行时一致 |
|---|---|---|
| `GitHub/RND_Chinese/sc3tools_rndchs/resources/rnd/charset.utf8` | 4499 | **完全相同** ✅ |
| `备份/sc3tools_backup/resources/rnd/charset.utf8` | 4411 | 否（是其前缀） |
| `备份/original tools/.../rnd/charset.utf8`（CoZ 原版） | 4096 | 否（仅 12.8% 相同） |

**结论**：编译 `.msb` 用的码表（`sc3tools_rndchs`）与运行时解码码表
**完全一致**，不存在"编码用 A 码表、解码用 B 码表"的错配。

→ 因此 `.msb` **不需要重编码**。此前观察到的"Takesh穿 Abo"等乱码是
**我自己解码器字节对齐错误**造成的假象，非文件真实问题。

> 排查中曾怀疑与隔壁 `RNDash_CN` 的 Runtime Error 同源（改写隐藏查找键），
> 经上述验证已排除。

---

## 5. `.msb` 文件格式（供后续工具开发参考）

正确布局（依据 `sc3tools_rndchs/src/format.rs`）：

```
偏移 0x00: b'MES\0'
偏移 0x04: u32  (未用)
偏移 0x08: u32  (未用)
偏移 0x0C: u32  字符串索引区结束位置 (idx_end)
偏移 0x10: 索引区起点，条目为 (u32 id, u32 offset)，每项 8 字节
偏移 idx_end: 字符串数据区（heap）
字符串地址 = idx_end + entry.offset
```

字形流规则：

- 字形 = 2 字节：`(0x80 | (id >> 8)), (id & 0xFF)`，**低字节可以 < 0x80**
- `0x03` = 1 字节控制码（cnscript 中显示为 `[%p]`）
- `0xFF` = 字符串终止
- 其余 `< 0x80` 为控制码（长度依具体命令而定，`0x04` 为 2 字节）

> 踩过的坑：若把低字节 `< 0x80` 误判为控制码并跳 1 字节，会导致整串错位，
> 产生大量虚假的"越界字形 id"。

---

## 6. 待办 / 已知未修问题

1. **PUA 图标字（30 个）不显示** —— U+E001–U+E01E 在 Noto 中无字形，
   被过滤后永不渲染。可参考隔壁 `Build-RNDZhNativeMapFont.ps1`。
2. **字符 `9`（index 10）仍被吞** —— 字节二义性固有限制，见代码修复文档。
3. **口袋电脑界面「八汐亲」的「汐」不显示** —— **排查中，见下节**。
4. **崩溃（Runtime Error）偶发** —— 2026-09-08 清理字体/缓存后玩家反馈
   **暂无法复现**，推测与"图集与字体错配"或"多字体残留"有关，但**未确证**。
   已排除：大图集超限（D3D11 上限 16384，实际最大 5589）、
   烘焙卡顿（实测 0.1–0.2 秒）、码表错配（已验证自洽）、
   签名扫描失败（日志无 not found）。

---

## 7. 「汐」不显示 —— 排查记录（未解决）

### 现象

口袋电脑界面中，人名「八汐亲」显示为「八 亲」—— **中间空一格**，
「汐」既不乱码也不显示为错误字符，就是**静默消失**。
对话正文中的「汐」**正常显示**。

### 已验证「没问题」的环节（全部排除）

| 环节 | 验证方式与结论 |
|---|---|
| 文本数据 | `_mail_00.msb id=1200` 原始字节 `83 49 90 6a 82 b0`<br>= 字形 id 841(八) / **4202(汐)** / 688(亲)，**无 ruby 标记干扰** |
| 字符集 | 「汐」在 charset 中**唯一**（count=1），索引 4202 |
| 字形烘焙 | 19 个字号（18–63）中，「汐」在 font 与 outline 图集里**均有墨迹** |
| 字形度量 | 各字号 width/rows/adv **全部非 0**（如 28 号：26/28/28） |
| 实际渲染 | 用游戏真实 fontData + 图集渲染「八汐亲」→ **三字均正确显示** |
| 代码路径 | 口袋电脑邮件走 `sghdDrawInteractiveMailHook`<br>(`GameText.cpp:2834`)，其内部调用的<br>`semiTokeniseSc3String`(1421) / `processSc3TokenList`(2593)<br>**正是修复 1 已覆盖的函数** |
| 烤字贴图 | `c0data/` 中**无** PhoneDroid 图集；<br>`data01_en.png` 是 4096×2048 的口袋电脑主屏图集，<br>但仍为英文原版（未汉化）——**与此处现象无关** |

### 走过的弯路（记录以免重复）

- **曾误判为"烤字贴图"**：猜测口袋电脑走 `c0data` 图片而非动态文本。
  **玩家指正**：该界面是**滚动文字**且已显示中文，不可能是图片。此方向废弃。
- **曾怀疑 ruby 标记**：但「汐」id=4202 不在危险区（9/10/11），且已由修复 1 覆盖。

### 根因（已确认，2026-09-09）

**游戏原生字体系统只支持 4096 个字形槽位。**

- 原版 CoZ 的 RND 字符集恰好是 **4096** 项
  （`备份/original tools/sc3tools_original/resources/rnd/charset.utf8`）
- 本补丁扩展后的字符集是 **4499** 项，比原版多 **403** 个
- 超出的部分（索引 ≥ 4096）在**游戏原生绘制路径**下取不到字形 →
  画成零宽度空精灵 → **静默消失**

| 索引范围 | 对话（LB 接管） | 口袋电脑等（游戏原生） |
|---|---|---|
| 0 – 4095 | 显示 | 显示 |
| 4096 – 4498 | 显示 | **不显示** |

这解释了为何「汐」在对话正常、在口袋电脑消失，以及"别的字也消失"。

### 修复（已实施并验证）

把"索引 ≥ 4096 且被 msb 实际使用"的字符**搬入未使用的低位空槽**。

- 第一轮（单字试验）：`4202 (汐)` ↔ `92 (")`
  - 92 号槽在 msb 中引用 **0 次**，安全
  - 玩家验证：**汐恢复显示** ✅
- 第二轮（批量）：335 个高位字 ↔ 335 个低位空槽
  - 重映射 **7389** 处引用，涉及 **180** 个 msb 文件
  - 低位空槽共有 600 个，容量充足

同步更新（必须三者一致，否则全乱码）：

1. `languagebarrier/patchdef.json` 的 `base.charset`
2. `GitHub/RND_Chinese/sc3tools_rndchs/resources/rnd/charset.utf8`
3. `enscript/*.msb` 中所有相关引用

验证：「八汐亲」= `83 49 80 5c 82 b0` ✅；「八汐海翔」✅

**备份**：

- `languagebarrier/enscript_backup_swap_20260909_023542/`（323 个 msb）
- 另有 `enscript_backup_swap_20260909_022945/`（第一轮）
- `patchdef.json.bak_swap_*`、`charset.utf8.bak_swap_*`
- 工具：`临时/swap_charset_slot.py`（`--pairs a:b,c:d --apply`）

**回滚**：覆盖备份文件 + 清空字体缓存。

### 残留待确认

批量后仍有约 **980** 处字形 id 越界，分散在 157 个文件（每处很少）。
其中 344 处集中在 `rnd_01_01_00-.msb`——该文件**在 patchdef/gamedef 中零引用**
且内容为无意义字串，判定为废弃残留。

其余 980 处大概率是**离线扫描器对控制码长度处理不准**造成的假象
（例如 `0x04` 需按 2 字节跳，处理正确后 `clrflg_00.msb` 曾归零）。
**尚未逐条确证**，但不影响已验证的显示效果。

### 当前卡点

数据链路（文本 → id → 图集 → 渲染）**已全链路验证健康**，
用游戏真实数据离线渲染能正确显示「汐」。
因此问题应出在**运行时绘制环节**，而非数据。

### 下一步需要的信息

1. 该界面**具体是哪个**（口袋电脑主屏 / 邮件列表 / 邮件正文 / 通讯录）？
2. 同一界面中，**其他汉字是否正常**（比如「亲」能显示，说明中文链路通）？
3. 该界面**使用的字号**是多少（可通过界面大小粗略判断）？
4. 若能提供**截图**，可直接定位是"零宽度精灵"还是"纹理坐标错误"。

---

## 附：发布注意事项

- **不要**打包 `simhei.ttf` / `noto.ttc`
  （前者为 Windows 系统字体不可分发；后者为日文且非必需）
- 建议打包 `NotoSansCJKsc-Regular.otf`（SIL OFL，可分发）
- 保留 CoZ 的 `LICENSE` 与 `THIRDPARTY.LB.txt`
- 字体缓存（`font_*.dds` / `fontData.bin`）**不建议预置**在发布包中，
  让用户在本地按其所拿到的 `patchdef.json` 生成，可从机制上避免
  "生成时字符集 ≠ 运行时字符集"这类问题

---

## 2026-09-12 安装包漏打包 9 个归档文件（`_` 前缀误判）

### 症状

安装包能装、能启动、`log.txt` 零错误，**但游戏里部分界面/提示直接失效**：
`languagebarrier/enscript/` 少了 8 个 `.msb`、`c0data/` 少了 `_nobg.png`，
而 `enscript.cls` / `c0data.cls` 仍然点名它们。
MES00/MES01 整个归档被重定向到 `languagebarrier/enscript`，
所以游戏按索引打开这些文件时**根本不存在**（不是回退到原版，是找不到）。

### 根因

`setup/build/build_installer.py` 的垃圾过滤规则里有 `n.startswith('_')`
（本意是排除 `_stage` / `_bak` / 临时目录）。但**游戏资源本身就有下划线开头的名字**：

```
languagebarrier/c0data/_nobg.png          ← bg fileId 0，被 fileRedirection 点名
languagebarrier/enscript/_anime_00.msb
                        /_ar_00.msb
                        /_geotag_00.msb
                        /_mail_00.msb
                        /_startup_ps4_00.msb
                        /_system_00.msb     ← 系统消息
                        /_tips_00.msb       ← TIPS 词条
                        /_twipo_00.msb      ← Twipo（聊天）界面
```

CoZ 原版补丁里这 8 个 `.msb` 同样存在，是**正常资源命名**，不是临时文件。

### 为什么一直没被发现

- 构建只打印「共 N 个文件」，**不校验**文件是否齐；
- `final_accept.py` 的判据是「装完能启动 + 卸载回纯净」，漏几个数据文件它看不出来；
- 验收只看 `rnd_01_01_00.msb` 的中文条数，那个文件恰好没被漏掉。

### 修法

1. 删掉 `startswith('_')` 这条规则，只保留明确的垃圾特征
   （`.bak` / `.obj` / `.res` / `.pdb` / `.ilk` / `silent_log` / `.log` / `__pycache__`）。
2. 打包后新增**归档清单门禁**：逐行读 `c0data.cls` 与 `enscript.cls`，
   点名而 stage 里不存在的文件一律报错退出。
   这类"清单与内容不一致"的 bug 由门禁兜住，不再依赖人眼。
3. `scripts/deploy_patch.py --dry-run` 的 `verify()` 也能抓到同样的不一致
   （`cls 指向但 c0data/ 缺失`），部署前可先跑。

### 验证

- 解包成品安装包：`enscript/` 322 个、`c0data/` 88 个，`_` 开头 9 个文件全部在。
- `final_accept.py` 全流程：安装 6 秒 → `log.txt` 5385 B / 0 错误 → 卸载 14 秒 → 回纯净、无残留。
- 实机安装后确认 `_system_00.msb` 等确实落到游戏目录。
