"""
GUI·엑셀 저장용 분석 파사드 – 기존 분석 모듈(birth_analysis / integrated_analysis / plot_births)을 묶는다
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 그림은 GUI 쪽에서 FigureCanvasQTAgg로 직접 붙인다
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

import birth_analysis as ba
import integrated_analysis as ia
import plot_births as pb

BIRTHS_FILE_NAME = ba.DEFAULT_XLSX.name
DEATHS_FILE_NAME = ia.DEATHS_XLSX.name

# 정제 데이터 시트에 내보낼 컬럼 (영문 -> 한글)
EXPORT_COLUMNS = {
    "births": "출생아수(명)",
    "deaths": "사망자수(명)",
    "natural_increase": "자연증가(명)",
    "births_yoy": "출생 전년대비(명)",
    "births_yoy_pct": "출생 전년대비(%)",
    "births_ma5": "출생 5년이동평균(명)",
    "birth_death_ratio": "출생/사망 비율",
    "crude_birth_rate": "조출생률(‰)",
    "crude_death_rate_filled": "조사망률(‰)",
    "natural_increase_rate": "자연증가율(‰)",
    "tfr": "합계출산율(명)",
    "sex_ratio": "출생성비",
    "life_exp": "기대수명(세)",
    "life_exp_male": "기대수명-남(세)",
    "life_exp_female": "기대수명-여(세)",
    "life_exp_gap": "기대수명 남녀격차(년)",
    "population_est": "추정인구(명)",
    "deaths_source": "사망자수 출처",
    "is_preliminary": "잠정치 여부",
}


@dataclass
class AnalysisResult:
    df: pd.DataFrame
    clean_log: list[str]
    report: str
    summary: dict[str, str]
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    has_deaths: bool = False


def run(births_path: str | Path, deaths_path: str | Path | None = None) -> AnalysisResult:
    b_raw, b_meta = ba.load_raw(Path(births_path))
    births, b_log = ba.clean(b_raw)
    log = ["[출생 데이터]"] + b_log
    report = [f"출처: {b_meta.get('통계표명', '')} ({b_meta.get('통계표ID', '')}, 다운로드 {b_meta.get('자료다운일자', '')})"]
    report += ba.analyze(births)

    df, has_deaths = births, False
    if deaths_path:
        d_raw, d_meta = ba.load_raw(Path(deaths_path))
        deaths, d_log = ia.clean_deaths(d_raw)
        df, m_log = ia.merge(births, deaths)
        log += ["", "[사망 데이터]"] + d_log + ["", "[병합 및 교차검증]"] + m_log
        report += ["", "", "#" * 72, f"# 통합 분석 – {d_meta.get('통계표명', '')} ({d_meta.get('통계표ID', '')}, "
                   f"다운로드 {d_meta.get('자료다운일자', '')})", "#" * 72]
        report += ia.analyze(df)
        has_deaths = True

    res = AnalysisResult(df=df, clean_log=log, report="\n".join(report), summary={}, has_deaths=has_deaths)
    res.summary = build_summary(res)
    res.tables = build_tables(res)
    return res


def build_summary(res: AnalysisResult) -> dict[str, str]:
    df = res.df
    y0, y1 = int(df.index.min()), int(df.index.max())
    b = df["births"]
    prelim = df.index[df["is_preliminary"].fillna(False).astype(bool)].tolist()
    s = {
        "분석 기간": f"{y0}~{y1}년 ({len(df)}개년)" + (f", {', '.join(map(str, prelim))}년 잠정치" if prelim else ""),
        "출생아수 변화": f"{b[y0]:,}명 → {b[y1]:,}명 ({(b[y1] / b[y0] - 1) * 100:+.1f}%)",
        "최다 / 최소 출생": f"{b.idxmax()}년 {b.max():,}명 / {b.idxmin()}년 {b.min():,}명",
        "합계출산율": f"{df.at[y0, 'tfr']:.2f} → {df.at[y1, 'tfr']:.2f}명 (최저 {df['tfr'].idxmin()}년 {df['tfr'].min():.3f})",
        "인구대체수준(2.1) 붕괴": f"{ba.first_year(df, df['tfr'] < ba.REPLACEMENT_TFR)}년",
        "자연감소 시작": f"{ba.first_year(df, df['natural_increase'] < 0)}년",
        "출생성비 최고": f"{df['sex_ratio'].idxmax()}년 {df['sex_ratio'].max():.1f}",
    }
    if res.has_deaths:
        le = df["life_exp"].dropna()
        ex = ia.excess_deaths(df)
        s.update({
            "사망자수 변화": f"{df.at[y0, 'deaths']:,}명 → {df.at[y1, 'deaths']:,}명",
            "출생/사망 비율": f"{df.at[y0, 'birth_death_ratio']:.2f} → {df.at[y1, 'birth_death_ratio']:.2f}",
            "기대수명": f"{le.iloc[0]:.1f}세 → {le.iloc[-1]:.1f}세 ({le.index[-1]}년, 최고 {le.idxmax()}년 {le.max():.1f}세)",
            "코로나19 초과사망 최대": f"{ex['excess'].idxmax()}년 +{ex['excess'].max():,.0f}명 ({ex['excess_pct'].max():+.1f}%)",
        })
    return s


def build_tables(res: AnalysisResult) -> dict[str, pd.DataFrame]:
    df = res.df
    tables: dict[str, pd.DataFrame] = {}

    cols = [c for c in EXPORT_COLUMNS if c in df.columns]
    data = df[cols].rename(columns=EXPORT_COLUMNS)
    data.index.name = "연도"
    tables["정제데이터"] = data

    num = [c for c in ["births", "deaths", "natural_increase", "tfr", "crude_birth_rate",
                       "crude_death_rate_filled", "sex_ratio", "life_exp"] if c in df.columns]
    desc = df[num].describe().T
    desc.index = [EXPORT_COLUMNS[c] for c in desc.index]
    desc.columns = ["개수", "평균", "표준편차", "최소", "25%", "중앙값", "75%", "최대"]
    tables["기술통계"] = desc

    agg = {"연평균출생아수": ("births", "mean"), "누적출생아수": ("births", "sum"),
           "누적자연증가": ("natural_increase", "sum"), "평균합계출산율": ("tfr", "mean"),
           "평균출생성비": ("sex_ratio", "mean")}
    if res.has_deaths:
        agg.update({"연평균사망자수": ("deaths", "mean"), "평균기대수명": ("life_exp", "mean")})
    agg["연수"] = ("births", "size")
    dec = df.groupby("decade").agg(**agg)
    dec.index.name = "연대"
    tables["연대별"] = dec

    yoy = df[["births", "births_yoy", "births_yoy_pct"]].dropna()
    yoy.columns = ["출생아수(명)", "전년대비(명)", "전년대비(%)"]
    yoy.index.name = "연도"
    tables["전년대비증감"] = yoy

    b, tfr = df["births"], df["tfr"]
    milestones = {
        "합계출산율 2.1(인구대체수준) 미만": ba.first_year(df, tfr < ba.REPLACEMENT_TFR),
        "합계출산율 1.3(초저출산) 미만": ba.first_year(df, tfr < ba.LOWEST_LOW_TFR),
        "합계출산율 1.0 미만": ba.first_year(df, tfr < 1.0),
        "출생아수 70만 명 미만": ba.first_year(df, b < 700_000),
        "출생아수 50만 명 미만": ba.first_year(df, b < 500_000),
        "출생아수 30만 명 미만": ba.first_year(df, b < 300_000),
        "자연감소(사망 > 출생)": ba.first_year(df, df["natural_increase"] < 0),
    }
    tables["주요임계점"] = pd.DataFrame({"최초 연도": milestones}).rename_axis("임계점")

    if res.has_deaths:
        ex = ia.excess_deaths(df)
        ex.columns = ["실제 사망자수", "추세 기대 사망자수", "초과사망", "초과사망(%)"]
        ex.index.name = "연도"
        tables["초과사망"] = ex

    corr = df[num].corr()
    corr.index = corr.columns = [EXPORT_COLUMNS[c] for c in num]
    tables["상관관계"] = corr
    return tables


def build_charts(res: AnalysisResult, start: int, end: int) -> dict[str, Figure]:
    charts = {
        "출생아수 추이": pb.build_births_chart(res.df, start, end),
        "출생 분석 대시보드": ba.build_dashboard(res.df),
    }
    if res.has_deaths:
        charts["출생·사망·기대수명 통합"] = ia.build_integrated(res.df)
    for fig in charts.values():
        plt.close(fig)  # pyplot 관리 목록에서만 제거 (Figure 객체는 계속 사용)
    return charts


def figure_png(fig: Figure, dpi: int = 110) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=fig.get_facecolor())
    return buf.getvalue()


def export_excel(res: AnalysisResult, charts: dict[str, Figure], path: str | Path) -> None:
    from openpyxl.chart import BarChart, LineChart, Reference
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def style_sheet(ws) -> None:
        for cell in ws[1]:
            cell.fill, cell.font = header_fill, header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
            for cell in row:
                cell.border = border
                if cell.row > 1 and isinstance(cell.value, float):
                    header = str(ws.cell(row=1, column=cell.column).value)
                    is_count = "(명)" in header and "출산율" not in header
                    cell.number_format = "#,##0" if is_count or abs(cell.value) >= 1000 else "#,##0.00"
                elif cell.row > 1 and isinstance(cell.value, int) and not isinstance(cell.value, bool):
                    cell.number_format = "0" if cell.column == 1 else "#,##0"
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 4, 10), 40)
        ws.freeze_panes = "B2"

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        summary = pd.DataFrame(list(res.summary.items()), columns=["항목", "값"])
        summary.to_excel(xw, sheet_name="요약", index=False)
        pd.DataFrame({"데이터 클렌징 로그": res.clean_log}).to_excel(
            xw, sheet_name="요약", index=False, startrow=len(summary) + 2)

        for name, table in res.tables.items():
            table.to_excel(xw, sheet_name=name)

        pd.DataFrame({"분석 리포트": res.report.splitlines()}).to_excel(xw, sheet_name="리포트", index=False)

        wb = xw.book
        for ws in wb.worksheets:
            style_sheet(ws)
        ws = wb["요약"]
        ws.column_dimensions["A"].width = 26
        ws.column_dimensions["B"].width = 70
        log_header = ws.cell(row=len(summary) + 3, column=1)
        log_header.fill, log_header.font = header_fill, header_font
        rep = wb["리포트"]
        rep.column_dimensions["A"].width = 130
        for row in rep.iter_rows(min_row=2):
            row[0].font = Font(name="맑은 고딕")
            row[0].border = Border()

        # 엑셀 네이티브 차트 (데이터와 연결되어 엑셀에서 바로 편집 가능)
        data_ws = wb["정제데이터"]
        n = data_ws.max_row
        headers = [c.value for c in data_ws[1]]
        ws_native = wb.create_sheet("엑셀차트")
        cats = Reference(data_ws, min_col=1, min_row=2, max_row=n)

        bar = BarChart()
        bar.title, bar.y_axis.title = "연도별 출생아수", "명"
        bar.add_data(Reference(data_ws, min_col=headers.index(EXPORT_COLUMNS["births"]) + 1, min_row=1, max_row=n),
                     titles_from_data=True)
        bar.set_categories(cats)
        bar.gapWidth, bar.width, bar.height = 40, 30, 11
        bar.legend = None
        ws_native.add_chart(bar, "A1")

        line = LineChart()
        line.title, line.y_axis.title = "합계출산율", "명"
        line.add_data(Reference(data_ws, min_col=headers.index(EXPORT_COLUMNS["tfr"]) + 1, min_row=1, max_row=n),
                      titles_from_data=True)
        line.set_categories(cats)
        line.width, line.height = 30, 8
        line.legend = None
        ws_native.add_chart(line, "A24")

        if res.has_deaths:
            bd = LineChart()
            bd.title, bd.y_axis.title = "출생아수 vs 사망자수", "명"
            for key in ("births", "deaths"):
                col = headers.index(EXPORT_COLUMNS[key]) + 1
                bd.add_data(Reference(data_ws, min_col=col, min_row=1, max_row=n), titles_from_data=True)
            bd.set_categories(cats)
            bd.width, bd.height = 30, 11
            ws_native.add_chart(bd, "A41")

        # 분석 그래프 이미지 시트
        ws_chart = wb.create_sheet("그래프")
        row = 1
        for title, fig in charts.items():
            ws_chart.cell(row=row, column=1, value=title).font = Font(bold=True, size=13)
            img = XLImage(io.BytesIO(figure_png(fig, dpi=90)))
            ws_chart.add_image(img, f"A{row + 1}")
            row += int(img.height / 20) + 4
