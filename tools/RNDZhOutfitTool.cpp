// RNDZhOutfitTool — ROBOTICS;NOTES DaSH 换装核对工具（开发用，不随补丁发布）
//
// 为什么单独一个程序：游戏本身没有换装菜单，服装名也不在任何可解包的数据里
// （.lkm 是纯二进制网格 + 内嵌贴图，无名称；.scx 是压缩脚本，不引用变体名）。
// 要把角色穿的每一套认出来，只能把该角色的全部变体都指向其中一套、进游戏肉眼看。
// 这件事只有开发者做一次，玩家不需要，所以从 RNDZhLauncher 里拆出来单独成 exe。
//
// 用法：把本 exe 放到游戏根目录（和 Game.exe 同级）运行 —— 它要写 LB 的配置、
// 还要能拉起 Game.exe。逐套核对：选角色 → 选服装（或按「下一套 ▶」顺序遍历）
// → 开始游戏 → 看外观 → 退出 → 下一套。结果填 成品ing/服装核对/服装名称表.json。
//
// 原理：把选择写进 %LOCALAPPDATA%\Committee of Zero\RNDSteam\config.json 的
// zzOutfitOverride（"c002_100" 形式，"off" 为关闭）。对应 patchdef.json 里
// settings.zzOutfitOverride.choices[<id>]，内含该角色【全部变体 → 目标变体】的
// fileIdRemap。必须先把「泳装／换装模式」打开，否则游戏用的是原版默认服。
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

static const int WIN_W = 760, WIN_H = 400;
static const wchar_t* VERIFY_KEY = L"zzOutfitOverride";

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
  C_WHITE  (255, 255, 255, 255);

// ── 核对项扁平列表（只收多变体角色；单变体角色没别的服装可切）──
struct VerifyItem { int ch; int var; };
static std::vector<VerifyItem> g_items;
static std::vector<int> g_pick;     // 角色下拉框里列出的角色索引
static int g_pos = 0;               // 在 g_items 里的位置

struct State {
  int  vChar = 0;      // 索引 -> OUTFIT_CHARS
  int  vVar  = 0;
  int  comboOpen = -1; // -1 / 0 角色 / 1 服装
  int  hot = -1, press = -1;
} st;

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
// 读出 config.json 里所有顶层键，原样保留（尤其 swimsuitPatch —— 不开它核对没意义）
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

static std::wstring ChoiceId() {
  if (st.vChar < 0 || st.vChar >= OUTFIT_CHAR_COUNT) return L"off";
  const OutfitChar& c = OUTFIT_CHARS[st.vChar];
  if (st.vVar < 0 || st.vVar >= c.count) return L"off";
  return std::wstring(c.id) + L"_" + c.variant[st.vVar];
}

static bool SwimsuitOn() {
  auto m = LoadFlatJson(ConfigPath() + L"\\config.json");
  auto it = m.find(L"swimsuitPatch");
  return it != m.end() && it->second.find(L"true") != std::wstring::npos;
}

// 写回 config.json：整份重写，未知键原样带上（我们只动 zzOutfitOverride）
static void SaveChoice() {
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
    if (kv.first == L"__schema_version" || kv.first == VERIFY_KEY || kv.first.empty()) continue;
    emit(kv.first, kv.second);
  }
  std::wstring id = ChoiceId();
  emit(VERIFY_KEY, L"\"" + id + L"\"");
  out << L"\n}";

  std::string u8 = WideToUtf8(out.str());
  std::ofstream f(path, std::ios::binary | std::ios::trunc);
  f.write(u8.data(), u8.size());
}

static void LoadChoice() {
  auto m = LoadFlatJson(ConfigPath() + L"\\config.json");
  auto it = m.find(VERIFY_KEY);
  if (it == m.end()) return;
  std::wstring id = it->second;
  while (!id.empty() && (id.front() == L'"' || id.front() == L' ')) id.erase(id.begin());
  while (!id.empty() && (id.back() == L'"' || id.back() == L' ' || id.back() == L'\r')) id.pop_back();
  size_t us = id.find(L'_');
  if (us == std::wstring::npos) return;
  std::wstring ch = id.substr(0, us), vv = id.substr(us + 1);
  for (int i = 0; i < OUTFIT_CHAR_COUNT; i++) {
    if (ch != OUTFIT_CHARS[i].id) continue;
    for (int k = 0; k < OUTFIT_CHARS[i].count; k++)
      if (vv == OUTFIT_CHARS[i].variant[k]) { st.vChar = i; st.vVar = k; return; }
  }
}

