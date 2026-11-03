"""
네이버 증권 코스피200 데이터 조회 GUI 앱 (PyQt6)
  1) 지수 현재가 요약
  2) 일별 시세 (날짜, 종가, 전일비, 등락률, 시가, 고가, 저가)
  3) 구성 종목 (종목코드, 종목명, 현재가, 등락률, 거래량, 거래대금, 시가총액)
엑셀 저장 시 시트 3개로 저장된다.

필요 패키지: pip install requests openpyxl PyQt6

※ stock.naver.com 페이지는 자바스크립트로 화면을 그리기 때문에 HTML 안에
  데이터가 없다. 그래서 BeautifulSoup으로 HTML을 파싱하는 대신, 페이지가
  내부적으로 호출하는 JSON 데이터 주소에서 직접 값을 받아온다.
  (공식 공개 API가 아니므로 주소나 형식이 예고 없이 바뀔 수 있다.)
"""
import sys
import time
from datetime import datetime

import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet
from PyQt6.QtCore import QThread, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSpinBox, QStatusBar,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

# ---------------------------------------------------------------------------
# 데이터 수집
# ---------------------------------------------------------------------------
API_BASE = "https://m.stock.naver.com/api/index/KPI200"
STOCK_PAGE_URL = "https://stock.naver.com/domestic/stock/{code}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": "https://stock.naver.com/",
}
PAGE_SIZE = 50  # 한 번에 받을 개수 (100으로 하면 응답이 비어 옴)


def get_json(path, params=None):
    res = requests.get(f"{API_BASE}/{path}", params=params, headers=HEADERS, timeout=10)
    res.raise_for_status()
    return res.json()


def to_number(value):
    """'219,500' / '-4.15' 같은 문자열을 숫자로 바꾼다. 숫자가 아니면 그대로 둔다."""
    if not isinstance(value, str):
        return value
    text = value.replace(",", "").strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return value


def get_index_summary():
    basic = get_json("basic")
    integration = get_json("integration")

    summary = {
        "지수명": basic.get("stockName", "코스피 200"),
        "현재가": to_number(basic.get("closePrice")),
        "전일비": to_number(basic.get("compareToPreviousClosePrice")),
        "등락률(%)": to_number(basic.get("fluctuationsRatio")),
        "장 상태": basic.get("marketStatus", ""),
        "기준 시각": basic.get("localTradedAt", ""),
    }
    # 전일 / 시가 / 고가 / 저가 / 52주 최고·최저 등 추가 항목
    for info in integration.get("totalInfos", []):
        summary[info.get("key", info.get("code"))] = to_number(info.get("value"))
    return summary


def get_daily_prices(days=60):
    rows = []
    page = 1
    while len(rows) < days:
        data = get_json("price", {"page": page, "pageSize": PAGE_SIZE})
        if not data:
            break
        for d in data:
            rows.append({
                "날짜": d.get("localTradedAt", ""),
                "종가": to_number(d.get("closePrice")),
                "전일비": to_number(d.get("compareToPreviousClosePrice")),
                "등락률(%)": to_number(d.get("fluctuationsRatio")),
                "시가": to_number(d.get("openPrice")),
                "고가": to_number(d.get("highPrice")),
                "저가": to_number(d.get("lowPrice")),
            })
        page += 1
        time.sleep(0.3)
    return rows[:days]


def get_constituents():
    rows = []
    seen = set()
    page = 1
    while True:
        data = get_json("enrollStocks", {"page": page, "pageSize": PAGE_SIZE})
        if not data:
            break
        new_count = 0
        for s in data:
            code = s.get("itemCode")
            if code in seen:
                continue
            seen.add(code)
            new_count += 1
            rows.append({
                "순위": len(rows) + 1,
                "종목코드": code,
                "종목명": s.get("stockName", ""),
                "현재가": to_number(s.get("closePrice")),
                "전일비": to_number(s.get("compareToPreviousClosePrice")),
                "등락률(%)": to_number(s.get("fluctuationsRatio")),
                "거래량": to_number(s.get("accumulatedTradingVolume")),
                "거래대금(백만원)": to_number(s.get("accumulatedTradingValue")),
                "시가총액(억원)": to_number(s.get("marketValue")),
            })
        if new_count == 0 or len(data) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.3)
    return rows


# ---------------------------------------------------------------------------
# 엑셀 저장
# ---------------------------------------------------------------------------
HEADER_FILL = PatternFill("solid", fgColor="DDEBF7")


