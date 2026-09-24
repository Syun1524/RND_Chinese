// RNDZhLauncher — ROBOTICS;NOTES DaSH 简体中文补丁 启动器
// 原生 Win32 + GDI+，不依赖 Qt。布局：左品牌 / 右选项。
//
// 职责：
//   1. 读写 %LOCALAPPDATA%\Committee of Zero\RNDSteam\config.json 的开关
//   2. 「换装」= 全员切换到 和服/泳装/体操服/猫耳 四套主题之一（写 zzOutfitSet）
//   3. 「启用 DXVK」= 对游戏根目录下的 d3d9/d3d10/... 做改名（带/不带 .dll）
//   4. 「开始游戏」= 以 "Game.exe roboticsnotesd EN" 拉起游戏
//
// 编译：见 build_launcher.bat
//
// 换装写 zzOutfitSet（四套并列：和服/泳装/体操服/猫耳），不再用 CoZ 的 swimsuitPatch
// —— 那只表达"泳装"一种，且覆盖范围已被本机制完全包住（见 scripts/add_outfit_sets.py，
// 该脚本会把 swimsuitPatch 从 patchdef 里删掉）。
//
// 另外：换装核对（把某角色单独指向某套）是开发者工具，见 RNDZhOutfitTool.cpp。
// 它写的 zz_<角色>_<变体> 键排序在 zzOutfitSet 之后，所以能压过主题单独固定某个角色。

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <windowsx.h>
#include <objidl.h>
#include <gdiplus.h>
#include <shlobj.h>
#include <shellapi.h>
#include <tlhelp32.h>
#include <wininet.h>
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <cwchar>
#include <cstring>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "wininet.lib")

// 图标：编译时把 game.ico 嵌入 exe 资源（ID 101），窗口/任务栏都用它。
// 资源文件 launcher.rc 引用，见 build_launcher.bat。

// 注意：启动器【不】导入 DINPUT8.dll。
// 补丁的 dinput8.dll 是代理 DLL，由 Game.exe 自身（它静态导入 DINPUT8.dll）加载，
// 生效位置是「分号后片段同名」的子目录（路径含 `;` 时加载器按分号切开、把片段
// 当相对目录搜）；无分号的目录则直接用根目录那份。详见 AGENTS.md「重大发现」。
// 无论如何都与启动器无关。

using namespace Gdiplus;

// ───────────────────────── 配置（颜色/布局常量） ─────────────────────────
// 配色与安装器/卸载器保持一致（纯白极简）：白底、浅灰边框、深灰字、蓝色主按钮。
// 三个窗口是一套东西，色调必须统一 —— 启动器以前是深色霓虹风，跟安装器对不上。
//
// 布局：左栏是主题图（主视觉），右栏是选项。
// **左栏宽度按主题图的实际比例算**（见 ApplyThemeGeometry）：图有多宽，栏就多宽，
// 图按栏高等比缩放、正好铺满，不变形也不留黑边。换一张不同比例的图也不用改代码。
static int WIN_H  = 500;      // 窗口高（逻辑像素）——固定值，由它反推左栏宽
static int LEFT_W = 375;      // 左栏宽（初值是 540x720 算出来的，运行时按实际图覆盖）
static int WIN_W  = 800;      // 窗口宽 = 左栏 + 右栏(425)
static const int RIGHT_W = 425;   // 右栏固定宽度（放选项）

// 产品版本。⚠ 改版本要同步三处：这里、成品ing/setup/src/RNDZhSetup.cpp 的 VER、
// 成品ing/setup/build/build_installer.py 的 VERSION（决定包文件名）。
static const wchar_t* VER = L"1.3";
// 产品标题（用户要求结尾带版本号）。窗口标题用这一份（游戏窗口标题不再改写）。
static const std::wstring APP_TITLE =
    std::wstring(L"ROBOTICS;NOTES DaSH 简体中文 AI人工精校版 v") + VER;

static const Color
  C_BG      (255, 255, 255, 255),   // 窗口底
  C_PANEL   (255, 245, 246, 248),   // 悬停底
  C_FIELD   (255, 255, 255, 255),   // 输入/下拉底色
  C_BORDER  (255, 216, 220, 227),   // 边框
  C_TEXT    (255,  31,  35,  40),   // 正文
  C_DIM     (255, 107, 114, 128),   // 次要文字
  C_MUTED   (255, 156, 163, 175),   // 更淡（禁用/提示）
  C_ACCENT  (255,  11, 107, 203),   // 主按钮 / 勾选态
  C_ACCENTH (255,  10,  95, 176),   // 主按钮悬停
  C_HILITE  (255, 236, 240, 245),   // 下拉项悬停底
  C_SEL     (255, 226, 238, 252),   // 下拉项"当前选中"底
  C_HOVER   (255, 233, 237, 242),   // 悬停底（下拉项/主按钮）——要比 C_HILITE 明显，
                                    // 否则玩家感觉"没有反馈"（2026-09-13 用户反馈）
  C_WHITE   (255, 255, 255, 255),
  C_DOT     (255, 226,  61,  54);   // 更新小红点（「检查更新」按钮右上角）

// ── DPI 缩放 ──
// 三个 exe 以前都没声明 DPI 感知，系统 125% 缩放时 Windows 会把整个界面
// 位图拉伸 1.25 倍 —— 文字发虚、边缘发糊（实测客户区 1125x775 而逻辑只有 900x620）。
// 现在声明「系统 DPI 感知」，并把绘制坐标统一乘 S：界面物理尺寸不变，但变清晰。
// 实现上用 GDI+ 的 ScaleTransform 一次性缩放坐标系，不用逐个坐标乘 ——
// 布局常量保持逻辑值，看源码仍能直接算。
static float S = 1.0f;                 // 缩放系数 = 窗口DPI / 96
static inline float unscale(int v) { return (float)v / S; }   // 鼠标坐标 → 逻辑坐标

// 设置项（「cosplay 模式」是下拉，不在这组复选里）
//
// ★ 标签措辞原则：功能就是功能，直说做什么；不写"（而不是键盘）""也可……"
//   这类绕弯解释，也不写实现术语。文案都对着 LB 源码的真实行为核过：
//
//   scrollDownToAdvanceText  → CustomInputRND.cpp:1808
//       `ScrollDownToAdvanceText && (mouseButtons & MouseScrollWheelDown) → PAD1A`
//       即**滚轮向下**推进文本。以前标签写"滚轮向上推进文本"是错的 ——
//       既与配置键名（scroll**Down**ToAdvanceText）相反，也与自己下面的灰字矛盾。
//   disableScrollDownToCloseBacklog → CustomInputRND.cpp:1211
//       `ScrollDownToCloseBacklog && 已翻到底 && ...(MouseScrollWheelDown) → PAD1B`
//       （PAD1B=返回）即**滚轮向下**在历史记录翻到底部时退出记录。
//   两个滚轮项的标签本身就是那句话，不再配灰字（2026-09-13 用户拍板：
//   「也可点左键或 Auto」这类补充是好笨的写法）。
enum Opt { OPT_MOUSE=0, OPT_SCROLL_ADV, OPT_SCROLL_CLOSE, OPT_DXVK, OPT_COUNT };
static const wchar_t* OPT_LABEL[OPT_COUNT] = {
  L"鼠标控制", L"滚轮向下推进文本", L"滚轮向下可退出历史记录", L"启用 DXVK"
};
static const wchar_t* OPT_KEY[OPT_COUNT] = {
  L"mouseControls", L"scrollDownToAdvanceText", L"disableScrollDownToCloseBacklog",
  L"enableDxvk"
};
static const wchar_t* OPT_HINT[OPT_COUNT] = {
  L"开启原版不支持的鼠标操作功能",
  L"",
  L"",
  L"用 Vulkan 转译渲染，缓解新显卡上的兼容问题"
};
// 注意：disableScrollDownToCloseBacklog 在配置里是"禁用"语义。
// 界面写正向「滚轮向下可退出历史记录」，勾选=启用该功能=写 false。
static bool OPT_INVERT[OPT_COUNT] = { false, false, true, false };
static bool OPT_DEF[OPT_COUNT]    = { true,  true,  true, false };

// ── cosplay 模式（界面名）──
// 玩家看到的叫「cosplay 模式」；实现上是全员换一套衣服。
// 值必须与 patchdef.json -> settings.zzOutfitSet.choices 的键一致。
// none = 保持原样（各角色穿默认服）。
static const wchar_t* OUTFIT_LABEL[5] = { L"原版", L"和服", L"泳装", L"体操服", L"猫耳" };
static const wchar_t* OUTFIT_VALUE[5] = { L"none", L"kimono", L"swimsuit", L"gym", L"nekomimi" };
static const int OUTFIT_N = 5;

// 下拉框下方那行灰字。**这是刻意写技术说明的地方**：
// 玩家问"为什么换个装就能改立绘"时，这行给出准确答案，
// 而不是"全员换成这套服装（各角色只换自己有的那套）"那种把玩家当傻子的废话。
//
// 实现细节（对着源码核过，别凭印象写）：
//   LB 的 mgsFileOpenHook 拦下模型归档的打开请求，按 fileIdRemap 把
//   「默认服装的 model fileId」重指向「目标服装的 fileId」；
//   命中即 return，不落到 fileRedirection。所以这是运行时重定向，不改任何游戏文件。
//   （原来这里有一行灰色小字把这件事写给玩家看，2026-09-24 用户要求删掉 ——
//     "cosplay 模式和影片字幕使用率不高"，而且这类实现说明对玩家没有用。
//     技术细节留在这条注释里备查。）

static const wchar_t* SUBS_LABEL[3] = { L"卡拉OK字幕 + 翻译", L"仅卡拉OK字幕", L"仅翻译" };
static const wchar_t* SUBS_VALUE[3] = { L"all", L"karaonly", L"tlonly" };

// ── 画面（对应原版启动器 Screen Setting 的两项）──
// 游戏内设置菜单里也有这两项，但一旦把分辨率设成显示器不支持的档位就会黑屏、
// 连菜单都进不去 —— 这里给一个"救急入口"（原版启动器的 Screen Setting 就是这作用）。
// 值必须与 config.dat 里的枚举一致（见 ScreenCfgRead/Write 的注释）：
//   displayMode: 0 = 窗口, 1 = 全屏
//   resolution : 0 = 1024*576, 1 = 1280*720, 2 = 1920*1080
// 分辨率文案照原版用星号（`1024*576`），玩家对照攻略时不会困惑。
static const wchar_t* SCRN_LABEL[2] = { L"窗口", L"全屏" };
static const wchar_t* RES_LABEL[3]  = { L"1024*576", L"1280*720", L"1920*1080" };
static const int SCRN_N = 2, RES_N = 3;

