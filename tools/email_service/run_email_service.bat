@echo off
set PY_EXE="C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe"
set APP_DIR="%~dp0"

cd /d %APP_DIR%
%PY_EXE% main.py
pause