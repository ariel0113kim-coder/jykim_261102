"""
대한민국 출생아수·합계출산율·자연증가 데이터 클렌징 및 다각도 분석 (KOSIS INH_1B8000F_01)

실행: python birth_analysis.py [엑셀경로]
결과: output/ 폴더에 정제 데이터(CSV), 분석 리포트(TXT), 분석 대시보드(PNG) 저장
"""

import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_XLSX = BASE_DIR.parent / "출생아수__합계출산율__자연증가_등_20260605082440.xlsx"
OUT_DIR = BASE_DIR / "output"

# 원본 항목명 -> 분석용 컬럼명
COLUMN_MAP = {
    "출생아수(명)": "births",
    "자연증가건수(명)": "natural_increase",
    "조출생률(천명당)": "crude_birth_rate",
    "자연증가율(천명당)": "natural_increase_rate",
    "합계출산율(명)": "tfr",
    "출생성비(명)": "sex_ratio",
}
KOR_LABEL = {
    "births": "출생아수(명)",
    "natural_increase": "자연증가(명)",
    "deaths_est": "사망자수 추정(명)",
    "crude_birth_rate": "조출생률(‰)",
    "natural_increase_rate": "자연증가율(‰)",
    "tfr": "합계출산율(명)",
    "sex_ratio": "출생성비",
}
REPLACEMENT_TFR = 2.1     # 인구대체수준
LOWEST_LOW_TFR = 1.3      # 초저출산 기준
NORMAL_SEX_RATIO = (103, 107)  # 자연 출생성비 범위


# ----------------------------------------------------------------------------
# 1. 데이터 클렌징
# ----------------------------------------------------------------------------
def load_raw(path: Path) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_excel(path, sheet_name="데이터", header=0, index_col=0)
    meta_df = pd.read_excel(path, sheet_name="메타정보", header=None)
    meta = {
        str(k).replace("○", "").strip(): str(v).strip()
        for k, v in zip(meta_df[0], meta_df[1])
        if pd.notna(k) and pd.notna(v)
    }
    return raw, meta