static const wchar_t* SET_KEY = L"zzOutfitSet";

struct State {
  bool on[OPT_COUNT];
  int  subs;            // 0/1/2
  int  outfit;          // 0..4
  int  scrn;            // 0 = 窗口 / 1 = 全屏
  int  res;             // 0..2（1024*576 / 1280*720 / 1920*1080）
  bool scrnOk = false;  // config.dat 读到了吗（读不到就别写，免得凭空造一个文件）
  int  openRow = -1;    // 展开的设置行（-1 全收起）—— 手风琴：同时只开一行
  int  hot = -1;        // 悬停项，用与 press 同一套 id
  int  press = -1;
} st;

static HWND g_hwnd;
// 从 exe 资源加载 256x256 图标（RT_ICON 里最大的一个），供左侧品牌区绘制。
static Gdiplus::Bitmap* g_iconBmp = nullptr;
static void LoadAppIconFromResource() {
  if (g_iconBmp) return;
  int bestW = 0;
  for (int id = 1; id <= 8; id++) {
    HRSRC hr = FindResourceW(nullptr, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(3));
    if (!hr) continue;
    DWORD sz = SizeofResource(nullptr, hr);
    HGLOBAL hg = LoadResource(nullptr, hr);
    void* p = LockResource(hg);
    if (!p) continue;
    HICON ico = CreateIconFromResourceEx((PBYTE)p, sz, TRUE, 0x00030000, 0, 0, LR_DEFAULTCOLOR);
    if (!ico) continue;
    ICONINFO ii = { 0 };
    GetIconInfo(ico, &ii);
    BITMAP bm = { 0 };
    GetObject(ii.hbmColor, sizeof(bm), &bm);
    int W = bm.bmWidth, H = bm.bmHeight;
    if (W > bestW) {
      Gdiplus::Bitmap* b = new Gdiplus::Bitmap(W, H, PixelFormat32bppARGB);
      Graphics gg(b);
      HDC hdc = gg.GetHDC();
      DrawIconEx(hdc, 0, 0, ico, W, H, 0, nullptr, DI_NORMAL);
      gg.ReleaseHDC(hdc);
      if (b->GetLastStatus() == Ok) {
        if (g_iconBmp) delete g_iconBmp;
        g_iconBmp = b; bestW = W;
      } else delete b;
    }
    if (ii.hbmColor) DeleteObject(ii.hbmColor);
    if (ii.hbmMask) DeleteObject(ii.hbmMask);
    DestroyIcon(ico);
  }
}
// 左侧主题图（资源 ID 102，RCDATA 里是一份 JPEG）。
// 直接从内存流解码，不需要外部文件 —— 启动器被拷来拷去也不会丢图。
static Gdiplus::Bitmap* g_themeBmp = nullptr;

// 按主题图的**实际比例**反推左栏宽度与窗口尺寸。
// 换一张不同比例的图（比如 16:9 的宽幅主视觉）不用改任何常量 —— 这里会自己算。
// 必须在建窗口之前调用（窗口尺寸取决于它）。
static void ApplyThemeGeometry() {
  if (g_themeBmp) {
    int iw = (int)g_themeBmp->GetWidth();
    int ih = (int)g_themeBmp->GetHeight();
    if (iw > 0 && ih > 0) {
      // 图按「窗口高」等比缩放到左栏宽；四舍五入免得差一像素露白边
      LEFT_W = (int)((double)WIN_H * iw / ih + 0.5);
    }
  }
  WIN_W = LEFT_W + RIGHT_W;
}

static FontFamily* g_ff = nullptr;   // 从系统字体取（中文正文）
// 主按钮用的字体：**微软雅黑 Bold**（用户 2026-09-13 指定）。
// 按钮文字改成中文「开始游戏」后，原来那套拉丁字体（Bahnschrift）**画不出汉字**
// —— GDI+ 遇到缺字会退化成方块/别的字体，所以必须换成能画汉字的中文字体。
// 用「Microsoft YaHei」而不是「Microsoft YaHei UI」：前者有真正的 Bold 字面
// （msyhbd.ttc），后者在 GDI+ 下加粗多为合成。找不到再依次退。
static FontFamily* g_ffTech = nullptr;
static std::wstring g_dir;           // 启动器所在目录

static void LoadThemeImage() {
  HRSRC hr = FindResourceW(nullptr, MAKEINTRESOURCEW(102), RT_RCDATA);
  if (!hr) return;
  DWORD sz = SizeofResource(nullptr, hr);
  HGLOBAL hg = LoadResource(nullptr, hr);
  if (!hg || !sz) return;
  void* p = LockResource(hg);
  if (!p) return;
  // GDI+ 需要一个 IStream：把资源字节包成内存流交给 Bitmap
  HGLOBAL hMem = GlobalAlloc(GMEM_MOVEABLE, sz);
  if (!hMem) return;
  void* dst = GlobalLock(hMem);
  memcpy(dst, p, sz);
  GlobalUnlock(hMem);
  IStream* is = nullptr;
  if (SUCCEEDED(CreateStreamOnHGlobal(hMem, TRUE, &is)) && is) {
    Gdiplus::Bitmap* b = new Gdiplus::Bitmap(is);
    if (b->GetLastStatus() == Ok) g_themeBmp = b;
    else delete b;
    is->Release();
  } else {
    GlobalFree(hMem);
  }
}

// ───────────────────────── 小工具 ─────────────────────────
static std::wstring ExeDir() {
  wchar_t buf[MAX_PATH]; GetModuleFileNameW(nullptr, buf, MAX_PATH);
  std::wstring s(buf); size_t p = s.find_last_of(L'\\');
  return p == std::wstring::npos ? L"." : s.substr(0, p);
}

static bool FileExists(const std::wstring& p) {
  return GetFileAttributesW(p.c_str()) != INVALID_FILE_ATTRIBUTES;
}

static std::wstring Utf8ToWide(const std::string& s) {
  if (s.empty()) return L"";
  int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
  std::wstring w(n, 0);
  MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), &w[0], n);
  return w;
}

static std::string WideToUtf8(const std::wstring& w) {
  if (w.empty()) return "";
  int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
  std::string s(n, 0);
  WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), &s[0], n, nullptr, nullptr);
  return s;
}

// 读文件为 UTF-8 → wstring 简易解析（只取顶层平铺键值）
static std::map<std::wstring, std::wstring> LoadFlatJson(const std::wstring& path) {
  std::map<std::wstring, std::wstring> m;
  std::ifstream f(path, std::ios::binary);
  if (!f) return m;
  std::stringstream ss; ss << f.rdbuf();
  std::string s = ss.str();
  size_t i = 0;
  while (i < s.size()) {
    size_t q1 = s.find('"', i);
    if (q1 == std::string::npos) break;
    size_t q2 = s.find('"', q1 + 1);
    if (q2 == std::string::npos) break;
    size_t colon = s.find(':', q2 + 1);
    if (colon == std::string::npos) break;
    std::string key = s.substr(q1 + 1, q2 - q1 - 1);
    size_t j = colon + 1;
    while (j < s.size() && isspace((unsigned char)s[j])) j++;
    size_t vstart = j; bool instr = false;
    if (j < s.size() && s[j] == '"') { instr = true; j++; }
    while (j < s.size()) {
      if (instr) { if (s[j] == '\\') { j += 2; continue; } if (s[j] == '"') { j++; break; } }
      else { if (s[j] == ',' || s[j] == '}' || s[j] == '\n') break; }
      j++;
    }
    m[Utf8ToWide(key)] = Utf8ToWide(s.substr(vstart, j - vstart));
    size_t nxt = s.find(',', j);
    i = (nxt == std::string::npos) ? s.size() : nxt + 1;
    if (s.find('}', j) != std::string::npos && s.find('}', j) < nxt) break;
  }
  return m;
}

static std::wstring ConfigPath() {
  wchar_t* appdata = nullptr;
  SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &appdata);
  std::wstring p = appdata ? appdata : L"";
  if (appdata) CoTaskMemFree(appdata);
  p += L"\\Committee of Zero\\RNDSteam";
  return p;
}

static void EnsureDir(const std::wstring& dir) {
  SHCreateDirectoryExW(nullptr, dir.c_str(), nullptr);
}

// ── 画面设置：读写游戏的 config.dat ──
// 原版启动器的 Screen Setting 改的就是这个文件。游戏自己也读写它（游戏内设置菜单
// 里的全屏/分辨率就是这两项），所以格式必须完全一致。
//
// ★ 只能**原位改 4 字节**，绝不整文件重写：
//   实测日文存档 108 字节、英文存档 76 字节（长度不同），文件里还有控制器 GUID、
//   窗口坐标、影片品质、语言等字段。整写会截掉后面的字段。
//
// 字段偏移（与 CoZ 开源启动器 realboot 的 GameConfig 逐字段核对过，且在本机
// 两份实际存档上验证了取值合理）：
//   +0x00  uint32（未知/版本）
//   +0x04  控制器 GUID（40 字节）
//   +0x2C  width       窗口宽
//   +0x30  height      窗口高
//   +0x34  displayMode 0 = 窗口, 1 = 全屏
//   +0x38  resolution  0 = 1024*576, 1 = 1280*720, 2 = 1920*1080
//   +0x3C  startWindowX    +0x40  startWindowY
//   +0x44  movieQuality    +0x48  language
static const long kOffDisplayMode = 0x34, kOffResolution = 0x38;
static const long kCfgMinSize = 0x3C;   // 至少要够到 displayMode/resolution

static const wchar_t* DetectLang();     // 定义在后面（要用 boot.bat 判语言）

static std::wstring ConfigDatPath() {
  wchar_t* docs = nullptr;
  if (SHGetKnownFolderPath(FOLDERID_Documents, 0, nullptr, &docs) != S_OK) return L"";
  std::wstring p = docs;
  CoTaskMemFree(docs);
  // 语言子目录与游戏一致（jpn/eng）—— 读 boot.bat 判定，和启动游戏时同一个来源
  const wchar_t* lang = DetectLang();
  p += L"\\My Games\\mages_steam\\Robotics Notes DASH\\";
  p += (_wcsicmp(lang, L"JP") == 0) ? L"jpn" : L"eng";
  p += L"\\config.dat";
  return p;
}

