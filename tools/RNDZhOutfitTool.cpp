// RNDZhOutfitTool — ROBOTICS;NOTES DaSH 换装核对工具（开发用，不随补丁发布）
//
// 为什么需要它：游戏本身没有换装菜单，服装名也不在任何可解包的数据里
// （.lkm 是纯网格 + 内嵌贴图，无名称；.scx 是压缩脚本，不引用变体名）。
// 要把每套服装认出来，只能把角色的变体都指向其中一套、进游戏肉眼看。
//
// 用法：把本 exe 放到游戏根目录（和 Game.exe 同级）运行 —— 它要写 LB 的配置、
// 还要能拉起 Game.exe。
//
// 批量核对：面板给**每个角色一行**，各选一套。一次进游戏就能同时看多个角色，
// 所以整轮核对只需十几次启动，而不是每套一次。
//
// 机制：每行写一个 bool 开关到 %LOCALAPPDATA%\Committee of Zero\RNDSteam\config.json，
// 形如 "zz_c002_100": true —— 对应 patchdef.json -> settings.zz_c002_100，
// 内含该角色【全部变体（含目标自身）→ 目标变体】的 fileIdRemap。
// 只写选中的那几个键，其余留空，所以任意多个角色能同时生效。
// 核对不依赖「泳装／换装模式」：mgsFileOpenHook 读 fileIdRemap 是无条件的，
// 且命中即 return（不会落到 fileRedirection）。
//
// 编译：build_outfit_tool.bat

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

#include "outfit_table.h"

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "shell32.lib")

using namespace Gdiplus;

static const wchar_t* PREFIX = L"zz_";

// ── 布局 ──
static const int WIN_W = 760;
static const int WIN_H = 520;      // 基准高度；下拉展开时按需加高
static const int ROWS_PER_COL = 6;
static const int ITEM_H = 28;

static const Color
  C_BG     (255, 24, 27, 34),
  C_PANEL  (255, 33, 38, 48),
  C_HILITE (255, 44, 50, 63),
  C_LINE   (255, 62, 70, 86),
  C_TEXT   (255, 233, 236, 242),
  C_DIM    (255, 150, 158, 172),
  C_MUTED  (255, 104, 113, 128),
  C_ACCENT (255, 64, 150, 255),
  C_WARN   (255, 226, 150, 70),
  C_OK     (255, 120, 220, 150),
  C_SEL    (255, 92, 106, 128),
  C_WHITE  (255, 255, 255, 255);

// 每行一个角色；g_sel = -1 表示「不动」（该角色不参与本次核对）
static std::vector<int> g_rows;                 // 显示的角色索引（只含多变体角色）
static int g_sel[OUTFIT_CHAR_COUNT];
static int g_openKey = -1;                      // -1 关；0..N-1 行下拉；2000 预设下拉
static int g_presetK = 1;                       // 「全体对齐第 k 套」
static int g_hot = -1, g_press = -1;
static HWND g_hwnd;
static FontFamily* g_ff = nullptr;
static std::wstring g_dir;

// ── 小工具 ──
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
static std::wstring ConfigPath() {
  wchar_t* appdata = nullptr;
  SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &appdata);
  std::wstring p = appdata ? appdata : L"";
  if (appdata) CoTaskMemFree(appdata);
  p += L"\\Committee of Zero\\RNDSteam";
  return p;
}

// 读 config.json 的顶层平铺键值（值取原始文本，原样保留未知键）
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

static int SelectedCount() {
  int n = 0;
  for (int ci : g_rows) if (g_sel[ci] >= 0) n++;
  return n;
}

