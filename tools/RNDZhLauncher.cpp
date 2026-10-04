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
#include <wincrypt.h>     // MD5（增量包校验）
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
#pragma comment(lib, "advapi32.lib")   // Crypto*（MD5）

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
static const wchar_t* VER = L"1.9";
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
  C_ROWALT  (255, 243, 246, 250),   // 设置行交替底纹（斑马纹：只做行边界暗示）
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

// ── 语言模式（2026-10-01 用户指定）──
// 0 = 中文（补丁注入生效）/ 1 = 日语（停用注入，进原版日文）
// 实现上**只把 dinput8.dll 改名**：它是补丁唯一的注入入口，改名后 Windows 加载器
// 回落到 System32 的真 dinput8.dll，LanguageBarrier 完全不跑。
// VSFilter.dll / languagebarrier 目录**不用动** —— 它们都是被 dinput8 加载/读取的，
// 注入不跑就都不生效，留着无害（用户确认「只改这一处即可」）。
// ⚠ 目录名含分号时，加载器读的是「分号后片段同名子目录」里那份 dinput8，
//   所以根目录 + 各片段子目录**都要改**（本项目踩过三次的坑）。
static const wchar_t* LANGMODE_LABEL[2] = { L"中文", L"日语" };
static const int LANGMODE_N = 2;
static const wchar_t* LANGMODE_KEY = L"langMode";
static const wchar_t* PATCHOFF_EXT = L".patchoff";   // 停用时的改名后缀

// ── 行间分隔线（2026-10-01 用户定稿：用线分割，要有设计感）──
// 设计：**左实右隐的渐隐线**（日式界面的「区切り線」做法）——
//   左端实、向右淡出到透明；不是贯穿实线（那像表格），也不是纯短刻度（太弱）。
//   既给出明确的分段信号，又不把版面切碎。颜色取自现有边框色，透明度渐变。
static void DrawRowSeparator(Graphics& g, const RectF& row) {
  float y = row.GetBottom() + 4.f;
  float x0 = row.X + 2.f, x1 = row.GetRight() - 60.f;   // 右端留白：不顶到边界
  LinearGradientBrush b(PointF(x0, y), PointF(x1, y),
                        Color(190, 200, 206, 216),    // 左端：淡灰蓝，可见
                        Color(0, 200, 206, 216));     // 右端：完全透明
  Pen p(&b, 1.f);
  g.DrawLine(&p, x0, y, x1, y);
}

static const wchar_t* SET_KEY = L"zzOutfitSet";

