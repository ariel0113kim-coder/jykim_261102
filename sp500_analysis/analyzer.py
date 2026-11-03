"""
S&P 500 데이터 정제 / 분석 / 차트 생성 핵심 로직.
GUI(app.py)와 콘솔(sp500_analysis.py)이 함께 사용한다.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # GUI에서는 FigureCanvasQTAgg로 직접 그리므로 pyplot 백엔드 불필요

import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib import rcParams
from matplotlib.figure import Figure

rcParams["font.family"] = "Malgun Gothic"
rcParams["axes.unicode_minus"] = False

COLUMN_MAP = {
    "날짜": "Date", "종가": "Close", "시가": "Open", "고가": "High",
    "저가": "Low", "거래량": "Volume", "변동 %": "ChangePct",
}
PRICE_COLS = ["Close", "Open", "High", "Low"]
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


@dataclass
class AnalysisResult:
    df: pd.DataFrame                       # 정제 + 파생 컬럼 포함 데이터
    clean_log: list[str]                   # 클렌징 과정 로그
    summary: dict[str, str]                # 핵심 지표 (항목 -> 값)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)  # 시트/탭 이름 -> 표


# ----------------------------------------------------------------------
# 1. 로드 & 클렌징
# ----------------------------------------------------------------------
def load_and_clean(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    log: list[str] = []
    raw = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    log.append(f"원본: {raw.shape[0]:,}행 x {raw.shape[1]}열")

    missing_cols = [c for c in COLUMN_MAP if c not in raw.columns]
    if missing_cols:
        raise ValueError(f"필수 컬럼이 없습니다: {missing_cols}\n(필요 컬럼: {list(COLUMN_MAP)})")

    df = raw.rename(columns=COLUMN_MAP)[list(COLUMN_MAP.values())]

    # 날짜: "2019- 11- 14" -> 공백 제거 후 datetime
    df["Date"] = pd.to_datetime(df["Date"].str.replace(" ", "", regex=False),
                                format="%Y-%m-%d", errors="coerce")
    # 가격: 쉼표 제거
    for c in PRICE_COLS:
        df[c] = pd.to_numeric(df[c].str.replace(",", "", regex=False), errors="coerce")
    # 변동률: % 제거
    df["ChangePct"] = pd.to_numeric(
        df["ChangePct"].str.replace("%", "", regex=False).str.replace(",", "", regex=False),
        errors="coerce")
    # 거래량: 전부 비어 있으면 제거
    vol = pd.to_numeric(df["Volume"].str.replace(",", "", regex=False), errors="coerce")
    if vol.isna().all():
        df = df.drop(columns="Volume")
        log.append("거래량 컬럼이 전부 비어 있어 제거")
    else:
        df["Volume"] = vol

    before = len(df)
    df = df.dropna(subset=["Date", "Close"])
    log.append(f"날짜/종가 결측 제거: {before - len(df)}행")

    before = len(df)
    df = df.drop_duplicates(subset="Date", keep="first")
    log.append(f"중복 날짜 제거: {before - len(df)}행")

    df = df.sort_values("Date").set_index("Date")

    bad_nonpos = (df[PRICE_COLS] <= 0).any(axis=1)
    oc_max = df[["Open", "Close"]].max(axis=1)
    oc_min = df[["Open", "Close"]].min(axis=1)
    bad_range = (oc_max > df["High"]) | (oc_min < df["Low"])
    log.append(f"가격 0 이하 제거: {int(bad_nonpos.sum())}행")
    if bad_range.any():
        days = ", ".join(d.strftime("%Y-%m-%d") for d in pd.DatetimeIndex(df.index[bad_range])[:5])
        log.append(f"시가·종가가 고저 범위 밖 → 고가/저가 보정: {int(bad_range.sum())}행 ({days})")
    df["High"] = pd.concat([df["High"], oc_max], axis=1).max(axis=1)
    df["Low"] = pd.concat([df["Low"], oc_min], axis=1).min(axis=1)
    df = df[~bad_nonpos]

    df["Return"] = df["Close"].pct_change() * 100
    mismatch = int(((df["Return"] - df["ChangePct"]).abs() > 0.05).sum())
    log.append(f"재계산 수익률과 원본 '변동 %' 불일치(>0.05%p): {mismatch}행")
    df["ChangePct"] = df["ChangePct"].fillna(df["Return"])

    idx = pd.DatetimeIndex(df.index)
    log.append(f"정제 후: {len(df):,}행  기간 {idx.min():%Y-%m-%d} ~ {idx.max():%Y-%m-%d}")
    return df, log


# ----------------------------------------------------------------------
# 2. 분석
# ----------------------------------------------------------------------
def analyze(df: pd.DataFrame, clean_log: list[str]) -> AnalysisResult:
    df = df.copy()
    dates = pd.DatetimeIndex(df.index)
    close = df["Close"].to_numpy(dtype=float)

    # 파생 지표
    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    df["Drawdown"] = (df["Close"] / df["Close"].cummax() - 1) * 100
    df["Range%"] = (df["High"] - df["Low"]) / df["Open"] * 100
    df["Vol21"] = df["Return"].rolling(21).std() * np.sqrt(252)

    # 요약
    years = (dates[-1] - dates[0]).days / 365.25
    total = close[-1] / close[0] - 1
    cagr = (close[-1] / close[0]) ** (1 / years) - 1 if years > 0 else np.nan
    mdd_pos = int(np.argmin(df["Drawdown"].to_numpy(dtype=float)))
    peak_pos = int(np.argmax(close[: mdd_pos + 1]))
    after = df["Close"].iloc[mdd_pos:]
    rec = pd.DatetimeIndex(after[after >= close[peak_pos]].index)
    ret = df["Return"]
    summary = {
        "분석 기간": f"{dates[0]:%Y-%m-%d} ~ {dates[-1]:%Y-%m-%d} ({len(df):,}거래일)",
        "시작 종가 → 마지막 종가": f"{close[0]:,.2f} → {close[-1]:,.2f}",
        "누적 수익률": f"{total * 100:,.2f}%",
        "연평균 성장률(CAGR)": f"{cagr * 100:.2f}%",
        "연환산 변동성": f"{ret.std() * np.sqrt(252):.2f}%",
        "최대 낙폭(MDD)": f"{df['Drawdown'].iloc[mdd_pos]:.2f}% "
                       f"({dates[peak_pos]:%Y-%m-%d} → {dates[mdd_pos]:%Y-%m-%d})",
        "MDD 고점 회복일": f"{rec[0]:%Y-%m-%d}" if len(rec) else "미회복",
        "최고 종가": f"{df['Close'].max():,.2f} ({pd.Timestamp(dates[int(np.argmax(close))]):%Y-%m-%d})",
        "최저 종가": f"{df['Close'].min():,.2f} ({pd.Timestamp(dates[int(np.argmin(close))]):%Y-%m-%d})",
        "상승일 비율": f"{(ret > 0).mean() * 100:.1f}%",
        "평균 일중 변동폭": f"{df['Range%'].mean():.2f}%",
        "수익률 왜도 / 첨도": f"{ret.skew():.3f} / {ret.kurt():.3f}",
    }

    tables: dict[str, pd.DataFrame] = {}

    # 기술 통계
    desc = df[PRICE_COLS + ["Return"]].describe()
    desc.columns = ["종가", "시가", "고가", "저가", "일수익률%"]
    tables["기술통계"] = desc

    # 연도별
    yearly = df.groupby(dates.year).agg(
        시작가=("Close", "first"), 종가=("Close", "last"),
        최고=("High", "max"), 최저=("Low", "min"),
        거래일=("Close", "size"), 일변동성=("Return", "std"),
    )
    yearly["연수익률%"] = (yearly["종가"] / yearly["종가"].shift(1) - 1) * 100
    yearly.iloc[0, yearly.columns.get_loc("연수익률%")] = (yearly["종가"].iloc[0] / yearly["시작가"].iloc[0] - 1) * 100
    yearly["연환산변동성%"] = yearly["일변동성"] * np.sqrt(252)
    yearly = yearly.drop(columns="일변동성")
    yearly.index.name = "연도"
    tables["연도별"] = yearly

    # 월별 수익률 (히트맵용) + 월 계절성
    monthly_ret = df["Close"].resample("ME").last().pct_change() * 100
    month_idx = pd.DatetimeIndex(monthly_ret.index)
    heat = pd.DataFrame({"연도": month_idx.year, "월": month_idx.month,
                         "r": monthly_ret.to_numpy()}).pivot_table(index="연도", columns="월", values="r")
    heat.columns = [f"{m}월" for m in heat.columns]
    tables["월별수익률"] = heat

    by_month = monthly_ret.groupby(month_idx.month).agg(
        ["mean", "median", lambda s: (s > 0).mean() * 100, "count"])
    by_month.columns = ["평균%", "중앙값%", "상승확률%", "표본수"]
    by_month.index = [f"{m}월" for m in by_month.index]
    by_month.index.name = "월"
    tables["월계절성"] = by_month

    by_wd = df.groupby(dates.dayofweek)["Return"].agg(["mean", "std", "count"])
    by_wd.index = [WEEKDAY_KR[i] for i in by_wd.index]
    by_wd.columns = ["평균%", "표준편차%", "일수"]
    by_wd.index.name = "요일"
    tables["요일별"] = by_wd

    # 등락 TOP 10
    top = df.nlargest(10, "Return")[["Close", "Return"]].reset_index()
    bottom = df.nsmallest(10, "Return")[["Close", "Return"]].reset_index()
    top.columns = bottom.columns = ["날짜", "종가", "수익률%"]
    updown = pd.concat([top.add_prefix("상승_"), bottom.add_prefix("하락_")], axis=1)
    updown.index = range(1, len(updown) + 1)
    updown.index.name = "순위"
    tables["등락TOP10"] = updown

    # 골든 / 데드 크로스
    diff = (df["MA50"] - df["MA200"]).apply(np.sign)
    cross = diff.diff().dropna()
    cross = cross[cross != 0]
    crosses = pd.DataFrame({
        "날짜": pd.DatetimeIndex(cross.index),
        "구분": np.where(cross.to_numpy() > 0, "골든크로스", "데드크로스"),
        "종가": df.loc[cross.index, "Close"].to_numpy(),
    })
    crosses.index = range(1, len(crosses) + 1)
    crosses.index.name = "No"
    tables["골든데드크로스"] = crosses
    summary["골든 / 데드 크로스"] = (f"{(crosses['구분'] == '골든크로스').sum()}회 / "
                                f"{(crosses['구분'] == '데드크로스').sum()}회")

    return AnalysisResult(df=df, clean_log=clean_log, summary=summary, tables=tables)


# ----------------------------------------------------------------------
# 3. 차트 (pyplot 미사용: Figure 객체를 반환해 GUI에 바로 임베드)
# ----------------------------------------------------------------------
def _fmt_thousands(ax) -> None:
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))


def chart_close(res: AnalysisResult, start: str, end: str) -> Figure:
    """[요청] 기간 지정 종가 라인그래프"""
    period = res.df.loc[start:end, "Close"]
    fig = Figure(figsize=(12, 5.5), layout="tight")
    ax = fig.add_subplot()
    if period.empty:
        ax.text(0.5, 0.5, "선택한 기간에 데이터가 없습니다.", ha="center", va="center", transform=ax.transAxes)
        return fig
    p_idx = pd.DatetimeIndex(period.index)
    ax.plot(p_idx, period.to_numpy(dtype=float), color="#1f77b4", lw=1.2, label="종가")
    s, e = p_idx[0], p_idx[-1]
    ax.set_title(f"S&P 500 종가 추이 ({s:%Y년 %m월} ~ {e:%Y년 %m월})", fontsize=14, fontweight="bold")
    ax.set_xlabel("날짜")
    ax.set_ylabel("종가 (포인트)")
    _fmt_thousands(ax)
    ax.grid(alpha=0.3)

    events = [("2002-10-09", "닷컴버블 저점"), ("2009-03-09", "금융위기 저점")]
    shown = False
    for date, text in events:
        d = pd.Timestamp(date)
        if s <= d <= e:
            pos = int(p_idx.searchsorted(d))
            ax.annotate(text, xy=(mdates.date2num(p_idx[pos]), float(period.iloc[pos])),
                        xytext=(0, -30), textcoords="offset points", ha="center", va="top",
                        arrowprops=dict(arrowstyle="->", color="gray"), fontsize=10)
            shown = True
    if shown:
        lo, hi = float(period.min()), float(period.max())
        ax.set_ylim(bottom=lo - (hi - lo) * 0.18)
    ax.legend(loc="upper left")
    return fig


def chart_ma_drawdown(res: AnalysisResult) -> Figure:
    df = res.df
    idx = pd.DatetimeIndex(df.index)
    fig = Figure(figsize=(12, 7), layout="tight")
    a1, a2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    a1.plot(idx, df["Close"].to_numpy(dtype=float), lw=1, label="종가")
    a1.plot(idx, df["MA50"].to_numpy(dtype=float), lw=1, label="50일 이동평균")
    a1.plot(idx, df["MA200"].to_numpy(dtype=float), lw=1, label="200일 이동평균")
    a1.set_title("종가와 이동평균", fontsize=13)
    _fmt_thousands(a1)
    a1.legend(); a1.grid(alpha=0.3)
    a2.fill_between(idx, df["Drawdown"].to_numpy(dtype=float), 0, color="#d62728", alpha=0.4)
    a2.set_title("고점 대비 낙폭(%)"); a2.grid(alpha=0.3)
    return fig


def chart_yearly(res: AnalysisResult) -> Figure:
    y = res.tables["연도별"]
    fig = Figure(figsize=(12, 5), layout="tight")
    ax = fig.add_subplot()
    vals = y["연수익률%"].to_numpy(dtype=float)
    ax.bar([str(i) for i in y.index], vals, color=np.where(vals >= 0, "#2ca02c", "#d62728"))
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("연도별 수익률(%)", fontsize=13)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.3)
    return fig


def chart_dist_vol(res: AnalysisResult) -> Figure:
    df = res.df
    fig = Figure(figsize=(12, 5), layout="tight")
    a1, a2 = fig.subplots(1, 2)
    a1.hist(df["Return"].dropna().to_numpy(dtype=float), bins=120, color="#1f77b4", alpha=0.8)
    a1.set_title("일간 수익률 분포(%)"); a1.grid(alpha=0.3)
    a2.plot(pd.DatetimeIndex(df.index), df["Vol21"].to_numpy(dtype=float), lw=1, color="#ff7f0e")
    a2.set_title("21일 롤링 변동성 (연환산 %)"); a2.grid(alpha=0.3)
    return fig


def chart_heatmap(res: AnalysisResult) -> Figure:
    heat = res.tables["월별수익률"]
    vals = heat.to_numpy(dtype=float)
    fig = Figure(figsize=(11, max(4.0, 0.38 * len(heat) + 1.5)), layout="tight")
    ax = fig.add_subplot()
    lim = float(np.nanmax(np.abs(vals))) if np.isfinite(vals).any() else 1.0
    im = ax.imshow(vals, cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(len(heat.columns)), list(heat.columns))
    ax.set_yticks(range(len(heat.index)), [str(i) for i in heat.index])
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            if not np.isnan(vals[i, j]):
                ax.text(j, i, f"{vals[i, j]:.1f}", ha="center", va="center", fontsize=7)
    ax.set_title("월별 수익률 히트맵(%)", fontsize=13)
    fig.colorbar(im, ax=ax, shrink=0.8)
    return fig


def build_charts(res: AnalysisResult, start: str, end: str) -> dict[str, Figure]:
    return {
        "종가 추이": chart_close(res, start, end),
        "이동평균·낙폭": chart_ma_drawdown(res),
        "연도별 수익률": chart_yearly(res),
        "수익률 분포·변동성": chart_dist_vol(res),
        "월별 히트맵": chart_heatmap(res),
    }


def figure_png(fig: Figure, dpi: int = 110) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    return buf.getvalue()


# ----------------------------------------------------------------------
# 4. 엑셀 저장
# ----------------------------------------------------------------------
def export_excel(res: AnalysisResult, charts: dict[str, Figure], path: str | Path) -> None:
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def style_sheet(ws, num_fmt: str = "#,##0.00") -> None:
        for cell in ws[1]:
            cell.fill, cell.font = header_fill, header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
            for cell in row:
                cell.border = border
                if cell.row > 1 and isinstance(cell.value, float):
                    cell.number_format = num_fmt
                elif cell.row > 1 and cell.is_date:
                    cell.number_format = "yyyy-mm-dd"
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 4, 10), 40)
        ws.freeze_panes = "B2"

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        # 요약
        summary = pd.DataFrame(list(res.summary.items()), columns=["항목", "값"])
        summary.to_excel(xw, sheet_name="요약", index=False)
        log = pd.DataFrame({"클렌징 로그": res.clean_log})
        log.to_excel(xw, sheet_name="요약", index=False, startrow=len(summary) + 2)

        # 정제 데이터
        out = res.df.reset_index().rename(columns={
            "Date": "날짜", "Close": "종가", "Open": "시가", "High": "고가", "Low": "저가",
            "Volume": "거래량", "ChangePct": "변동%", "Return": "수익률%(재계산)",
            "MA50": "MA50", "MA200": "MA200", "Drawdown": "낙폭%", "Range%": "일중변동폭%",
            "Vol21": "21일변동성%"})
        out["날짜"] = pd.DatetimeIndex(out["날짜"]).date
        out.to_excel(xw, sheet_name="정제데이터", index=False)

        for name, table in res.tables.items():
            t = table.copy()
            for c in t.columns:
                if pd.api.types.is_datetime64_any_dtype(t[c]):
                    t[c] = pd.DatetimeIndex(t[c]).date
            t.to_excel(xw, sheet_name=name)

        wb = xw.book
        for ws in wb.worksheets:
            style_sheet(ws)
        ws = wb["요약"]
        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 60
        log_header = ws.cell(row=len(summary) + 3, column=1)
        log_header.fill, log_header.font = header_fill, header_font

        # 차트 시트 (PNG 이미지 삽입)
        ws_chart = wb.create_sheet("차트")
        row = 1
        for title, fig in charts.items():
            ws_chart.cell(row=row, column=1, value=title).font = Font(bold=True, size=13)
            img = XLImage(io.BytesIO(figure_png(fig, dpi=90)))
            ws_chart.add_image(img, f"A{row + 1}")
            row += int(img.height / 20) + 4