static void LoadScreenCfg() {
  std::wstring p = ConfigDatPath();
  std::ifstream f(p, std::ios::binary);
  if (!f) return;                                  // 没装过/没跑过游戏 → 保持默认
  f.seekg(0, std::ios::end);
  long sz = (long)f.tellg();
  if (sz < kCfgMinSize) return;
  unsigned char buf[8] = { 0 };
  f.seekg(kOffDisplayMode);
  f.read((char*)buf, 8);
  if (f.gcount() != 8) return;
  unsigned dm = 0, rs = 0;
  memcpy(&dm, buf, 4); memcpy(&rs, buf + 4, 4);
  st.scrn = (dm == 1) ? 1 : 0;
  st.res  = (rs < (unsigned)RES_N) ? (int)rs : 0;
  st.scrnOk = true;
}

static void SaveScreenCfg() {
  if (!st.scrnOk) return;                          // 没读到过就不写，别凭空造文件
  std::wstring p = ConfigDatPath();
  // ★ 用 r+b（读写、不截断）而不是 wb —— 只覆盖这 4 个字节，其余原样保留。
  std::fstream f(p, std::ios::binary | std::ios::in | std::ios::out);
  if (!f) return;
  f.seekg(0, std::ios::end);
  if ((long)f.tellg() < kCfgMinSize) return;
  unsigned dm = (st.scrn == 1) ? 1u : 0u;
  unsigned rs = (unsigned)st.res;
  f.seekp(kOffDisplayMode);
  f.write((const char*)&dm, 4);
  f.write((const char*)&rs, 4);
  f.flush();
}

// 写配置：整份重写，未知键原样带上。
// 换装核对工具写的 zz_<角色>_<变体> 属于未知键 → 会被保留，
// 玩家在这里改开关不会把开发工具的当前核对项清掉。
static void SaveConfig() {
  std::wstring dir = ConfigPath();
  EnsureDir(dir);
  std::wstring path = dir + L"\\config.json";

  auto old = LoadFlatJson(path);

  std::wstringstream out;
  out << L"{\n";
  auto b = [](bool v) { return v ? L"true" : L"false"; };
  bool first = true;
  auto emit = [&](const std::wstring& k, const std::wstring& v) {
    if (!first) out << L",\n";
    first = false;
    out << L"    \"" << k << L"\": " << v;
  };
  emit(L"__schema_version", L"5");
  for (int i = 0; i < OPT_COUNT; i++) {
    bool v = st.on[i];
    if (OPT_INVERT[i]) v = !v;            // 界面正向 → 配置语义
    emit(OPT_KEY[i], b(v));
  }
  emit(SET_KEY, std::wstring(L"\"") + OUTFIT_VALUE[st.outfit] + L"\"");
  emit(L"karaokeSubs", std::wstring(L"\"") + SUBS_VALUE[st.subs] + L"\"");
  emit(L"showAllSettings", L"true");
  emit(L"rneMouseControls", L"true");
  static const wchar_t* MINE[] = { L"__schema_version", L"mouseControls",
    L"scrollDownToAdvanceText", L"disableScrollDownToCloseBacklog",
    SET_KEY, L"enableDxvk", L"karaokeSubs", L"showAllSettings", L"rneMouseControls" };
  for (auto& kv : old) {
    bool mine = false;
    for (auto m : MINE) if (kv.first == m) { mine = true; break; }
    if (mine || kv.first.empty()) continue;
    // 丢掉除 zzOutfitSet 外的所有 zz* 键：
    //  - zz_<角色>_<变体>：核对工具的固定项。它排序在 zzOutfitSet 之后，会把对应
    //    角色压过主题（选了「和服」但那几个角色不换），玩家的"一键切换"就废了。
    //  - swimsuitPatch：CoZ 的老键，patchdef 里已删除（四套并列，泳装不再特殊）。
    //  - zzOutfitOverride：更早的单选机制残留。
    // 这三者都是开发/历史状态，不该跟着成品走。
    if (kv.first.rfind(L"zz", 0) == 0 && kv.first != SET_KEY) continue;
    if (kv.first == L"swimsuitPatch") continue;
    emit(kv.first, kv.second);
  }
  out << L"\n}";

  std::string u8 = WideToUtf8(out.str());
  std::ofstream f(path, std::ios::binary | std::ios::trunc);
  f.write(u8.data(), u8.size());
}

static void LoadConfig() {
  std::wstring path = ConfigPath() + L"\\config.json";
  auto m = LoadFlatJson(path);
  auto getb = [&](const wchar_t* k, bool dflt) {
    auto it = m.find(k); if (it == m.end()) return dflt;
    return it->second.find(L"true") != std::wstring::npos;
  };
  for (int i = 0; i < OPT_COUNT; i++) {
    bool v = getb(OPT_KEY[i], OPT_DEF[i]);
    if (OPT_INVERT[i]) v = !v;
    st.on[i] = v;
  }
  st.subs = 0;
  auto it = m.find(L"karaokeSubs");
  if (it != m.end())
    for (int i = 0; i < 3; i++)
      if (it->second.find(SUBS_VALUE[i]) != std::wstring::npos) st.subs = i;

  st.outfit = 0;                          // 默认「原版」，不换装
  auto sit = m.find(SET_KEY);
  if (sit != m.end())
    for (int i = 0; i < OUTFIT_N; i++)
      if (sit->second.find(OUTFIT_VALUE[i]) != std::wstring::npos) { st.outfit = i; break; }

  // 画面设置不在 config.json 里，读游戏自己的 config.dat（见 LoadScreenCfg）
  LoadScreenCfg();
}

// DXVK：d3d9/d3d10/d3d10_1/d3d10core/d3d11/dxgi 带/不带 .dll
// 必须与 Game.exe 同目录（游戏根目录）才会被 Windows 加载。
static const wchar_t* DXVK_NAMES[6] = { L"d3d9", L"d3d10", L"d3d10_1", L"d3d10core", L"d3d11", L"dxgi" };

static void ApplyDxvk(bool enable) {
  std::wstring dir = g_dir;
  for (int i = 0; i < 6; i++) {
    std::wstring base = dir + L"\\" + DXVK_NAMES[i];
    std::wstring withdll = base + L".dll", nodll = base;
    if (enable) { if (FileExists(nodll) && !FileExists(withdll)) MoveFileW(nodll.c_str(), withdll.c_str()); }
    else        { if (FileExists(withdll) && !FileExists(nodll)) MoveFileW(withdll.c_str(), nodll.c_str()); }
  }
}

// ───────────────────────── 绘制 ─────────────────────────
static Font* F(float sz, bool bold = false) {
  static std::map<std::pair<int,bool>, Font*> cache;
  auto key = std::make_pair((int)(sz * 10), bold);
  auto it = cache.find(key);
  if (it != cache.end()) return it->second;
  Font* f = new Font(g_ff, sz, bold ? FontStyleBold : FontStyleRegular, UnitPixel);
  cache[key] = f; return f;
}

// 主按钮字（g_ffTech = 微软雅黑），同样缓存
static Font* FTech(float sz, bool bold = true) {
  static std::map<std::pair<int,bool>, Font*> cache;
  auto key = std::make_pair((int)(sz * 10), bold);
  auto it = cache.find(key);
  if (it != cache.end()) return it->second;
  Font* f = new Font(g_ffTech, sz, bold ? FontStyleBold : FontStyleRegular, UnitPixel);
  cache[key] = f; return f;
}

static void FillRR(Graphics& g, const RectF& r, float rad, const Color& c) {
  GraphicsPath p;
  // ★ rad=0 不能走 AddArc：GDI+ 对零尺寸圆弧返回 InvalidParameter，
  //   整条路径作废 → FillPath 静默画不出任何东西。下拉第 1 项起的悬停高亮
  //   （圆角 0）就是这么"消失"的（2026-09-13 查实）。直角一律 AddRectangle。
  if (rad > 0.5f) {
    float d = rad * 2;
    p.AddArc(r.X, r.Y, d, d, 180, 90);
    p.AddArc(r.GetRight() - d, r.Y, d, d, 270, 90);
    p.AddArc(r.GetRight() - d, r.GetBottom() - d, d, d, 0, 90);
    p.AddArc(r.X, r.GetBottom() - d, d, d, 90, 90);
    p.CloseFigure();
  } else {
    p.AddRectangle(r);
  }
  SolidBrush b(c); g.FillPath(&b, &p);
}

static void StrokeRR(Graphics& g, const RectF& r, float rad, const Color& c, float w) {
  GraphicsPath p;
  if (rad > 0.5f) {
    float d = rad * 2;
    p.AddArc(r.X, r.Y, d, d, 180, 90);
    p.AddArc(r.GetRight() - d, r.Y, d, d, 270, 90);
    p.AddArc(r.GetRight() - d, r.GetBottom() - d, d, d, 0, 90);
    p.AddArc(r.X, r.GetBottom() - d, d, d, 90, 90);
    p.CloseFigure();
  } else {
    p.AddRectangle(r);
  }
  Pen pen(c, w); g.DrawPath(&pen, &p);
}

// 画一行文字。
//
// ★ wrapW > 0 时自动换行 —— 这是防"文案太长被窗口裁掉"的兜底。
//   以前固定传 RectF(x, y, 0, 0)，宽度 0 = 不约束，GDI+ 把整句画成一行，
//   超出部分被窗口边缘直接裁掉，看起来像文字凭空断掉（踩过：
//   「用 LanguageBarrier 重定向模型归档…」那句就出界了）。
//   需要的地方传可用宽度即可折行，不会再"看不到后半句"。
static void DrawTxtW(Graphics& g, const wchar_t* s, Font* f, const Color& c,
                     float x, float y, float wrapW, int align = 0) {
  SolidBrush b(c);
  StringFormat sf; sf.SetAlignment((StringAlignment)align);
  sf.SetLineAlignment(StringAlignmentNear);
  if (wrapW > 0) {
    // 中文没有空格，要显式允许"不按词断行"，否则 GDI+ 找不到断点就整句不折
    sf.SetFormatFlags(StringFormatFlagsLineLimit);
    g.DrawString(s, -1, f, RectF(x, y, wrapW, 0), &sf, &b);
  } else {
    g.DrawString(s, -1, f, RectF(x, y, 0, 0), &sf, &b);
  }
}
static void DrawTxt(Graphics& g, const wchar_t* s, Font* f, const Color& c, float x, float y, int align = 0) {
  DrawTxtW(g, s, f, c, x, y, 0, align);
}

