@echo off
chcp 65001 > nul
REM ================================================================
REM  S&P 500 데이터 분석기 exe 빌드 (PyInstaller, 단일 파일)
REM  결과: sp500_analysis\dist\SP500Analyzer.exe
REM ================================================================
cd /d "%~dp0"

python -m pip install --quiet PyQt6 pandas matplotlib openpyxl pyinstaller || goto :error

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name SP500Analyzer ^
  --add-data "..\S&P 500 과거 데이터.csv;." ^
  --exclude-module PySide6 --exclude-module PySide2 --exclude-module PyQt5 ^
  --exclude-module tkinter --exclude-module IPython --exclude-module notebook ^
  app.py || goto :error

echo.
echo 빌드 완료: %~dp0dist\SP500Analyzer.exe
goto :eof

:error
echo.
echo 빌드 실패 (위 오류 메시지를 확인하세요)
exit /b 1