// 写 config.json：丢弃旧的 zz_* 键，只为当前选中的角色写 true。
// 其余键（含玩家启动器写的开关）原样保留。
static void SaveSelection() {
  std::wstring dir = ConfigPath();
  SHCreateDirectoryExW(nullptr, dir.c_str(), nullptr);
  std::wstring path = dir + L"\\config.json";
  auto old = LoadFlatJson(path);

  std::wstringstream out;
  out << L"{\n";
  bool first = true;
  auto emit = [&](const std::wstring& k, const std::wstring& v) {
    if (!first) out << L",\n";
    first = false;
    out << L"    \"" << k << L"\": " << v;
  };
  emit(L"__schema_version", L"5");
  for (auto& kv : old) {
    if (kv.first == L"__schema_version" || kv.first.empty()) continue;
    if (kv.first.rfind(PREFIX, 0) == 0) continue;          // 上次的核对选择全丢
    if (kv.first == L"zzOutfitOverride") continue;         // 旧单选机制残留
    emit(kv.first, kv.second);
  }
  int n = 0;
  for (int ci = 0; ci < OUTFIT_CHAR_COUNT; ci++) {
    if (g_sel[ci] < 0) continue;
    const OutfitChar& c = OUTFIT_CHARS[ci];
    if (g_sel[ci] >= c.count) continue;
    emit(std::wstring(PREFIX) + c.id + L"_" + c.variant[g_sel[ci]], L"true");
    n++;
  }
  out << L"\n}";

  std::string u8 = WideToUtf8(out.str());
  std::ofstream f(path, std::ios::binary | std::ios::trunc);
  f.write(u8.data(), u8.size());
  (void)n;
}

static void LoadSelection() {
  for (int i = 0; i < OUTFIT_CHAR_COUNT; i++) g_sel[i] = -1;
  auto m = LoadFlatJson(ConfigPath() + L"\\config.json");
  for (auto& kv : m) {
    if (kv.first.rfind(PREFIX, 0) != 0) continue;
    if (kv.second.find(L"true") == std::wstring::npos) continue;
    std::wstring key = kv.first.substr(3);              // "c002_100"
    size_t us = key.find(L'_');
    if (us == std::wstring::npos) continue;
    std::wstring ch = key.substr(0, us), vv = key.substr(us + 1);
    for (int i = 0; i < OUTFIT_CHAR_COUNT; i++) {
      if (ch != OUTFIT_CHARS[i].id) continue;
      for (int k = 0; k < OUTFIT_CHARS[i].count; k++)
        if (vv == OUTFIT_CHARS[i].variant[k]) { g_sel[i] = k; break; }
    }
  }
}

static void BuildRows() {
  g_rows.clear();
  for (int i = 0; i < OUTFIT_CHAR_COUNT; i++)
    if (OUTFIT_CHARS[i].count > 1) g_rows.push_back(i);
}

// ── 绘制 ──
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
  p.AddArc(r.GetRight()-d, r.Y, d, d, 270, 90);
  p.AddArc(r.GetRight()-d, r.GetBottom()-d, d, d, 0, 90);
  p.AddArc(r.X, r.GetBottom()-d, d, d, 90, 90);
  p.CloseFigure();
  SolidBrush b(c); g.FillPath(&b, &p);
}
static void StrokeRR(Graphics& g, const RectF& r, float rad, const Color& c, float w) {
  GraphicsPath p; float d = rad * 2;
  p.AddArc(r.X, r.Y, d, d, 180, 90);
  p.AddArc(r.GetRight()-d, r.Y, d, d, 270, 90);
  p.AddArc(r.GetRight()-d, r.GetBottom()-d, d, d, 0, 90);
  p.AddArc(r.X, r.GetBottom()-d, d, d, 90, 90);
  p.CloseFigure();
  Pen pen(c, w); g.DrawPath(&pen, &p);
}
static void DrawTxt(Graphics& g, const wchar_t* s, Font* f, const Color& c, float x, float y, int align = 0) {
  SolidBrush b(c); StringFormat sf; sf.SetAlignment((StringAlignment)align);
  sf.SetLineAlignment(StringAlignmentNear);
  g.DrawString(s, -1, f, RectF(x, y, 0, 0), &sf, &b);
}
static void DrawCombo(Graphics& g, const RectF& r, const wchar_t* v, bool hot, bool on) {
  FillRR(g, r, 6, C_HILITE);
  StrokeRR(g, r, 6, hot ? C_DIM : (on ? C_ACCENT : C_LINE), on ? 1.6f : 1.f);
  DrawTxt(g, v, F(14), on ? C_TEXT : C_DIM, r.X + 10, r.Y + 7);
  float cx = r.GetRight() - 14, cy = r.Y + 16;
  SolidBrush db(C_DIM); PointF tri[3] = { {cx-5,cy-2},{cx+5,cy-2},{cx,cy+3} };
  g.FillPolygon(&db, tri, 3);
}
static void DrawBtn(Graphics& g, const RectF& r, const wchar_t* t, bool hot) {
  FillRR(g, r, 6, hot ? C_ACCENT : C_HILITE);
  StrokeRR(g, r, 6, hot ? C_ACCENT : C_LINE, 1.f);
  SolidBrush b(C_TEXT); StringFormat sf;
  sf.SetAlignment(StringAlignmentCenter); sf.SetLineAlignment(StringAlignmentCenter);
  g.DrawString(t, -1, F(14,true), r, &sf, &b);
}