// 在矩形内**水平+垂直居中**画一行字（按钮文字用）。
static void DrawTxtCentered(Graphics& g, const wchar_t* s, Font* f, const Color& c,
                            const RectF& r) {
  SolidBrush b(c);
  StringFormat sf;
  sf.SetAlignment(StringAlignmentCenter);
  sf.SetLineAlignment(StringAlignmentCenter);
  sf.SetFormatFlags(StringFormatFlagsNoWrap);
  g.DrawString(s, -1, f, r, &sf, &b);
}

// 勾选框（含对勾 / 空框）
static void DrawCheck(Graphics& g, const RectF& box, bool on, bool hot) {
  if (on) {
    FillRR(g, box, 5, C_ACCENT);
    Pen p(C_WHITE, 2.4f); p.SetStartCap(LineCapRound); p.SetEndCap(LineCapRound);
    g.DrawLine(&p, box.X + 5, box.Y + 11.5f, box.X + 9.5f, box.Y + 16);
    g.DrawLine(&p, box.X + 9.5f, box.Y + 16, box.X + 17.5f, box.Y + 5.5f);
  } else {
    FillRR(g, box, 5, C_FIELD);
    StrokeRR(g, box, 5, hot ? C_DIM : C_BORDER, 1.4f);
  }
}

// ── GitHub 标志（octicon mark-github，16x16 视图框）──
// ★ 本函数由 scripts/make_github_mark.py 从官方 SVG path 生成，**不要手改**；
//   要调整请改脚本里的 PATH 再重新生成。
// 单条闭合轮廓 + 非零环绕填充（FillModeWinding）形成中间镂空的猫形 ——
// 位图做不到这点（要么带透明遮罩，要么自己写扫描线填充），
// GraphicsPath 直接就能画对，而且任意缩放都清晰。
static void GithubMarkPath(GraphicsPath& p, float ox, float oy, float s) {
  p.SetFillMode(FillModeWinding);
  p.StartFigure();
  p.AddBezier(ox + s*8.f, oy, ox + s*3.58f, oy, ox, oy + s*3.58f, ox, oy + s*8.f);
  p.AddBezier(ox, oy + s*8.f, ox, oy + s*11.54f, ox + s*2.29f, oy + s*14.53f, ox + s*5.47f, oy + s*15.59f);
  p.AddBezier(ox + s*5.47f, oy + s*15.59f, ox + s*5.87f, oy + s*15.66f, ox + s*6.02f, oy + s*15.42f, ox + s*6.02f, oy + s*15.21f);
  p.AddBezier(ox + s*6.02f, oy + s*15.21f, ox + s*6.02f, oy + s*15.02f, ox + s*6.01f, oy + s*14.39f, ox + s*6.01f, oy + s*13.72f);
  p.AddBezier(ox + s*6.01f, oy + s*13.72f, ox + s*4.f, oy + s*14.09f, ox + s*3.48f, oy + s*13.23f, ox + s*3.32f, oy + s*12.78f);
  p.AddBezier(ox + s*3.32f, oy + s*12.78f, ox + s*3.23f, oy + s*12.55f, ox + s*2.84f, oy + s*11.84f, ox + s*2.5f, oy + s*11.65f);
  p.AddBezier(ox + s*2.5f, oy + s*11.65f, ox + s*2.22f, oy + s*11.5f, ox + s*1.82f, oy + s*11.13f, ox + s*2.49f, oy + s*11.12f);
  p.AddBezier(ox + s*2.49f, oy + s*11.12f, ox + s*3.12f, oy + s*11.11f, ox + s*3.57f, oy + s*11.7f, ox + s*3.72f, oy + s*11.94f);
  p.AddBezier(ox + s*3.72f, oy + s*11.94f, ox + s*4.44f, oy + s*13.15f, ox + s*5.59f, oy + s*12.81f, ox + s*6.05f, oy + s*12.6f);
  p.AddBezier(ox + s*6.05f, oy + s*12.6f, ox + s*6.12f, oy + s*12.08f, ox + s*6.33f, oy + s*11.73f, ox + s*6.56f, oy + s*11.53f);
  p.AddBezier(ox + s*6.56f, oy + s*11.53f, ox + s*4.78f, oy + s*11.33f, ox + s*2.92f, oy + s*10.64f, ox + s*2.92f, oy + s*7.58f);
  p.AddBezier(ox + s*2.92f, oy + s*7.58f, ox + s*2.92f, oy + s*6.71f, ox + s*3.23f, oy + s*5.99f, ox + s*3.74f, oy + s*5.43f);
  p.AddBezier(ox + s*3.74f, oy + s*5.43f, ox + s*3.66f, oy + s*5.23f, ox + s*3.38f, oy + s*4.41f, ox + s*3.82f, oy + s*3.31f);
  p.AddBezier(ox + s*3.82f, oy + s*3.31f, ox + s*3.82f, oy + s*3.31f, ox + s*4.49f, oy + s*3.1f, ox + s*6.02f, oy + s*4.13f);
  p.AddBezier(ox + s*6.02f, oy + s*4.13f, ox + s*6.66f, oy + s*3.95f, ox + s*7.34f, oy + s*3.86f, ox + s*8.02f, oy + s*3.86f);
  p.AddBezier(ox + s*8.02f, oy + s*3.86f, ox + s*8.7f, oy + s*3.86f, ox + s*9.38f, oy + s*3.95f, ox + s*10.02f, oy + s*4.13f);
  p.AddBezier(ox + s*10.02f, oy + s*4.13f, ox + s*11.55f, oy + s*3.09f, ox + s*12.22f, oy + s*3.31f, ox + s*12.22f, oy + s*3.31f);
  p.AddBezier(ox + s*12.22f, oy + s*3.31f, ox + s*12.66f, oy + s*4.41f, ox + s*12.38f, oy + s*5.23f, ox + s*12.3f, oy + s*5.43f);
  p.AddBezier(ox + s*12.3f, oy + s*5.43f, ox + s*12.81f, oy + s*5.99f, ox + s*13.12f, oy + s*6.7f, ox + s*13.12f, oy + s*7.58f);
  p.AddBezier(ox + s*13.12f, oy + s*7.58f, ox + s*13.12f, oy + s*10.65f, ox + s*11.25f, oy + s*11.33f, ox + s*9.47f, oy + s*11.53f);
  p.AddBezier(ox + s*9.47f, oy + s*11.53f, ox + s*9.76f, oy + s*11.78f, ox + s*10.01f, oy + s*12.26f, ox + s*10.01f, oy + s*13.01f);
  p.AddBezier(ox + s*10.01f, oy + s*13.01f, ox + s*10.01f, oy + s*14.08f, ox + s*10.f, oy + s*14.94f, ox + s*10.f, oy + s*15.21f);
  p.AddBezier(ox + s*10.f, oy + s*15.21f, ox + s*10.f, oy + s*15.42f, ox + s*10.15f, oy + s*15.67f, ox + s*10.55f, oy + s*15.59f);
  p.AddArc(ox - s*0.02f, oy - s*0.01f, s*16.02f, s*16.02f, 71.361f, -71.362f);
  p.AddBezier(ox + s*16.f, oy + s*8.f, ox + s*16.f, oy + s*3.58f, ox + s*12.42f, oy, ox + s*8.f, oy);
  p.CloseFigure();
}

// 画 GitHub 标志：外接正方形边长 = 边长 side（16 单位视图框等比缩放）
static void DrawGithubMark(Graphics& g, float cx, float cy, float side, const Color& c) {
  float s = side / 16.f;
  GraphicsPath p;
  GithubMarkPath(p, cx - side / 2.f, cy - side / 2.f, s);
  SolidBrush b(c);
  g.FillPath(&b, &p);
}

// 自绘关闭按钮（窗口无标题栏）：悬停给一层浅底，× 的线加粗变色
static void DrawCloseBtn(Graphics& g, const RectF& r, bool hot) {
  if (hot) { SolidBrush b(C_HOVER); g.FillRectangle(&b, r); }
  Pen p(hot ? C_TEXT : C_DIM, 1.4f);
  p.SetStartCap(LineCapRound); p.SetEndCap(LineCapRound);
  const float m = 8.f;
  g.DrawLine(&p, r.X + m, r.Y + m, r.GetRight() - m, r.GetBottom() - m);
  g.DrawLine(&p, r.GetRight() - m, r.Y + m, r.X + m, r.GetBottom() - m);
}

// 一行设置：左边标签，右边**当前值** + 小三角。
// 收起态就把当前值写在这里 —— 玩家不展开也能一眼看全所有设置，
// 展开只是为了"改"。悬停时整行给一层浅底，暗示可点。
// dim = 该项当前不生效（如全屏时的分辨率）。只把值调淡一档（C_DIM 而非 C_MUTED，
// 后者太浅像坏掉的控件）—— 它仍可点开，玩家常要先选好分辨率再切回窗口模式。
static void DrawSettingRow(Graphics& g, const RectF& r, const wchar_t* label,
                           const wchar_t* value, bool hot, bool open,
                           bool dim = false) {
  if (hot || open) FillRR(g, r, 7, hot ? C_HOVER : C_PANEL);
  DrawTxt(g, label, F(15), C_TEXT, r.X + 4, r.Y + 8);
  // 值右对齐，给右侧的小三角留 22px
  DrawTxt(g, value, F(14), dim ? C_DIM : C_TEXT, r.GetRight() - 22, r.Y + 9, 2);
  // 小三角：收起时朝右、展开时朝下（比旋转箭头更好画也更清楚）
  float cx = r.GetRight() - 10, cy = r.Y + 17;
  SolidBrush db(open ? C_ACCENT : C_DIM);
  PointF tri[3];
  if (open) { tri[0] = { cx-4, cy-2 }; tri[1] = { cx+4, cy-2 }; tri[2] = { cx, cy+3 }; }
  else      { tri[0] = { cx-2, cy-4 }; tri[1] = { cx-2, cy+4 }; tri[2] = { cx+3, cy }; }
  g.FillPolygon(&db, tri, 3);
}

// 展开的选项列表（单独一个函数，便于最后绘制 —— 见 Paint 里的 z 序说明）。
// 注意：RowBox/RowItemRect 定义在下面（几何区），所以本函数声明在前、实现放在几何之后。
static void DrawRowItems(Graphics& g, int row, int n,
                         const wchar_t* const* labels, int sel, int hot);

