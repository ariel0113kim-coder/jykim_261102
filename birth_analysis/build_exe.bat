@echo off
chcp 65001 > nul
REM ================================================================
REM  대한민국 출생·사망 통계 분석기 exe 빌드 (PyInstaller, 단일 파일)
REM  결과: birth_analysis\dist\BirthStatsAnalyzer.exe
REM ================================================================
cd /d "%~dp0"

python -m pip install --quiet PyQt6 pandas matplotlib openpyxl pyinstaller || goto :error

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name BirthStatsAnalyzer ^
  --add-data "..\출생아수__합계출산율__자연증가_등_20260605082440.xlsx;." ^
  --add-data "..\사망자수__조사망률__기대수명_20240726085317.xlsx;." ^
  --exclude-module PySide6 --exclude-module PySide2 --exclude-module PyQt5 ^
  --exclude-module tkinter --exclude-module IPython --exclude-module notebook ^
  app.py || goto :error

echo.
echo 빌드 완료: %~dp0dist\BirthStatsAnalyzer.exe
goto :eof

:error
echo.
echo 빌드 실패 (위 오류 메시지를 확인하세요)
exit /b 1