// ── 几何 ──
static RectF RowRect(int r) {
  int col = r / ROWS_PER_COL, row = r % ROWS_PER_COL;
  return RectF(20.f + col * 372.f, 150.f + row * 44.f, 344.f, 44.f);
}
static RectF RowComboRect(int r) {
  RectF rr = RowRect(r);
  return RectF(rr.X + 104.f, rr.Y + 6.f, 196.f, 32.f);
}
static RectF PresetComboRect() { return RectF(116.f, 96.f, 74.f, 32.f); }
static RectF ClearRect()       { return RectF(240.f, 96.f, 110.f, 32.f); }
static RectF StartRect() {
  RECT rc; GetClientRect(g_hwnd, &rc);
  return RectF(300.f, 452.f, 160.f, 46.f);
}
// 下拉项。一律向下展开；窗口不够高时由 FitWindowFor 加高。
// （早先版本按"向上展开"算，控件在窗口上部直接算出负 y，列表跑到窗口外点不到。）
static RectF ItemRect(const RectF& combo, int k) {
  return RectF(combo.X, combo.GetBottom() + 2.f + k * (float)ITEM_H,
               combo.Width, (float)ITEM_H);
}
static float ListBottom(const RectF& combo, int n) {
  return combo.GetBottom() + 2.f + n * (float)ITEM_H + 8.f;
}

static int RowItemCount(int r) { return 1 + OUTFIT_CHARS[g_rows[r]].count; }  // +1 = 不动

// 展开的下拉所需高度（取当前打开的那个算）
static int NeededHeight() {
  if (g_openKey < 0) return WIN_H;
  if (g_openKey == 2000) {
    float b = ListBottom(PresetComboRect(), OUTFIT_MAX_VARIANTS) + 4.f;
    return b > WIN_H ? (int)b : WIN_H;
  }
  float b = ListBottom(RowComboRect(g_openKey), RowItemCount(g_openKey)) + 4.f;
  return b > WIN_H ? (int)b : WIN_H;
}

static void FitWindowFor(HWND h) {
  int want = NeededHeight();
  RECT rc; GetClientRect(h, &rc);
  if (rc.bottom == want) return;
  RECT wr; GetWindowRect(h, &wr);
  DWORD style = (DWORD)GetWindowLongPtrW(h, GWL_STYLE);
  RECT r{ 0, 0, WIN_W, want };
  AdjustWindowRect(&r, style, FALSE);
  SetWindowPos(h, nullptr, wr.left, wr.top, r.right - r.left, r.bottom - r.top,
               SWP_NOZORDER | SWP_NOACTIVATE);
}

