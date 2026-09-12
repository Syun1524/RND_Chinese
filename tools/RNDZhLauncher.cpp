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
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <cwchar>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "shell32.lib")

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
static const int WIN_W = 820;
static const int WIN_H = 580;
static const int LEFT_W = 280;

static const Color
  C_BG      (255, 255, 255, 255),   // 窗口底
  C_PANEL   (255, 245, 246, 248),   // 左侧品牌区 / 悬停底
  C_FIELD   (255, 255, 255, 255),   // 输入/下拉底色
  C_BORDER  (255, 216, 220, 227),   // 边框
  C_TEXT    (255,  31,  35,  40),   // 正文
  C_DIM     (255, 107, 114, 128),   // 次要文字
  C_MUTED   (255, 156, 163, 175),   // 更淡（禁用/提示）
  C_ACCENT  (255,  11, 107, 203),   // 主按钮 / 勾选态
  C_ACCENTH (255,  10,  95, 176),   // 主按钮悬停
  C_HILITE  (255, 236, 240, 245),   // 下拉项悬停底
  C_SEL     (255, 226, 238, 252),   // 下拉项"当前选中"底
  C_WHITE   (255, 255, 255, 255);

// ── DPI 缩放 ──
// 三个 exe 以前都没声明 DPI 感知，系统 125% 缩放时 Windows 会把整个界面
// 位图拉伸 1.25 倍 —— 文字发虚、边缘发糊（实测客户区 1125x775 而逻辑只有 900x620）。
// 现在声明「系统 DPI 感知」，并把绘制坐标统一乘 S：界面物理尺寸不变，但变清晰。
// 实现上用 GDI+ 的 ScaleTransform 一次性缩放坐标系，不用逐个坐标乘 ——
// 布局常量保持逻辑值，看源码仍能直接算。
static float S = 1.0f;                 // 缩放系数 = 窗口DPI / 96
static inline float unscale(int v) { return (float)v / S; }   // 鼠标坐标 → 逻辑坐标

// 设置项（「换装」是下拉，不在这组复选里）
enum Opt { OPT_MOUSE=0, OPT_SCROLL_ADV, OPT_SCROLL_CLOSE, OPT_DXVK, OPT_COUNT };
static const wchar_t* OPT_LABEL[OPT_COUNT] = {
  L"鼠标控制", L"滚轮向上推进文本", L"滚轮向下关闭已读记录", L"启用 DXVK"
};
static const wchar_t* OPT_KEY[OPT_COUNT] = {
  L"mouseControls", L"scrollDownToAdvanceText", L"disableScrollDownToCloseBacklog",
  L"enableDxvk"
};
static const wchar_t* OPT_HINT[OPT_COUNT] = {
  L"用鼠标（而不是键盘）在 ADV 场景里控制视角与推进",
  L"滚轮向下推文本；关闭后只能点左键/Auto",
  L"关闭后滚轮向下不会退出已读记录",
  L"用 Vulkan 转译渲染，缓解新显卡上的兼容问题"
};
// 注意：disableScrollDownToCloseBacklog 在配置里是"禁用"语义。
// 界面写正向「滚轮向下关闭已读记录」，勾选=启用该功能=写 false。
static bool OPT_INVERT[OPT_COUNT] = { false, false, true, false };
static bool OPT_DEF[OPT_COUNT]    = { true,  true,  true, false };

// ── 换装主题 ──
// 值必须与 patchdef.json -> settings.zzOutfitSet.choices 的键一致。
// none = 不换装（各角色穿默认服）。
static const wchar_t* OUTFIT_LABEL[5] = { L"原版", L"和服", L"泳装", L"体操服", L"猫耳" };
static const wchar_t* OUTFIT_VALUE[5] = { L"none", L"kimono", L"swimsuit", L"gym", L"nekomimi" };
static const int OUTFIT_N = 5;

static const wchar_t* SUBS_LABEL[3] = { L"卡拉OK + 翻译", L"仅卡拉OK", L"仅翻译" };
static const wchar_t* SUBS_VALUE[3] = { L"all", L"karaonly", L"tlonly" };

static const wchar_t* SET_KEY = L"zzOutfitSet";