struct State {
  bool on[OPT_COUNT];
  int  subs;            // 0/1/2
  int  outfit;          // 0..4
  int  scrn;            // 0 = 窗口 / 1 = 全屏
  int  res;             // 0..2（1024*576 / 1280*720 / 1920*1080）
  int  langMode;        // 0 = 汉化版 / 1 = 原版（见 LANGMODE_LABEL）
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

// ── config.dat 缺失时补一份默认的（2026-10-03）──
//
// ★ 为什么必须补：config.dat 是**原版 MAGES launcher.exe** 在第一次「Start Game」
//   时创建的（文件里是它自己的 Screen Setting：显示模式/分辨率/窗口坐标/影片品质）。
//   我们的链路 Steam → boot.bat → RNDZhLauncher.exe → Game.exe **完全绕过了那个
//   启动器**，而本启动器对 config.dat 历来是「只改不造」（SaveScreenCfg 里那句
//   `if (!st.scrnOk) return;`）。于是「没跑过一次原版游戏就装补丁」的玩家
//   —— 新电脑、重装系统、清过存档 —— 存档目录里没有 config.dat，
//   Game.exe 启动时报 **「There is an error importing setup files.」**
//   （内部键 LANG_LAUNCHER_ERROR；同一资源块的简中/日文版分别是
//   「无法读取配置文件。」/「設定ファイルの読込みに失敗しました。」）。
//   CoZ 的安装说明因此要求「至少先从 Steam 启动一次游戏」；我们把那条删掉之后
//   就只剩这条路兜底。
//
// ★ 默认值取最保守的一组（**窗口 + 1024*576**）：宁可小、不可黑屏 ——
//   分辨率写高了玩家显示器不支持就进不去游戏，而本启动器的「画面」行
//   本来就是给这种情况留的救急入口。
//   实测本机两份 config.dat 都是 108 字节（日文旧格式曾是 76 字节，
//   游戏自己会升级），这里直接写 108 字节的当前格式。
//   +0x04 起 40 字节是控制器 GUID：全 0 = 未配置，游戏会走默认键位。
static const long kCfgSize = 108;        // 当前格式的完整长度
static const long kOffWidth = 0x2C, kOffHeight = 0x30;
static const long kOffWinX = 0x3C, kOffWinY = 0x40;
static const long kOffMovieQuality = 0x44, kOffLanguage = 0x48;

// 返回 true = 现在文件确实可用（本来就存在，或刚补成功）。
static bool EnsureConfigDat() {
  std::wstring p = ConfigDatPath();
  if (p.empty()) return false;

  {  // 已存在且够大 → 什么都不做
    std::ifstream f(p, std::ios::binary);
    if (f) {
      f.seekg(0, std::ios::end);
      if ((long)f.tellg() >= kCfgSize) return true;
    }
  }

  // 目录可能整条都不存在（全新机器连 My Games 都没有）
  std::wstring dir = p;
  size_t s = dir.find_last_of(L'\\');
  if (s != std::wstring::npos) EnsureDir(dir.substr(0, s));

  std::vector<unsigned char> buf((size_t)kCfgSize, 0);
  auto put = [&](long off, unsigned v) { memcpy(&buf[(size_t)off], &v, 4); };
  put(kOffWidth,  1024u);      // 窗口宽
  put(kOffHeight, 576u);       // 窗口高
  put(kOffDisplayMode, 0u);    // 0 = 窗口（不要全屏：全屏档位不匹配会黑屏）
  put(kOffResolution, 0u);     // 0 = 1024*576
  put(kOffWinX, 80u);          // 起始窗口位置（原版给的是居中偏左上）
  put(kOffWinY, 60u);
  put(kOffMovieQuality, 0u);
  put(kOffLanguage, 0u);

  {
    std::ofstream f(p, std::ios::binary | std::ios::trunc);
    if (!f) return false;
    f.write((const char*)buf.data(), (std::streamsize)buf.size());
    f.flush();
    if (!f) return false;
  }

  // 写完立刻回读校验：读不回来就当没写成功，删掉别留半成品害人
  LoadScreenCfg();
  if (!st.scrnOk) { DeleteFileW(p.c_str()); return false; }
  return true;
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
  emit(LANGMODE_KEY, st.langMode ? L"true" : L"false");   // true = 原版（停用注入）
  emit(L"showAllSettings", L"true");
  emit(L"rneMouseControls", L"true");
  static const wchar_t* MINE[] = { L"__schema_version", L"mouseControls",
    L"scrollDownToAdvanceText", L"disableScrollDownToCloseBacklog",
    SET_KEY, L"enableDxvk", L"karaokeSubs", LANGMODE_KEY,
    L"showAllSettings", L"rneMouseControls" };
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

  st.langMode = getb(LANGMODE_KEY, false) ? 1 : 0;   // 默认汉化版

  // 画面设置不在 config.json 里，读游戏自己的 config.dat（见 LoadScreenCfg）
  LoadScreenCfg();
}

// ── 语言模式：汉化版 / 原版（2026-10-01 用户指定）──
// 停用 = 把 dinput8.dll 改名成 dinput8.dll.patchoff；启用 = 改回来。
// **根目录 + 分号片段子目录都要改**（目录名含 ';' 时加载器读的是片段里那份）。
// 只改这一个文件就够：VSFilter.dll 是静态链进 dinput8 的，languagebarrier/ 是被
// dinput8 读取的数据目录 —— 注入不跑，两者都不会生效，留着无害。
// 改名是 O(1) 元数据操作，不改内容、不需要备份，失败也不损坏安装。
static std::vector<std::wstring> SemicolonFragments(const std::wstring& gameDir);  // 定义在后

static bool ApplyLangMode(bool native) {
  std::wstring dir = g_dir;
  std::vector<std::wstring> dirs{ dir };
  for (auto& frag : SemicolonFragments(dir)) dirs.push_back(dir + L"\\" + frag);
  int changed = 0, failed = 0;
  for (auto& d : dirs) {
    std::wstring on  = d + L"\\dinput8.dll";
    std::wstring off = on + PATCHOFF_EXT;
    if (native) {                       // 原版：改名停用
      if (FileExists(on) && !FileExists(off)) {
        if (MoveFileW(on.c_str(), off.c_str())) changed++; else failed++;
      }
    } else {                            // 汉化：改回来
      if (FileExists(off) && !FileExists(on)) {
        if (MoveFileW(off.c_str(), on.c_str())) changed++; else failed++;
      }
    }
  }
  if (failed) {
    MessageBoxW(g_hwnd,
        L"切换语言模式失败：dinput8.dll 被占用（游戏正在运行？）。\n\n请先完全退出游戏再切换。",
        L"语言模式", MB_ICONWARNING | MB_OK);
    return false;
  }
  return true;
}

// 当前磁盘状态是否已是目标模式（用于启动前判断要不要动文件）
static bool LangModeMatches(bool native) {
  std::wstring dir = g_dir;
  std::vector<std::wstring> dirs{ dir };
  for (auto& frag : SemicolonFragments(dir)) dirs.push_back(dir + L"\\" + frag);
  bool anyOn = false, anyOff = false;
  for (auto& d : dirs) {
    if (FileExists(d + L"\\dinput8.dll")) anyOn = true;
    if (FileExists(d + L"\\dinput8.dll" + PATCHOFF_EXT)) anyOff = true;
  }
  if (native) return anyOff && !anyOn;   // 原版态：只剩 .patchoff
  return anyOn;                          // 汉化态：dinput8.dll 在
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

// 量一段文字的**紧贴宽度**（GenericTypographic：不含 GDI+ 默认的额外留白）。
// ★ 绘制与命中判定共用这一个函数，保证「看到的框」与「点得到的区域」永远一致
//   （2026-10-01 用户反馈"文案和框对不上"）。
static float TextW(const wchar_t* s, Font* f) {
  static Graphics* mg = nullptr;
  if (!mg) mg = Graphics::FromHDC(CreateCompatibleDC(nullptr));
  RectF b;
  mg->MeasureString(s, -1, f, PointF(0.f, 0.f),
                    StringFormat::GenericTypographic(), &b);
  return b.Width;
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
  // ★ 层级：标签深色（"找什么"），当前值降一档灰（"现在是什么"）。
  //   两者原本同色同重，所以五行连读像"一片字"（2026-10-01 用户反馈"堆在一起"）。
  DrawTxt(g, label, F(15), C_TEXT, r.X + 4, r.Y + 8);
  // ★ 「值 + 三角」作为一个整体**右对齐到同一条右边界**（2026-10-01 用户反馈
  //   "右边空白没对齐"）：三角固定在最右，值紧贴在三角左侧。
  //   旧版值右对齐、三角再跟着值跑 → 三角位置随值长度浮动，右列看着参差。
  const float TRI_W = 7.f, GAP = 8.f;
  float right = r.GetRight() - 6.f;              // 三角右缘统一在这条线
  Font* fv = F(14);
  float vw = TextW(value, fv);
  float vx = right - TRI_W - GAP - vw;
  DrawTxt(g, value, fv, dim ? C_MUTED : C_DIM, vx, r.Y + 9);
  float cx = right - TRI_W / 2.f, cy = r.Y + 17;   // 三角中心：固定列
  SolidBrush db(open ? C_ACCENT : C_DIM);
  PointF tri[3];
  if (open) { tri[0] = { cx-4, cy-2 }; tri[1] = { cx+4, cy-2 }; tri[2] = { cx, cy+3 }; }
  else      { tri[0] = { cx-2, cy-4 }; tri[1] = { cx-2, cy+4 }; tri[2] = { cx+3, cy }; }
  g.FillPolygon(&db, tri, 3);
}

// 紧凑半格（并排的两格专用）：**每个格是独立控件**。
// ★ 2026-10-01 用户三轮反馈后的定稿：
//   ① 值必须贴住自己的标签（值离邻格标签太近会被读成别人的值）；
//   ② 悬停框必须紧贴内容（旧版左右各留一堆白，"框和文案对不上"）；
//   ③ **经典两列式**：左格内容贴左缘、右格内容贴右缘 —— 右格的三角因此落在
//      与其它行相同的三角列上，右边不再有一片莫名的空白；两格之间留自然间隔。
//   两格各自独立高亮/各自展开（**不做整行合并**：两个独立下拉共用一个高亮框，
//   会让人以为点下去展开同一个东西，市面上没有这种做法）。
static float CompactPairW(const wchar_t* label, const wchar_t* value) {
  return TextW(label, F(15)) + 8.f + TextW(value, F(14)) + 8.f + 7.f;
}
static RectF CompactContentRect(const RectF& r, const wchar_t* label,
                                const wchar_t* value, bool alignRight) {
  float w = CompactPairW(label, value) + 8.f;    // 两侧各留 4px 呼吸
  return RectF(alignRight ? (r.GetRight() - w - 2.f) : r.X, r.Y, w, 34.f);
}
static void DrawSettingRowCompact(Graphics& g, const RectF& r, const wchar_t* label,
                                  const wchar_t* value, bool hot, bool open,
                                  bool dim = false, bool alignRight = false) {
  RectF cap = CompactContentRect(r, label, value, alignRight);
  if (hot || open) FillRR(g, cap, 7, hot ? C_HOVER : C_PANEL);
  const float TRI_W = 7.f, GAP = 8.f;
  float right = alignRight ? (r.GetRight() - 6.f) : (r.X + 4.f + CompactPairW(label, value));
  Font* fv = F(14);
  float vw = TextW(value, fv);
  float vx = right - TRI_W - GAP - vw;
  Font* fl = F(15);
  DrawTxt(g, label, fl, C_TEXT, vx - 8.f - TextW(label, fl), r.Y + 8);
  DrawTxt(g, value, fv, dim ? C_MUTED : C_DIM, vx, r.Y + 9);
  float cx = right - TRI_W / 2.f, cy = r.Y + 17;
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

// 命中 id：0..OPT_COUNT-1 选项 / 200 开始 / 201 检查更新(兼「立即更新」) / 202 关闭 /
//         203 GitHub / 1000+i 第 i 个设置行的"行头"（点它展开/收起）
//         1100+i*10+k 第 i 行展开后的第 k 个选项
enum { ID_START = 200, ID_CHECK = 201, ID_CLOSE = 202, ID_GITHUB = 203,
       ID_ROW = 1000, ID_ROWITEM = 1100 };
// 四个设置行的语义（下标即 ROW 顺序）：0 = cosplay / 1 = 影片字幕 / 2 = 显示模式 / 3 = 分辨率
// 2026-10-01 起：显示模式与分辨率**并排各占半行**（同一个 ROW 槽位），
// 语言模式独占下一行。ROW_N 仍是 4，但 2/3 共用一行（见 RowRect）。
enum { ROW_OUTFIT = 0, ROW_SUBS = 1, ROW_SCRN = 2, ROW_RES = 3, ROW_LANG = 4 };

// 4 个复选框：行高 37（标题 15px + 灰色说明 11px）
// （原为 42；为了在**不加大窗口**的前提下腾出「画面」那一行，整体收紧 5px。
//   收紧后仍保持"标题→说明→下一条"的清晰层次，不是简单挤压。）
static RectF OptRect(int i)   { return RectF(RXL, 48.f + i * 37.f, RW - RXL, 26.f); }
// ★ 勾选框的**可点区域**（2026-10-01 用户指定：不要整行都能点，只有勾选方块本身）。
//   方块绘制在 (r.X, r.Y+2, 22, 22)，这里给一圈小余量便于点中（±4px）。
static RectF OptBoxRect(int i) {
  RectF r = OptRect(i);
  return RectF(r.X - 4.f, r.Y - 2.f, 30.f, 30.f);
}
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
// ── 分组（2026-10-01）──
// 右栏是「两段式清单」：上半 = 开关（复选框，点一下即生效），下半 = 设置（行内下拉）。
// ★ 分组的**唯一手段是「组标签 + 更大的组间间隔」**，不画线、不加框、不铺底色：
//   原来组间间隔（21px）比组内行距（37/46px）还小，两组"粘"在一起才显得乱；
//   现在组间（约 35px）> 组内行距（42px 那一档的视觉间隙），边界自己就出来了。
//   组标签复用已有的「选项」样式（12px C_MUTED），不是新装饰。
static const float ROW_Y0 = 224.f, ROW_STEP = 42.f, ROW_H = 34.f;
static const float HINT_OFF = 16.f;      // cosplay 那行小字占掉的高度
static const int ROW_N = 4;              // 行槽位数（显示模式/分辨率并排 = 第 2 槽）
// 第二组（设置）的组标签位置：与顶部「选项」标签的节奏一致（标签 → 18px → 内容）
static RectF Section2LabelRect() { return RectF(RXL, ROW_Y0 - 18.f, RW - RXL, 14.f); }
// 行槽位 → 实际 y：第 0 行 = cosplay，第 1 行 = 影片字幕，第 2 行 = 显示模式|分辨率（并排），
// 第 3 行 = 语言模式。逻辑行号仍用 ROW_* 常量。
static RectF RowSlotRect(int slot) {
  float dy = (slot >= 1) ? HINT_OFF : 0.f;   // 第 0 行（cosplay）之后让出小字位置
  return RectF(RXL, ROW_Y0 + slot * ROW_STEP + dy, RW - RXL, ROW_H);
}
// 兼容旧调用：ROW_SCRN / ROW_RES 都落到第 2 槽（并排，左右各半）；
// ROW_LANG 落到第 3 槽。其余按自身下标。
static RectF RowRect(int i) {
  int slot = (i == ROW_SCRN || i == ROW_RES) ? 2 : (i == ROW_LANG ? 3 : i);
  RectF r = RowSlotRect(slot);
  if (i == ROW_SCRN) { r.Width = (r.Width - 8.f) / 2.f; return r; }        // 左半
  if (i == ROW_RES)  { RectF l = RowSlotRect(slot);                       // 右半
                       l.X += (l.Width + 8.f) / 2.f;
                       l.Width = (l.Width - 8.f) / 2.f; return l; }
  return r;
}
// 逻辑行数（5）：cosplay / 影片字幕 / 显示模式 / 分辨率 / 语言模式
// （显示模式与分辨率并排占同一槽位，但各自是独立的下拉行）
static const int ROW_COUNT = 5;
// 各行的选项个数（下标 = ROW_* 常量）
static const int ROW_ITEM_N[ROW_COUNT] = { OUTFIT_N, 3, SCRN_N, RES_N, LANGMODE_N };
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
// ★ 「已是最新」常驻（2026-10-01 用户指定）：启动自动检查若判定已是最新，
//   按钮就停在这个字样上，不再几秒后回到「检查更新」—— 否则玩家看不出查过没有。
//   与 g_checkMsg 分开：g_checkMsg 是临时闪显（检查失败/升级完成），会被定时器清掉。
static std::wstring g_idleMsg;            // 常驻文案（"已是最新 vX.Y"），空 = 无

// 查到有新版本后的常驻状态（直到本版升级才消失）：
static std::wstring g_newVer;             // 远程版本号（如 "v1.3"），空 = 没有新版本
static std::wstring g_newUrl;             // 下载页链接（仅「只有全量」时跳转用）
static unsigned long long g_newDeltaSize = 0;  // 查到的增量大小（未装配也记，提示行用）

// status: 0 = 有新版本(仅全量) / 1 = 已是最新 / 2 = 查询失败 / 3 = 有新版本且有可用增量
// （2026-09-30 用户裁定：发现新版本**不出横幅卡片**，入口全部集成在「检查更新」
//   按钮上 —— 查出增量后按钮变「立即更新」，点它就地升级）
struct UpdFile { std::wstring path; std::string md5; };
struct DeltaInfo {
  std::wstring from;                    // 基线版本（"1.6"），匹配 languagebarrier\version.txt
  std::wstring file;                    // 增量包资产名（RNDZh-Update-vX_to_vY.7z）
  unsigned long long size = 0;          // 字节数（横幅显示用）
  std::string md5;                      // 增量包 md5（下载后必校验）
  std::vector<std::wstring> del;        // 该基线到达新版要删的文件（'/' 分隔相对路径）
  std::vector<UpdFile> files;           // 增量包含的文件 + 目标 md5（覆盖后逐一复核）
};
struct RemoteUpdate {
  std::wstring version;                 // 远端最新版本（"1.7"，无 v 前缀）
  std::vector<DeltaInfo> deltas;
};
struct UpdResult {
  int status;
  std::wstring latest;                  // 如 "v1.7"（横幅显示用）
  std::wstring url;                     // 全量兜底的下载页
  std::wstring localVer;                // 本地补丁版本（version.txt；空 = v1.5 及更早的安装）
  RemoteUpdate remote;
  int deltaIdx = -1;                    // 命中的基线增量下标（status==3 时有效）
  bool arms = false;                    // ★ 本次检查是否由玩家**手动点「检查更新」**触发。
                                        //   只有手动检查才把增量装配到按钮（第二级「立即更新」）；
                                        //   启动时的自动检查只亮红点 —— 检查绝不直接下载（用户裁定）
};

// ── 增量更新（v1.6 新增）──
//
// v1.5 及以前：查到新版本只能跳浏览器全量重装（233MB）。
// v1.6 起，Release 上随安装包一起发布「增量包 + update.json」两个资产，update.json
// 固定走 .../releases/latest/download/update.json（302 自动跟随）—— 一个 GET 就拿到
// 版本与全部增量，不需要解析 assets、不依赖 GitHub API（每小时 60 次的匿名限额）：
//
//   { "version": "1.7",
//     "setup": { "name": "RNDZh-Setup-v1.7.exe", "size": 244455135 },
//     "deltas": [
//       { "from": "1.6", "file": "RNDZh-Update-v1.6_to_v1.7.7z", "size": 4200000,
//         "md5": "...", "delete": ["languagebarrier/c0data/x.png"],
//         "files": [ {"path": "languagebarrier/patchdef.json", "md5": "..."} ] } ] }
//
// 本地版本标记 = languagebarrier\version.txt（安装器随包写入；增量应用后由本程序改写）。
// 没有它（v1.5 及更早装的）退回按启动器自身 VER 比较 —— 那时最多只能给全量兜底，
// 旧启动器没有这段代码，本来就只会打开下载页，行为一致。
//
// 应用流程：下载到 %TEMP% → md5 校验 → languagebarrier\7zr.exe 解包 → 写权限探测
//   （被拒则 UAC 自提权，由 --apply-update 子进程完成同样的应用流程）→ 备份被覆盖的
//   原文件 → 逐文件覆盖并复核 md5 → 处理 delete[] → 分号片段子目录同步（复刻安装器
//   6.5 步，漏了就是「根目录 DLL 新、片段 DLL 旧」的老坑）→ 最后写 version.txt
//   （前面任何一步失败，标记仍是旧版，下次检查会再次增量，幂等）。
// 启动器本体更新用「改名让位」：运行中的 exe 锁的是写/删，不锁改名。
// 永不触碰 boot.bat（语言 token 按安装而异）/ RNDZhSetup.exe / Game.exe / 卸载汉化.exe。

// 更新元数据基址（--update-base 可覆盖，本地测试指向 http 服务）。结尾强制带 '/'
static std::wstring g_updBase =
    L"https://github.com/Syun1524/RND_Chinese/releases/latest/download/";

// 更新运行状态：
//   g_updRun: 0 空闲 / 1 下载 / 2 校验·解压 / 3 应用（完成与失败都回 0，
//             结果走按钮上的临时文字 / 失败弹窗 —— 2026-09-30 用户裁定**去掉横幅**，
//             更新入口全部集成进「检查更新」按钮）
static volatile LONG g_updRun = 0;
static volatile LONG g_updBusy = 0;       // 一次完整更新流程进行中（防重入）
static int g_updPct = 0;                  // 0..100（下载/应用进度，按钮上显示）
static std::wstring g_updTmpDir;          // 本次更新的 %TEMP% 工作目录
static DeltaInfo g_delta;                 // 命中的增量（file 为空 = 无，走全量兜底）
static std::wstring g_remoteVer;          // 远端版本（无 v 前缀，应用后写进 version.txt）
static std::wstring g_localVer;           // 检查时读到的本地补丁版本
static bool g_headless = false;           // --selftest-update：无窗口跑完即退（自动化测试）

// ── 小工具 ──
static std::wstring TrimW(const std::wstring& s) {
  size_t a = s.find_first_not_of(L" \t\r\n");
  if (a == std::wstring::npos) return L"";
  size_t b = s.find_last_not_of(L" \t\r\n");
  return s.substr(a, b - a + 1);
}
// 增量元数据里的相对路径（'/' 分隔）→ 本地分隔符
static std::wstring NativeRel(const std::wstring& p) {
  std::wstring r = p;
  for (auto& c : r) if (c == L'/') c = L'\\';
  return r;
}
static std::wstring DirPart(const std::wstring& p) {
  size_t s1 = p.find_last_of(L'/'), s2 = p.find_last_of(L'\\');
  size_t k = std::wstring::npos;
  if (s1 != std::wstring::npos) k = s1;
  if (s2 != std::wstring::npos && (k == std::wstring::npos || s2 > k)) k = s2;
  return (k == std::wstring::npos) ? L"" : p.substr(0, k);
}
static std::wstring FmtMB(unsigned long long b) {
  wchar_t buf[40];
  if (b < 100 * 1024) {                       // KB 级（模拟/极小差量）显示 KB，别出 0.0MB
    swprintf(buf, 40, L"%dKB", (int)(b / 1024));
    return buf;
  }
  swprintf(buf, 40, L"%.1fMB", (double)b / (1024.0 * 1024.0));
  return buf;
}
// 左下角版本号显示的「当前补丁版本」：初始取 version.txt（没有则退启动器 VER），
// 增量应用成功后跟着新版本走 —— 不然玩家更新完了看到左下角还是旧号，会以为没更上
static std::wstring g_dispVer;

static bool ReadFileAll(const std::wstring& path, std::string& out) {
  out.clear();
  HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                         OPEN_EXISTING, 0, nullptr);
  if (h == INVALID_HANDLE_VALUE) return false;
  char buf[65536]; DWORD rd = 0;
  for (;;) {
    if (!ReadFile(h, buf, sizeof(buf), &rd, nullptr) || rd == 0) break;
    out.append(buf, rd);
  }
  CloseHandle(h);
  return true;                              // 空文件也算读到
}
static bool WriteFileAll(const std::wstring& path, const std::string& data) {
  HANDLE h = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, 0, nullptr);
  if (h == INVALID_HANDLE_VALUE) return false;
  DWORD wr = 0;
  BOOL ok = WriteFile(h, data.data(), (DWORD)data.size(), &wr, nullptr);
  CloseHandle(h);
  return ok && wr == data.size();
}

// 文件 MD5（WinCrypt，无第三方依赖）。失败返回 false。
static bool Md5File(const std::wstring& path, std::string& hex) {
  hex.clear();
  HCRYPTPROV hProv = 0;
  if (!CryptAcquireContextW(&hProv, nullptr, MS_DEF_PROV, PROV_RSA_FULL,
                            CRYPT_VERIFYCONTEXT)) return false;
  HCRYPTHASH hHash = 0;
  bool ok = CryptCreateHash(hProv, CALG_MD5, 0, 0, &hHash) != FALSE;
  if (ok) {
    HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                           OPEN_EXISTING, 0, nullptr);
    ok = (h != INVALID_HANDLE_VALUE);
    if (ok) {
      BYTE buf[65536]; DWORD rd = 0;
      for (;;) {
        if (!ReadFile(h, buf, sizeof(buf), &rd, nullptr) || rd == 0) break;
        if (!CryptHashData(hHash, buf, rd, 0)) { ok = false; break; }
      }
      CloseHandle(h);
    }
  }
  if (ok) {
    BYTE dg[16]; DWORD dglen = sizeof(dg);
    ok = CryptGetHashParam(hHash, HP_HASHVAL, dg, &dglen, 0) != FALSE && dglen == 16;
    if (ok) {
      static const char* HX = "0123456789abcdef";
      hex.resize(32);
      for (int i = 0; i < 16; i++) { hex[i * 2] = HX[dg[i] >> 4]; hex[i * 2 + 1] = HX[dg[i] & 15]; }
    }
  }
  if (hHash) CryptDestroyHash(hHash);
  if (hProv) CryptReleaseContext(hProv, 0);
  return ok;
}

