@echo off
REM Build the single-file installer (RNDZh-Setup-v0.1.exe) into ..\
REM Uses the SDK's installer-SFX module (sdk\7zSD_custom.sfx) + 7zr,
REM exactly as documented in the LZMA SDK (DOC/installer.txt).
REM Python drives it because the paths and SFX config contain non-ASCII text,
REM which cmd's codepage handling mangles.
setlocal
cd /d "%~dp0"
python build_installer.py