// ── 几何 ──
// 左栏宽度由**主题图的比例**决定（见顶部 LEFT_W 的推导），窗口高度固定 620。
// 右栏所有控件从右边界反推 —— 以前这里是一堆手写死坐标，
// StartRect() 的右边界曾超出窗口 10px（「开始游戏」被切），现在不会再有这种问题。
static const float PAD_R = 24.f;                   // 右栏右边距
// ★ 必须写成**函数**，不能写成 `static const float`：
//   RXL/RW 依赖 LEFT_W，而 LEFT_W 是运行时由主题图比例算出来的（ApplyThemeGeometry，
//   在建窗口之前调用）。static const 在**程序启动时**就取值，那时 LEFT_W 还是初值，
//   常量就永久过期了。以前 WIN_H=500 时算出来恰好也是 375（与初值相同），
//   所以这个错一直隐形；WIN_H 一改就暴露成"标签跑到左栏图上"。
static inline float RXLf() { return (float)LEFT_W + 28.f; }   // 右栏内容左边界
static inline float RWf()  { return (float)WIN_W - PAD_R; }   // 右栏内容右边界
#define RXL RXLf()
#define RW  RWf()

// 命中 id：0..OPT_COUNT-1 选项 / 200 开始 / 201 检查更新 / 202 关闭 / 203 GitHub
//         204 更新卡片 / 1000+i 第 i 个设置行的"行头"（点它展开/收起）
//         1100+i*10+k 第 i 行展开后的第 k 个选项
enum { ID_START = 200, ID_CHECK = 201, ID_CLOSE = 202, ID_GITHUB = 203,
       ID_BANNER = 204,
       ID_ROW = 1000, ID_ROWITEM = 1100 };
// 四个设置行的语义（下标即 ROW 顺序）：0 = cosplay / 1 = 影片字幕 / 2 = 显示模式 / 3 = 分辨率
enum { ROW_OUTFIT = 0, ROW_SUBS = 1, ROW_SCRN = 2, ROW_RES = 3 };

// 4 个复选框：行高 37（标题 15px + 灰色说明 11px）
// （原为 42；为了在**不加大窗口**的前提下腾出「画面」那一行，整体收紧 5px。
//   收紧后仍保持"标题→说明→下一条"的清晰层次，不是简单挤压。）
static RectF OptRect(int i)   { return RectF(RXL, 48.f + i * 37.f, RW - RXL, 26.f); }
// ── 右栏下半：4 个「标签 + 当前值」行（点哪行展开哪行的选项）──
// 原先是 3 个带外框的下拉 + 2 行灰色小字说明 + 3 条分隔线，视觉很碎、也占地方。
// 现在统一成同构的 4 行：左边标签、右边当前值 + 小三角。
// ★ **收起态就把当前值写在行里** —— 不展开也能一眼看全所有设置，
//   而展开只是为了"改"。这比"折叠后只剩标题"实用得多。
//
// ★ 只有 cosplay 那一行带灰色小字（用户 2026-09-24 指定"至少对这一个补小注释"）：
//   它的值（原版/和服/泳装/体操服/猫耳）不看解释不知道是干什么的；
//   而「影片字幕」「显示模式」「分辨率」看字面就懂，不必解释。
//   小字占一行（11px + 留白），所以它**下面三行整体下移 HINT_OFF**。
static const wchar_t* OUTFIT_HINT =
    L"LanguageBarrier 重定向模型归档，运行时切换该套立绘";
static const float ROW_Y0 = 206.f, ROW_STEP = 46.f, ROW_H = 34.f;
static const float HINT_OFF = 16.f;      // cosplay 那行小字占掉的高度
static const int ROW_N = 4;
static RectF RowRect(int i) {
  float dy = (i >= 1) ? HINT_OFF : 0.f;   // 第 1 行（cosplay）之后都让出小字的位置
  return RectF(RXL, ROW_Y0 + i * ROW_STEP + dy, RW - RXL, ROW_H);
}
// cosplay 那行下方的小字位置
static RectF RowHintRect() { return RectF(RXL + 4.f, ROW_Y0 + ROW_H + 5.f, RW - RXL, 12.f); }
// 主按钮的位置（RowBox 要拿它判断"向下弹会不会压住按钮"，故提前声明）
static RectF StartRect();
// 选项列表：优先向下弹；下方装不下（会压到主按钮）就向上弹。
// 判定写成纯函数（不存状态），HitTest 与 Paint 各自算一次，结果必然一致。
static bool RowOpensUp(int i, int n) {
  float h = n * 34.f + 4;
  return RowRect(i).GetBottom() + 2 + h > StartRect().Y - 6;
}
static RectF RowBox(int i, int n) {
  RectF r = RowRect(i);
  float h = n * 34.f + 4;
  return RowOpensUp(i, n) ? RectF(r.X, r.Y - 2 - h, r.Width, h)
                          : RectF(r.X, r.GetBottom() + 2, r.Width, h);
}
static RectF RowItemRect(int i, int n, int k) {
  RectF b = RowBox(i, n);
  return RectF(b.X + 1, b.Y + 2 + k * 34.f, b.Width - 2, 34.f);
}
// 主按钮：右下角对齐，宽 200 高 46，离底 24
static RectF StartRect()      { return RectF(RW - 200.f, (float)WIN_H - 24.f - 46.f, 200.f, 46.f); }
// 「检查更新」：主按钮左侧的小按钮 —— 比主按钮矮一截，底边与主按钮对齐
// （用户指定：再小一点，贴住这块区域的左下角）。
static RectF CheckRect()      { RectF sr = StartRect();
                                return RectF(sr.X - 10.f - 84.f, sr.GetBottom() - 24.f, 84.f, 24.f); }
// GitHub 标志按钮：贴在「检查更新」左侧，点它直接开仓库主页。
// 方形小按钮，与「检查更新」同高同底边。
static RectF GithubRect()     { RectF cr = CheckRect();
                                return RectF(cr.X - 6.f - 24.f, cr.Y, 24.f, 24.f); }
// 自绘关闭按钮：右上角（窗口无标题栏，得自己给一个「×」）
static RectF CloseRect()      { return RectF((float)WIN_W - 10.f - 26.f, 10.f, 26.f, 26.f); }

// 展开的选项列表（实现在这里，因为要用 RowBox/RowItemRect）
static void DrawRowItems(Graphics& g, int row, int n,
                         const wchar_t* const* labels, int sel, int hot) {
  RectF box = RowBox(row, n);
  FillRR(g, box, 6, C_FIELD);
  for (int k = 0; k < n; k++) {
    RectF ir = RowItemRect(row, n, k);
    bool isHot = (hot == ID_ROWITEM + row * 10 + k);
    Color bg = isHot ? C_HOVER : (k == sel ? C_SEL : C_FIELD);
    float rad = (k == 0 || k == n - 1) ? 5.f : 0.f;
    FillRR(g, ir, rad, bg);
    // 悬停反馈要一眼能看出来（2026-09-13 用户反馈"没有鼓起来的感觉"）：
    // 只变一点底色太淡，再加一圈主题色描边。
    if (isHot) StrokeRR(g, ir, rad, C_ACCENT, 1.2f);
    DrawTxt(g, labels[k], F(14), k == sel ? C_ACCENT : C_TEXT, ir.X + 12, ir.Y + 8);
  }
  StrokeRR(g, box, 6, C_BORDER, 1.f);
}

// ───────────────────── 检查更新（GitHub） ─────────────────────
// 点「检查更新」拿到仓库的最新 release / tag 跟本地 VER 比一比。
// 网络请求必须放后台线程：WinINet 是阻塞的，直接在消息循环里跑会让窗口假死。
// 结果用 WM_APP+2 带回主线程处理（结果对象的生命周期也一并交过去）。
//
// ★ 启动即自动查一次（2026-09-15 用户要求）：有新版本时「检查更新」按钮右上角
//   常亮小红点、并在窗口内出一张小卡片（点卡片去下载页）—— **不再弹系统对话框**。
//   「已是最新」「查不到」仍只在按钮上闪一下文字，几秒后恢复。
static const wchar_t* REPO_URL = L"https://github.com/Syun1524/RND_Chinese";
static const wchar_t* REL_URL  = L"https://github.com/Syun1524/RND_Chinese/releases";
static volatile LONG g_checking = 0;      // 0 空闲 / 1 查询中（防重复点击）
// 「已是最新」「查不到」这类正常结果直接显示在按钮上、几秒后自动恢复，**不弹窗**。
static std::wstring g_checkMsg;           // 非空时按钮显示它
static const UINT_PTR TIMER_CHECKMSG = 1; // 用它定时清掉 g_checkMsg

// 查到有新版本后的常驻状态（直到本版升级才消失）：
static std::wstring g_newVer;             // 远程版本号（如 "v1.3"），空 = 没有新版本
static std::wstring g_newUrl;             // 下载页链接（点卡片跳转用）
// 卡片按下态（按下→抬起都在卡片上才跳转，和其它按钮同一手感）
static bool g_bannerDown = false;

// 更新卡片：**放在左栏主题图上**（版本号上方的小卡片）。
// 原先它在右栏主按钮上方，会白占 36px —— 而它只在"确实有新版本"时才出现，
// 平时那 36px 就是空的。搬到左栏后右栏省下这块空间，「画面」那一行才放得下
// 而窗口尺寸不用变大。深色半透明底压在图上，本身也是常见的"提示卡"观感。
static RectF BannerRect()     { return RectF(12.f, (float)WIN_H - 78.f, (float)LEFT_W - 24.f, 40.f); }

// status: 0 = 有新版本 / 1 = 已是最新 / 2 = 查询失败
struct UpdResult { int status; std::wstring latest; std::wstring url; };

// 极简 JSON 取字符串值：只认第一个 "key" : "value"，够用且不引依赖
static std::wstring JsonStr(const std::string& s, const char* key) {
  std::string k = std::string("\"") + key + "\"";
  size_t p = s.find(k);
  if (p == std::string::npos) return L"";
  p = s.find(':', p + k.size());
  if (p == std::string::npos) return L"";
  size_t q1 = s.find('"', p + 1);
  if (q1 == std::string::npos) return L"";
  size_t q2 = s.find('"', q1 + 1);
  if (q2 == std::string::npos) return L"";
  return Utf8ToWide(s.substr(q1 + 1, q2 - q1 - 1));
}

