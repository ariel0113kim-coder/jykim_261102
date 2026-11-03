"""
네이버 뉴스 검색 결과에서 기사 본문을 크롤링하는 GUI 앱 (PyQt6)
필요 패키지: pip install requests beautifulsoup4 PyQt6 openpyxl
"""
import csv
import re
import sys
import time

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet
from PyQt6.QtCore import QThread, QUrl, pyqtSignal, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

# ---------------------------------------------------------------------------
# 크롤링 로직
# ---------------------------------------------------------------------------
SEARCH_URL = "https://search.naver.com/search.naver"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.naver.com/",
}
ARTICLE_RE = re.compile(r"^https://n\.news\.naver\.com/(mnews/)?article/\d+/\d+")
FIELDS = ["title", "press", "date", "url", "body"]
EXCEL_HEADERS = ["제목", "언론사", "날짜", "URL", "본문"]
EXCEL_WIDTHS = [50, 14, 20, 45, 100]
EXCEL_CELL_LIMIT = 32767  # 엑셀 셀 하나에 들어가는 최대 글자 수


def save_to_excel(articles, path, sheet_title="뉴스"):
    """기사 목록을 서식이 적용된 엑셀(.xlsx) 파일로 저장한다."""
    wb = Workbook()
    ws = wb.active
    if not isinstance(ws, Worksheet):  # 새 Workbook에는 항상 기본 시트가 있음 (타입 검사용)
        ws = wb.create_sheet()
    ws.title = sheet_title[:31] or "뉴스"  # 시트 이름은 최대 31자

    ws.append(EXCEL_HEADERS)
    header_fill = PatternFill("solid", fgColor="DDEBF7")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for art in articles:
        # 엑셀에서 허용하지 않는 제어문자 제거 + 셀 길이 제한
        row = [ILLEGAL_CHARACTERS_RE.sub("", art[k])[:EXCEL_CELL_LIMIT] for k in FIELDS]
        ws.append(row)
        r = ws.max_row
        url_cell = ws.cell(row=r, column=4)
        url_cell.hyperlink = art["url"]
        url_cell.font = Font(color="0563C1", underline="single")
        for c in range(1, 6):
            ws.cell(row=r, column=c).alignment = Alignment(vertical="top", wrap_text=(c == 5))

    for i, width in enumerate(EXCEL_WIDTHS):
        ws.column_dimensions[chr(ord("A") + i)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    wb.save(path)


def get_soup(url, params=None):
    res = requests.get(url, params=params, headers=HEADERS, timeout=10)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")


def get_news_links(query, page):
    """검색 결과 한 페이지에서 '네이버뉴스' 기사 링크를 수집한다."""
    params = {
        "where": "news",          # 통합검색(nexearch) 대신 뉴스 탭 사용
        "query": query,
        "sm": "tab_pge",
        "start": page * 10 + 1,   # 1, 11, 21, ...
    }
    soup = get_soup(SEARCH_URL, params)
    links = []
    for a in soup.select('a[href^="https://n.news.naver.com/"]'):
        href = str(a.get("href", "")).split("?")[0]
        if ARTICLE_RE.match(href) and href not in links:
            links.append(href)
    return links


def text_of(soup, *selectors):
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return el.get_text(" ", strip=True)
    return ""


def parse_article(url):
    """네이버뉴스 기사 페이지에서 제목/언론사/날짜/본문을 추출한다."""
    soup = get_soup(url)

    title = text_of(soup, "#title_area", "h2.media_end_head_headline")

    press_meta = soup.select_one('meta[property="og:article:author"]')
    press = str(press_meta.get("content", "")).split("|")[0].strip() if press_meta else ""

    date_el = soup.select_one("span.media_end_head_info_datestamp_time")
    date = date_el.get("data-date-time", date_el.get_text(strip=True)) if date_el else ""

    body_el = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
    body = ""
    if body_el:
        # 사진 설명, 스크립트 등 불필요한 요소 제거
        for tag in body_el.select("script, style, .img_desc, .end_photo_org em"):
            tag.decompose()
        body = body_el.get_text("\n", strip=True)

    return {"title": title, "press": press, "date": date, "url": url, "body": body}


# ---------------------------------------------------------------------------
# 백그라운드 작업 스레드 (크롤링 중에도 화면이 멈추지 않도록)
# ---------------------------------------------------------------------------
class CrawlWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int)        # 현재, 전체
    article_found = pyqtSignal(dict)
    finished_ok = pyqtSignal(int)          # 수집 건수

    def __init__(self, query, pages):
        super().__init__()
        self.query = query
        self.pages = pages
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        links = []
        for page in range(self.pages):
            if self._stop:
                break
            try:
                for link in get_news_links(self.query, page):
                    if link not in links:
                        links.append(link)
                self.log.emit(f"검색 {page + 1}페이지 완료 (누적 링크 {len(links)}건)")
            except Exception as e:
                self.log.emit(f"검색 {page + 1}페이지 실패: {e}")
            time.sleep(1)

        count = 0
        total = len(links)
        for i, url in enumerate(links, 1):
            if self._stop:
                self.log.emit("사용자가 중지했습니다.")
                break
            try:
                art = parse_article(url)
                self.article_found.emit(art)
                count += 1
            except Exception as e:
                self.log.emit(f"실패: {url} ({e})")
            self.progress.emit(i, total)
            time.sleep(0.5)

        self.finished_ok.emit(count)


