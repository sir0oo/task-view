@echo off
python "%~dp0app\taskview.py" --root "%~dp0sample-data" %*
if errorlevel 1 pause