// ── update.json 解析 ──
// 只服务我们自己生成的文件，不需要完整 JSON 解析器；按「键名 → 值」定位即可。
static bool JsonLocate(const std::string& s, const char* key, size_t from,
                       size_t* vBegin, size_t* vEnd) {
  std::string pat = std::string("\"") + key + "\"";
  size_t p = s.find(pat, from);
  if (p == std::string::npos) return false;
  size_t c = s.find(':', p + pat.size());
  if (c == std::string::npos) return false;
  size_t j = c + 1;
  while (j < s.size() && (s[j] == ' ' || s[j] == '\t' || s[j] == '\r' || s[j] == '\n')) j++;
  if (j >= s.size()) return false;
  *vBegin = j;
  if (s[j] == '"') {                        // 字符串值
    size_t q = j + 1;
    while (q < s.size()) {
      if (s[q] == '\\') { q += 2; continue; }
      if (s[q] == '"') break;
      q++;
    }
    if (q >= s.size()) return false;
    *vEnd = q + 1;
  } else if (s[j] == '[' || s[j] == '{') {
    // 数组/对象值：括号配对扫描（引号感知）。
    // ★ 不能走下面的标量扫描 —— 它遇到换行就停，而 update.json 是缩进多行的，
    //   "deltas": [ 会在第一行就被截断，整个增量数组静默变成空（测试抓到过）。
    int depth = 0;
    bool instr = false;
    size_t q = j;
    for (; q < s.size(); q++) {
      char c = s[q];
      if (instr) {
        if (c == '\\') { q++; continue; }
        if (c == '"') instr = false;
        continue;
      }
      if (c == '"') instr = true;
      else if (c == '[' || c == '{') depth++;
      else if (c == ']' || c == '}') { if (--depth == 0) { q++; break; } }
    }
    *vEnd = (q <= s.size()) ? q : s.size();
  } else {                                  // 数字 / true / false
    size_t q = j;
    while (q < s.size() && s[q] != ',' && s[q] != '}' && s[q] != ']' && s[q] != '\n') q++;
    *vEnd = q;
  }
  return true;
}
static std::string JsonStrVal(const std::string& s, const char* key, size_t from) {
  size_t b, e;
  if (!JsonLocate(s, key, from, &b, &e) || s[b] != '"') return "";
  std::string raw = s.substr(b + 1, e - b - 2);
  std::string out; out.reserve(raw.size());   // 常规转义兜底（我们生成的路径不含反斜杠）
  for (size_t i = 0; i < raw.size(); i++) {
    if (raw[i] == '\\' && i + 1 < raw.size()) { i++; out += (raw[i] == 'n') ? '\n' : raw[i]; }
    else out += raw[i];
  }
  return out;
}
static unsigned long long JsonNumVal(const std::string& s, const char* key, size_t from) {
  size_t b, e;
  if (!JsonLocate(s, key, from, &b, &e)) return 0;
  return _strtoui64(s.substr(b, e - b).c_str(), nullptr, 10);
}
static bool ParseUpdateJson(const std::string& js, RemoteUpdate& out) {
  out.deltas.clear();
  out.version = Utf8ToWide(JsonStrVal(js, "version", 0));
  if (out.version.empty()) return false;
  size_t db, de;
  if (!JsonLocate(js, "deltas", 0, &db, &de)) return true;   // 没有增量数组 = 只发全量
  if (db >= js.size() || js[db] != '[') return false;
  size_t i = db + 1;
  while (i < js.size() && i < de) {
    size_t ob = js.find('{', i);
    if (ob == std::string::npos || ob >= de) break;
    int depth = 0; size_t q = ob;
    for (; q < js.size(); q++) {
      if (js[q] == '{') depth++;
      else if (js[q] == '}') { if (--depth == 0) { q++; break; } }
    }
    std::string obj = js.substr(ob, q - ob);
    DeltaInfo d;
    d.file = Utf8ToWide(JsonStrVal(obj, "file", 0));
    d.from = Utf8ToWide(JsonStrVal(obj, "from", 0));
    d.md5  = JsonStrVal(obj, "md5", 0);
    d.size = JsonNumVal(obj, "size", 0);
    if (!d.file.empty() && !d.from.empty() && d.md5.size() == 32) {
      size_t lb, le;
      if (JsonLocate(obj, "delete", 0, &lb, &le) && lb < obj.size() && obj[lb] == '[') {
        size_t p = lb + 1;
        for (;;) {
          size_t q1 = obj.find('"', p);
          if (q1 == std::string::npos || q1 >= le) break;
          size_t q2 = obj.find('"', q1 + 1);
          if (q2 == std::string::npos) break;
          d.del.push_back(Utf8ToWide(obj.substr(q1 + 1, q2 - q1 - 1)));
          p = q2 + 1;
        }
      }
      if (JsonLocate(obj, "files", 0, &lb, &le) && lb < obj.size() && obj[lb] == '[') {
        size_t p = lb + 1;
        for (;;) {
          size_t o2 = obj.find('{', p);
          if (o2 == std::string::npos || o2 >= le) break;
          size_t c2 = obj.find('}', o2);
          if (c2 == std::string::npos) break;
          std::string fo = obj.substr(o2, c2 - o2 + 1);
          UpdFile uf;
          uf.path = Utf8ToWide(JsonStrVal(fo, "path", 0));
          uf.md5  = JsonStrVal(fo, "md5", 0);
          if (!uf.path.empty() && uf.md5.size() == 32) d.files.push_back(uf);
          p = c2 + 1;
        }
      }
      out.deltas.push_back(d);
    }
    i = q;
  }
  return true;
}