// ── 绘制 ──
static void Paint(HDC hdc) {
  RECT rc; GetClientRect(g_hwnd, &rc);
  HDC mem = CreateCompatibleDC(hdc);
  HBITMAP bmp = CreateCompatibleBitmap(hdc, rc.right, rc.bottom);
  HBITMAP old = (HBITMAP)SelectObject(mem, bmp);
  {
    Graphics gr(mem);
    gr.SetSmoothingMode(SmoothingModeAntiAlias);
    gr.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    SolidBrush bg(C_BG); gr.FillRectangle(&bg, 0, 0, rc.right, rc.bottom);
    SolidBrush pan(C_PANEL); gr.FillRectangle(&pan, 0, 0, rc.right, 52);

    DrawTxt(gr, L"换装核对（开发工具）", F(17,true), C_TEXT, 20, 14);
    DrawTxt(gr, L"给每个角色选一套服装 —— 一次进游戏可以同时看多个角色。选「不动」= 该角色不参与本次核对。",
            F(12), C_MUTED, 20, 56);

    // 全体预设。注意语义是「各角色的第 k 个变体」而非「变体号 k」——
    // 各角色变体编号不一致（c001 从 010 起，c005 从 030 起），
    // 所以第 1 套 = c001_010 但 = c005_030，行内下拉会显示实际选中的编号。
    DrawTxt(gr, L"全体：各角色第", F(14), C_DIM, 20, 102);
    std::wstring pk = std::to_wstring(g_presetK);
    DrawCombo(gr, PresetComboRect(), pk.c_str(), g_hot == 2000, false);
    DrawTxt(gr, L"套", F(14), C_DIM, 196, 102);
    DrawBtn(gr, ClearRect(), L"全部清除", g_hot == 3000);

    // 角色行
    for (int r = 0; r < (int)g_rows.size(); r++) {
      int ci = g_rows[r];
      const OutfitChar& c = OUTFIT_CHARS[ci];
      RectF rr = RowRect(r), cb = RowComboRect(r);
      bool on = g_sel[ci] >= 0;
      DrawTxt(gr, c.id, F(14,true), on ? C_TEXT : C_DIM, rr.X + 2, rr.Y + 4);
      if (c.hint[0]) DrawTxt(gr, c.hint, F(11), C_MUTED, rr.X + 2, rr.Y + 23);
      std::wstring cnt = std::to_wstring(c.count);
      cnt += L" 套";
      DrawTxt(gr, cnt.c_str(), F(11), C_MUTED, rr.X + 60, rr.Y + 23);

      std::wstring val;
      if (!on) val = L"不动";
      else {
        val = c.variant[g_sel[ci]];
        val += L"   #";
        val += std::to_wstring(c.fileId[g_sel[ci]]);
      }
      DrawCombo(gr, cb, val.c_str(), g_hot == r, on);
    }

    // 状态 + 开始
    int n = SelectedCount();
    std::wstring st;
    if (n == 0) st = L"尚未选择任何角色（全部「不动」= 游戏按原样显示）。";
    else {
      st = L"已固定 ";
      st += std::to_wstring(n);
      st += L" 个角色的服装：";
      int shown = 0;
      for (int ci : g_rows) {
        if (g_sel[ci] < 0) continue;
        if (shown == 4) { st += L" …"; break; }
        if (shown) st += L"、";
        st += OUTFIT_CHARS[ci].id;
        st += L"=";
        st += OUTFIT_CHARS[ci].variant[g_sel[ci]];
        shown++;
      }
    }
    DrawTxt(gr, st.c_str(), F(13), n ? C_OK : C_MUTED, 20, 424);
    DrawTxt(gr, L"进游戏看这几个角色穿什么，退出后改上一行的选择再进。认出的名字填 成品ing/服装核对/服装名称表.json。",
            F(11), C_MUTED, 20, 444);
    DrawBtn(gr, StartRect(), L"开始游戏", g_hot == 4000);

    // ── 展开的下拉（画在最上层）──
    if (g_openKey == 2000) {
      RectF cb = PresetComboRect();
      int nk = OUTFIT_MAX_VARIANTS;
      for (int k = 0; k < nk; k++) {
        RectF ir = ItemRect(cb, k);
        int kv = k + 1;
        bool sel = (kv == g_presetK);
        FillRR(gr, ir, 5, (g_hot == 2100 + k) ? C_ACCENT : (sel ? C_SEL : C_PANEL));
        std::wstring lab = L"各角色第 ";
        lab += std::to_wstring(kv);
        lab += L" 套";
        DrawTxt(gr, lab.c_str(), F(14), C_TEXT, ir.X + 10, ir.Y + 6);
      }
    } else if (g_openKey >= 0 && g_openKey < (int)g_rows.size()) {
      int ci = g_rows[g_openKey];
      const OutfitChar& c = OUTFIT_CHARS[ci];
      RectF cb = RowComboRect(g_openKey);
      int n = RowItemCount(g_openKey);
      for (int k = 0; k < n; k++) {
        RectF ir = ItemRect(cb, k);
        bool sel = (k == 0) ? (g_sel[ci] < 0) : (g_sel[ci] == k - 1);
        FillRR(gr, ir, 5, (g_hot == 100 + k) ? C_ACCENT : (sel ? C_SEL : C_PANEL));
        std::wstring lab;
        if (k == 0) lab = L"不动";
        else {
          lab = c.variant[k-1];
          lab += L"   (fileId ";
          lab += std::to_wstring(c.fileId[k-1]);
          lab += L")";
        }
        DrawTxt(gr, lab.c_str(), F(14), C_TEXT, ir.X + 10, ir.Y + 6);
      }
    }
  }
  BitBlt(hdc, 0, 0, rc.right, rc.bottom, mem, 0, 0, SRCCOPY);
  SelectObject(mem, old); DeleteObject(bmp); DeleteDC(mem);
}