def write_table(ws, rows):
    if not rows:
        ws.append(["데이터 없음"])
        return
    headers = list(rows[0].keys())
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        ws.append([row.get(h) for h in headers])

    for col_idx, header in enumerate(headers, 1):
        width = max(len(str(header)) * 2, *(len(str(r.get(header, ""))) for r in rows)) + 2
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(width, 30)
        for r in range(2, ws.max_row + 1):
            cell = ws.cell(row=r, column=col_idx)
            if isinstance(cell.value, int):
                cell.number_format = "#,##0"
            elif isinstance(cell.value, float):
                cell.number_format = "#,##0.00"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def save_excel(summary, daily, stocks, path):
    wb = Workbook()
    ws = wb.active
    if not isinstance(ws, Worksheet):
        ws = wb.create_sheet()

    ws.title = "지수요약"
    ws.append(["항목", "값"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
    for key, value in summary.items():
        ws.append([key, value])
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 28

    write_table(wb.create_sheet("일별시세"), daily)
    write_table(wb.create_sheet("구성종목"), stocks)
    wb.save(path)


# ---------------------------------------------------------------------------
# 백그라운드 작업 스레드
# ---------------------------------------------------------------------------
class FetchWorker(QThread):
    status = pyqtSignal(str)
    # dict/list로 지정하면 Qt 형식으로 변환되면서 키 순서가 가나다순으로 바뀌므로
    # object로 지정해 파이썬 객체를 그대로 넘긴다.
    done = pyqtSignal(object, object, object)
    failed = pyqtSignal(str)

    def __init__(self, days):
        super().__init__()
        self.days = days

    def run(self):
        try:
            self.status.emit("지수 요약 조회 중...")
            summary = get_index_summary()
            self.status.emit("일별 시세 조회 중...")
            daily = get_daily_prices(self.days)
            self.status.emit("구성 종목 조회 중...")
            stocks = get_constituents()
            self.done.emit(summary, daily, stocks)
        except Exception as e:
            self.failed.emit(str(e))


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------
UP_COLOR = QColor("#D32F2F")    # 상승: 빨강
DOWN_COLOR = QColor("#1565C0")  # 하락: 파랑
SIGNED_COLUMNS = {"전일비", "등락률(%)"}


class SortableItem(QTableWidgetItem):
    """숫자는 숫자 크기대로 정렬되도록 하는 표 칸."""

    def __init__(self, value):
        if isinstance(value, int):
            text = f"{value:,}"
        elif isinstance(value, float):
            text = f"{value:,.2f}"
        else:
            text = "" if value is None else str(value)
        super().__init__(text)
        self.sort_value = value
        if isinstance(value, (int, float)):
            self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        a = self.sort_value
        b = other.sort_value if isinstance(other, SortableItem) else other.text()
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a < b
        return str(a) < str(b)


def make_table():
    table = QTableWidget()
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    vheader = table.verticalHeader()
    if vheader is not None:
        vheader.setVisible(False)
    return table


def fill_table(table, rows):
    table.setSortingEnabled(False)
    table.clear()
    if not rows:
        table.setRowCount(0)
        table.setColumnCount(0)
        return
    headers = list(rows[0].keys())
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, key in enumerate(headers):
            value = row.get(key)
            item = SortableItem(value)
            if key in SIGNED_COLUMNS and isinstance(value, (int, float)) and value != 0:
                item.setForeground(UP_COLOR if value > 0 else DOWN_COLOR)
            table.setItem(r, c, item)
    table.setSortingEnabled(True)
    header = table.horizontalHeader()
    if header is not None:
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("코스피200 데이터 조회")
        self.resize(1100, 720)
        self.summary = {}
        self.daily = []
        self.stocks = []
        self.worker = None

        # 상단: 조회 조건 / 버튼
        self.days_spin = QSpinBox()
        self.days_spin.setRange(5, 1000)
        self.days_spin.setValue(60)
        self.days_spin.setSuffix(" 일")

        self.fetch_btn = QPushButton("데이터 조회")
        self.fetch_btn.clicked.connect(self.fetch)
        self.excel_btn = QPushButton("엑셀 저장")
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.save)

        top = QHBoxLayout()
        top.addWidget(QLabel("일별 시세 기간"))
        top.addWidget(self.days_spin)
        top.addStretch(1)
        top.addWidget(self.fetch_btn)
        top.addWidget(self.excel_btn)

        # 현재가 표시
        self.price_label = QLabel("코스피 200  -")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.price_label.setFont(font)
        self.time_label = QLabel("")

        price_row = QHBoxLayout()
        price_row.addWidget(self.price_label)
        price_row.addStretch(1)
        price_row.addWidget(self.time_label)

        # 탭: 지수요약 / 일별시세 / 구성종목
        self.summary_table = make_table()
        self.daily_table = make_table()
        self.stock_table = make_table()
        self.stock_table.cellDoubleClicked.connect(self.open_stock_page)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("종목명 또는 종목코드 검색")
        self.search_edit.textChanged.connect(self.filter_stocks)
        self.stock_count_label = QLabel("")

        stock_top = QHBoxLayout()
        stock_top.addWidget(self.search_edit, 1)
        stock_top.addWidget(self.stock_count_label)
        stock_tab = QWidget()
        stock_layout = QVBoxLayout(stock_tab)
        stock_layout.setContentsMargins(0, 6, 0, 0)
        stock_layout.addLayout(stock_top)
        stock_layout.addWidget(self.stock_table)
        stock_layout.addWidget(QLabel("※ 열 제목을 클릭하면 정렬, 종목을 더블클릭하면 네이버 증권 페이지가 열립니다."))

        self.tabs = QTabWidget()
        self.tabs.addTab(self.summary_table, "지수요약")
        self.tabs.addTab(self.daily_table, "일별시세")
        self.tabs.addTab(stock_tab, "구성종목")

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addLayout(price_row)
        layout.addWidget(self.tabs, 1)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("'데이터 조회'를 눌러 시작하세요.")

    # --- 동작 ---
    def fetch(self):
        if self.worker and self.worker.isRunning():
            return
        self.fetch_btn.setEnabled(False)
        self.excel_btn.setEnabled(False)
        self.worker = FetchWorker(self.days_spin.value())
        self.worker.status.connect(self.status_bar.showMessage)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_done(self, summary, daily, stocks):
        self.summary, self.daily, self.stocks = summary, daily, stocks

        price = summary.get("현재가")
        diff = summary.get("전일비")
        rate = summary.get("등락률(%)")
        if isinstance(price, (int, float)) and isinstance(diff, (int, float)):
            arrow = "▲" if diff > 0 else "▼" if diff < 0 else "-"
            color = "#D32F2F" if diff > 0 else "#1565C0" if diff < 0 else "#000000"
            self.price_label.setText(
                f"코스피 200  {price:,.2f}  "
                f"<span style='color:{color}'>{arrow} {abs(diff):,.2f} ({rate}%)</span>"
            )
        self.time_label.setText(f"기준: {summary.get('기준 시각', '')}  ({summary.get('장 상태', '')})")

        fill_table(self.summary_table, [{"항목": k, "값": v} for k, v in summary.items()])
        fill_table(self.daily_table, daily)
        fill_table(self.stock_table, stocks)
        self.filter_stocks(self.search_edit.text())

        self.fetch_btn.setEnabled(True)
        self.excel_btn.setEnabled(True)
        self.status_bar.showMessage(
            f"조회 완료 ({datetime.now():%H:%M:%S}) - 일별 시세 {len(daily)}일, 구성 종목 {len(stocks)}개"
        )

    def on_failed(self, message):
        self.fetch_btn.setEnabled(True)
        self.excel_btn.setEnabled(bool(self.stocks))
        self.status_bar.showMessage("조회 실패")
        QMessageBox.critical(self, "오류", f"데이터를 가져오지 못했습니다.\n{message}")

    def filter_stocks(self, text):
        text = text.strip().lower()
        visible = 0
        for r in range(self.stock_table.rowCount()):
            code = self.stock_table.item(r, 1)
            name = self.stock_table.item(r, 2)
            match = not text or any(
                item is not None and text in item.text().lower() for item in (code, name)
            )
            self.stock_table.setRowHidden(r, not match)
            visible += match
        self.stock_count_label.setText(f"{visible} / {self.stock_table.rowCount()} 종목")

    def open_stock_page(self, row, _col):  # cellDoubleClicked 시그널이 열 번호도 넘겨줌
        code_item = self.stock_table.item(row, 1)
        if code_item is not None:
            QDesktopServices.openUrl(QUrl(STOCK_PAGE_URL.format(code=code_item.text())))

    def save(self):
        default = f"kospi200_{datetime.now():%Y%m%d_%H%M}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "엑셀 저장", default, "엑셀 파일 (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            save_excel(self.summary, self.daily, self.stocks, path)
            self.status_bar.showMessage(f"엑셀 저장 완료: {path}")
        except PermissionError:
            QMessageBox.critical(self, "오류", "파일이 엑셀에서 열려 있으면 저장할 수 없습니다. 파일을 닫고 다시 시도하세요.")
        except OSError as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.wait(5000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
