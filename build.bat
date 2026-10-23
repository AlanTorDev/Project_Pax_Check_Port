@echo off
cd /d "%~dp0"
echo === Dong goi PortCheck.exe ===
if not exist port_check.py (
  echo Khong thay port_check.py. Hay de build.bat CHUNG THU MUC voi port_check.py
  pause
  exit /b 1
)
python --version >nul 2>&1
if errorlevel 1 (
  echo Khong tim thay Python. Hay cai Python va tick "Add python.exe to PATH".
  pause
  exit /b 1
)
python -m pip install --upgrade pyinstaller customtkinter
if errorlevel 1 goto fail
python -m PyInstaller --noconfirm --onefile --windowed --name PortCheck --collect-all customtkinter port_check.py
if errorlevel 1 goto fail
copy /y dist\PortCheck.exe PortCheck.exe >nul
echo.
echo === XONG! File chay: %~dp0PortCheck.exe ===
echo Copy PortCheck.exe sang may bat ky (Windows) la chay duoc, khong can cai Python.
pause
exit /b 0
:fail
echo.
echo === LOI. Chup man hinh cua so nay gui lai de duoc ho tro ===
pause
exit /b 1
