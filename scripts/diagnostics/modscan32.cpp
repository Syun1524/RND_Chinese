// modscan32 -- list a process's loaded modules whose name matches a substring.
//
// Needed because the usual tools lie here: `tasklist /m` silently prints nothing for
// these WOW64 game processes, and 64-bit PowerShell cannot enumerate a 32-bit process'
// modules. Building a 32-bit tool that uses the toolhelp API gives the ground truth:
// WHICH dinput8.dll (full path!) a running Game.exe actually mapped.
//
//   modscan32.exe <pid> [substring]
//
// Build: see build_modscan.bat
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>
#include <cwchar>

static int contains_ci(const wchar_t* hay, const wchar_t* needle) {
  if (!*needle) return 1;
  size_t nh = wcslen(hay), nn = wcslen(needle);
  if (nn > nh) return 0;
  for (size_t i = 0; i + nn <= nh; i++) {
    size_t j = 0;
    for (; j < nn; j++) {
      wchar_t a = hay[i + j], b = needle[j];
      if (a >= L'A' && a <= L'Z') a += 32;
      if (b >= L'A' && b <= L'Z') b += 32;
      if (a != b) break;
    }
    if (j == nn) return 1;
  }
  return 0;
}

int wmain(int argc, wchar_t** argv) {
  if (argc < 2) {
    wprintf(L"usage: modscan32.exe <pid> [nameSubstring]\n");
    return 2;
  }
  DWORD pid = (DWORD)_wtoi(argv[1]);
  const wchar_t* needle = (argc >= 3) ? argv[2] : L"dinput";

  HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid);
  if (snap == INVALID_HANDLE_VALUE) {
    wprintf(L"# no module snapshot for pid %lu (err=%lu)\n", pid, GetLastError());
    return 1;
  }
  MODULEENTRY32W me;
  me.dwSize = sizeof(me);
  int n = 0;
  if (Module32FirstW(snap, &me)) {
    do {
      if (contains_ci(me.szModule, needle)) {
        wprintf(L"%s\t%s\n", me.szModule, me.szExePath);
        n++;
      }
    } while (Module32NextW(snap, &me));
  }
  CloseHandle(snap);
  if (n == 0) wprintf(L"# no module matching '%ls' in pid %lu\n", needle, pid);
  return 0;
}
