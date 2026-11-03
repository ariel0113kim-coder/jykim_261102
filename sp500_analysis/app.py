"""
S&P 500 데이터 분석기 (PyQt6 GUI)

실행:  python sp500_analysis/app.py
기능:  CSV 열기 → 클렌징·분석 → 차트/표 확인 → 엑셀(.xlsx) 저장
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication, QDateEdit, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTableView,
    QTabWidget, QVBoxLayout, QWidget,
)

import analyzer

APP_TITLE = "S&P 500 데이터 분석기"
DEFAULT_CSV_NAME = "S&P 500 과거 데이터.csv"


def resource_dir() -> Path:
    """exe(PyInstaller)로 실행 시 번들 임시폴더, 아니면 스크립트 폴더"""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def find_default_csv() -> Path | None:
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
        else Path(__file__).resolve().parent
    for d in (exe_dir, exe_dir.parent, resource_dir()):
        p = d / DEFAULT_CSV_NAME
        if p.exists():
            return p
    return None


class PandasModel(QAbstractTableModel):
    """pandas DataFrame → QTableView"""

    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return self._df.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        v = self._df.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            if isinstance(v, pd.Timestamp):
                return v.strftime("%Y-%m-%d")
            if isinstance(v, float):
                return f"{v:,.2f}"
            return str(v)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.ForegroundRole and isinstance(v, float) and "%" in str(
                self._df.columns[index.column()]) and v < 0:
            return Qt.GlobalColor.red
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        v = self._df.index[section]
        return v.strftime("%Y-%m-%d") if isinstance(v, pd.Timestamp) else str(v)


class ChartTab(QWidget):
    def __init__(self, fig: Figure):
        super().__init__()
        canvas = FigureCanvasQTAgg(fig)
        lay = QVBoxLayout(self)
        lay.addWidget(NavigationToolbar2QT(canvas, self))
        lay.addWidget(canvas)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1400, 860)
        self.csv_path: Path | None = None
        self.result: analyzer.AnalysisResult | None = None
        self.charts: dict[str, Figure] = {}

        self._build_ui()
        default = find_default_csv()
        if default:
            self.load_csv(default)

    # ---------------- UI ----------------
    def _build_ui(self):
        # 메뉴
        m_file = self.menuBar().addMenu("파일(&F)")
        act_open = QAction("CSV 열기...", self, shortcut="Ctrl+O", triggered=self.on_open)
        act_save = QAction("엑셀로 저장...", self, shortcut="Ctrl+S", triggered=self.on_save_excel)
        act_quit = QAction("종료", self, shortcut="Ctrl+Q", triggered=self.close)
        m_file.addActions([act_open, act_save])
        m_file.addSeparator()
        m_file.addAction(act_quit)

        # 상단 컨트롤 바
        self.lbl_file = QLabel("파일: (없음)")
        self.lbl_file.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        btn_open = QPushButton("📂 CSV 열기")
        btn_open.clicked.connect(self.on_open)

        self.date_start = QDateEdit(QDate(2000, 1, 1), calendarPopup=True, displayFormat="yyyy-MM")
        self.date_end = QDateEdit(QDate(2019, 12, 31), calendarPopup=True, displayFormat="yyyy-MM")
        self.btn_run = QPushButton("▶ 분석 실행")
        self.btn_run.clicked.connect(self.run_analysis)
        self.btn_save = QPushButton("💾 엑셀 저장")
        self.btn_save.clicked.connect(self.on_save_excel)
        for b in (self.btn_run, self.btn_save):
            b.setEnabled(False)
            b.setMinimumHeight(30)

        bar = QHBoxLayout()
        bar.addWidget(btn_open)
        bar.addWidget(self.lbl_file, 1)
        bar.addWidget(QLabel("종가 그래프 기간:"))
        bar.addWidget(self.date_start)
        bar.addWidget(QLabel("~"))
        bar.addWidget(self.date_end)
        bar.addSpacing(12)
        bar.addWidget(self.btn_run)
        bar.addWidget(self.btn_save)

        # 좌측: 요약 + 클렌징 로그
        self.summary_box = QGroupBox("핵심 지표")
        self.summary_form = QFormLayout(self.summary_box)
        log_box = QGroupBox("데이터 클렌징 로그")
        self.txt_log = QPlainTextEdit(readOnly=True)
        QVBoxLayout(log_box).addWidget(self.txt_log)
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.addWidget(self.summary_box)
        left_lay.addWidget(log_box, 1)

        # 우측: 차트 탭 / 표 탭
        self.chart_tabs = QTabWidget()
        self.table_tabs = QTabWidget()
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self.chart_tabs, "📈 차트")
        self.main_tabs.addTab(self.table_tabs, "📋 분석 표")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.main_tabs)
        splitter.setSizes([380, 1020])

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.addLayout(bar)
        lay.addWidget(splitter, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("CSV 파일을 열어 주세요.")

    # ---------------- 동작 ----------------
    def on_open(self):
        start = str(self.csv_path.parent) if self.csv_path else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "S&P 500 CSV 선택", start, "CSV 파일 (*.csv);;모든 파일 (*)")
        if path:
            self.load_csv(Path(path))

    def load_csv(self, path: Path):
        self.csv_path = path
        self.lbl_file.setText(f"파일: {path}")
        self.btn_run.setEnabled(True)
        self.run_analysis()

    def run_analysis(self):
        if not self.csv_path:
            return
        start = self.date_start.date()
        end = self.date_end.date()
        if start > end:
            QMessageBox.warning(self, APP_TITLE, "시작 월이 종료 월보다 늦습니다.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            df, log = analyzer.load_and_clean(self.csv_path)
            self.result = analyzer.analyze(df, log)
            self.charts = analyzer.build_charts(
                self.result, start.toString("yyyy-MM"), end.toString("yyyy-MM"))
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_TITLE, f"분석 중 오류가 발생했습니다.\n\n{e}")
            traceback.print_exc()
            return
        QApplication.restoreOverrideCursor()
        self._render()
        self.btn_save.setEnabled(True)
        self.statusBar().showMessage(f"분석 완료: {len(self.result.df):,}행", 8000)

    def _render(self):
        res = self.result
        assert res is not None
        # 요약
        while self.summary_form.rowCount():
            self.summary_form.removeRow(0)
        bold = QFont()
        bold.setBold(True)
        for k, v in res.summary.items():
            lv = QLabel(v)
            lv.setWordWrap(True)
            lk = QLabel(k)
            lk.setFont(bold)
            self.summary_form.addRow(lk, lv)
        self.txt_log.setPlainText("\n".join(f"• {line}" for line in res.clean_log))

        # 차트
        cur = self.chart_tabs.currentIndex()
        self.chart_tabs.clear()
        for name, fig in self.charts.items():
            self.chart_tabs.addTab(ChartTab(fig), name)
        self.chart_tabs.setCurrentIndex(max(cur, 0))

        # 표
        self.table_tabs.clear()
        data_view = res.df.drop(columns=["Vol21"], errors="ignore")
        for name, table in {"정제데이터": data_view, **res.tables}.items():
            view = QTableView()
            view.setModel(PandasModel(table))
            view.setAlternatingRowColors(True)
            view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.table_tabs.addTab(view, name)

    def on_save_excel(self):
        if not self.result:
            QMessageBox.information(self, APP_TITLE, "먼저 분석을 실행해 주세요.")
            return
        base = self.csv_path.parent if self.csv_path else Path.home()
        path, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", str(base / "SP500_분석결과.xlsx"), "Excel 통합 문서 (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            analyzer.export_excel(self.result, self.charts, path)
        except PermissionError:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_TITLE, "파일을 저장할 수 없습니다.\n엑셀에서 열려 있다면 닫고 다시 시도해 주세요.")
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_TITLE, f"저장 중 오류가 발생했습니다.\n\n{e}")
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"저장 완료: {path}", 8000)
        QMessageBox.information(self, APP_TITLE, f"엑셀 파일로 저장했습니다.\n\n{path}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setFont(QFont("Malgun Gothic", 9))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
