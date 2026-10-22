@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."

set "DEFAULT_MANIFEST=announcements\manifest.json"
if exist "announcements\manifest.draft.json" set "DEFAULT_MANIFEST=announcements\manifest.draft.json"

if /I "%DEFAULT_MANIFEST%"=="announcements\manifest.draft.json" echo [DRAFT] Using announcements\manifest.draft.json
python tools\announcement_preview.py --manifest "%DEFAULT_MANIFEST%" %*
if errorlevel 1 pause