static bool HttpGet(const std::wstring& url, std::string& out) {
  out.clear();
  HINTERNET hNet = InternetOpenW(L"RNDZhLauncher", INTERNET_OPEN_TYPE_PRECONFIG,
                                 nullptr, nullptr, 0);
  if (!hNet) return false;
  HINTERNET hUrl = InternetOpenUrlW(hNet, url.c_str(), nullptr, 0,
      INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE, 0);
  if (!hUrl) { InternetCloseHandle(hNet); return false; }
  char buf[4096]; DWORD rd = 0;
  while (InternetReadFile(hUrl, buf, sizeof(buf), &rd) && rd > 0) {
    out.append(buf, rd);
    if (out.size() > 65536) break;       // 只需要头部几十字节，防跑飞
  }
  InternetCloseHandle(hUrl);
  InternetCloseHandle(hNet);
  return !out.empty();
}

// 远程版本号比本地新吗：抽数字逐段比（"v1.2" vs "1.10"），非数字一律忽略
static bool VerNewer(const std::wstring& remote, const std::wstring& local) {
  auto nums = [](const std::wstring& s) {
    std::vector<int> v; std::wstring t;
    for (wchar_t c : s) {
      if (c >= L'0' && c <= L'9') t += c;
      else if (!t.empty()) { v.push_back(_wtoi(t.c_str())); t.clear(); }
    }
    if (!t.empty()) v.push_back(_wtoi(t.c_str()));
    return v;
  };
  std::vector<int> a = nums(remote), b = nums(local);
  for (size_t i = 0; i < a.size() || i < b.size(); i++) {
    int x = i < a.size() ? a[i] : 0, y = i < b.size() ? b[i] : 0;
    if (x != y) return x > y;
  }
  return false;
}

// 先问 releases/latest（有发布就用它，能拿到 html_url 直达下载页）；
// 仓库没有 release 时退回 tags 的第一个。都拿不到 = 查询失败。
static DWORD WINAPI UpdateThread(LPVOID) {
  UpdResult* r = new UpdResult{ 2, L"", REL_URL };
  std::string body;
  if (HttpGet(std::wstring(L"https://api.github.com/repos/Syun1524/RND_Chinese/releases/latest"), body)) {
    std::wstring tag = JsonStr(body, "tag_name");
    std::wstring u   = JsonStr(body, "html_url");
    if (!tag.empty()) {
      r->latest = tag;
      if (!u.empty()) r->url = u;
      r->status = VerNewer(tag, VER) ? 0 : 1;
    }
  }
  if (r->latest.empty()) {
    std::string tb;
    if (HttpGet(std::wstring(L"https://api.github.com/repos/Syun1524/RND_Chinese/tags"), tb)) {
      std::wstring n = JsonStr(tb, "name");
      if (!n.empty()) { r->latest = n; r->url = REL_URL; r->status = VerNewer(n, VER) ? 0 : 1; }
    }
  }
  PostMessageW(g_hwnd, WM_APP + 2, 0, (LPARAM)r);
  return 0;
}

static void StartUpdateCheck() {
  if (InterlockedCompareExchange(&g_checking, 1, 0) != 0) return;   // 已在查
  InvalidateRect(g_hwnd, nullptr, FALSE);
  HANDLE t = CreateThread(nullptr, 0, UpdateThread, nullptr, 0, nullptr);
  if (t) CloseHandle(t);
  else   InterlockedExchange(&g_checking, 0);
}

static void Paint(HDC hdc) {
  RECT rc; GetClientRect(g_hwnd, &rc);
  // 物理客户区尺寸。声明 DPI 感知后 rc 就是物理像素；绘制时用 ScaleTransform
  // 把坐标系缩放到逻辑尺寸，但 BitBlt 必须用物理尺寸往回拷。
  const int pw = rc.right, ph = rc.bottom;
  HDC mem = CreateCompatibleDC(hdc);
  HBITMAP bmp = CreateCompatibleBitmap(hdc, pw, ph);
  HBITMAP old = (HBITMAP)SelectObject(mem, bmp);
  {
    Graphics gr(mem);
    gr.SetSmoothingMode(SmoothingModeAntiAlias);
    gr.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    float sx = (float)pw / WIN_W, sy = (float)ph / WIN_H;
    S = sx;
    gr.ScaleTransform(sx, sy);

    SolidBrush bg(C_BG); gr.FillRectangle(&bg, 0, 0, WIN_W, WIN_H);

    // ── 左：主题图（铺满左栏）──
    // 图是 3:4 竖版，左栏宽度就是按这个比例算的，所以直接铺满即可，
    // 不会变形也不留黑边。找不到资源时退化成一个纯色块 + 文字提示。
    if (g_themeBmp) {
      // 目标矩形 = 整个左栏；源矩形 = 整张图。图的比例与左栏一致（见 LEFT_W
      // 的推导），所以等比缩放后正好铺满，不会变形。
      RectF dst(0, 0, (float)LEFT_W, (float)WIN_H);
      RectF src(0, 0, (float)g_themeBmp->GetWidth(), (float)g_themeBmp->GetHeight());
      gr.DrawImage(g_themeBmp, dst, src.X, src.Y, src.Width, src.Height, UnitPixel);
    } else {
      SolidBrush ph(C_PANEL); gr.FillRectangle(&ph, 0, 0, LEFT_W, WIN_H);
      DrawTxt(gr, L"主题图", F(14), C_MUTED, LEFT_W / 2.f, WIN_H / 2.f, 1);
    }
    Pen edge(C_BORDER, 1.f); gr.DrawLine(&edge, LEFT_W, 0, LEFT_W, WIN_H);
    // 版本号压在图上：左下角，图上多半是深色，用白字加一层淡阴影保证可读
    {
      RectF vb(12, (float)WIN_H - 30, 80, 20);
      SolidBrush sh(Color(90, 0, 0, 0));
      gr.FillRectangle(&sh, RectF(vb.X + 1, vb.Y + 1, 58, 18));
      DrawTxt(gr, (std::wstring(L"v") + VER).c_str(), F(12), C_WHITE, vb.X, vb.Y);
    }

    // ── 右上角小字：实现方式 + 署名（右对齐，一眼能看到出处）──
    // 两人工作量五五开，「x」刻意不分先后；「汉化:」与名字之间要留空格
    // （2026-09-13 用户指定格式「汉化: aaa x bbb」）。
    // 右边界要给右上角的关闭按钮让位（窗口无标题栏，那个 × 是我们自绘的）。
    DrawTxt(gr, L"基于CoZ LanguageBarrier·Gemini3.0Flash·人工精校",
            F(10), C_MUTED, RW - 34.f, 14, 2);
    DrawTxt(gr, L"汉化: 仓式同学◆ x Eight_tide",
            F(10), C_MUTED, RW - 34.f, 29, 2);

    // ── 右：选项 ──
    // 纵向节奏：复选框 48..190 ｜ 4 个设置行 206..368 ｜ 底部按钮 430..476
    // （原先三行下拉各带分隔线和小字说明，视觉很碎；现在统一成同构的 4 行，
    //   收起态直接把当前值写在行里，不展开也能看全设置。）
    DrawTxt(gr, L"选项", F(12), C_MUTED, RXL, 30);
    for (int i = 0; i < OPT_COUNT; i++) {
      RectF r = OptRect(i);
      bool on = st.on[i];
      DrawCheck(gr, RectF(r.X, r.Y + 2, 22, 22), on, st.hot == i);
      DrawTxt(gr, OPT_LABEL[i], F(15), on ? C_TEXT : C_DIM, r.X + 32, r.Y + 1);
      // 说明行统一走折行版：宽度给 0 时 GDI+ 不折行，太长会被窗口裁掉
      DrawTxtW(gr, OPT_HINT[i], F(11), C_MUTED, r.X + 32, r.Y + 19, RW - (r.X + 32));
    }

    // ── 4 个设置行：cosplay 模式 / 影片字幕 / 显示模式 / 分辨率 ──
    // 收起态 = 「标签 ……… 当前值 ▸」；点行头展开该项的选项列表。
    // 全屏时分辨率那行淡一档（它不生效），但仍可点开 ——
    // 玩家常要先选好分辨率再切回窗口模式。
    {
      // 第 2 行「显示模式」与第 3 行「分辨率」是两个独立下拉，
      // 但语义上是一组（原版 Screen Setting 里就是 SCREEN MODE + RESOLUTION），
      // 所以分成 4 行后仍挨在一起，中间不加分隔线。
      const wchar_t* vals[ROW_N] = {
        OUTFIT_LABEL[st.outfit], SUBS_LABEL[st.subs],
        SCRN_LABEL[st.scrn], RES_LABEL[st.res]
      };
      const wchar_t* names[ROW_N] = { L"cosplay 模式", L"影片字幕", L"显示模式", L"分辨率" };
      for (int i = 0; i < ROW_N; i++) {
        bool dim = (i == ROW_RES && st.scrn == 1);
        DrawSettingRow(gr, RowRect(i), names[i], vals[i],
                       st.hot == ID_ROW + i, st.openRow == i, dim);
      }
      // cosplay 那行下方的小字 —— 只有这一行有（用户 2026-09-24 指定）。
      // 其余三行（影片字幕/显示模式/分辨率）看字面就懂，不解释。
      DrawTxtW(gr, OUTFIT_HINT, F(11), C_MUTED,
               RowHintRect().X, RowHintRect().Y, RW - RXL);
    }

    // ── 主按钮 ──
    // 浅色极简 + **直角**（2026-09-13 用户指定：棱角分明，不再圆角）。
    // 文字「开始游戏」+ 微软雅黑 Bold（中文按字格排版，本来就有均匀的字距，
    // 不需要像拉丁字母那样手动逐字加 tracking）。
    // 悬停底色加深 + 边框加深。沿用现有色板，不引入新颜色。
    { RectF sr = StartRect();
      bool hot = (st.hot == ID_START);
      SolidBrush fillb(hot ? C_HOVER : C_PANEL);
      gr.FillRectangle(&fillb, sr);
      Pen bp(hot ? C_DIM : C_BORDER, 1.f);
      gr.DrawRectangle(&bp, sr);
      DrawTxtCentered(gr, L"开始游戏", FTech(20, true), C_TEXT, sr); }

    // ── 更新卡片：**左栏主题图上**的小卡片，只在查到新版本时出现 ──
    // 整张卡片可点：点它打开下载页（2026-09-15 用户要求：小卡片 + 跳转，不弹窗）。
    // 压在图上所以用**深色半透明底 + 白字**（浅色卡片压在照片上会看不清）；
    // 左侧「新」字徽标（主题蓝底白字），右侧「前往下载 →」。
    if (!g_newVer.empty()) {
      RectF br = BannerRect();
      bool hot = (st.hot == ID_BANNER);
      SolidBrush fillb(Color(hot ? 235 : 210, 18, 24, 34));
      FillRR(gr, br, 6, Color(hot ? 235 : 210, 18, 24, 34));
      StrokeRR(gr, br, 6, C_ACCENT, hot ? 1.6f : 1.2f);
      // 左侧「新」徽标
      RectF tag(br.X + 9.f, br.Y + 10.f, 26.f, 20.f);
      SolidBrush tagb(C_ACCENT);
      gr.FillRectangle(&tagb, tag);
      DrawTxtCentered(gr, L"新", F(11, true), C_WHITE, tag);
      // 文案：发现新版本 vX.Y（当前版本号左下角已有，卡片里不重复）
      std::wstring line = L"发现新版本 " + g_newVer;
      DrawTxtW(gr, line.c_str(), F(13), C_WHITE, tag.GetRight() + 9.f,
               br.Y + 10.f, br.Width - 160.f);
      // 右侧「前往下载 →」
      DrawTxt(gr, L"前往下载 →", F(12), C_WHITE, br.GetRight() - 11.f,
              br.Y + 11.f, 2 /*右对齐*/);
    }

    // ── 「检查更新」小按钮：贴在「开始游戏」左侧 ──
    // 点它去 GitHub 查最新版本：有新版本 → 右上角亮小红点 + 窗口内出小卡片
    // （**不弹系统对话框**）；「已是最新」「查不到」直接显示在按钮上、
    // 几秒后自动恢复，不打断玩家。
    // 网络请求在后台线程跑（见 UpdateThread），查期间显示「检查中…」并挡住重复点击。
    // ★ 启动即自动查一次（见 wWinMain），有更新不用点按钮也会亮红点。
    { RectF cr = CheckRect();
      bool busy = (g_checking != 0);
      bool hot  = (st.hot == ID_CHECK) && !busy;
      SolidBrush fillb(hot ? C_HOVER : C_PANEL);
      gr.FillRectangle(&fillb, cr);
      Pen bp(hot ? C_DIM : C_BORDER, 1.f);
      gr.DrawRectangle(&bp, cr);
      const wchar_t* txt = busy ? L"检查中…"
                        : (!g_checkMsg.empty() ? g_checkMsg.c_str() : L"检查更新");
      DrawTxtW(gr, txt, F(11), busy ? C_MUTED : C_DIM, cr.X, cr.Y + 5, cr.Width, 1);
      // 小红点：查到新版本后常亮（右上角，压在按钮边框上，直径 8）
      if (!g_newVer.empty()) {
        SolidBrush dotb(C_DOT);
        gr.FillEllipse(&dotb, cr.GetRight() - 5.f, cr.Y - 4.f, 8.f, 8.f);
      } }

    // ── GitHub 标志按钮：贴在「检查更新」左侧，直接开仓库主页 ──
    { RectF gb = GithubRect();
      bool hot = (st.hot == ID_GITHUB);
      SolidBrush fillb(hot ? C_HOVER : C_PANEL);
      gr.FillRectangle(&fillb, gb);
      Pen bp(hot ? C_DIM : C_BORDER, 1.f);
      gr.DrawRectangle(&bp, gb);
      DrawGithubMark(gr, gb.X + gb.Width / 2.f, gb.Y + gb.Height / 2.f, 15.f,
                     hot ? C_TEXT : C_DIM); }

    // ── 自绘关闭按钮（无标题栏）──
    DrawCloseBtn(gr, CloseRect(), st.hot == ID_CLOSE);

    // ── 窗口描边：无标题栏后需要一圈细线把窗口从桌面上"切"出来 ──
    { Pen eb(C_BORDER, 1.f);
      gr.DrawRectangle(&eb, 0.f, 0.f, (float)WIN_W - 1.f, (float)WIN_H - 1.f); }


    // ── 下拉列表最后画 ──
    // 必须放在所有控件之后：展开的选项会盖住下面的分隔线与主按钮，
    // 若按源码顺序（换装就在换装标题之后）绘制，会被后面画的「影片字幕」
    // 和「开始游戏」覆盖，看起来像下拉框被切了一块。
    if (st.openRow == ROW_OUTFIT)
      DrawRowItems(gr, ROW_OUTFIT, OUTFIT_N, OUTFIT_LABEL, st.outfit, st.hot);
    else if (st.openRow == ROW_SUBS)
      DrawRowItems(gr, ROW_SUBS, 3, SUBS_LABEL, st.subs, st.hot);
    else if (st.openRow == ROW_SCRN)
      DrawRowItems(gr, ROW_SCRN, SCRN_N, SCRN_LABEL, st.scrn, st.hot);
    else if (st.openRow == ROW_RES)
      DrawRowItems(gr, ROW_RES, RES_N, RES_LABEL, st.res, st.hot);
  }
  BitBlt(hdc, 0, 0, pw, ph, mem, 0, 0, SRCCOPY);
  SelectObject(mem, old); DeleteObject(bmp); DeleteDC(mem);
}

