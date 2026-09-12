@echo off
REM Rebuild the single-file installer RNDZh-Setup-v0.1.exe.
REM Uses the SDK's installer-SFX module (sdk\7zSD_custom.sfx) and 7zr.
REM Python drives it because the paths and SFX config contain non-ASCII text,
REM which cmd's codepage handling mangles. Keep this file's comments ASCII.
cd /d "%~dp0"
python build_installer.py