static void BuildItems() {
  g_items.clear(); g_pick.clear();
  for (int i = 0; i < OUTFIT_CHAR_COUNT; i++) {
    if (OUTFIT_CHARS[i].count < 2) continue;
    g_pick.push_back(i);
    for (int k = 0; k < OUTFIT_CHARS[i].count; k++) g_items.push_back({ i, k });
  }
}
static void SyncPos() {
  g_pos = 0;
  for (size_t i = 0; i < g_items.size(); i++)
    if (g_items[i].ch == st.vChar && g_items[i].var == st.vVar) { g_pos = (int)i; return; }
}
static void Move(int dir) {
  int n = (int)g_items.size(); if (!n) return;
  g_pos = ((g_pos + dir) % n + n) % n;
  st.vChar = g_items[g_pos].ch; st.vVar = g_items[g_pos].var;
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
static void DrawCombo(Graphics& g, const RectF& r, const wchar_t* v, bool hot) {
  FillRR(g, r, 7, C_HILITE);
  StrokeRR(g, r, 7, hot ? C_DIM : C_LINE, 1.f);
  DrawTxt(g, v, F(15), C_TEXT, r.X + 12, r.Y + 8);
  float cx = r.GetRight() - 16, cy = r.Y + 18;
  SolidBrush db(C_DIM); PointF tri[3] = { {cx-5,cy-2},{cx+5,cy-2},{cx,cy+3} };
  g.FillPolygon(&db, tri, 3);
}
static void DrawBtn(Graphics& g, const RectF& r, const wchar_t* t, bool hot) {
  FillRR(g, r, 7, hot ? C_ACCENT : C_HILITE);
  StrokeRR(g, r, 7, hot ? C_ACCENT : C_LINE, 1.f);
  SolidBrush b(C_TEXT); StringFormat sf;
  sf.SetAlignment(StringAlignmentCenter); sf.SetLineAlignment(StringAlignmentCenter);
  g.DrawString(t, -1, F(15,true), r, &sf, &b);
}

// 一行排下：角色 [..] 服装 [..] ◀ 下一套▶
// 注意留出标签宽度 —— 标签是单独绘制的，若坐标压到前一个下拉框上会叠字。
static RectF CharRect() { return RectF( 64.f, 92.f, 150.f, 36.f); }  // 64..214
static RectF VarRect()  { return RectF(274.f, 92.f, 155.f, 36.f); }  // 274..429
static RectF PrevRect() { return RectF(445.f, 92.f,  42.f, 36.f); }  // 445..487
static RectF NextRect() { return RectF(495.f, 92.f, 104.f, 36.f); }  // 495..599
static RectF StartRect(){ return RectF(300.f, 300.f, 160.f, 46.f); }
// 下拉向上展开（贴窗口底部，往下弹会被裁）
static RectF ItemRect(const RectF& base, int k, int n) {
  float bottom = base.Y - 2.f - (float)(n - 1 - k) * 32.f;
  return RectF(base.X, bottom - 32.f, base.Width, 32.f);
}

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
    SolidBrush pan(C_PANEL); gr.FillRectangle(&pan, 0, 0, rc.right, 60);

    DrawTxt(gr, L"换装核对（开发工具）", F(17,true), C_TEXT, 20, 20);

    const OutfitChar& c = OUTFIT_CHARS[st.vChar];

    DrawTxt(gr, L"角色", F(14), C_DIM, 20, 102);
    DrawCombo(gr, CharRect(), c.id, st.hot == 500);
    DrawTxt(gr, L"服装", F(14), C_DIM, 230, 102);
    std::wstring vl = c.variant[st.vVar];
    vl += L"   #";
    vl += std::to_wstring(c.fileId[st.vVar]);
    DrawCombo(gr, VarRect(), vl.c_str(), st.hot == 510);
    DrawBtn(gr, PrevRect(), L"◀", st.hot == 700);
    DrawBtn(gr, NextRect(), L"下一套 ▶", st.hot == 701);

    // 进度
    std::wstring prog = L"第 ";
    prog += std::to_wstring(g_pos + 1);
    prog += L" / ";
    prog += std::to_wstring((int)g_items.size());
    prog += L" 套";
    DrawTxt(gr, prog.c_str(), F(22,true), C_WARN, 20, 172);
    DrawTxt(gr, (L"当前 " + ChoiceId()).c_str(), F(13), C_MUTED, 20, 206);

    // 核对【不依赖】「泳装／换装模式」。机制上看 zzOutfitOverride 自带 fileIdRemap，
    // 而 mgsFileOpenHook 读 config["patch"]["fileIdRemap"] 是【无条件】的
    // （且命中就直接 return，不会落到 fileRedirection）。所以开着/关着都能核对：
    //   开着  -> 被核对角色穿选中的那套，其它角色穿泳装
    //   关着  -> 被核对角色穿选中的那套，其它角色穿原版默认服
    // 两种都可用，关着时画面更干净。
    DrawTxt(gr, L"点「开始游戏」进游戏看这套长什么样，退出后点「下一套 ▶」继续。",
            F(13), C_TEXT, 20, 236);
    if (SwimsuitOn()) {
      DrawTxt(gr, L"（「泳装／换装模式」已开：其它角色会是泳装，被核对角色是选中的这一套。）",
              F(12), C_MUTED, 20, 262);
    } else {
      DrawTxt(gr, L"（「泳装／换装模式」未开：其它角色是原版默认服，被核对角色是选中的这一套。不影响核对。）",
              F(12), C_MUTED, 20, 262);
    }
    DrawTxt(gr, L"认出来的名字填进 成品ing/服装核对/服装名称表.json。",
            F(12), C_MUTED, 20, 284);

    DrawBtn(gr, StartRect(), L"开始游戏", st.hot == 800);

    // 展开的下拉项
    if (st.comboOpen == 0) {
      for (int k = 0; k < (int)g_pick.size(); k++) {
        int ci = g_pick[k];
        RectF ir = ItemRect(CharRect(), k, (int)g_pick.size());
        bool sel = (ci == st.vChar);
        FillRR(gr, ir, 6, (st.hot == 520 + k) ? C_ACCENT : (sel ? C_HILITE : C_PANEL));
        std::wstring lab = OUTFIT_CHARS[ci].id;
        lab += L"　";
        lab += std::to_wstring(OUTFIT_CHARS[ci].count);
        lab += L" 套";
        DrawTxt(gr, lab.c_str(), F(15), C_TEXT, ir.X + 12, ir.Y + 7);
      }
    }
    if (st.comboOpen == 1) {
      for (int k = 0; k < c.count; k++) {
        RectF ir = ItemRect(VarRect(), k, c.count);
        bool sel = (k == st.vVar);
        FillRR(gr, ir, 6, (st.hot == 600 + k) ? C_ACCENT : (sel ? C_HILITE : C_PANEL));
        std::wstring lab = c.variant[k];
        lab += L"   #";
        lab += std::to_wstring(c.fileId[k]);
        DrawTxt(gr, lab.c_str(), F(15), C_TEXT, ir.X + 12, ir.Y + 7);
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
  SaveChoice();
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
static int Hit(int x, int y) {
  auto in = [&](const RectF& r) {
    return x >= r.X && x <= r.GetRight() && y >= r.Y && y <= r.GetBottom();
  };
  if (st.comboOpen == 0) for (int k = 0; k < (int)g_pick.size(); k++)
    if (in(ItemRect(CharRect(), k, (int)g_pick.size()))) return 520 + k;
  if (st.comboOpen == 1 && st.vChar < OUTFIT_CHAR_COUNT)
    for (int k = 0; k < OUTFIT_CHARS[st.vChar].count; k++)
      if (in(ItemRect(VarRect(), k, OUTFIT_CHARS[st.vChar].count))) return 600 + k;
  if (in(CharRect())) return 500;
  if (in(VarRect())) return 510;
  if (in(PrevRect())) return 700;
  if (in(NextRect())) return 701;
  if (in(StartRect())) return 800;
  return -1;
}

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
  switch (m) {
  case WM_MOUSEMOVE: {
    int id = Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id != st.hot) { st.hot = id; InvalidateRect(h, nullptr, FALSE); }
    TRACKMOUSEEVENT t{ sizeof(t) }; t.dwFlags = TME_LEAVE; t.hwndTrack = h;
    TrackMouseEvent(&t);
    return 0;
  }
  case WM_MOUSELEAVE: st.hot = -1; InvalidateRect(h, nullptr, FALSE); return 0;
  case WM_LBUTTONDOWN: { st.press = Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l)); return 0; }
  case WM_LBUTTONUP: {
    int id = Hit(GET_X_LPARAM(l), GET_Y_LPARAM(l));
    if (id == st.press) {
      if (id == 500) { st.comboOpen = (st.comboOpen == 0) ? -1 : 0; InvalidateRect(h, nullptr, FALSE); }
      else if (id == 510) { st.comboOpen = (st.comboOpen == 1) ? -1 : 1; InvalidateRect(h, nullptr, FALSE); }
      else if (id == 700) { Move(-1); st.comboOpen = -1; SaveChoice(); InvalidateRect(h, nullptr, FALSE); }
      else if (id == 701) { Move(+1); st.comboOpen = -1; SaveChoice(); InvalidateRect(h, nullptr, FALSE); }
      else if (id == 800) { Launch(); }
      else if (id >= 520 && id < 520 + (int)g_pick.size()) {
        st.vChar = g_pick[id - 520];
        if (st.vVar >= OUTFIT_CHARS[st.vChar].count) st.vVar = 0;
        SyncPos(); st.comboOpen = -1; SaveChoice(); InvalidateRect(h, nullptr, FALSE);
      }
      else if (id >= 600 && st.vChar < OUTFIT_CHAR_COUNT &&
               id < 600 + OUTFIT_CHARS[st.vChar].count) {
        st.vVar = id - 600; SyncPos();
        st.comboOpen = -1; SaveChoice(); InvalidateRect(h, nullptr, FALSE);
      }
    } else if (st.comboOpen >= 0 && id == -1) { st.comboOpen = -1; InvalidateRect(h, nullptr, FALSE); }
    st.press = -1; return 0;
  }
  case WM_PAINT: { PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps); Paint(dc); EndPaint(h, &ps); return 0; }
  case WM_ERASEBKGND: return 1;
  case WM_KEYDOWN: if (w == VK_ESCAPE) PostMessageW(h, WM_CLOSE, 0, 0); return 0;
  case WM_CLOSE: SaveChoice(); DestroyWindow(h); return 0;
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
  BuildItems();
  LoadChoice();
  SyncPos();

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