// ───────────────────────── 启动游戏 ─────────────────────────
static bool HasSaveDir(const wchar_t* lang) {
  wchar_t* docs = nullptr;
  SHGetKnownFolderPath(FOLDERID_Documents, 0, nullptr, &docs);
  std::wstring p = docs ? docs : L"";
  if (docs) CoTaskMemFree(docs);
  p += L"\\My Games\\mages_steam\\Robotics Notes DASH\\";
  p += lang;
  return FileExists(p);
}

// 从 boot.bat 读语言（游戏权威来源）：内容形如 "start launcher.exe JP"
// 补丁会覆盖 boot.bat，故优先读我们备份的原版；都没有则看存档目录。
static const wchar_t* DetectLang() {
  static wchar_t buf[8] = { 0 };
  const wchar_t* cands[] = {
    L"\\_cn_patch_boot_orig.bat",   // 安装器保留的游戏原版
    L"\\boot.bat"
  };
  for (auto c : cands) {
    std::wstring p = g_dir + c;
    std::ifstream f(p, std::ios::binary);
    if (!f) continue;
    std::stringstream ss; ss << f.rdbuf();
    std::string s = ss.str();
    for (auto& ch : s) ch = (char)toupper((unsigned char)ch);
    size_t e = s.find("EN"), j = s.find("JP");
    if (e != std::string::npos && (j == std::string::npos || e < j)) { wcscpy_s(buf, L"EN"); return buf; }
    if (j != std::string::npos) { wcscpy_s(buf, L"JP"); return buf; }
  }
  // 退化：按存档目录判断
  wcscpy_s(buf, (!HasSaveDir(L"eng") && HasSaveDir(L"jpn")) ? L"JP" : L"EN");
  return buf;
}

// Steam 客户端在运行吗（查进程表里有没有 steam.exe）
static bool SteamRunning() {
  HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
  if (snap == INVALID_HANDLE_VALUE) return true;    // 查不到就别拦，让它试
  PROCESSENTRY32W pe; pe.dwSize = sizeof(pe);
  bool found = false;
  if (Process32FirstW(snap, &pe)) {
    do {
      if (_wcsicmp(pe.szExeFile, L"steam.exe") == 0) { found = true; break; }
    } while (Process32NextW(snap, &pe));
  }
  CloseHandle(snap);
  return found;
}

// 是 Steam 库安装吗：路径里有 steamapps 即是（盗版免 DVD 版不在，直接启动即可）
static bool IsSteamInstall() {
  std::wstring d = g_dir;
  for (auto& c : d) c = (wchar_t)towlower(c);
  return d.find(L"steamapps") != std::wstring::npos;
}

static void LaunchGame() {
  SaveConfig();
  ApplyDxvk(st.on[OPT_DXVK]);
  const wchar_t* lang = DetectLang();   // 跟随玩家原本的版本（存档目录随之）

  // Steam 版必须先开 Steam 客户端，否则游戏会弹英文模态框
  // （"You need to execute Steam system..."）且主窗口根本不出来。
  // 检测不到进程时不拦 —— 免得误伤（比如改名版 Steam）。
  if (IsSteamInstall() && !SteamRunning()) {
    MessageBoxW(g_hwnd,
        L"请先启动 Steam，再点「开始游戏」。\n\n也可以直接从 Steam 库里启动游戏。",
        L"Steam 未运行", MB_ICONINFORMATION | MB_OK);
    return;
  }

  std::wstring cmd = L"Game.exe roboticsnotesd " + std::wstring(lang);
  STARTUPINFOW si{}; si.cb = sizeof(si);
  PROCESS_INFORMATION pi{};
  if (CreateProcessW(L"Game.exe", &cmd[0], nullptr, nullptr, FALSE, 0, nullptr, g_dir.c_str(), &si, &pi)) {
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    PostMessageW(g_hwnd, WM_CLOSE, 0, 0);
  } else {
    MessageBoxW(g_hwnd, L"未找到 Game.exe，请把本启动器放在游戏根目录。",
                L"启动失败", MB_ICONERROR | MB_OK);
  }
}

