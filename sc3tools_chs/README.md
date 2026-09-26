# sc3tools —— ROBOTICS;NOTES DaSH 简体中文汉化专用改版

**这是 fork，不是上游原件。**

| | |
|---|---|
| **用途** | [ROBOTICS;NOTES DaSH](https://store.steampowered.com/app/1111390/)（MAGES/5pb）**简体中文汉化补丁**的文本工具 |
| **汉化项目** | [Syun1524/RND_Chinese](https://github.com/Syun1524/RND_Chinese) |
| **fork 自** | [CommitteeOfZero/sc3tools](https://github.com/CommitteeOfZero/sc3tools) |
| **基准提交** | `6ba9278a`（2025-05-22） |
| **本分支** | `rnd-chinese` |
| **改动** | 3 个源文件 + 新增 `resources/rndzh/` 码表 |

上游 sc3tools 是 CoZ 为 MAGES 引擎视觉小说做**英化**补丁用的文本提取/回写工具。
本项目在它之上加了**简体中文**支持，其余保持原样。

## 和上游的区别

上游一个游戏只有一套码表：英化补丁**不改码表**，日文版与英文版共用
同一份 `resources/rnd/charset.utf8`。而简体中文码表从 **3020 扩到 4550 字符**，
放不进同一资源目录，所以拆成两个「游戏」条目（**资源目录名即码表所在目录**）：

| game | 码表 | 用途 |
|---|---|---|
| `rnd` | 3020 字符（日文原版，**与上游一致**） | 提取日文原版脚本 |
| **`rndzh`** | **4550 字符**（简体中文，**本 fork 新增**） | 提取 / 回写中文译文 |

### 中文管线的三处调整

上游逻辑对英文补丁是对的，但用在中文码表上会产生可见 bug。
三处都**只对 `rndzh` 生效**（`GameDef::chinese_pipeline` 开关），`rnd` 不受影响：

| 文件 | 改动 | 原因 |
|---|---|---|
| `text.rs` | 半角空格不转全角 U+3000 | 中文码表里 U+3000 走汉字字形步进，`Mr. Pleiades` 两侧会出现一个汉字宽的间隔 |
| `lib.rs` | 禁用「底稿含全角字母数字 → 新文本整行转全角」 | 英文底稿会命中 755 行 twipo 推文，把 `@B_TITOR` 变成全角 `＠Ｂ＿ＴＩＴＯＲ` |
| `lib.rs` | 全半角按**字面**比较（上游先归一化再比） | 否则底稿 U+3000 与译文半角空格被判「相同」而跳过重写，旧的全角空格字节残留 |

## 用法

```bash
sc3tools extract-text "mes00.cpk/*.msb" rnd      # 提日文原版脚本
sc3tools extract-text "enscript/*.msb" rndzh     # 提中文译文
sc3tools replace-text "cnscript/*.msb.txt" rndzh # 回写中文
```

输出放在输入文件同级的 `txt/` 子目录。回写是**就地改写**脚本文件；
文本与脚本按文件名 stem 配对（`<name>.msb` 配 `<name>.msb.txt`）。

## 构建

```bash
cargo build --release      # 产物 target/release/sc3tools.exe
```

⚠️ 码表是 `rust-embed` **编译期**打进 exe 的（`#[folder = "resources/"]`，
**整目录**打包）。改码表、或增删 `resources/` 下任何文件，都必须重编，
直接跑旧 exe 无效。

## 改动清单与验证

完整改动集：`git diff 6ba9278a`。细节见 **[FORK-NOTES.md](FORK-NOTES.md)**。

改完工具应跑汉化仓库里的两道门禁（`scripts/diagnostics/`）：

- **A/B 对照**：966 个 msb（日文 mes00/mes01 各 322 + 中文 322）逐一比对
  「提取产物 + 回写产物」，与改动前的旧工具**逐字节一致**。
- **反向验证**：证明三处开关是活的（两条管线产出确实不同）。

## 许可

沿用上游 MIT 许可，版权声明见 [LICENSE](LICENSE)（原样保留）。

---

## 附：上游 sc3tools 简介

> 以下摘自上游 README，供了解这个工具的全貌。**上游支持的其它游戏
> 本 fork 原样保留**（`sghd` / `cc` / `rn` / `sg0` / `sglbp` / `cclcc` 等），
> 只是本项目用不到。

A CLI tool for extracting and modifying text in `.scx` and `.msb` scripts found in
visual novels based on the MAGES. engine. It is meant to be a replacement for the old,
overly complicated tool which had the same name and was part of the now-abandoned
[SciAdv.Net project](https://github.com/CommitteeOfZero/SciAdv.Net).

**Supported games**（上游）：STEINS;GATE (Steam)、CHAOS;HEAD Love Chu☆Chu!、
ROBOTICS;NOTES ELITE、STEINS;GATE: Linear Bounded Phenogram、CHAOS;CHILD、
STEINS;GATE 0、CHAOS;CHILD Love Chu☆Chu!!、ROBOTICS;NOTES DaSH
（本 fork 另加 **ROBOTICS;NOTES DaSH (简体中文)** = `rndzh`）。

**Usage**：运行 `./sc3tools` 查看命令列表与各游戏别名（如 `sg0`）；
`./sc3tools help <command>` 查看具体命令帮助。
