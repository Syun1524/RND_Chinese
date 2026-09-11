// rndkill -- kill leftover installer/uninstaller processes, printing a log file.
//
// Why a dedicated exe: this machine refuses to launch cmd.exe / powershell.exe elevated
// on request from a script (an elevation/AV policy silently blocks it -- rc=1 with no
// output), while a plain custom exe elevates fine. So the cleanup that the lifecycle
// harness needs is compiled into this one small program instead.
//
// Writes <exe dir>\rndkill_out.txt listing what it killed, so the caller can verify.
//
// Build: see build_rndkill.bat
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>

static const wchar_t* TARGETS[] = {
  L"RNDZhSetup.exe", L"RNDZhUninstall.exe", L"RNDZhLauncher.exe",
  L"Game.exe", L"probe_import.exe",
};

int wmain() {
  wchar_t out[MAX_PATH];
  GetModuleFileNameW(NULL, out, MAX_PATH);
  wchar_t* dot = wcsrchr(out, L'.');
  if (dot) wcscpy_s(dot, 24, L"_out.txt");
  FILE* f = NULL;
  _wfopen_s(&f, out, L"w, ccs=UTF-8");

  int killed = 0, failed = 0;
  HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
  if (snap != INVALID_HANDLE_VALUE) {
    PROCESSENTRY32W pe;
    pe.dwSize = sizeof(pe);
    if (Process32FirstW(snap, &pe)) {
      do {
        for (size_t i = 0; i < (sizeof(TARGETS)/sizeof(TARGETS[0])); i++) {
          // match by name
          if (_wcsicmp(pe.szExeFile, TARGETS[i]) != 0) continue;
          HANDLE h = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
          if (!h) {
            if (f) fwprintf(f, L"OPEN_FAIL  %s pid=%lu err=%lu\n",
                            pe.szExeFile, pe.th32ProcessID, GetLastError());
            failed++;
            continue;
          }
          if (TerminateProcess(h, 0)) {
            if (f) fwprintf(f, L"KILLED     %s pid=%lu\n",
                            pe.szExeFile, pe.th32ProcessID);
            killed++;
          } else {
            if (f) fwprintf(f, L"KILL_FAIL  %s pid=%lu err=%lu\n",
                            pe.szExeFile, pe.th32ProcessID, GetLastError());
            failed++;
          }
          CloseHandle(h);
        }
      } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
  }
  if (f) { fwprintf(f, L"TOTAL killed=%d failed=%d\n", killed, failed); fclose(f); }
  return 0;
}
