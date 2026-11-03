@echo off
cd /d "%~dp0"
set GUION=%1
if "%GUION%"=="" set GUION=guion_paralisis.json
python hacer_video.py %GUION%
pause