// ── 版本号 ──
static std::vector<int> VerNums(const std::wstring& s) {
  std::vector<int> v; std::wstring t;
  for (wchar_t c : s) {
    if (c >= L'0' && c <= L'9') t += c;
    else if (!t.empty()) { v.push_back(_wtoi(t.c_str())); t.clear(); }
  }
  if (!t.empty()) v.push_back(_wtoi(t.c_str()));
  return v;
}
static bool VerEq(const std::wstring& a, const std::wstring& b) { return VerNums(a) == VerNums(b); }

// 本地补丁版本：languagebarrier\version.txt（安装器写入，如 "1.6"）。
// 读不到（v1.5 及更早的安装）返回空 —— 调用方退回按启动器 VER 比较。
static std::wstring LocalVer() {
  std::string s;
  if (!ReadFileAll(g_dir + L"\\languagebarrier\\version.txt", s)) return L"";
  std::wstring w = TrimW(Utf8ToWide(s));
  if (!w.empty() && (w[0] == L'v' || w[0] == L'V')) w = w.substr(1);
  return w;
}

// ── 路径安检 ──
// 元数据由我们自己的脚本生成，但落在玩家机器上执行前仍要设防：
// 拒绝空/绝对/越界路径与受保护文件。
static bool SafeRelPath(const std::wstring& p) {
  if (p.empty()) return false;
  if (p.find(L"..") != std::wstring::npos) return false;
  if (p[0] == L'/' || p[0] == L'\\' || p.find(L':') != std::wstring::npos) return false;
  static const wchar_t* prot[] = { L"boot.bat", L"RNDZhSetup.exe", L"Game.exe", L"卸载汉化.exe" };
  for (auto n : prot) if (_wcsicmp(p.c_str(), n) == 0) return false;
  return true;
}
// 删除清单额外禁碰启动器本体（更新它走「改名让位」，不走删除）
static bool SafeDelPath(const std::wstring& p) {
  return SafeRelPath(p) && _wcsicmp(p.c_str(), L"RNDZhLauncher.exe") != 0;
}

// ── 分号片段子目录 ──
// 目录名含 ';' 时 Windows 加载器按分号切开、把片段当相对目录搜 DLL
// （AGENTS.md「重大发现」）。安装器第 6.5 步把 8 个代理文件拷进各片段目录；
// 增量更新替换了根目录的这些文件时必须同步刷新片段副本，否则游戏加载的还是旧 DLL
// ——「根目录是新的、片段是旧的」这个坑本项目踩过三次。
static const wchar_t* kProxyFiles[] = { L"dinput8.dll", L"d3d9", L"d3d10", L"d3d10_1",
                                        L"d3d10core", L"d3d11", L"dxgi", L"VSFilter.dll" };
static std::vector<std::wstring> SemicolonFragments(const std::wstring& gameDir) {
  std::vector<std::wstring> out;
  std::wstring name = gameDir;
  size_t sl = name.find_last_of(L"\\/");
  if (sl != std::wstring::npos) name = name.substr(sl + 1);
  for (size_t p = name.find(L';'); p != std::wstring::npos; p = name.find(L';', p)) {
    size_t q = name.find(L';', p + 1);
    std::wstring seg = (q == std::wstring::npos) ? name.substr(p + 1)
                                                 : name.substr(p + 1, q - p - 1);
    while (!seg.empty() && (seg.back() == L' ' || seg.back() == L'.')) seg.pop_back();
    if (!seg.empty()) out.push_back(seg);
    if (q == std::wstring::npos) break;
    p = q;                                   // for 循环的 find 会从 p 处重找，让位
  }
  return out;
}
static void CopyProxiesInto(const std::wstring& sub) {
  for (auto n : kProxyFiles) {
    std::wstring src = g_dir + L"\\" + n;
    if (FileExists(src)) CopyFileW(src.c_str(), (sub + L"\\" + n).c_str(), FALSE);
  }
}
static void SyncFragments() {
  // 动态片段：缺就建（与安装器 6.5 步一致）
  for (auto& frag : SemicolonFragments(g_dir)) {
    std::wstring sub = g_dir + L"\\" + frag;
    CreateDirectoryW(sub.c_str(), nullptr);
    DWORD a = GetFileAttributesW(sub.c_str());
    if (a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY))
      CopyProxiesInto(sub);
  }
  // 兼容旧版安装器的硬编码片段目录（存在才刷新，不新建）
  std::wstring hard = g_dir + L"\\NOTES DaSH";
  DWORD a = GetFileAttributesW(hard.c_str());
  if (a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY))
    CopyProxiesInto(hard);
}
static bool DeltaHasLauncher(const DeltaInfo& d) {
  for (auto& f : d.files)
    if (_wcsicmp(f.path.c_str(), L"RNDZhLauncher.exe") == 0) return true;
  return false;
}
// 自测诊断：最近一次 HttpGet 在 InternetOpenUrl 上失败的 URL 与 GetLastError
static std::wstring g_diagUrl;
static DWORD g_diagGle = 0;
static int g_diagStage = 0;        // RunCheckCore 走到哪一步（0=update.json 路径成功）
static std::string g_diagBody;     // update.json 响应前 200 字节
static DWORD g_diagStatus = 0;     // update.json 响应的 HTTP 状态码
static DWORD g_diagOutLen = 0;     // update.json 响应收到的字节数
static std::wstring g_diagLastReq; // 最近一次 HttpGet 实际请求的 URL（成功也记）
static DWORD g_diag1Status = 0;    // 第一次（update.json）调用的快照，兜底不覆盖
static DWORD g_diag1OutLen = 0;
static DWORD g_diag1Gle = 0;

// ── 环境探测 ──
static bool ProcessRunning(const wchar_t* exe) {
  HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
  if (snap == INVALID_HANDLE_VALUE) return false;
  PROCESSENTRY32W pe; pe.dwSize = sizeof(pe);
  bool found = false;
  if (Process32FirstW(snap, &pe)) {
    do { if (_wcsicmp(pe.szExeFile, exe) == 0) { found = true; break; } }
    while (Process32NextW(snap, &pe));
  }
  CloseHandle(snap);
  return found;
}
static bool CanWriteGameDir() {
  EnsureDir(g_dir + L"\\languagebarrier");
  std::wstring p = g_dir + L"\\languagebarrier\\.upd_probe";
  HANDLE h = CreateFileW(p.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, 0, nullptr);
  if (h == INVALID_HANDLE_VALUE) return false;
  CloseHandle(h); DeleteFileW(p.c_str());
  return true;
}

// ── 临时目录 / 解压 ──
// SHFileOperation 要求路径以双 \0 结尾
static void DelTree(const std::wstring& dir) {
  std::wstring from = dir;
  from.push_back(L'\0'); from.push_back(L'\0');
  SHFILEOPSTRUCTW op{};
  op.wFunc = FO_DELETE; op.pFrom = from.c_str();
  op.fFlags = FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI;
  SHFileOperationW(&op);
}
static std::wstring MakeTmpDir() {
  wchar_t t[MAX_PATH];
  GetTempPathW(MAX_PATH, t);
  std::wstring d = std::wstring(t) + L"RNDZhUpd";
  DelTree(d);                               // 上次残留（含旧的 update.json/payload）
  EnsureDir(d); EnsureDir(d + L"\\payload"); EnsureDir(d + L"\\backup");
  return d;
}
static bool Run7zExtract(const std::wstring& exe7z, const std::wstring& arc,
                         const std::wstring& outDir, DWORD* exitCode) {
  *exitCode = (DWORD)-1;
  // ★ -o 与路径之间不能有空格，含空格的路径把引号包在 -o 里面（7z 的解析规则）
  std::wstring cmd = L"\"" + exe7z + L"\" x \"" + arc + L"\" -o\"" + outDir + L"\" -y";
  STARTUPINFOW si{}; si.cb = sizeof(si);
  si.dwFlags = STARTF_USESHOWWINDOW; si.wShowWindow = SW_HIDE;
  PROCESS_INFORMATION pi{};
  if (!CreateProcessW(exe7z.c_str(), &cmd[0], nullptr, nullptr, FALSE,
                      CREATE_NO_WINDOW, nullptr, g_dir.c_str(), &si, &pi)) return false;
  WaitForSingleObject(pi.hProcess, 300000);        // 应用阶段不该超过 5 分钟
  GetExitCodeProcess(pi.hProcess, exitCode);
  CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
  return true;
}

