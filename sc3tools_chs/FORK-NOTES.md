# FORK-NOTES —— ROBOTICS;NOTES DaSH 简体中文汉化专用改版

**本目录（`sc3tools_chs/`）是为机器人笔记 DaSH 汉化改过的版本，不是上游原件。**

| | |
|---|---|
| **用途** | **ROBOTICS;NOTES DaSH**（MAGES/5pb，Steam 版）**简体中文汉化补丁**的文本工具 |
| **汉化项目** | [Syun1524/RND_Chinese](https://github.com/Syun1524/RND_Chinese) |
| **fork 自** | [CommitteeOfZero/sc3tools](https://github.com/CommitteeOfZero/sc3tools) |
| **基准提交** | `6ba9278a`（2025-05-22，"Polished charset"） |
| **本分支** | `rnd-chinese` |
| **改动** | 3 个源文件 + 新增 `resources/rndzh/` 码表 |

- 独立 fork 仓库：<https://github.com/Kurashift/sc3tools_chs>（分支 `rnd-chinese`）
- `git diff 6ba9278a` 即为本项目的完整改动集
- **上游没有 `rndzh`**。若你要处理日文原版脚本，用上游自带的 `rnd` 即可
  （本 fork 的 `rnd` 与上游行为完全一致）

## 改了什么

上游一个游戏只有一套码表：他们的英化补丁**不改码表**，日文版与英文版
共用同一份 `resources/rnd/charset.utf8`。本汉化项目的简体中文码表从
**3020 扩到 4550 字符**，放不进同一资源目录，故拆成两个「游戏」条目
（**资源目录名即码表所在目录**）：

| game | 资源目录 | 码表 | 用途 |
|---|---|---|---|
| `rnd` | `resources/rnd/` | 3020 字符（日文原版，**未改动**） | 提取日文原版脚本 |
| `rndzh` | `resources/rndzh/` | **4550 字符**（简体中文，本 fork 新增） | 提取 / 回写中文译文 |

### 三处代码改动（`chinese_pipeline`）

上游逻辑对英文补丁是对的，但用在中文码表上会产生可见 bug。
三处改动都**只对 `rndzh` 生效**（`GameDef::chinese_pipeline` 开关），
`rnd` 保持上游行为：

| 文件 | 改动 | 原因 |
|---|---|---|
| `text.rs` | 半角空格不转全角 U+3000 | 中文码表里 U+3000 走汉字字形步进，会让 `Mr. Pleiades` 两侧出现一个汉字宽的间隔 |
| `lib.rs` | 禁用「底稿含全角字母数字 → 新文本整行转全角」 | 英文底稿会命中 755 行 twipo 推文，把 `@B_TITOR` 变成全角 `＠Ｂ＿ＴＩＴＯＲ` |
| `lib.rs` | 全半角按**字面**比较（上游先归一化再比） | 否则底稿 U+3000 与译文半角空格被判「相同」而跳过重写，旧的全角空格字节残留 |

## 用法

```bash
sc3tools extract-text "mes00.cpk/*.msb" rnd      # 提日文
sc3tools extract-text "enscript/*.msb" rndzh     # 提中文
sc3tools replace-text "cnscript/*.msb.txt" rndzh # 回写中文
```

## 构建

```
cargo build --release      # 产物 target/release/sc3tools.exe
```

⚠️ 码表是 `rust-embed` **编译期**打进 exe 的（`#[folder = "resources/"]`，
**整目录**打包）。所以改码表、或增删 `resources/` 下任何文件，都必须重编，
直接跑旧 exe 无效。

## 验证

汉化仓库 `scripts/diagnostics/` 下有两道门禁（改工具后应跑）：

- **A/B 对照**：966 个 msb（日文 mes00/mes01 各 322 + 中文 322）逐一比对
  「提取产物 + 回写产物」，与改动前的旧工具**逐字节一致**。
- **反向验证**：证明三处开关是活的（两条管线产出确实不同）。

## 许可

沿用上游 MIT 许可，版权声明见 `LICENSE`（原样保留）。