# ---------------------------------------------------------------------------
# 메인 화면
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 뉴스 크롤러")
        self.resize(1100, 720)
        self.articles = []
        self.worker = None

        # 상단: 검색어 / 페이지 수 / 버튼
        self.query_edit = QLineEdit("전장")
        self.query_edit.setPlaceholderText("검색어 입력")
        self.query_edit.returnPressed.connect(self.start_crawl)

        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 20)
        self.page_spin.setValue(2)
        self.page_spin.setSuffix(" 페이지")

        self.start_btn = QPushButton("크롤링 시작")
        self.start_btn.clicked.connect(self.start_crawl)
        self.stop_btn = QPushButton("중지")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_crawl)
        self.save_btn = QPushButton("CSV 저장")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_csv)
        self.excel_btn = QPushButton("엑셀 저장")
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.save_excel)

        top = QHBoxLayout()
        top.addWidget(QLabel("검색어"))
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.page_spin)
        top.addWidget(self.start_btn)
        top.addWidget(self.stop_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.excel_btn)

        # 가운데: 기사 목록 + 본문
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["제목", "언론사", "날짜"])
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.show_body)
        self.table.cellDoubleClicked.connect(self.open_in_browser)

        self.body_view = QTextEdit()
        self.body_view.setReadOnly(True)
        self.body_view.setPlaceholderText("기사를 선택하면 본문이 표시됩니다. (더블클릭: 브라우저에서 열기)")

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.body_view)
        splitter.setSizes([400, 300])

        # 하단: 진행률 + 로그
        self.progress_bar = QProgressBar()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(100)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_view)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    # --- 동작 ---
    def start_crawl(self):
        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "알림", "검색어를 입력하세요.")
            return
        if self.worker and self.worker.isRunning():
            return

        self.articles.clear()
        self.table.setRowCount(0)
        self.body_view.clear()
        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.set_running(True)
        self.append_log(f"'{query}' 검색 시작 ({self.page_spin.value()}페이지)")

        self.worker = CrawlWorker(query, self.page_spin.value())
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.update_progress)
        self.worker.article_found.connect(self.add_article)
        self.worker.finished_ok.connect(self.crawl_finished)
        self.worker.start()

    def stop_crawl(self):
        if self.worker:
            self.worker.stop()
            self.stop_btn.setEnabled(False)
            self.append_log("중지 요청 중...")

    def set_running(self, running):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.query_edit.setEnabled(not running)
        self.page_spin.setEnabled(not running)
        can_save = not running and bool(self.articles)
        self.save_btn.setEnabled(can_save)
        self.excel_btn.setEnabled(can_save)

    def append_log(self, msg):
        self.log_view.append(msg)

    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def add_article(self, art):
        self.articles.append(art)
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, key in enumerate(["title", "press", "date"]):
            self.table.setItem(row, col, QTableWidgetItem(art[key]))

    def crawl_finished(self, count):
        self.append_log(f"완료: 기사 {count}건 수집")
        self.set_running(False)

    def show_body(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.articles):
            art = self.articles[row]
            self.body_view.setPlainText(
                f"{art['title']}\n{art['press']} | {art['date']}\n{art['url']}\n\n{art['body']}"
            )

    def open_in_browser(self, row, _col):  # noqa: ARG002 (cellDoubleClicked 시그널이 열 번호도 넘겨줌)
        if 0 <= row < len(self.articles):
            QDesktopServices.openUrl(QUrl(self.articles[row]["url"]))

    def save_csv(self):
        default = f"naver_news_{self.query_edit.text().strip()}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", default, "CSV 파일 (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(self.articles)
            self.append_log(f"저장 완료: {path}")
        except OSError as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")

    def save_excel(self):
        query = self.query_edit.text().strip()
        default = f"naver_news_{query}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "엑셀 저장", default, "엑셀 파일 (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            save_to_excel(self.articles, path, sheet_title=query)
            self.append_log(f"엑셀 저장 완료: {path}")
        except PermissionError:
            QMessageBox.critical(self, "오류", "파일이 엑셀에서 열려 있으면 저장할 수 없습니다. 파일을 닫고 다시 시도하세요.")
        except OSError as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
