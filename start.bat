@echo off
rem Read the task lists in the folder that contains this task-view folder.
python "%~dp0app\taskview.py" %*
if errorlevel 1 pause