def parse_year(label) -> tuple[int, bool]:
    """'1970.0' -> (1970, False), '2025 p)' -> (2025, True)  (p) = 잠정치)"""
    text = str(label).strip()
    m = re.match(r"^(\d{4})", text)
    if not m:
        raise ValueError(f"연도 해석 불가: {label!r}")
    return int(m.group(1)), "p" in text.lower()


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    log = []
    log.append(f"원본 형태: {raw.shape[0]}개 항목 x {raw.shape[1]}개 연도 (가로형 wide)")

    # (1) 항목명 정리 및 영문 컬럼명으로 변환
    raw.index = raw.index.astype(str).str.strip()
    unknown = set(raw.index) - set(COLUMN_MAP)
    if unknown:
        log.append(f"매핑되지 않은 항목 제외: {sorted(unknown)}")
    raw = raw.loc[[k for k in COLUMN_MAP if k in raw.index]]

    # (2) 가로형 -> 세로형(연도가 행)으로 전치
    df = raw.T.rename(columns=COLUMN_MAP)
    df.columns.name = None

    # (3) 연도 라벨 정리: 1970.0 같은 float, '2025 p)' 같은 잠정치 표기 처리
    parsed = [parse_year(c) for c in df.index]
    df.index = pd.Index([y for y, _ in parsed], name="year")
    df["is_preliminary"] = [p for _, p in parsed]
    prelim = df.index[df["is_preliminary"]].tolist()
    log.append(f"잠정치(p) 연도 분리 표시: {prelim}")

    # (4) 수치형 변환 (쉼표, '-', 공백 등 문자열 대비)
    for col in COLUMN_MAP.values():
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "").str.strip().replace({"-": np.nan, "": np.nan}),
            errors="coerce",
        )

    # (5) 중복 연도 / 결측치 / 연도 연속성 점검
    dup = df.index.duplicated().sum()
    if dup:
        df = df[~df.index.duplicated(keep="last")]
    log.append(f"중복 연도: {dup}건")
    na = df[list(COLUMN_MAP.values())].isna().sum()
    log.append(f"결측치: {int(na.sum())}건" + (f" -> {na[na > 0].to_dict()}" if na.sum() else ""))
    if na.sum():
        df[list(COLUMN_MAP.values())] = df[list(COLUMN_MAP.values())].interpolate(limit_direction="both")
        log.append("결측치는 선형보간으로 채움")
    missing_years = sorted(set(range(df.index.min(), df.index.max() + 1)) - set(df.index))
    log.append(f"누락 연도: {missing_years or '없음'} ({df.index.min()}~{df.index.max()}, {len(df)}개년)")

    # (6) 자료형 정리: 인원수는 정수, 비율은 소수
    for col in ("births", "natural_increase"):
        df[col] = df[col].round().astype("int64")

    # (7) 값 범위 검증 (이상치 점검)
    checks = {
        "births > 0": (df["births"] > 0).all(),
        "0 < tfr < 10": df["tfr"].between(0, 10, inclusive="neither").all(),
        "90 <= sex_ratio <= 130": df["sex_ratio"].between(90, 130).all(),
        "crude_birth_rate > 0": (df["crude_birth_rate"] > 0).all(),
    }
    for name, ok in checks.items():
        log.append(f"범위 검증 [{name}]: {'통과' if ok else '실패'}")

    # (8) 파생 변수
    df["deaths_est"] = df["births"] - df["natural_increase"]           # 사망자수 = 출생 - 자연증가
    df["population_est"] = (df["births"] / df["crude_birth_rate"] * 1000).round(-3)  # 연앙인구 추정
    df["births_yoy"] = df["births"].diff()
    df["births_yoy_pct"] = df["births"].pct_change() * 100
    df["births_ma5"] = df["births"].rolling(5, center=True, min_periods=3).mean()
    df["births_index_1970"] = df["births"] / df["births"].iloc[0] * 100
    df["decade"] = (df.index // 10 * 10).astype(str) + "년대"
    log.append("파생 변수 추가: deaths_est, population_est, births_yoy(_pct), births_ma5, births_index_1970, decade")

    return df, log


# ----------------------------------------------------------------------------
# 2. 다각도 분석
# ----------------------------------------------------------------------------
def first_year(df: pd.DataFrame, mask: pd.Series):
    hit = df.index[mask]
    return int(hit[0]) if len(hit) else None


def cagr(start, end, years):
    return ((end / start) ** (1 / years) - 1) * 100


def analyze(df: pd.DataFrame) -> list[str]:
    r = []
    sec = lambda title: r.extend(["", "=" * 72, f" {title}", "=" * 72])
    y0, y1 = df.index.min(), df.index.max()
    fmt = lambda n: f"{n:,.0f}"

    # 2-1. 기술통계
    sec("1. 기술통계")
    cols = ["births", "natural_increase", "deaths_est", "tfr", "crude_birth_rate", "sex_ratio"]
    desc = df[cols].describe().T[["mean", "std", "min", "50%", "max"]]
    desc.index = [KOR_LABEL[c] for c in desc.index]
    r.append(desc.to_string(float_format=lambda v: f"{v:,.2f}"))

    # 2-2. 장기 추세
    sec("2. 장기 추세 (1970 -> 2025)")
    b = df["births"]
    r.append(f"출생아수: {fmt(b[y0])}명 -> {fmt(b[y1])}명 ({b[y1] / b[y0] * 100:.1f}% 수준, "
             f"{(1 - b[y1] / b[y0]) * 100:.1f}% 감소)")
    r.append(f"합계출산율: {df.at[y0, 'tfr']:.2f}명 -> {df.at[y1, 'tfr']:.2f}명")
    r.append(f"최다 출생: {b.idxmax()}년 {fmt(b.max())}명 / 최소 출생: {b.idxmin()}년 {fmt(b.min())}명")
    r.append(f"합계출산율 최저: {df['tfr'].idxmin()}년 {df['tfr'].min():.3f}명")
    for a, z in [(1970, 1983), (1983, 2001), (2001, 2015), (2015, 2023), (1970, 2025)]:
        r.append(f"  연평균 증감률(CAGR) {a}~{z}: {cagr(b[a], b[z], z - a):+.2f}%")

    # 2-3. 주요 임계점
    sec("3. 주요 임계점(마일스톤)")
    milestones = {
        "합계출산율 인구대체수준(2.1) 미만 진입": first_year(df, df["tfr"] < REPLACEMENT_TFR),
        "초저출산(합계출산율 1.3 미만) 진입": first_year(df, df["tfr"] < LOWEST_LOW_TFR),
        "합계출산율 1.0 미만": first_year(df, df["tfr"] < 1.0),
        "출생아수 70만 명 미만": first_year(df, b < 700_000),
        "출생아수 50만 명 미만": first_year(df, b < 500_000),
        "출생아수 30만 명 미만": first_year(df, b < 300_000),
        "자연감소(데드크로스: 사망 > 출생)": first_year(df, df["natural_increase"] < 0),
    }
    for k, v in milestones.items():
        r.append(f"  {k:<36} {v}년")

    # 2-4. 전년 대비 증감
    sec("4. 전년 대비 증감 (YoY)")
    yoy = df[["births", "births_yoy", "births_yoy_pct"]].dropna()
    r.append("감소폭 상위 5개년:")
    for y, row in yoy.nsmallest(5, "births_yoy_pct").iterrows():
        r.append(f"  {y}년 {row.births_yoy:+,.0f}명 ({row.births_yoy_pct:+.1f}%)")
    r.append("증가폭 상위 5개년:")
    for y, row in yoy.nlargest(5, "births_yoy_pct").iterrows():
        r.append(f"  {y}년 {row.births_yoy:+,.0f}명 ({row.births_yoy_pct:+.1f}%)")
    r.append(f"감소한 해 {int((yoy.births_yoy < 0).sum())}개년 / 증가한 해 {int((yoy.births_yoy > 0).sum())}개년")
    # 최장 연속 감소
    neg = (yoy.births_yoy < 0).astype(int)
    runs = neg.groupby((neg != neg.shift()).cumsum()).agg(["sum", "size"])
    runs = runs[runs["sum"] > 0]
    gid = runs["size"].idxmax()
    run_years = neg.index[(neg != neg.shift()).cumsum() == gid]
    r.append(f"최장 연속 감소: {run_years[0]}~{run_years[-1]}년 ({len(run_years)}년 연속)")

    # 2-5. 연대별 분석
    sec("5. 연대별 분석")
    dec = df.groupby("decade").agg(
        연평균출생아수=("births", "mean"),
        누적출생아수=("births", "sum"),
        평균합계출산율=("tfr", "mean"),
        평균출생성비=("sex_ratio", "mean"),
        누적자연증가=("natural_increase", "sum"),
        연수=("births", "size"),
    )
    dec["연평균출생아수_증감률(%)"] = dec["연평균출생아수"].pct_change() * 100
    r.append(dec.to_string(float_format=lambda v: f"{v:,.1f}"))

    # 2-6. 출생성비
    sec("6. 출생성비 분석 (여아 100명당 남아)")
    sr = df["sex_ratio"]
    high = df.index[sr > 110].tolist()
    r.append(f"최고 성비: {sr.idxmax()}년 {sr.max():.1f} (자연 성비 {NORMAL_SEX_RATIO[0]}~{NORMAL_SEX_RATIO[1]})")
    r.append(f"성비 110 초과 연도({len(high)}개년): {high}")
    normal_since = first_year(df, sr.between(*NORMAL_SEX_RATIO) & (df.index > sr.idxmax()))
    r.append(f"성비 정상범위 복귀: {normal_since}년 이후 대체로 105 내외로 안정")
    # 1990년대 남아선호에 따른 '사라진 여아' 추정
    excess = df.loc[sr > NORMAL_SEX_RATIO[1]]
    girls_actual = excess["births"] / (1 + excess["sex_ratio"] / 100)
    girls_expected = excess["births"] / (1 + 105 / 100)
    r.append(f"성비 107 초과 연도 기준, 정상성비(105) 대비 '덜 태어난 여아' 추정: "
             f"약 {fmt((girls_expected - girls_actual).sum())}명")

    # 2-7. 출생·사망·자연증가
    sec("7. 출생 vs 사망 (자연증가)")
    d = df["deaths_est"]
    r.append(f"추정 사망자수: {y0}년 {fmt(d[y0])}명 -> {y1}년 {fmt(d[y1])}명 ({d[y1] / d[y0]:.2f}배)")
    r.append(f"자연증가 최대: {df['natural_increase'].idxmax()}년 {fmt(df['natural_increase'].max())}명")
    r.append(f"자연감소 최대: {df['natural_increase'].idxmin()}년 {fmt(df['natural_increase'].min())}명")
    neg_sum = df.loc[df["natural_increase"] < 0, "natural_increase"].sum()
    r.append(f"자연감소 누적(2020~{y1}): {fmt(neg_sum)}명")

    # 2-8. 상관관계
    sec("8. 지표 간 상관관계 (Pearson)")
    corr = df[["births", "tfr", "crude_birth_rate", "natural_increase", "deaths_est", "sex_ratio"]].corr()
    corr.index = corr.columns = [KOR_LABEL[c] for c in corr.columns]
    r.append(corr.to_string(float_format=lambda v: f"{v:+.2f}"))
    r.append("※ 출생아수와 합계출산율 상관이 높지만, 같은 출산율에서도 가임여성 인구 규모에 따라 출생아수가 달라짐")
    # 출생아수 / 합계출산율 = '출산율 1명당 출생아수' -> 가임 인구 규모의 대리 지표
    df_tmp = df["births"] / df["tfr"]
    r.append(f"출생아수/합계출산율(가임인구 규모 대리지표): {y0}년 {fmt(df_tmp[y0])} -> "
             f"{df_tmp.idxmax()}년 최대 {fmt(df_tmp.max())} -> {y1}년 {fmt(df_tmp[y1])}")

    # 2-9. 최근 반등
    sec("9. 최근 동향 (2015~2025)")
    recent = df.loc[2015:, ["births", "births_yoy_pct", "tfr", "natural_increase", "is_preliminary"]]
    r.append(recent.to_string(float_format=lambda v: f"{v:,.2f}"))
    trough = b.loc[2015:].idxmin()
    r.append(f"{trough}년 저점 이후 {y1}년까지 {fmt(b[y1] - b[trough])}명 증가 "
             f"({(b[y1] / b[trough] - 1) * 100:+.1f}%), 합계출산율 {df.at[trough, 'tfr']:.3f} -> {df.at[y1, 'tfr']:.3f}")
    r.append("※ 2025년은 잠정치(p)로 확정 시 수정될 수 있음")
    return r


# ----------------------------------------------------------------------------
# 3. 분석 대시보드 (2x3 small multiples, 단일 y축)
# ----------------------------------------------------------------------------
BLUE, ORANGE, GRAY, INK, INK2 = "#2a78d6", "#eb6834", "#b5b4ae", "#0b0b0b", "#52514e"


def setup_style():
    plt.rcParams.update({
        "font.family": "Malgun Gothic",   # Windows 한글 폰트 (macOS: AppleGothic)
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": GRAY,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "axes.grid": True,
        "grid.color": "#e8e7e3",
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb",
        "axes.titleweight": "bold",
        "axes.titlesize": 12,
        "axes.titlelocation": "left",
    })


def build_dashboard(df: pd.DataFrame):
    setup_style()
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    years = df.index

    # (a) 합계출산율 + 기준선
    ax = axes[0, 0]
    ax.plot(years, df["tfr"], color=BLUE, lw=2)
    for v, lab in [(REPLACEMENT_TFR, "인구대체수준 2.1"), (LOWEST_LOW_TFR, "초저출산 1.3"), (1.0, "1.0")]:
        ax.axhline(v, color=INK2, lw=0.8, ls="--")
        ax.text(years[-1], v + 0.05, lab, ha="right", fontsize=9, color=INK2)
    ax.set_title("합계출산율 (명)")

    # (b) 전년 대비 증감률 (증가/감소 2색)
    ax = axes[0, 1]
    pct = df["births_yoy_pct"].dropna()
    ax.bar(pct.index, pct, color=np.where(pct >= 0, BLUE, ORANGE), width=0.8)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.legend(handles=[Patch(color=BLUE, label="증가"), Patch(color=ORANGE, label="감소")],
              frameon=False, loc="upper right", ncol=2)
    ax.set_title("출생아수 전년 대비 증감률 (%)")

    # (c) 출생 vs 사망 (같은 단위 -> 한 축)
    ax = axes[0, 2]
    ax.plot(years, df["births"] / 1e4, color=BLUE, lw=2, label="출생아수")
    ax.plot(years, df["deaths_est"] / 1e4, color=ORANGE, lw=2, label="사망자수(추정)")
    ax.fill_between(years, df["births"] / 1e4, df["deaths_est"] / 1e4,
                    where=df["births"] < df["deaths_est"], color=ORANGE, alpha=0.2, interpolate=True)
    cross = first_year(df, df["natural_increase"] < 0)
    ax.annotate(f"{cross}년 데드크로스", xy=(cross, df.at[cross, "births"] / 1e4), xytext=(1995, 20),
                fontsize=9, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.legend(frameon=False, loc="upper right")
    ax.set_title("출생 vs 사망 (만 명)")

    # (d) 연대별 연평균 출생아수
    ax = axes[1, 0]
    dec = df.groupby("decade")["births"].mean() / 1e4
    bars = ax.bar(dec.index, dec.values, color=BLUE, width=0.6)
    ax.bar_label(bars, labels=[f"{v:.1f}" for v in dec.values], padding=3, fontsize=9, color=INK)
    ax.set_title("연대별 연평균 출생아수 (만 명, 2020년대는 2020~2025)")
    ax.grid(axis="x", visible=False)

    # (e) 출생성비
    ax = axes[1, 1]
    ax.axhspan(*NORMAL_SEX_RATIO, color=GRAY, alpha=0.25, lw=0)
    ax.text(1971, NORMAL_SEX_RATIO[0] + 0.3, "자연 성비 범위(103~107)", fontsize=9, color=INK2)
    ax.plot(years, df["sex_ratio"], color=BLUE, lw=2)
    peak = df["sex_ratio"].idxmax()
    ax.annotate(f"{peak}년 {df.at[peak, 'sex_ratio']:.1f}", xy=(peak, df.at[peak, "sex_ratio"]),
                xytext=(peak + 4, df.at[peak, "sex_ratio"] + 0.3), fontsize=9, color=INK)
    ax.set_title("출생성비 (여아 100명당 남아)")

    # (f) 출생아수 / 합계출산율 (가임인구 규모 대리지표)
    ax = axes[1, 2]
    ax.plot(years, df["births"] / df["tfr"] / 1e4, color=BLUE, lw=2)
    ax.set_title("출생아수 ÷ 합계출산율 (만 명) – 가임인구 규모 대리지표")

    fig.suptitle("대한민국 출생 통계 다각도 분석 (1970~2025, 2025년 잠정치)", fontsize=16,
                 fontweight="bold", x=0.01, ha="left")
    fig.text(0.01, 0.005, "자료: 통계청(국가데이터처) 「인구동향조사」, KOSIS", fontsize=9, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    return fig


def plot_dashboard(df: pd.DataFrame, path: Path):
    fig = build_dashboard(df)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    OUT_DIR.mkdir(exist_ok=True)

    raw, meta = load_raw(xlsx)
    df, clean_log = clean(raw)
    df.to_csv(OUT_DIR / "births_clean.csv", encoding="utf-8-sig")

    report = [f"출처: {meta.get('출처', '')} / 통계표: {meta.get('통계표명', '')} ({meta.get('통계표ID', '')})",
              "", "[데이터 클렌징 로그]"] + [f"- {line}" for line in clean_log]
    report += analyze(df)
    text = "\n".join(report)
    (OUT_DIR / "analysis_report.txt").write_text(text, encoding="utf-8")
    print(text)

    plot_dashboard(df, OUT_DIR / "analysis_dashboard.png")
    print(f"\n저장 완료: {OUT_DIR}")


if __name__ == "__main__":
    main()
