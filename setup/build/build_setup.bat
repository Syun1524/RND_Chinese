@echo off
REM Build RNDZhSetup.exe (native Win32 + GDI+, installer GUI).
REM Sources are in ..\src, the finished exe goes to ..\bin.
REM The .res and .obj are produced under %TEMP% so no build junk lands in the tree.
REM Keep comments ASCII: cmd parses REM lines in the OEM codepage.
setlocal
call "C:\VS2022BT\VC\Auxiliary\Build\vcvars32.bat" >nul
set "RES=%TEMP%\rnd_setup.res"

pushd "%~dp0..\src"
rc /nologo /fo "%RES%" setup.rc
if errorlevel 1 ( echo RC FAILED & popd & exit /b 1 )
popd

pushd "%TEMP%"
cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE ^
   "%~dp0..\src\RNDZhSetup.cpp" ^
   /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup ^
   gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib advapi32.lib ^
   "%RES%" /OUT:"%~dp0..\bin\RNDZhSetup.exe"
if errorlevel 1 ( echo BUILD FAILED & popd & exit /b 1 )
popd

del "%RES%" >nul 2>&1
echo BUILD OK
