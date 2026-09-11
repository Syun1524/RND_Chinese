@echo off
REM 编译 RNDZhSetup.exe（原生 Win32 + GDI+，安装程序）
setlocal
call "C:\VS2022BT\VC\Auxiliary\Build\vcvars32.bat" >nul
cd /d "%~dp0"
rc /nologo /fo setup.res setup.rc
if errorlevel 1 ( echo RC FAILED & exit /b 1 )
cl /nologo /std:c++17 /EHsc /utf-8 /O2 /MT /DUNICODE /D_UNICODE ^
   RNDZhSetup.cpp ^
   /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup ^
   gdiplus.lib shell32.lib user32.lib gdi32.lib ole32.lib advapi32.lib ^
   setup.res /OUT:RNDZhSetup.exe
if errorlevel 1 ( echo BUILD FAILED & exit /b 1 )
echo BUILD OK