struct State {
  bool on[OPT_COUNT];
  int  subs;            // 0/1/2
  int  outfit;          // 0..4
  int  comboOpen = -1;  // -1 无 / 0 subs / 1 outfit
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
static FontFamily* g_ff = nullptr;   // 从系统字体取
static std::wstring g_dir;           // 启动器所在目录

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

static void FillRR(Graphics& g, const RectF& r, float rad, const Color& c) {
  GraphicsPath p; float d = rad * 2;
  p.AddArc(r.X, r.Y, d, d, 180, 90);
  p.AddArc(r.GetRight() - d, r.Y, d, d, 270, 90);
  p.AddArc(r.GetRight() - d, r.GetBottom() - d, d, d, 0, 90);
  p.AddArc(r.X, r.GetBottom() - d, d, d, 90, 90);
  p.CloseFigure();
  SolidBrush b(c); g.FillPath(&b, &p);
}

static void StrokeRR(Graphics& g, const RectF& r, float rad, const Color& c, float w) {
  GraphicsPath p; float d = rad * 2;
  p.AddArc(r.X, r.Y, d, d, 180, 90);
  p.AddArc(r.GetRight() - d, r.Y, d, d, 270, 90);
  p.AddArc(r.GetRight() - d, r.GetBottom() - d, d, d, 0, 90);
  p.AddArc(r.X, r.GetBottom() - d, d, d, 90, 90);
  p.CloseFigure();
  Pen pen(c, w); g.DrawPath(&pen, &p);
}

static void DrawTxt(Graphics& g, const wchar_t* s, Font* f, const Color& c, float x, float y, int align = 0) {
  SolidBrush b(c);
  StringFormat sf; sf.SetAlignment((StringAlignment)align);
  sf.SetLineAlignment(StringAlignmentNear);
  g.DrawString(s, -1, f, RectF(x, y, 0, 0), &sf, &b);
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

// 下拉框外框 + 当前值 + 箭头
static void DrawComboFrame(Graphics& g, const RectF& cr, const wchar_t* value, bool hot) {
  FillRR(g, cr, 7, C_FIELD);
  StrokeRR(g, cr, 7, hot ? C_ACCENT : C_BORDER, hot ? 1.4f : 1.f);
  DrawTxt(g, value, F(16), C_TEXT, cr.X + 14, cr.Y + 8);
  float cx = cr.GetRight() - 18, cy = cr.Y + 18;
  SolidBrush db(C_DIM); PointF tri[3] = { {cx-5,cy-2},{cx+5,cy-2},{cx,cy+3} };
  g.FillPolygon(&db, tri, 3);
}

// 下拉展开的选项列表（单独一个函数，便于最后绘制 —— 见 Paint 里的 z 序说明）。
// 注意：ItemRect 定义在下面（几何区），所以本函数声明在前、实现放在几何之后。
static void DrawComboItems(Graphics& g, const RectF& base, int n,
                           const wchar_t* const* labels, int sel, int idBase, int hot);

// ── 几何 ──
// 统一栅格：右边距 PAD_R = 32，内容右边界 = WIN_W - 32 = 788。
// 以前这里是一堆手写死坐标，StartRect() = X660 + 宽250 → 右边界 910，
// 而窗口只有 900 宽 —— 「开始游戏」按钮右边被切掉 10 px（实机截图可见）。
// 现在全部由右边界反推，改窗口尺寸不会再散架。
static const float PAD_R = 32.f;
static const float RX = (float)LEFT_W + 36.f;      // 右栏内容左边界
static const float RW = (float)WIN_W - PAD_R;      // 右栏内容右边界

// 4 个复选框：行高 46（标题 17px + 灰色说明 12px）
static RectF OptRect(int i)   { return RectF(RX, 64.f + i * 46.f, RW - RX, 30.f); }
static RectF OutfitRect()     { return RectF(RX + 92.f, 292.f, RW - (RX + 92.f), 36.f); }
static RectF ComboRect()      { return RectF(RX + 92.f, 386.f, RW - (RX + 92.f), 36.f); }
// 主按钮：右下角对齐，宽 220 高 52，离底 28
static RectF StartRect()      { return RectF(RW - 220.f, (float)WIN_H - 28.f - 52.f, 220.f, 52.f); }
// 下拉一律【向下】展开。换装 5 项、字幕 3 项，展开时下面要留得下 ——
// 窗口高度按「字幕框底 + 3 项 + 主按钮」反推（见 WIN_H）。
static RectF ItemRect(const RectF& base, int k) {
  return RectF(base.X, base.GetBottom() + 2 + k * 34.f, base.Width, 34.f);
}

// 下拉列表的绘制（实现在这里，因为要用 ItemRect）
static void DrawComboItems(Graphics& g, const RectF& base, int n,
                           const wchar_t* const* labels, int sel, int idBase, int hot) {
  // 先铺一层白底，避免选项和背景的分隔线/按钮混在一起
  RectF box(base.X, base.GetBottom() + 2, base.Width, n * 34.f + 4);
  FillRR(g, box, 6, C_FIELD);
  for (int k = 0; k < n; k++) {
    RectF ir = ItemRect(base, k);
    bool isHot = (hot == idBase + k);
    Color bg = isHot ? C_HILITE : (k == sel ? C_SEL : C_FIELD);
    FillRR(g, RectF(ir.X + 1, ir.Y, ir.Width - 2, ir.Height), k == 0 ? 5.f : 0.f, bg);
    DrawTxt(g, labels[k], F(16), k == sel ? C_ACCENT : C_TEXT, ir.X + 12, ir.Y + 7);
  }
  StrokeRR(g, box, 6, C_BORDER, 1.f);
}

// 命中 id：0..OPT_COUNT-1 选项 / 100+k subs / 200 开始 / 300 subs框
//         400+k outfit / 500 outfit框
enum { ID_START = 200, ID_COMBO_SUBS = 300, ID_COMBO_OUTFIT = 500 };

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

    SolidBrush bg(C_BG); gr.FillRectangle(&bg, 0, 0, rc.right, rc.bottom);
    SolidBrush panel(C_PANEL); gr.FillRectangle(&panel, 0, 0, LEFT_W, rc.bottom);
    Pen edge(C_BORDER, 1.f); gr.DrawLine(&edge, LEFT_W, 0, LEFT_W, rc.bottom);

    // ── 左：品牌 ──
    if (g_iconBmp) {
      GraphicsPath clip; float d0 = 24;
      RectF ib(LEFT_W/2.f - 56, 96, 112, 112);
      clip.AddArc(ib.X, ib.Y, d0, d0, 180, 90);
      clip.AddArc(ib.GetRight()-d0, ib.Y, d0, d0, 270, 90);
      clip.AddArc(ib.GetRight()-d0, ib.GetBottom()-d0, d0, d0, 0, 90);
      clip.AddArc(ib.X, ib.GetBottom()-d0, d0, d0, 90, 90);
      clip.CloseFigure();
      gr.SetClip(&clip);
      gr.DrawImage(g_iconBmp, (INT)ib.X, (INT)ib.Y, (INT)ib.Width, (INT)ib.Height);
      gr.ResetClip();
    } else {
      FillRR(gr, RectF(LEFT_W/2.f - 56, 96, 112, 112), 14, C_HILITE);
      DrawTxt(gr, L"图标", F(14), C_MUTED, LEFT_W/2.f, 146, 1);
    }
    DrawTxt(gr, L"ROBOTICS;NOTES DaSH", F(17,true), C_TEXT, LEFT_W/2.f, 234, 1);
    DrawTxt(gr, L"简体中文补丁", F(17,true), C_ACCENT, LEFT_W/2.f, 262, 1);
    DrawTxt(gr, L"v0.1", F(12), C_MUTED, LEFT_W/2.f, rc.bottom - 28, 1);

    // ── 右：选项 ──
    DrawTxt(gr, L"选项", F(13), C_MUTED, RX, 34);
    for (int i = 0; i < OPT_COUNT; i++) {
      RectF r = OptRect(i);
      bool on = st.on[i];
      DrawCheck(gr, RectF(r.X, r.Y + 3, 22, 22), on, st.hot == i);
      DrawTxt(gr, OPT_LABEL[i], F(17), on ? C_TEXT : C_DIM, r.X + 34, r.Y + 3);
      DrawTxt(gr, OPT_HINT[i], F(12), C_MUTED, r.X + 34, r.Y + 24);
    }

    // ── 换装 ──
    Pen sep0(C_BORDER, 1.f); gr.DrawLine(&sep0, RX, 272.f, RW, 272.f);
    DrawTxt(gr, L"换装", F(17), C_TEXT, RX, 301);
    DrawComboFrame(gr, OutfitRect(), OUTFIT_LABEL[st.outfit], st.hot == ID_COMBO_OUTFIT);
    DrawTxt(gr, L"全员换成这套服装（各角色只换自己有的那套）",
            F(12), C_MUTED, RX, 336);

    Pen sep(C_BORDER, 1.f); gr.DrawLine(&sep, RX, 366.f, RW, 366.f);
    DrawTxt(gr, L"影片字幕", F(17), C_TEXT, RX, 395);
    DrawComboFrame(gr, ComboRect(), SUBS_LABEL[st.subs], st.hot == ID_COMBO_SUBS);

    // ── 主按钮 ──
    { RectF sr = StartRect();
      FillRR(gr, sr, 8, (st.hot == ID_START) ? C_ACCENTH : C_ACCENT);
      SolidBrush w(C_WHITE); StringFormat sf;
      sf.SetAlignment(StringAlignmentCenter); sf.SetLineAlignment(StringAlignmentCenter);
      gr.DrawString(L"开始游戏", -1, F(19,true), sr, &sf, &w); }

    // ── 下拉列表最后画 ──
    // 必须放在所有控件之后：展开的选项会盖住下面的分隔线与主按钮，
    // 若按源码顺序（换装就在换装标题之后）绘制，会被后面画的「影片字幕」
    // 和「开始游戏」覆盖，看起来像下拉框被切了一块。
    if (st.comboOpen == 1)
      DrawComboItems(gr, OutfitRect(), OUTFIT_N, OUTFIT_LABEL, st.outfit,
                     400, st.hot);
    else if (st.comboOpen == 0)
      DrawComboItems(gr, ComboRect(), 3, SUBS_LABEL, st.subs, 100, st.hot);
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

static void LaunchGame() {
  SaveConfig();
  ApplyDxvk(st.on[OPT_DXVK]);
  const wchar_t* lang = DetectLang();   // 跟随玩家原本的版本（存档目录随之）

  std::wstring cmd = L"Game.exe roboticsnotesd " + std::wstring(lang);
  STARTUPINFOW si{}; si.cb = sizeof(si);
  PROCESS_INFORMATION pi{};
  if (CreateProcessW(L"Game.exe", &cmd[0], nullptr, nullptr, FALSE, 0, nullptr, g_dir.c_str(), &si, &pi)) {
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
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
  // 下拉优先：展开时它盖在下面的控件上，命中判定也必须先于它们
  if (st.comboOpen == 1) for (int k = 0; k < OUTFIT_N; k++) if (in(ItemRect(OutfitRect(), k))) return 400 + k;
  if (st.comboOpen == 0) for (int k = 0; k < 3; k++) if (in(ItemRect(ComboRect(), k))) return 100 + k;
  if (in(StartRect())) return ID_START;
  if (in(OutfitRect())) return ID_COMBO_OUTFIT;
  if (in(ComboRect())) return ID_COMBO_SUBS;
  for (int i = 0; i < OPT_COUNT; i++) {
    RectF r = OptRect(i);
    if (x >= r.X - 4 && x <= r.X + r.Width && y >= r.Y - 2 && y <= r.Y + 40) return i;
  }
  return -1;
}

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
  switch (m) {
  case WM_MOUSEMOVE: {
    int id = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id != st.hot) { st.hot = id; InvalidateRect(h, nullptr, FALSE); }
    TRACKMOUSEEVENT t{ sizeof(t) }; t.dwFlags = TME_LEAVE; t.hwndTrack = h;
    TrackMouseEvent(&t);
    return 0;
  }
  case WM_MOUSELEAVE: st.hot = -1; InvalidateRect(h, nullptr, FALSE); return 0;
  case WM_LBUTTONDOWN: { st.press = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l)); return 0; }
  case WM_LBUTTONUP: {
    int id = HitTest(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id == st.press) {
      bool saveNow = false;
      if (id >= 0 && id < OPT_COUNT) { st.on[id] = !st.on[id]; InvalidateRect(h, nullptr, FALSE); saveNow = true; }
      else if (id >= 100 && id < 103) { st.subs = id - 100; st.comboOpen = -1; InvalidateRect(h, nullptr, FALSE); saveNow = true; }
      else if (id >= 400 && id < 400 + OUTFIT_N) { st.outfit = id - 400; st.comboOpen = -1; InvalidateRect(h, nullptr, FALSE); saveNow = true; }
      else if (id == ID_COMBO_SUBS) { st.comboOpen = (st.comboOpen == 0) ? -1 : 0; InvalidateRect(h, nullptr, FALSE); }
      else if (id == ID_COMBO_OUTFIT) { st.comboOpen = (st.comboOpen == 1) ? -1 : 1; InvalidateRect(h, nullptr, FALSE); }
      else if (id == ID_START) { LaunchGame(); }
      // 立刻落盘：玩家可能在这里改完就关窗口、再用 Steam 或 boot.bat 直启游戏
      if (saveNow) SaveConfig();
    } else if (st.comboOpen >= 0 && id == -1) { st.comboOpen = -1; InvalidateRect(h, nullptr, FALSE); }
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
  LoadAppIconFromResource();
  LoadConfig();

  WNDCLASSEXW wc{ sizeof(wc) };
  wc.lpfnWndProc = WndProc; wc.hInstance = hInst; wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
  wc.lpszClassName = L"RNDZhLauncherWnd"; wc.hbrBackground = nullptr;
  wc.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(101));
  wc.hIconSm = wc.hIcon;
  RegisterClassExW(&wc);

  DWORD style = WS_OVERLAPPEDWINDOW & ~(WS_THICKFRAME | WS_MAXIMIZEBOX);
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
  AdjustWindowRect(&r, style, FALSE);
  int ww = r.right - r.left, wh = r.bottom - r.top;
  int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
  g_hwnd = CreateWindowExW(0, wc.lpszClassName, L"ROBOTICS;NOTES DaSH 简体中文补丁",
                           style, (sw - ww) / 2, (sh - wh) / 2, ww, wh,
                           nullptr, nullptr, hInst, nullptr);
  ShowWindow(g_hwnd, SW_SHOW); UpdateWindow(g_hwnd);

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
  GdiplusShutdown(token);
  return 0;
}
