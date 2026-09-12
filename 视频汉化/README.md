# 视频汉化（USM 重定向）

本目录存放替换游戏内影片的成品 USM。影片替换走 LanguageBarrier 的
`fileRedirection`（`mgsFileOpenHook` 对 movie 归档同样生效），**不改视频文件本身**、
不需要重打 movie.cpk。

## movie_dar020.usm

替换游戏内 `movie_dar020.usm`（达鲁事件短片，258 帧 @29.97fps，1080p）。
视频画面由外部剪辑重编码（H.264 → MPEG-2 MP@HL），音轨沿用原片 ADX
（48kHz 立体声，逐字节未动）。

### 安装该替换需要成套改三处（缺一不可）

1. `languagebarrier/c0data/movie_dar020.usm` —— 本目录同名文件拷入；
2. `languagebarrier/c0data.cls` —— **末尾追加**一行 `movie_dar020.usm`
   （追加安全，它的行号 78 就是 c0data fileId；**绝不能插在中间**，
   fileRedirection 存的是行号，插行会让后面全部错位）；
3. `patchdef.json → base.fileRedirection` 增加条目：

```json
"movie": { "35": 78 }
```

键 `35` = movie.cpk 目录表里 `movie_dar020.usm` 的 ID（用
`scripts/cpk_toc.py <游戏目录>/movie.cpk` 可查任意影片的 ID）；
值 `78` = c0data.cls 里 `movie_dar020.usm` 的行号（0 起）。

## 重封工具

- `scripts/cpk_toc.py` —— 读 MAGES Steam 版 CPK（TOC 被乘法 LCG
  `key=0x655F; key*=0x4115` 逐字节 XOR 混淆，块=`tag(4)+u32 0+u64LE size+数据`），
  输出文件名 → ID 映射。
- `scripts/build_usm.py` —— 用原 USM 的容器结构重封新视频：
  保留全部元数据块与逐帧 24 字节前置头（每块恰一帧、帧号不变故可复用），
  只替换帧数据、更新块长字段、重算 `VIDEO_SEEKINFO`（每 13 帧一条的
  文件绝对偏移索引）和 CRID 里的 filesize/avbps。音轨块整段原样复制。
  ⚠️ 当前版本写死了 dar020 的参数（258 帧/20 行 seek/CRID 旧值），
  换别的影片要先改这些常量并重新核对结构。

## 已验证 / 待验证

- 已验证：块遍历精确到 EOF、分流出视频=重编码 ES、音轨=原片逐字节一致、
  ffmpeg 全帧零错误解码、seek 表 20 条全部指向 `@SFV` 块魔数。
- 待验证：游戏内实际播放（dar020 触发场景较靠后）。重定向不命中时游戏
  回落播放原片，无副作用。