// ── 应用增量 ──
// 把解包出的 payload 覆盖进游戏目录。返回 0 = 成功；失败时 err 给出原因，
// 调用方据 applied（本次真正落盘的文件）回滚（半途失败绝不留混合版本）。
// ★ 两段式：先把整份元数据安检完、再备份、最后覆盖。元数据不合法时游戏目录
//   一个字节都不碰 —— 旧版把安检与备份交织在一个循环里，中止时已备份一半，
//   而回滚按全量清单走，把「没来得及备份」当成「本次新增」删掉，误删玩家原文件
//   （2026-10-03 实测：卸载汉化.exe / 安装说明.txt 被删）。
static int ApplyPayload(const DeltaInfo& d, const std::wstring& newVer,
                        const std::wstring& tmpDir, std::wstring& err,
                        std::vector<std::wstring>& applied) {
  std::wstring payload = tmpDir + L"\\payload";
  std::wstring backup  = tmpDir + L"\\backup";
  // 0) 安检：整份元数据验完再动手
  for (auto& f : d.files)
    if (!SafeRelPath(f.path)) { err = L"增量元数据含非法路径：" + f.path; return 1; }
  // 0b) 备份将被覆盖的原文件
  for (auto& f : d.files) {
    std::wstring dest = g_dir + L"\\" + NativeRel(f.path);
    if (FileExists(dest)) {
      std::wstring bk = backup + L"\\" + NativeRel(f.path);
      std::wstring bkDir = DirPart(bk);
      if (!bkDir.empty()) EnsureDir(bkDir);
      if (!CopyFileW(dest.c_str(), bk.c_str(), FALSE)) { err = L"备份失败：" + f.path; return 1; }
    }
  }
  // 1) 覆盖（启动器本体例外：写到 .new，由「改名让位」在最后落位）
  int n = (int)d.files.size(), i = 0;
  for (auto& f : d.files) {
    i++;
    g_updPct = n ? i * 100 / n : 100;
    if (g_hwnd) PostMessageW(g_hwnd, WM_APP + 3, 0, 0);
    std::wstring src = payload + L"\\" + NativeRel(f.path);
    if (!FileExists(src)) { err = L"增量包缺文件：" + f.path; return 2; }
    if (_wcsicmp(f.path.c_str(), L"RNDZhLauncher.exe") == 0) {
      std::wstring nw = g_dir + L"\\RNDZhLauncher.new.exe";
      if (!CopyFileW(src.c_str(), nw.c_str(), FALSE)) { err = L"写入 RNDZhLauncher.new.exe 失败"; return 2; }
      std::string hx;
      if (!Md5File(nw, hx) || hx != f.md5) {
        DeleteFileW(nw.c_str());            // 半成品 .new 不能留（下次检查会再次增量）
        err = L"校验失败：RNDZhLauncher.new.exe";
        return 2;
      }
      continue;
    }
    std::wstring dest = g_dir + L"\\" + NativeRel(f.path);
    std::wstring ddir = DirPart(dest);
    if (!ddir.empty()) EnsureDir(ddir);
    // ★ 动手前就记账：复制中途失败（磁盘满等）会把目标写成半成品，同样必须回滚
    applied.push_back(f.path);
    if (!CopyFileW(src.c_str(), dest.c_str(), FALSE)) { err = L"覆盖失败：" + f.path; return 2; }
    std::string hx;
    if (!Md5File(dest, hx) || hx != f.md5) { err = L"校验失败：" + f.path; return 2; }
  }
  // 2) 删除清单（非法条目跳过不中断；条目本来就不存在也无所谓）
  for (auto& p : d.del) {
    if (!SafeDelPath(p)) continue;
    DeleteFileW((g_dir + L"\\" + NativeRel(p)).c_str());
  }
  // 3) 分号片段子目录的代理 DLL 副本同步
  SyncFragments();
  // 4) 最后才写版本标记
  EnsureDir(g_dir + L"\\languagebarrier");
  if (!WriteFileAll(g_dir + L"\\languagebarrier\\version.txt",
                    WideToUtf8(newVer) + "\r\n")) { err = L"写 version.txt 失败"; return 3; }
  return 0;
}
// 覆盖失败后的回滚：只回滚 applied 里真正落盘过的文件 ——
// 有备份的恢复原文件，没备份的（本次新增）删掉。
// ★ 绝不能按 d.files 全量走：没覆盖过的文件既没备份、也不是新增，
//   全量回滚会把玩家原文件当新增删掉（2026-10-03 事故的次生伤害）。
static void Rollback(const std::vector<std::wstring>& applied,
                     const std::wstring& tmpDir) {
  std::wstring backup = tmpDir + L"\\backup";
  for (auto& p : applied) {
    std::wstring bk = backup + L"\\" + NativeRel(p);
    std::wstring dest = g_dir + L"\\" + NativeRel(p);
    if (FileExists(bk)) CopyFileW(bk.c_str(), dest.c_str(), FALSE);
    else DeleteFileW(dest.c_str());
  }
}
// 自更新落位：把 .new 改名顶上（运行中的 exe 允许被改名，锁的是写/删）。
static bool FinalizeSelfUpdate(std::wstring& err) {
  std::wstring exe = g_dir + L"\\RNDZhLauncher.exe";
  std::wstring old = g_dir + L"\\RNDZhLauncher.old.exe";
  std::wstring nw  = g_dir + L"\\RNDZhLauncher.new.exe";
  if (!FileExists(nw)) return true;         // 本次没有本体更新
  DeleteFileW(old.c_str());                 // 上次残留（能删就删）
  if (!MoveFileW(exe.c_str(), old.c_str())) { err = L"旧启动器改名失败"; return false; }
  if (!MoveFileW(nw.c_str(), exe.c_str())) {
    MoveFileW(old.c_str(), exe.c_str());    // 回滚
    err = L"新启动器落位失败";
    return false;
  }
  DeleteFileW(old.c_str());                 // 自己还映射着它 —— 删不掉留给下次/卸载器清理
  return true;
}

// --update-base 指向本地 http 服务（自动化测试）时绕过系统代理：
// PRECONFIG 会把 127.0.0.1 也交给代理，代理连的是它自己的回环，必然失败。
// 只对回环 URL 生效，GitHub 正常走系统代理。
static bool IsLoopbackUrl(const std::wstring& url) {
  return url.find(L"//127.0.0.1:") != std::wstring::npos
      || url.find(L"//localhost:") != std::wstring::npos;
}
static void BypassProxyForLoopback(HINTERNET hNet, const std::wstring& url) {
  if (!IsLoopbackUrl(url)) return;
  INTERNET_PROXY_INFO pi{};
  pi.dwAccessType = INTERNET_OPEN_TYPE_DIRECT;
  InternetSetOptionW(hNet, INTERNET_OPTION_PROXY, &pi, sizeof(pi));
}

// 流式下载到文件（增量包可达几十 MB，不能像 HttpGet 那样全进内存）。
// 进度写 g_updPct，每变一个百分点请求一次重绘（WM_APP+3）。
static bool HttpDownloadToFile(const std::wstring& url, const std::wstring& dest) {
  HINTERNET hNet = InternetOpenW(L"RNDZhLauncher", INTERNET_OPEN_TYPE_PRECONFIG,
                                 nullptr, nullptr, 0);
  if (!hNet) return false;
  BypassProxyForLoopback(hNet, url);
  HINTERNET hUrl = InternetOpenUrlW(hNet, url.c_str(), nullptr, 0,
      INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE, 0);
  if (!hUrl) { InternetCloseHandle(hNet); return false; }
  bool ok = false;
  DWORD status = 0, slen = sizeof(status);
  // >=400 视为失败（404 = 该版本没发增量包等）；重定向后拿到的是最终响应码
  if (HttpQueryInfoW(hUrl, HTTP_QUERY_STATUS_CODE | HTTP_QUERY_FLAG_NUMBER,
                     &status, &slen, nullptr) && status >= 400) {
    InternetCloseHandle(hUrl); InternetCloseHandle(hNet);
    return false;
  }
  unsigned long long total = 0;
  DWORD need = 0, nlen = sizeof(need);
  if (HttpQueryInfoW(hUrl, HTTP_QUERY_CONTENT_LENGTH | HTTP_QUERY_FLAG_NUMBER,
                     &need, &nlen, nullptr))
    total = need;
  HANDLE hFile = CreateFileW(dest.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, 0, nullptr);
  if (hFile != INVALID_HANDLE_VALUE) {
    BYTE buf[65536]; DWORD rd = 0;
    unsigned long long done = 0;
    int lastPct = -1;
    ok = true;
    while (InternetReadFile(hUrl, buf, sizeof(buf), &rd)) {
      if (rd == 0) break;
      DWORD wr = 0;
      if (!WriteFile(hFile, buf, rd, &wr, nullptr) || wr != rd) { ok = false; break; }
      done += rd;
      int pct = total ? (int)(done * 100 / total) : 0;
      if (pct != lastPct) {
        lastPct = pct;
        g_updPct = pct;
        if (g_hwnd) PostMessageW(g_hwnd, WM_APP + 3, 0, 0);
      }
    }
    CloseHandle(hFile);
  }
  InternetCloseHandle(hUrl); InternetCloseHandle(hNet);
  return ok;
}

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

