@echo off
cd /d "%~dp0"
title SpeechTranslate Pro
if not exist "venv\Scripts\python.exe" py -3 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt --disable-pip-version-check -q
start "" http://127.0.0.1:5000
venv\Scripts\python.exe app.py
pause
