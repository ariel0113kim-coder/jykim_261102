"""
대한민국 출생·사망 통계 분석기 (PyQt6 GUI)

실행:  python birth_analysis/app.py
기능:  출생(필수)·사망(선택) 엑셀 열기 → 클렌징·분석 → 차트/표/리포트 확인 → 엑셀(.xlsx) 저장
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTableView, QTabWidget,
    QVBoxLayout, QWidget,
)

import analyzer

APP_TITLE = "대한민국 출생·사망 통계 분석기"


def resource_dir() -> Path:
    """exe(PyInstaller)로 실행 시 번들 임시폴더, 아니면 스크립트 폴더"""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def app_dir() -> Path:
    """exe가 있는 폴더(빌드 시) 또는 스크립트 폴더"""
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
        else Path(__file__).resolve().parent


def is_bundled(path: Path) -> bool:
    """exe에 내장되어 실행 중 임시폴더(_MEIxxxx)에 풀린 파일인지"""
    return getattr(sys, "frozen", False) and resource_dir().resolve() in path.resolve().parents


def describe_path(path: Path) -> str:
    return f"(내장 데이터) {path.name}" if is_bundled(path) else str(path)


def find_default(name: str) -> Path | None:
    """exe/스크립트 폴더 → 상위 폴더 → 번들 순으로 기본 데이터 파일을 찾는다"""
    base = app_dir()
    for d in (base, base.parent, resource_dir()):
        p = d / name
        if p.exists():
            return p
    return None


def is_count_column(name) -> bool:
    """'(명)' 단위 인원수 컬럼은 정수로 표시 (합계출산율(명)은 제외)"""
    return "(명)" in str(name) and "출산율" not in str(name)


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
            if v is None or v is pd.NA or (isinstance(v, float) and pd.isna(v)):
                return ""
            if isinstance(v, (bool, pd.BooleanDtype().type)) or str(v) in ("True", "False"):
                return "예" if str(v) == "True" else ""
            if isinstance(v, float):
                return f"{v:,.0f}" if is_count_column(self._df.columns[index.column()]) or abs(v) >= 1000                     else f"{v:,.2f}"
            if isinstance(v, int) or hasattr(v, "dtype"):
                try:
                    return f"{int(v):,}"
                except (TypeError, ValueError):
                    return str(v)
            return str(v)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if isinstance(v, str):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and isinstance(v, float) and v < 0:
            return Qt.GlobalColor.red
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return str(self._df.index[section])


class FitCanvas(FigureCanvasQTAgg):
    """창 크기에 맞춰 dpi를 조절 → 그림의 인치 크기(=레이아웃)는 유지하고 글자·선까지 함께 확대/축소"""

    def __init__(self, fig: Figure):
        self._native_in = tuple(fig.get_size_inches())
        super().__init__(fig)

    def resizeEvent(self, event):
        w = event.size().width() * self.device_pixel_ratio
        h = event.size().height() * self.device_pixel_ratio
        if w > 0 and h > 0:
            self.figure.dpi = min(w / self._native_in[0], h / self._native_in[1])
        super().resizeEvent(event)


class ChartTab(QWidget):
    def __init__(self, fig: Figure):
        super().__init__()
        canvas = FitCanvas(fig)
        lay = QVBoxLayout(self)
        lay.addWidget(NavigationToolbar2QT(canvas, self))
        lay.addWidget(canvas)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1500, 900)
        self.births_path: Path | None = None
        self.deaths_path: Path | None = None
        self.result: analyzer.AnalysisResult | None = None
        self.charts: dict[str, Figure] = {}

        self._build_ui()
        self.births_path = find_default(analyzer.BIRTHS_FILE_NAME)
        self.deaths_path = find_default(analyzer.DEATHS_FILE_NAME)
        self._update_file_labels()
        if self.births_path:
            self.run_analysis()

    # ---------------- UI ----------------
    def _build_ui(self):
        m_file = self.menuBar().addMenu("파일(&F)")
        act_births = QAction("출생 데이터 열기...", self, shortcut="Ctrl+O", triggered=self.on_open_births)
        act_deaths = QAction("사망 데이터 열기...", self, shortcut="Ctrl+D", triggered=self.on_open_deaths)
        act_save = QAction("엑셀로 저장...", self, shortcut="Ctrl+S", triggered=self.on_save_excel)
        act_quit = QAction("종료", self, shortcut="Ctrl+Q", triggered=self.close)
        m_file.addActions([act_births, act_deaths])
        m_file.addSeparator()
        m_file.addAction(act_save)
        m_file.addSeparator()
        m_file.addAction(act_quit)

        # 상단: 파일 선택
        self.lbl_births = QLabel()
        self.lbl_deaths = QLabel()
        for lbl in (self.lbl_births, self.lbl_deaths):
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        btn_births = QPushButton("📂 출생 데이터 (필수)")
        btn_births.clicked.connect(self.on_open_births)
        btn_deaths = QPushButton("📂 사망 데이터 (선택)")
        btn_deaths.clicked.connect(self.on_open_deaths)
        btn_clear = QPushButton("✕")
        btn_clear.setToolTip("사망 데이터 제외 (출생 데이터만 분석)")
        btn_clear.setFixedWidth(32)
        btn_clear.clicked.connect(self.on_clear_deaths)

        files = QGridLayout()
        files.addWidget(btn_births, 0, 0)
        files.addWidget(self.lbl_births, 0, 1, 1, 2)
        files.addWidget(btn_deaths, 1, 0)
        files.addWidget(self.lbl_deaths, 1, 1)
        files.addWidget(btn_clear, 1, 2)
        files.setColumnStretch(1, 1)

        # 상단: 그래프 기간 + 실행/저장
        self.spin_start = QSpinBox(minimum=1970, maximum=2100, value=1970)
        self.spin_end = QSpinBox(minimum=1970, maximum=2100, value=2025)
        self.btn_run = QPushButton("▶ 분석 실행")
        self.btn_run.clicked.connect(self.run_analysis)
        self.btn_save = QPushButton("💾 엑셀 저장")
        self.btn_save.clicked.connect(self.on_save_excel)
        for b in (self.btn_run, self.btn_save):
            b.setEnabled(False)
            b.setMinimumHeight(34)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("출생아수 그래프 기간:"))
        ctrl.addWidget(self.spin_start)
        ctrl.addWidget(QLabel("~"))
        ctrl.addWidget(self.spin_end)
        ctrl.addStretch(1)
        ctrl.addWidget(self.btn_run)
        ctrl.addWidget(self.btn_save)

        # 좌측: 핵심 지표 + 클렌징 로그
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

        # 우측: 차트 / 표 / 리포트
        self.chart_tabs = QTabWidget()
        self.table_tabs = QTabWidget()
        self.txt_report = QPlainTextEdit(readOnly=True)
        self.txt_report.setFont(QFont("Malgun Gothic", 10))
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self.chart_tabs, "📈 차트")
        self.main_tabs.addTab(self.table_tabs, "📋 분석 표")
        self.main_tabs.addTab(self.txt_report, "📝 분석 리포트")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.main_tabs)
        splitter.setSizes([420, 1080])

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.addLayout(files)
        lay.addLayout(ctrl)
        lay.addWidget(splitter, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("출생 데이터 엑셀 파일을 열어 주세요.")

    def _update_file_labels(self):
        self.lbl_births.setText(describe_path(self.births_path) if self.births_path else "(선택 안 됨)")
        self.lbl_deaths.setText(describe_path(self.deaths_path) if self.deaths_path
                                else "(선택 안 됨 – 출생 데이터만 분석)")
        self.btn_run.setEnabled(self.births_path is not None)

    # ---------------- 동작 ----------------
    def _pick_xlsx(self, title: str) -> Path | None:
        cur = self.births_path or self.deaths_path
        start = str(cur.parent) if cur and not is_bundled(cur) else str(app_dir())
        path, _ = QFileDialog.getOpenFileName(self, title, start, "엑셀 파일 (*.xlsx *.xls);;모든 파일 (*)")
        return Path(path) if path else None

    def on_open_births(self):
        p = self._pick_xlsx("출생 데이터 (출생아수, 합계출산율, 자연증가 등) 선택")
        if p:
            self.births_path = p
            self._update_file_labels()
            self.run_analysis()

    def on_open_deaths(self):
        p = self._pick_xlsx("사망 데이터 (사망자수, 조사망률, 기대수명) 선택")
        if p:
            self.deaths_path = p
            self._update_file_labels()
            if self.births_path:
                self.run_analysis()

    def on_clear_deaths(self):
        if self.deaths_path:
            self.deaths_path = None
            self._update_file_labels()
            if self.births_path:
                self.run_analysis()

    def run_analysis(self):
        if not self.births_path:
            return
        start, end = self.spin_start.value(), self.spin_end.value()
        if start >= end:
            QMessageBox.warning(self, APP_TITLE, "그래프 시작 연도는 종료 연도보다 앞서야 합니다.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.result = analyzer.run(self.births_path, self.deaths_path)
            self.charts = analyzer.build_charts(self.result, start, end)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            traceback.print_exc()
            QMessageBox.critical(self, APP_TITLE, f"분석 중 오류가 발생했습니다.\n"
                                 f"KOSIS에서 받은 원본 형식의 엑셀인지 확인해 주세요.\n\n{type(e).__name__}: {e}")
            return
        QApplication.restoreOverrideCursor()
        self._render()
        self.btn_save.setEnabled(True)
        mode = "출생+사망 통합" if self.result.has_deaths else "출생 단독"
        self.statusBar().showMessage(f"분석 완료 ({mode}): {len(self.result.df)}개년", 8000)

    def _render(self):
        res = self.result
        assert res is not None
        while self.summary_form.rowCount():
            self.summary_form.removeRow(0)
        bold = QFont()
        bold.setBold(True)
        for k, v in res.summary.items():
            lk, lv = QLabel(k), QLabel(v)
            lk.setFont(bold)
            lv.setWordWrap(True)
            self.summary_form.addRow(lk, lv)
        self.txt_log.setPlainText("\n".join(f"• {x}" if x and not x.startswith("[") else x
                                            for x in res.clean_log))
        self.txt_report.setPlainText(res.report)

        cur = self.chart_tabs.currentIndex()
        self.chart_tabs.clear()
        for name, fig in self.charts.items():
            self.chart_tabs.addTab(ChartTab(fig), name)
        self.chart_tabs.setCurrentIndex(min(max(cur, 0), self.chart_tabs.count() - 1))

        self.table_tabs.clear()
        for name, table in res.tables.items():
            view = QTableView()
            view.setModel(PandasModel(table))
            view.setAlternatingRowColors(True)
            view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.table_tabs.addTab(view, name)

    def on_save_excel(self):
        if not self.result:
            QMessageBox.information(self, APP_TITLE, "먼저 분석을 실행해 주세요.")
            return
        base = self.births_path.parent if self.births_path and not is_bundled(self.births_path) else app_dir()
        path, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", str(base / "출생사망_분석결과.xlsx"), "Excel 통합 문서 (*.xlsx)")
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
            traceback.print_exc()
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
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