// ── 启动游戏 ──
static bool HasSaveDir(const wchar_t* lang) {
  wchar_t* docs = nullptr;
  SHGetKnownFolderPath(FOLDERID_Documents, 0, nullptr, &docs);
  std::wstring p = docs ? docs : L"";
  if (docs) CoTaskMemFree(docs);
  p += L"\\My Games\\mages_steam\\Robotics Notes DASH\\";
  p += lang;
  return FileExists(p);
}
static const wchar_t* DetectLang() {
  static wchar_t buf[8] = { 0 };
  const wchar_t* cands[] = { L"\\_cn_patch_boot_orig.bat", L"\\boot.bat" };
  for (auto c : cands) {
    std::ifstream f(g_dir + c, std::ios::binary);
    if (!f) continue;
    std::stringstream ss; ss << f.rdbuf();
    std::string s = ss.str();
    for (auto& ch : s) ch = (char)toupper((unsigned char)ch);
    size_t e = s.find("EN"), j = s.find("JP");
    if (e != std::string::npos && (j == std::string::npos || e < j)) { wcscpy_s(buf, L"EN"); return buf; }
    if (j != std::string::npos) { wcscpy_s(buf, L"JP"); return buf; }
  }
  wcscpy_s(buf, (!HasSaveDir(L"eng") && HasSaveDir(L"jpn")) ? L"JP" : L"EN");
  return buf;
}
static void Launch() {
  SaveSelection();
  std::wstring cmd = L"Game.exe roboticsnotesd " + std::wstring(DetectLang());
  STARTUPINFOW si{}; si.cb = sizeof(si);
  PROCESS_INFORMATION pi{};
  if (CreateProcessW(L"Game.exe", &cmd[0], nullptr, nullptr, FALSE, 0, nullptr, g_dir.c_str(), &si, &pi)) {
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    PostMessageW(g_hwnd, WM_CLOSE, 0, 0);
  } else {
    MessageBoxW(g_hwnd, L"未找到 Game.exe，请把本工具放在游戏根目录。",
                L"启动失败", MB_ICONERROR | MB_OK);
  }
}

// ── 交互 ──
enum { ID_PRESET = 2000, ID_ITEM_PRESET = 2100, ID_CLEAR = 3000, ID_START = 4000,
       ID_ITEM_ROW = 100 };

static int Hit(int x, int y) {
  auto in = [&](const RectF& r) {
    return x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom();
  };
  // 展开的列表优先（画在最上层）
  if (g_openKey == 2000) {
    for (int k = 0; k < OUTFIT_MAX_VARIANTS; k++)
      if (in(ItemRect(PresetComboRect(), k))) return ID_ITEM_PRESET + k;
  } else if (g_openKey >= 0 && g_openKey < (int)g_rows.size()) {
    for (int k = 0; k < RowItemCount(g_openKey); k++)
      if (in(ItemRect(RowComboRect(g_openKey), k))) return ID_ITEM_ROW + k;
  }
  if (in(StartRect())) return ID_START;
  if (in(PresetComboRect())) return ID_PRESET;
  if (in(ClearRect())) return ID_CLEAR;
  for (int r = 0; r < (int)g_rows.size(); r++)
    if (in(RowComboRect(r))) return r;
  return -1;
}