static bool HttpGet(const std::wstring& url, std::string& out, DWORD maxBytes = 65536) {
  out.clear();
  g_diagLastReq = url;
  HINTERNET hNet = InternetOpenW(L"RNDZhLauncher", INTERNET_OPEN_TYPE_PRECONFIG,
                                 nullptr, nullptr, 0);
  if (!hNet) { g_diagGle = GetLastError(); g_diagUrl = url; return false; }
  BypassProxyForLoopback(hNet, url);
  HINTERNET hUrl = InternetOpenUrlW(hNet, url.c_str(), nullptr, 0,
      INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE, 0);
  if (!hUrl) { g_diagGle = GetLastError(); g_diagUrl = url; InternetCloseHandle(hNet); return false; }
  DWORD status = 0, slen = sizeof(status);
  bool netOk = !HttpQueryInfoW(hUrl, HTTP_QUERY_STATUS_CODE | HTTP_QUERY_FLAG_NUMBER,
                               &status, &slen, nullptr) || status < 400;
  g_diagStatus = netOk ? status : 0xFFFFFFFF;
  char buf[4096]; DWORD rd = 0;
  while (netOk && InternetReadFile(hUrl, buf, sizeof(buf), &rd) && rd > 0) {
    out.append(buf, rd);
    if (out.size() > maxBytes) break;    // 防跑飞（update.json 会传更大的上限）
  }
  g_diagOutLen = (DWORD)out.size();
  InternetCloseHandle(hUrl);
  InternetCloseHandle(hNet);
  return netOk && !out.empty();
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

// 检查核心：先问 update.json（一个 GET 拿到版本 + 全部增量，不依赖 GitHub API、
// 不吃每小时 60 次的匿名限额）；拿不到再退回 releases/latest → tags 的老路。
// 版本比较基准 = languagebarrier\version.txt（补丁版本），没有它才退回启动器 VER
// —— 增量只更新内容不动启动器时，VER 会落后于补丁版本，必须用 version.txt 比对。
static UpdResult* RunCheckCore(bool arms) {
  UpdResult* r = new UpdResult{ 2, L"", REL_URL };
  r->arms = arms;
  r->localVer = LocalVer();
  std::wstring cmpBase = r->localVer.empty() ? std::wstring(VER) : r->localVer;
  std::string js;
  bool got    = HttpGet(g_updBase + L"update.json", js, 4 << 20);
  // 第一次调用的快照（后面兜底的 HttpGet 会覆盖全局诊断）
  DWORD st1 = g_diagStatus, ol1 = g_diagOutLen, gl1 = g_diagGle;
  g_diag1Status = st1; g_diag1OutLen = ol1; g_diag1Gle = gl1;
  std::wstring req1 = g_diagLastReq;
  bool parsed = got && ParseUpdateJson(js, r->remote);
  bool haveVer = parsed && !r->remote.version.empty();
  if (!haveVer) {                       // 自测诊断：1=没取到 2=解析失败 3=version 空
    g_diagStage = !got ? 1 : (!parsed ? 2 : 3);
    g_diagBody  = js.substr(0, 200);
    g_diagStatus = st1; g_diagOutLen = ol1; g_diagGle = gl1; g_diagUrl = req1;
  }
  if (haveVer) {
    r->latest = L"v" + r->remote.version;
    r->url = REL_URL;
    if (VerNewer(r->remote.version, cmpBase)) {
      if (!r->localVer.empty()) {
        for (int i = 0; i < (int)r->remote.deltas.size(); i++)
          if (VerEq(r->remote.deltas[i].from, r->localVer)) { r->deltaIdx = i; break; }
      }
      r->status = (r->deltaIdx >= 0) ? 3 : 0;    // 无匹配基线 → 只能给全量兜底
    } else {
      r->status = 1;
    }
    return r;
  }
  // 兜底：releases/latest（能拿到 html_url 直达下载页）；没有 release 退 tags 第一个
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
  return r;
}
static DWORD WINAPI UpdateThread(LPVOID lp) {
  UpdResult* r = RunCheckCore(lp != nullptr);   // 参数非空 = 玩家手动点的「检查更新」
  PostMessageW(g_hwnd, WM_APP + 2, 0, (LPARAM)r);
  return 0;
}

// arms=true：玩家手动点的检查 → 查出增量后装配「立即更新」（第二级）；
// arms=false：启动自动检查 → 只亮红点，绝不装配下载（检查≠下载，用户裁定）。
static void StartUpdateCheck(bool arms) {
  if (InterlockedCompareExchange(&g_checking, 1, 0) != 0) return;   // 已在查
  InvalidateRect(g_hwnd, nullptr, FALSE);
  HANDLE t = CreateThread(nullptr, 0, UpdateThread, (LPVOID)(intptr_t)(arms ? 1 : 0), 0, nullptr);
  if (t) CloseHandle(t);
  else   InterlockedExchange(&g_checking, 0);
}

// ── 增量更新执行 ──
struct UpdDone { bool ok; bool selfUpdated; std::wstring ver; std::wstring err; };

// 完整更新流程：下载 → md5 校验 → 解压 → 应用。交互模式在后台线程跑；
// --selftest-update 同步调用。返回值 new 出来，调用方负责释放。
static UpdDone* RunUpdateCore() {
  UpdDone* r = new UpdDone{ false, false, g_remoteVer, L"" };
  do {
    if (!FileExists(g_dir + L"\\Game.exe")) {
      r->err = L"未找到 Game.exe，请把启动器放在游戏根目录再更新"; break;
    }
    if (ProcessRunning(L"Game.exe")) {
      r->err = L"游戏正在运行，请先退出游戏再更新（补丁文件被占用）"; break;
    }
    if (!FileExists(g_dir + L"\\languagebarrier\\7zr.exe")) {
      r->err = L"缺少 languagebarrier\\7zr.exe，请用全量安装包升级"; break;
    }
    // 元数据快照进临时目录：UAC 提权的子进程读不到本进程的内存，只能读文件
    std::string meta;
    if (!HttpGet(g_updBase + L"update.json", meta, 4 << 20)
        || !WriteFileAll(g_updTmpDir + L"\\update.json", meta)) {
      r->err = L"update.json 下载失败"; break;
    }
    // 1) 下载
    g_updRun = 1; g_updPct = 0;
    if (g_hwnd) PostMessageW(g_hwnd, WM_APP + 3, 0, 0);
    std::wstring arc = g_updTmpDir + L"\\" + NativeRel(g_delta.file);
    if (!HttpDownloadToFile(g_updBase + g_delta.file, arc)) {
      r->err = L"增量包下载失败，请检查网络后重试"; break;
    }
    // 2) 校验 + 解压
    g_updRun = 2; g_updPct = 0;
    if (g_hwnd) PostMessageW(g_hwnd, WM_APP + 3, 0, 0);
    std::string hx;
    if (!Md5File(arc, hx) || hx != g_delta.md5) {
      r->err = L"增量包校验失败（md5 不符），请重试或改用全量安装包"; break;
    }
    DWORD code = (DWORD)-1;
    if (!Run7zExtract(g_dir + L"\\languagebarrier\\7zr.exe", arc,
                      g_updTmpDir + L"\\payload", &code) || code != 0) {
      r->err = L"增量包解压失败（7zr 退出码 " + std::to_wstring((unsigned long)code) + L"）";
      break;
    }
    // 3) 应用：写不进游戏目录就 UAC 自提权，由 --apply-update 子进程完成同样的应用流程
    g_updRun = 3;
    if (CanWriteGameDir()) {
      std::vector<std::wstring> applied;
      int rc = ApplyPayload(g_delta, g_remoteVer, g_updTmpDir, r->err, applied);
      g_diagStage = 100 + rc;              // 自测诊断：应用阶段返回码
      if (rc != 0) { Rollback(applied, g_updTmpDir); break; }
      if (DeltaHasLauncher(g_delta)) {
        // 本体落位必须在这里做（提权路径由子进程做）：先把 .new 备好，
        // 成功后靠「改名让位」换上 —— 漏了这步，重启拉起的还是旧本体。
        std::wstring e2;
        if (!FinalizeSelfUpdate(e2)) { Rollback(applied, g_updTmpDir); r->err = e2; break; }
      }
      r->selfUpdated = DeltaHasLauncher(g_delta);
      r->ok = true;                        // ★ 应用内路径的成功出口（曾漏掉 → 恒报失败）
    } else {
      if (g_hwnd) PostMessageW(g_hwnd, WM_APP + 3, 0, 0);
      std::wstring exe = g_dir + L"\\RNDZhLauncher.exe";
      std::wstring prm = L"--apply-update \"" + g_updTmpDir + L"\" \"" + g_delta.file + L"\"";
      SHELLEXECUTEINFOW se{ sizeof(se) };
      se.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI;   // UAC 被拒要自己感知
      se.lpVerb = L"runas"; se.lpFile = exe.c_str(); se.lpParameters = prm.c_str();
      se.nShow = SW_HIDE; se.hwnd = g_hwnd;
      if (!ShellExecuteExW(&se)) {
        r->err = (GetLastError() == ERROR_CANCELLED)
            ? L"已取消管理员授权，更新未应用"
            : L"无法请求管理员权限，请右键以管理员身份运行启动器后重试";
        break;
      }
      WaitForSingleObject(se.hProcess, 300000);
      DWORD ec = 1; GetExitCodeProcess(se.hProcess, &ec);
      CloseHandle(se.hProcess);
      if (ec != 0) {
        std::string log;
        ReadFileAll(g_updTmpDir + L"\\apply.log", log);
        r->err = log.empty()
            ? L"提权应用失败（退出码 " + std::to_wstring((unsigned long)ec) + L"）"
            : Utf8ToWide(log);
        break;
      }
      r->ok = true;
      r->selfUpdated = DeltaHasLauncher(g_delta);   // 子进程已把本体落位
    }
  } while (0);
  if (r->ok) DelTree(g_updTmpDir);          // 成功就清 %TEMP%；失败留着便于排查
  return r;
}
static DWORD WINAPI UpdateRunThread(LPVOID) {
  UpdDone* r = RunUpdateCore();
  PostMessageW(g_hwnd, WM_APP + 4, 0, (LPARAM)r);
  return 0;
}
// 点横幅「一键更新」进入（防重入）
static void StartUpdateRun(HWND h) {
  if (InterlockedCompareExchange(&g_updBusy, 1, 0) != 0) return;
  if (g_delta.file.empty() || g_updRun != 0) { InterlockedExchange(&g_updBusy, 0); return; }
  g_updTmpDir = MakeTmpDir();
  // 顺手清上次自更新被占用删不掉的残留
  DeleteFileW((g_dir + L"\\RNDZhLauncher.old.exe").c_str());
  DeleteFileW((g_dir + L"\\RNDZhLauncher.new.exe").c_str());
  InvalidateRect(h, nullptr, FALSE);
  HANDLE t = CreateThread(nullptr, 0, UpdateRunThread, nullptr, 0, nullptr);
  if (t) CloseHandle(t);
  else { InterlockedExchange(&g_updBusy, 0); g_updRun = 0; }
}

// UAC 提权后的应用阶段子进程：父进程写不进游戏目录时，以管理员身份重跑「应用」。
// 不建窗口；交代 = %TEMP% 里的 apply.log（空 = 成功）+ 退出码（0 成功）。
static int RunApplyChild(const std::wstring& tmpDir, const std::wstring& deltaFile) {
  g_dir = ExeDir();
  std::string js;
  std::wstring err;
  int code = 1;
  do {
    if (!ReadFileAll(tmpDir + L"\\update.json", js)) { err = L"提权子进程读不到 update.json"; break; }
    RemoteUpdate ru;
    if (!ParseUpdateJson(js, ru)) { err = L"提权子进程解析 update.json 失败"; break; }
    const DeltaInfo* d = nullptr;
    for (auto& x : ru.deltas) if (x.file == deltaFile) { d = &x; break; }
    if (!d) { err = L"update.json 里没有增量 " + deltaFile; break; }
    std::vector<std::wstring> applied;
    int rc = ApplyPayload(*d, ru.version, tmpDir, err, applied);
    if (rc != 0) { Rollback(applied, tmpDir); code = rc; break; }
    if (DeltaHasLauncher(*d)) {
      if (!FinalizeSelfUpdate(err)) { code = 5; break; }
    }
    code = 0;
  } while (0);
  WriteFileAll(tmpDir + L"\\apply.log", WideToUtf8(err));   // 空 = 成功
  return code;
}

// --selftest-update 的结果落盘（自动化测试读取），固定 %TEMP%\rndzh_upd_selftest.json
static void WriteSelftestResult(const UpdResult* chk, const UpdDone* done) {
  std::wstring js = L"{";
  js += L"\"check_status\":" + std::to_wstring(chk ? chk->status : -1);
  js += L",\"remote\":\"" + (chk ? chk->latest : L"") + L"\"";
  js += L",\"local\":\"" + (chk ? chk->localVer : L"") + L"\"";
  js += L",\"delta_found\":" + std::to_wstring(chk && chk->deltaIdx >= 0 ? 1 : 0);
  js += L",\"ok\":" + std::wstring(done && done->ok ? L"true" : L"false");
  js += L",\"selfUpdated\":" + std::wstring(done && done->selfUpdated ? L"true" : L"false");
  js += L",\"err\":\"" + [&]{ std::wstring e = done ? done->err : L"";
                              for (auto& c : e) if (c == L'"' || c == L'\\') c = L'\'';
                              return e; }() + L"\"";
  js += L",\"diag_gle\":" + std::to_wstring((unsigned long)g_diagGle);
  js += L",\"diag_url\":\"" + g_diagUrl + L"\"";
  js += L",\"diag_stage\":" + std::to_wstring(g_diagStage);
  js += L",\"diag_status\":" + std::to_wstring((unsigned long)g_diag1Status);
  js += L",\"diag_outlen\":" + std::to_wstring((unsigned long)g_diag1OutLen);
  js += L",\"diag_gle\":" + std::to_wstring((unsigned long)g_diag1Gle);
  js += L"}";
  wchar_t t[MAX_PATH]; GetTempPathW(MAX_PATH, t);
  WriteFileAll(std::wstring(t) + L"rndzh_upd_selftest.json", WideToUtf8(js));
}

// 打开外部链接。ShellExecuteW 返回值 <= 32 就是失败（没有默认浏览器、被安全软件
// 拦下、URL 非法…），此时**不能什么都不做** —— 玩家看到的就是"点了没反应"。
// 退化成把链接显示出来让他手动复制（2026-09-29 用户反馈"不跳转"）。
// 返回是否成功打开，调用方据此决定要不要收起卡片。
static bool OpenUrl(HWND h, const wchar_t* url) {
  if (!url || !*url) url = REL_URL;
  HINSTANCE r = ShellExecuteW(h, L"open", url, nullptr, nullptr, SW_SHOWNORMAL);
  if ((INT_PTR)r > 32) return true;
  std::wstring msg = L"没能自动打开浏览器，请手动复制下面的链接：\n\n";
  msg += url;
  MessageBoxW(h, msg.c_str(), L"打开下载页", MB_ICONINFORMATION | MB_OK);
  return false;
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
    // 版本号压在图上：左下角（显示当前补丁版本，增量后跟着变），图上多半是
    // 深色，用白字加一层淡阴影保证可读
    {
      RectF vb(12, (float)WIN_H - 30, 80, 20);
      SolidBrush sh(Color(90, 0, 0, 0));
      gr.FillRectangle(&sh, RectF(vb.X + 1, vb.Y + 1, 58, 18));
      DrawTxt(gr, (L"v" + g_dispVer).c_str(), F(12), C_WHITE, vb.X, vb.Y);
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

    // ── 设置组：先画组标签（与顶部「选项」同款，12px 灰）──
    // 分组靠"标签 + 更大的组间间隔"，不画线不加框（见 Section2LabelRect 注释）。
    DrawTxt(gr, L"设置", F(12), C_MUTED, RXL, Section2LabelRect().Y);

    // ── 设置行：cosplay / 影片字幕 / 显示模式|分辨率（并排各半）/ 语言模式 ──
    // 收起态 = 「标签 ……… 当前值 ▸」；点行头展开该项的选项列表。
    // 全屏时分辨率那格淡一档（它不生效），但仍可点开 ——
    // 玩家常要先选好分辨率再切回窗口模式。
    {
      // 显示模式与分辨率**并排**（2026-10-01 用户指定：各缩一半、放同一行），
      // 语言模式独占下面一行。
      // （斑马纹已撤：改用行间渐隐线分割，见下方 DrawRowSeparator）
      DrawSettingRow(gr, RowRect(ROW_OUTFIT), L"cosplay 模式",
                     OUTFIT_LABEL[st.outfit], st.hot == ID_ROW + ROW_OUTFIT,
                     st.openRow == ROW_OUTFIT, false);
      DrawSettingRow(gr, RowRect(ROW_SUBS), L"影片字幕",
                     SUBS_LABEL[st.subs], st.hot == ID_ROW + ROW_SUBS,
                     st.openRow == ROW_SUBS, false);
      // 显示模式/分辨率：经典两列（左格贴左、右格贴右，见 DrawSettingRowCompact）
      DrawSettingRowCompact(gr, RowRect(ROW_SCRN), L"显示模式",
                            SCRN_LABEL[st.scrn], st.hot == ID_ROW + ROW_SCRN,
                            st.openRow == ROW_SCRN, false, /*alignRight=*/false);
      DrawSettingRowCompact(gr, RowRect(ROW_RES), L"分辨率",
                            RES_LABEL[st.res], st.hot == ID_ROW + ROW_RES,
                            st.openRow == ROW_RES, st.scrn == 1, /*alignRight=*/true);
      DrawSettingRow(gr, RowRect(ROW_LANG), L"语言模式",
                     LANGMODE_LABEL[st.langMode], st.hot == ID_ROW + ROW_LANG,
                     st.openRow == ROW_LANG, false);
      // 行间轻量分隔线（极淡短刻度，只做分组暗示，不画满框）——
      // 画在行与行之间的空隙里；展开下拉时不画，免得和弹层打架。
      if (st.openRow < 0) {
        DrawRowSeparator(gr, RowRect(ROW_OUTFIT));
        DrawRowSeparator(gr, RowRect(ROW_SUBS));
        DrawRowSeparator(gr, RowSlotRect(2));       // 显示模式|分辨率 那一槽
      }
      // 行间分隔线（渐隐线，见 DrawRowSeparator）——展开下拉时不画，免得和弹层打架
      if (st.openRow < 0) {
        DrawRowSeparator(gr, RowRect(ROW_OUTFIT));
        DrawRowSeparator(gr, RowRect(ROW_SUBS));
        DrawRowSeparator(gr, RowSlotRect(2));       // 显示模式|分辨率 那一槽
      }
      // cosplay 那行下方的小字 —— 只有这一行有（用户 2026-09-24 指定）。
      // 其余行看字面就懂，不解释。
      DrawTxtW(gr, OUTFIT_HINT, F(11), C_MUTED,
               RowHintRect().X, RowHintRect().Y, RW - RXL);
    }

    // ── 更新反馈全部走弹窗与按钮（2026-09-30 用户裁定：不要横幅、不要长文案行）──
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

    // ── 更新提示：**没有横幅卡片**（2026-09-30 用户裁定：排版难看且多余）。
    //    发现新版本 → 「检查更新」按钮变「立即更新」+ 小红点，点击就地升级；
    //    只有全量时按钮是「前往下载」。全部状态都收敛在按钮上，见下方按钮绘制。

    // ── 「检查更新」小按钮：贴在「开始游戏」左侧 ──
    // 点它去 GitHub 查最新版本：有新版本 → 右上角亮小红点 + 窗口内出小卡片
    // （**不弹系统对话框**）；「已是最新」「查不到」直接显示在按钮上、
    // 几秒后自动恢复，不打断玩家。
    // 网络请求在后台线程跑（见 UpdateThread），查期间显示「检查中…」并挡住重复点击。
    // ★ 启动即自动查一次（见 wWinMain），有更新不用点按钮也会亮红点。
    { RectF cr = CheckRect();
      bool updating = (g_updRun >= 1 && g_updRun <= 3);
      bool busy = (g_checking != 0) || updating;
      bool hot  = (st.hot == ID_CHECK) && !busy;
      SolidBrush fillb(hot ? C_HOVER : C_PANEL);
      gr.FillRectangle(&fillb, cr);
      Pen bp(hot ? C_DIM : C_BORDER, 1.f);
      gr.DrawRectangle(&bp, cr);
      wchar_t upd[32];
      swprintf(upd, 32, L"更新中 %d%%", g_updPct);
      const wchar_t* txt = (g_checking != 0) ? L"检查中…"
                        : updating ? upd
                        : (!g_checkMsg.empty() ? g_checkMsg.c_str()
                        : (!g_idleMsg.empty() ? g_idleMsg.c_str() : L"检查更新"));
      DrawTxtW(gr, txt, F(11), busy ? C_MUTED : C_DIM, cr.X, cr.Y + 5, cr.Width, 1);
      // 小红点：查出有新版本后常亮，升级完成即熄
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
    else if (st.openRow == ROW_LANG)
      DrawRowItems(gr, ROW_LANG, LANGMODE_N, LANGMODE_LABEL, st.langMode, st.hot);
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
  // 更新进行中不进游戏：补丁文件正被替换，拉起游戏会锁文件、半新半旧
  if (g_updRun >= 1 && g_updRun <= 3) {
    MessageBoxW(g_hwnd, L"正在更新，请等更新完成后再开始游戏。", L"更新进行中",
                MB_ICONINFORMATION | MB_OK);
    return;
  }
  SaveConfig();
  ApplyDxvk(st.on[OPT_DXVK]);
  // 语言模式：确保磁盘状态与所选模式一致（玩家可能绕过启动器改过文件）
  if (!LangModeMatches(st.langMode == 1)) {
    ApplyLangMode(st.langMode == 1);
  }
  const wchar_t* lang = DetectLang();   // 跟随玩家原本的版本（存档目录随之）

  // config.dat 兜底：这份文件历来由原版 MAGES launcher.exe 首次启动时创建，
  // 而我们的链路绕过了它 —— 没跑过原版就装补丁的玩家会缺这个文件，
  // Game.exe 随后弹「There is an error importing setup files.」。见 EnsureConfigDat。
  // 失败不拦：也许是只读盘/权限问题，让玩家自己从 Steam 走一次原版即可。
  EnsureConfigDat();

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
  if (st.openRow >= 0 && st.openRow < ROW_COUNT) {
    int n = ROW_ITEM_N[st.openRow];
    for (int k = 0; k < n; k++)
      if (in(RowItemRect(st.openRow, n, k))) return ID_ROWITEM + st.openRow * 10 + k;
  }
  if (in(CloseRect())) return ID_CLOSE;
  if (in(StartRect())) return ID_START;
  if (in(CheckRect())) return ID_CHECK;
  if (in(GithubRect())) return ID_GITHUB;
  // 行头命中：显示模式/分辨率并排 —— 命中区 = **内容胶囊**（与绘制同一个矩形），
  // 所以鼠标只有落在"文字那一块"才算命中，两个半格之间的空白不算（用户要求框与文案一致）
  if (in(CompactContentRect(RowRect(ROW_SCRN), L"显示模式", SCRN_LABEL[st.scrn], false)))
    return ID_ROW + ROW_SCRN;
  if (in(CompactContentRect(RowRect(ROW_RES), L"分辨率", RES_LABEL[st.res], true)))
    return ID_ROW + ROW_RES;
  for (int i = 0; i < ROW_COUNT; i++) {
    if (i == ROW_SCRN || i == ROW_RES) continue;
    if (in(RowRect(i))) return ID_ROW + i;
  }
  // ★ 复选框：只有**方块本身**可点（2026-10-01 用户指定），不再整行可点
  for (int i = 0; i < OPT_COUNT; i++) {
    if (in(OptBoxRect(i))) return i;
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
      // 启动自动检查（arms=false）只亮红点，不弹窗不装配；手动点「检查更新」
      // 弹窗报结果，确认了才下载/跳转（2026-09-30 用户裁定）。
      if (r->status == 0 || r->status == 3) {
        g_newVer = r->latest;
        g_newUrl  = r->url;
        g_localVer = r->localVer;
        g_remoteVer = (r->status == 3) ? r->remote.version : L"";
        g_newDeltaSize = (r->status == 3) ? r->remote.deltas[r->deltaIdx].size : 0;
        g_delta = (r->status == 3 && r->arms) ? r->remote.deltas[r->deltaIdx] : DeltaInfo();
        g_idleMsg.clear();                  // 有新版本 → 不再显示「已是最新」
        if (r->arms) {
          if (r->status == 3) {
            std::wstring q = L"发现新版本 " + r->latest + L"（增量 "
                           + FmtMB(g_newDeltaSize) + L"），立即更新？";
            if (MessageBoxW(h, q.c_str(), L"检查更新",
                            MB_YESNO | MB_ICONINFORMATION) == IDYES)
              StartUpdateRun(h);
          } else {
            std::wstring q = L"发现新版本 " + r->latest + L"，需完整安装。打开下载页？";
            if (MessageBoxW(h, q.c_str(), L"检查更新",
                            MB_YESNO | MB_ICONINFORMATION) == IDYES)
              OpenUrl(h, r->url.c_str());
          }
        }
      } else if (r->status == 1) {
        g_newVer.clear(); g_newUrl.clear(); g_newDeltaSize = 0;
        g_delta = DeltaInfo();
        // 「已是最新」常驻按钮（不再 4 秒后消失）—— 手动检查弹窗、自动检查只常驻
        g_idleMsg = L"已是最新 v" + g_dispVer;
        if (r->arms)
          MessageBoxW(h, g_idleMsg.c_str(), L"检查更新", MB_OK | MB_ICONINFORMATION);
      } else {
        if (r->arms)
          MessageBoxW(h, L"检查失败", L"检查更新", MB_OK | MB_ICONWARNING);
      }
      delete r;
    }
    InvalidateRect(h, nullptr, FALSE);
    return 0;
  }
  case WM_APP + 3:                         // 增量更新进度（后台线程请求重绘）
    InvalidateRect(h, nullptr, FALSE);
    return 0;
  case WM_APP + 4: {                       // 增量更新结束（成功/失败都回 0 态）
    UpdDone* r = (UpdDone*)l;
    InterlockedExchange(&g_updBusy, 0);
    g_updRun = 0;
    if (r) {
      if (r->ok) {
        // 结果显示在按钮上（几秒后回常驻文案），左下角版本号跟着走
        g_checkMsg = L"已更新到 " + r->ver + L" ✔";
        SetTimer(h, TIMER_CHECKMSG, 5000, nullptr);
        g_idleMsg = L"已是最新 v" + r->ver;   // 更新完即最新（定时器只清 g_checkMsg）
        g_delta = DeltaInfo();
        g_dispVer = r->ver;
        g_newDeltaSize = 0;
        g_newVer.clear(); g_newUrl.clear(); // 红点熄灭，下次检查按新 version.txt 比对
        if (r->selfUpdated) {              // 本体已换：拉起新启动器再退场
          ShellExecuteW(h, L"open", (g_dir + L"\\RNDZhLauncher.exe").c_str(),
                        nullptr, nullptr, SW_SHOWNORMAL);
          PostMessageW(h, WM_CLOSE, 0, 0);
        }
      } else {
        // 失败弹窗说明原因；g_delta 保留，再点一次「检查更新」可重试
        MessageBoxW(h, (r->err + L"\n\n也可用完整安装包升级。").c_str(),
                    L"增量更新失败", MB_ICONERROR | MB_OK);
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
    return 0; }
  case WM_LBUTTONUP: {
    int id = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id == st.press) {
      bool saveNow = false;
      if (id >= 0 && id < OPT_COUNT) { st.on[id] = !st.on[id]; InvalidateRect(h, nullptr, FALSE); saveNow = true; }
      // 点行头：展开/收起该项的选项（手风琴 —— 同时只开一行，免得撑破窗口）
      else if (id >= ID_ROW && id < ID_ROW + ROW_COUNT) {
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
        else if (r == ROW_LANG && k < LANGMODE_N) {
          // 语言模式：切换 dinput8.dll 的启用/停用（游戏在跑会失败并提示）
          bool wantNative = (k == 1);
          if (ApplyLangMode(wantNative)) { st.langMode = k; saveNow = true; }
        }
        st.openRow = -1;
        InvalidateRect(h, nullptr, FALSE);
      }
      else if (id == ID_START) { LaunchGame(); }
      else if (id == ID_CHECK) {
        if (g_updRun < 1 || g_updRun > 3) StartUpdateCheck(true);   // 检查 → 弹窗确认后才下载
      }
      else if (id == ID_GITHUB) { OpenUrl(h, REPO_URL); }
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

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR cmdLine, int) {
  // ── 内部命令行（增量更新的测试/提权通道，见「增量更新」注释块）──
  //   --update-base <url>              更新元数据基址（默认 GitHub latest 下载目录）
  //   --selftest-update                无窗口跑一次 检查→下载→应用，结果写
  //                                    %TEMP%\rndzh_upd_selftest.json，退出码 0/1/2
  //   --apply-update <tmpDir> <7z名>   UAC 提权子进程：应用增量后立即退出（不建窗口）
  //   --selftest-configdat             无窗口验证 config.dat 兜底逻辑（见 EnsureConfigDat），
  //                                    结果写 %TEMP%\rndzh_cfg_selftest.json，退出码 0/1
  int argc = 0;
  LPWSTR* argv = CommandLineToArgvW(cmdLine, &argc);
  // ⚠ wWinMain 的 lpCmdLine 已被 CRT 去掉程序名，所以 CommandLineToArgvW 的
  //   结果里没有 argv[0]，必须从 i=0 遍历 —— 从 i=1 开始会把「--update-base」
  //   本身跳过、URL 落在偶数位全部漏掉（本轮自测踩过：参数从未生效）。
  bool selftest = false, cfgSelftest = false;
  for (int i = 0; argv && i < argc; i++) {
    if (!wcscmp(argv[i], L"--update-base") && i + 1 < argc) {
      g_updBase = argv[++i];
      if (!g_updBase.empty() && g_updBase.back() != L'/') g_updBase.push_back(L'/');
    } else if (!wcscmp(argv[i], L"--selftest-update")) {
      selftest = true;
    } else if (!wcscmp(argv[i], L"--selftest-configdat")) {
      cfgSelftest = true;
    } else if (!wcscmp(argv[i], L"--apply-update") && i + 2 < argc) {
      int rc = RunApplyChild(argv[i + 1], argv[i + 2]);
      if (argv) LocalFree(argv);
      return rc;                       // 不初始化 GDI+/窗口，跑完即退
    }
  }
  if (argv) LocalFree(argv);

  if (cfgSelftest) {
    // 无窗口验证 config.dat 兜底：跑 EnsureConfigDat，把结果落盘供测试脚本断言。
    // 只读游戏目录、只写存档目录里的 config.dat，不拉起游戏、不建窗口。
    g_dir = ExeDir();
    std::wstring path = ConfigDatPath();
    std::wstring before;
    { std::ifstream f(path, std::ios::binary); before = f ? L"exists" : L"missing"; }
    bool ok = EnsureConfigDat();
    std::wstring after;
    long sz = 0;
    { std::ifstream f(path, std::ios::binary | std::ios::ate);
      if (f) { sz = (long)f.tellg(); after = L"exists"; } else after = L"missing"; }
    std::wstring js = L"{\n  \"path\": \"" + path + L"\",\n"
                      L"  \"before\": \"" + before + L"\",\n"
                      L"  \"after\": \"" + after + L"\",\n"
                      L"  \"size\": " + std::to_wstring(sz) + L",\n"
                      L"  \"ok\": " + (ok ? L"true" : L"false") + L",\n"
                      L"  \"scrnOk\": " + (st.scrnOk ? L"true" : L"false") + L",\n"
                      L"  \"scrn\": " + std::to_wstring(st.scrn) + L",\n"
                      L"  \"res\": " + std::to_wstring(st.res) + L"\n}\n";
    wchar_t tmp[MAX_PATH] = { 0 };
    GetTempPathW(MAX_PATH, tmp);
    WriteFileAll(std::wstring(tmp) + L"rndzh_cfg_selftest.json", WideToUtf8(js));
    ExitProcess(ok ? 0 : 1);
  }

  g_dir = ExeDir();
  g_dispVer = LocalVer();                    // 左下角显示当前补丁版本（无 version.txt 退 VER）
  if (g_dispVer.empty()) g_dispVer = VER;

  if (selftest) {
    // 自动化测试通道：无窗口、同步执行。命中增量才真正更新。
    UpdResult* chk = RunCheckCore(true);
    UpdDone* done = nullptr;
    if (chk && chk->status == 3) {
      g_delta = chk->remote.deltas[chk->deltaIdx];
      g_remoteVer = chk->remote.version;
      g_updTmpDir = MakeTmpDir();
      done = RunUpdateCore();
    }
    WriteSelftestResult(chk, done);
    int code = done ? (done->ok ? 0 : 1) : 2;
    DelTree(g_updTmpDir);
    ExitProcess(code);
  }

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

  // 启动即自动查一次更新（2026-09-15 用户要求）。★ 2026-09-30 起 arms=false：
  // 自动检查只亮红点，不装配「立即更新」—— 检查与下载严格两级（用户裁定）。
  StartUpdateCheck(false);

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
  GdiplusShutdown(token);
  return 0;
}