// ───────────────────────── 交互 ─────────────────────────
// 注意：鼠标消息给的是**物理像素**，而布局是逻辑坐标，所以先 unscale 再比。
static int HitTest(int px, int py) {
  int x = (int)unscale(px), y = (int)unscale(py);
  auto in = [&](const RectF& r) {
    return x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom();
  };
  // 展开的选项列表优先判定：它盖在别的控件上，命中判定也必须先于它们
  if (st.openRow >= 0) {
    static const int rowN[ROW_N] = { OUTFIT_N, 3, SCRN_N, RES_N };
    int n = rowN[st.openRow];
    for (int k = 0; k < n; k++)
      if (in(RowItemRect(st.openRow, n, k))) return ID_ROWITEM + st.openRow * 10 + k;
  }
  if (in(CloseRect())) return ID_CLOSE;
  if (!g_newVer.empty() && in(BannerRect())) return ID_BANNER;
  if (in(StartRect())) return ID_START;
  if (in(CheckRect())) return ID_CHECK;
  if (in(GithubRect())) return ID_GITHUB;
  for (int i = 0; i < ROW_N; i++) if (in(RowRect(i))) return ID_ROW + i;
  for (int i = 0; i < OPT_COUNT; i++) {
    RectF r = OptRect(i);
    if (x >= r.X - 4 && x <= r.X + r.Width && y >= r.Y - 2 && y <= r.Y + 40) return i;
  }
  return -1;
}

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
  switch (m) {
  // 无标题栏窗口靠 WM_NCHITTEST 划分「可拖动区」：把非客户区当成标题栏（HTCAPTION），
  // 系统就会给原生的拖动行为。主题图整块 + 顶部横条都是拖动区；
  // 关闭按钮必须显式留在客户区，否则它的点击会被拖动逻辑吞掉。
  case WM_NCHITTEST: {
    POINT p{ GET_X_LPARAM(l), GET_Y_LPARAM(l) };
    ScreenToClient(h, &p);
    int x = (int)unscale(p.x), y = (int)unscale(p.y);
    RectF cb = CloseRect();
    if (x >= cb.X && x <= cb.GetRight() && y >= cb.Y && y <= cb.GetBottom()) return HTCLIENT;
    if (x < LEFT_W || y < 46) return HTCAPTION;
    return HTCLIENT;
  }
  case WM_NCLBUTTONDBLCLK:                 // 拖动区双击不要触发最大化
    if (w == HTCAPTION) return 0;
    break;
  case WM_APP + 2: {                       // 检查更新结果（后台线程 PostMessage 回来）
    UpdResult* r = (UpdResult*)l;
    InterlockedExchange(&g_checking, 0);
    if (r) {
      // ★ 不弹系统对话框（2026-09-15 用户要求）：有新版本 → 按钮亮小红点 +
      //   窗口内出一张小卡片（点它去下载页）；「已是最新」「查不到」仍只是
      //   按钮上的临时文字，几秒后自己消失。
      if (r->status == 0) {
        g_newVer = r->latest;
        g_newUrl = r->url;
      } else if (r->status == 1) {
        g_checkMsg = std::wstring(L"已是最新 v") + VER;
        SetTimer(h, TIMER_CHECKMSG, 4000, nullptr);
      } else {
        g_checkMsg = L"检查失败";
        SetTimer(h, TIMER_CHECKMSG, 4000, nullptr);
      }
      delete r;
    }
    InvalidateRect(h, nullptr, FALSE);
    return 0;
  }
  case WM_TIMER:
    if (w == TIMER_CHECKMSG) {
      KillTimer(h, TIMER_CHECKMSG);
      g_checkMsg.clear();
      InvalidateRect(h, nullptr, FALSE);
    }
    return 0;
  case WM_MOUSEMOVE: {
    int id = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id != st.hot) { st.hot = id; InvalidateRect(h, nullptr, FALSE); }
#ifndef RND_DBG_NOLEAVE   // 调试版可关掉：光标不在客户区时 TrackMouseEvent 会立刻
    TRACKMOUSEEVENT t{ sizeof(t) }; t.dwFlags = TME_LEAVE; t.hwndTrack = h;
    TrackMouseEvent(&t);  // 补发 WM_MOUSELEAVE，把假鼠标消息模拟出的悬停态清掉
#endif
    return 0;
  }
  case WM_MOUSELEAVE: st.hot = -1; InvalidateRect(h, nullptr, FALSE); return 0;
  case WM_LBUTTONDOWN: {
    // ★ 必须记录按下的是哪一项：WM_LBUTTONUP 用 `id == st.press` 判「按下与抬起
    //   在同一控件上」才执行动作（防止按下后拖走再松手误触发）。
    //   漏掉这一行 → st.press 永远是初值 -1 → **所有按钮/勾选框/下拉全都没反应**。
    st.press = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (st.press == ID_BANNER) g_bannerDown = true;
    return 0; }
  case WM_LBUTTONUP: {
    int id = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    bool bannerDown = g_bannerDown; g_bannerDown = false;
    if (id == st.press || (bannerDown && id == ID_BANNER)) {
      bool saveNow = false;
      if (id >= 0 && id < OPT_COUNT) { st.on[id] = !st.on[id]; InvalidateRect(h, nullptr, FALSE); saveNow = true; }
      // 点行头：展开/收起该项的选项（手风琴 —— 同时只开一行，免得撑破窗口）
      else if (id >= ID_ROW && id < ID_ROW + ROW_N) {
        int r = id - ID_ROW;
        st.openRow = (st.openRow == r) ? -1 : r;
        InvalidateRect(h, nullptr, FALSE);
      }
      // 点选项：写入对应的值
      else if (id >= ID_ROWITEM) {
        int r = (id - ID_ROWITEM) / 10, k = (id - ID_ROWITEM) % 10;
        if (r == ROW_OUTFIT && k < OUTFIT_N) { st.outfit = k; saveNow = true; }
        else if (r == ROW_SUBS && k < 3) { st.subs = k; saveNow = true; }
        else if (r == ROW_SCRN && k < SCRN_N) { st.scrn = k; SaveScreenCfg(); }
        else if (r == ROW_RES && k < RES_N) { st.res = k; SaveScreenCfg(); }
        st.openRow = -1;
        InvalidateRect(h, nullptr, FALSE);
      }
      else if (id == ID_START) { LaunchGame(); }
      else if (id == ID_CHECK) { StartUpdateCheck(); }
      else if (id == ID_BANNER) {   // 点更新卡片 → 打开下载页（卡片消失，红点熄灭）
        ShellExecuteW(h, L"open", g_newUrl.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
        g_newVer.clear(); g_newUrl.clear();
        InvalidateRect(h, nullptr, FALSE);
      }
      else if (id == ID_GITHUB) { ShellExecuteW(h, L"open", REPO_URL, nullptr, nullptr, SW_SHOWNORMAL); }
      else if (id == ID_CLOSE) { PostMessageW(h, WM_CLOSE, 0, 0); }
      // 立刻落盘：玩家可能在这里改完就关窗口、再用 Steam 或 boot.bat 直启游戏
      if (saveNow) SaveConfig();
    } else if (st.openRow >= 0 && id == -1) { st.openRow = -1; InvalidateRect(h, nullptr, FALSE); }
    st.press = -1; return 0;
  }
  case WM_PAINT: { PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps); Paint(dc); EndPaint(h, &ps); return 0; }
  case WM_ERASEBKGND: return 1;
  case WM_KEYDOWN: if (w == VK_ESCAPE) PostMessageW(h, WM_CLOSE, 0, 0); return 0;
  case WM_CLOSE: SaveConfig(); DestroyWindow(h); return 0;
  case WM_DESTROY: PostQuitMessage(0); return 0;
  }
  return DefWindowProcW(h, m, w, l);
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR, int) {
  g_dir = ExeDir();

  GdiplusStartupInput gi; ULONG_PTR token;
  GdiplusStartup(&token, &gi, nullptr);

  // 字体：GDI+ 的 PrivateFontCollection 无法加载 CFF/OTF 轮廓（本项目的
  // NotoSansCJKsc-Regular.otf 会返回 FontFamilyNotFound），故直接用系统中文字体。
  {
    const wchar_t* cand[] = { L"Microsoft YaHei UI", L"Microsoft YaHei",
                              L"SimHei", L"SimSun", L"MS Gothic" };
    for (auto nm : cand) {
      FontFamily* f = new FontFamily(nm);
      if (f->IsAvailable()) { g_ff = f; break; }
      delete f;
    }
    if (!g_ff) { g_ff = new FontFamily(L"Arial"); }
  }
  {
    // 主按钮字体：微软雅黑（Bold 字面），能画汉字。
    // 不要放 Bahnschrift/Segoe UI —— 它们画不出「开始游戏」这些汉字。
    const wchar_t* cand[] = { L"Microsoft YaHei", L"Microsoft YaHei UI",
                              L"SimHei", L"Noto Sans SC", L"SimSun" };
    for (auto nm : cand) {
      FontFamily* f = new FontFamily(nm);
      if (f->IsAvailable()) { g_ffTech = f; break; }
      delete f;
    }
    if (!g_ffTech) g_ffTech = g_ff;   // 兜底的兜底：正文中文字体也能画
  }
  LoadAppIconFromResource();
  LoadThemeImage();
  // ★ 必须在建窗口之前：窗口尺寸取决于左栏宽度，而左栏宽度由主题图比例算出来。
  ApplyThemeGeometry();
  LoadConfig();

  WNDCLASSEXW wc{ sizeof(wc) };
  wc.lpfnWndProc = WndProc; wc.hInstance = hInst; wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
  wc.lpszClassName = L"RNDZhLauncherWnd"; wc.hbrBackground = nullptr;
  wc.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(101));
  wc.hIconSm = wc.hIcon;
  RegisterClassExW(&wc);

  // 无标题栏：WS_POPUP，客户区 == 窗口（没有非客户区边框要画）。
  // 拖动靠 WM_NCHITTEST 返回 HTCAPTION（见 WndProc）。
  // 不加 WS_THICKFRAME：它会在客户区外留一圈 8px 边框，而我们自绘的界面
  // 只覆盖客户区，那圈边框没人画 —— 会露出未绘制的杂色。
  DWORD style = WS_POPUP;
  DWORD exStyle = WS_EX_APPWINDOW;   // WS_POPUP 窗口默认不进任务栏，显式要求
  // DPI 感知：先声明，再按【当前窗口 DPI】换算客户区尺寸。
  // 不声明的话 Windows 会把整个窗口位图拉伸（125% 缩放下发虚），
  // 而且 SetProcessDPIAware 之后再取 DPI 才是真实值。
  SetProcessDPIAware();
  HDC screen = GetDC(nullptr);
  float dpi = (float)GetDeviceCaps(screen, LOGPIXELSX);
  ReleaseDC(nullptr, screen);
  if (dpi <= 0) dpi = 96.f;
  S = dpi / 96.f;

  int cw = (int)(WIN_W * S + 0.5f), ch = (int)(WIN_H * S + 0.5f);
  RECT r{ 0, 0, cw, ch };
  AdjustWindowRectEx(&r, style, FALSE, exStyle);
  int ww = r.right - r.left, wh = r.bottom - r.top;
  int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
  g_hwnd = CreateWindowExW(exStyle, wc.lpszClassName, APP_TITLE.c_str(),
                           style, (sw - ww) / 2, (sh - wh) / 2, ww, wh,
                           nullptr, nullptr, hInst, nullptr);
  ShowWindow(g_hwnd, SW_SHOW); UpdateWindow(g_hwnd);

  // 启动即自动查一次更新（后台线程，不卡窗口）：有新版本时按钮亮小红点 +
  // 出现更新卡片，玩家不用点「检查更新」也能知道（2026-09-15 用户要求）。
  StartUpdateCheck();

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
  GdiplusShutdown(token);
  return 0;
}
