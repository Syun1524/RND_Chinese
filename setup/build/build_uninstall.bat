@echo off
REM Build the uninstaller (native Win32 + GDI+, no external deps).
REM Sources are in ..\src, the finished exe goes to ..\bin.
REM
REM Keep this file PURE ASCII. The product name is Chinese, and Chinese text inside a
REM .bat is fragile: cmd re-reads the file line by line in the OEM codepage, chcp
REM only helps the lines it has not read yet, and an editor writing LF instead of
REM CRLF breaks it outright (both were hit). So the compiler writes an ASCII name and
REM rename_uninstall.py gives it the Chinese product name afterwards -- Python handles
REM Unicode paths natively. Same reason build_installer.py is Python.
REM
REM Always recompile the resource: uninstall.rc carries the icon AND the
REM requireAdministrator manifest. The old "if not exist uninstall.res" guard meant a
REM stale .res was reused forever, and it also regenerated uninstall.rc, silently
REM dropping the manifest.
REM The .res and .obj go under %TEMP% so no build junk lands in the tree.
setlocal
call "C:\VS2022BT\VC\Auxiliary\Build\vcvars32.bat" >nul
set "RES=%TEMP%\rnd_uninstall.res"

pushd "%~dp0..\src"
rc /nologo /fo "%RES%" uninstall.rc
if errorlevel 1 ( echo RC FAILED & popd & exit /b 1 )
popd

pushd "%TEMP%"
cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE ^
   "%~dp0..\src\RNDZhUninstall.cpp" ^
   /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup ^
   gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib ^
   "%RES%" /OUT:"%~dp0..\bin\RNDZhUninstall.exe"
if errorlevel 1 ( echo BUILD FAILED & popd & exit /b 1 )
popd

del "%RES%" >nul 2>&1
python "%~dp0rename_uninstall.py"
if errorlevel 1 ( echo RENAME FAILED & exit /b 1 )
dir /b "%~dp0..\bin"
