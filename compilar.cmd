@echo off
title Compilando...
pyinstaller --onefile --windowed --icon=icon.ico --add-data "icon.ico;." --name emmanager main.py
rmdir /s /q build && del /q *.spec
title Listo!
cls
color a
echo Listo!
start dist
pause > NUL
color