static void CloseList() {
  if (g_openKey >= 0) { g_openKey = -1; FitWindowFor(g_hwnd); }
}

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
  switch (m) {
  case WM_MOUSEMOVE: {
    int id = Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id != g_hot) { g_hot = id; InvalidateRect(h, nullptr, FALSE); }
    TRACKMOUSEEVENT t{ sizeof(t) }; t.dwFlags = TME_LEAVE; t.hwndTrack = h;
    TrackMouseEvent(&t);
    return 0;
  }
  case WM_MOUSELEAVE: g_hot = -1; InvalidateRect(h, nullptr, FALSE); return 0;
  case WM_LBUTTONDOWN: { g_press = Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l)); return 0; }
  case WM_LBUTTONUP: {
    int id = Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id == g_press) {
      if (id == ID_PRESET) {
        g_openKey = (g_openKey == 2000) ? -1 : 2000;
        FitWindowFor(h); InvalidateRect(h, nullptr, FALSE);
      }
      else if (id >= ID_ITEM_PRESET && id < ID_ITEM_PRESET + OUTFIT_MAX_VARIANTS) {
        int k = (id - ID_ITEM_PRESET) + 1;          // 1-based
        g_presetK = k;
        for (int ci : g_rows)                        // 变体不够的角色设为「不动」（已核完）
          g_sel[ci] = (OUTFIT_CHARS[ci].count >= k) ? (k - 1) : -1;
        CloseList(); SaveSelection(); InvalidateRect(h, nullptr, FALSE);
      }
      else if (id == ID_CLEAR) {
        for (int i = 0; i < OUTFIT_CHAR_COUNT; i++) g_sel[i] = -1;
        CloseList(); SaveSelection(); InvalidateRect(h, nullptr, FALSE);
      }
      else if (id >= 0 && id < (int)g_rows.size()) {
        g_openKey = (g_openKey == id) ? -1 : id;
        FitWindowFor(h); InvalidateRect(h, nullptr, FALSE);
      }
      else if (id >= ID_ITEM_ROW && g_openKey >= 0 && g_openKey < (int)g_rows.size() &&
               id < ID_ITEM_ROW + RowItemCount(g_openKey)) {
        int k = id - ID_ITEM_ROW;
        g_sel[g_rows[g_openKey]] = (k == 0) ? -1 : (k - 1);
        CloseList(); SaveSelection(); InvalidateRect(h, nullptr, FALSE);
      }
      else if (id == ID_START) { Launch(); }
    } else if (g_openKey >= 0 && id == -1) {
      CloseList(); InvalidateRect(h, nullptr, FALSE);
    }
    g_press = -1; return 0;
  }
  case WM_PAINT: { PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps); Paint(dc); EndPaint(h, &ps); return 0; }
  case WM_ERASEBKGND: return 1;
  case WM_KEYDOWN: if (w == VK_ESCAPE) PostMessageW(h, WM_CLOSE, 0, 0); return 0;
  case WM_CLOSE: SaveSelection(); DestroyWindow(h); return 0;
  case WM_DESTROY: PostQuitMessage(0); return 0;
  }
  return DefWindowProcW(h, m, w, l);
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR, int) {
  g_dir = ExeDir();
  GdiplusStartupInput gi; ULONG_PTR token;
  GdiplusStartup(&token, &gi, nullptr);
  {
    const wchar_t* cand[] = { L"Microsoft YaHei UI", L"Microsoft YaHei",
                              L"SimHei", L"SimSun", L"MS Gothic" };
    for (auto nm : cand) {
      FontFamily* f = new FontFamily(nm);
      if (f->IsAvailable()) { g_ff = f; break; }
      delete f;
    }
    if (!g_ff) g_ff = new FontFamily(L"Arial");
  }
  BuildRows();
  LoadSelection();

  WNDCLASSEXW wc{ sizeof(wc) };
  wc.lpfnWndProc = WndProc; wc.hInstance = hInst; wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
  wc.lpszClassName = L"RNDZhOutfitToolWnd"; wc.hbrBackground = nullptr;
  RegisterClassExW(&wc);

  DWORD style = WS_OVERLAPPEDWINDOW & ~(WS_THICKFRAME | WS_MAXIMIZEBOX);
  int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
  RECT r{ 0, 0, WIN_W, WIN_H };
  AdjustWindowRect(&r, style, FALSE);
  int ww = r.right - r.left, wh = r.bottom - r.top;
  g_hwnd = CreateWindowExW(0, wc.lpszClassName, L"换装核对 — ROBOTICS;NOTES DaSH",
                           style, (sw - ww) / 2, (sh - wh) / 2, ww, wh,
                           nullptr, nullptr, hInst, nullptr);
  ShowWindow(g_hwnd, SW_SHOW); UpdateWindow(g_hwnd);

  MSG msg;
  while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
  GdiplusShutdown(token);
  return 0;
}
