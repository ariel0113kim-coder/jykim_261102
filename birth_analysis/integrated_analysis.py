"""
출생(INH_1B8000F_01) + 사망·기대수명(INH_1B8000F_02) 통합 분석

실행: python integrated_analysis.py
결과: output/ 폴더에 통합 정제 데이터(CSV), 통합 리포트(TXT), 통합 대시보드(PNG) 저장
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from birth_analysis import (BLUE, DEFAULT_XLSX, GRAY, INK, INK2, ORANGE, OUT_DIR, clean, first_year,
                            load_raw, parse_year, setup_style)

DEATHS_XLSX = DEFAULT_XLSX.parent / "사망자수__조사망률__기대수명_20240726085317.xlsx"

DEATH_COLUMN_MAP = {
    "사망자수(명)": "deaths_reported",
    "조사망률(천명당)": "crude_death_rate",
    "기대수명(출생시 기대여명)": "life_exp",
    "기대수명(출생시 기대여명) - 남": "life_exp_male",
    "기대수명(출생시 기대여명) - 여": "life_exp_female",
}
EXCESS_BASELINE = (2015, 2019)  # 코로나19 이전 사망 추세 기준 기간
AQUA = "#1baf7a"


# ----------------------------------------------------------------------------
# 1. 사망 데이터 클렌징
# ----------------------------------------------------------------------------
def clean_deaths(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    log = [f"원본 형태: {raw.shape[0]}개 항목 x {raw.shape[1]}개 연도 (가로형 wide)"]

    raw.index = raw.index.astype(str).str.strip()
    raw = raw.loc[[k for k in DEATH_COLUMN_MAP if k in raw.index]]
    df = raw.T.rename(columns=DEATH_COLUMN_MAP)
    df.columns.name = None

    parsed = [parse_year(c) for c in df.index]
    df.index = pd.Index([y for y, _ in parsed], name="year")
    df["deaths_is_preliminary"] = [p for _, p in parsed]
    log.append(f"잠정치(p) 연도: {df.index[df['deaths_is_preliminary']].tolist()}")

    # '-' (미공표) -> NaN. 기대수명 미공표 연도는 보간하지 않고 결측으로 둔다(추정값을 만들지 않음)
    for col in DEATH_COLUMN_MAP.values():
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    na = df[list(DEATH_COLUMN_MAP.values())].isna()
    for col in na.columns[na.any()]:
        log.append(f"결측('-' 미공표): {col} -> {df.index[na[col]].tolist()}년 (보간하지 않음)")

    log.append(f"중복 연도: {int(df.index.duplicated().sum())}건, 기간 {df.index.min()}~{df.index.max()}")
    df["deaths_reported"] = df["deaths_reported"].round().astype("Int64")

    checks = {
        "남 < 전체 < 여 (기대수명)": ((df["life_exp_male"] < df["life_exp"]) & (df["life_exp"] < df["life_exp_female"]))
        [df["life_exp"].notna()].all(),
        "30 < 기대수명 < 100": df["life_exp"].dropna().between(30, 100).all(),
        "사망자수 > 0": (df["deaths_reported"] > 0).all(),
    }
    for name, ok in checks.items():
        log.append(f"범위 검증 [{name}]: {'통과' if ok else '실패'}")
    return df, log


# ----------------------------------------------------------------------------
# 2. 병합 및 정합성 검증
# ----------------------------------------------------------------------------
def merge(births: pd.DataFrame, deaths: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    log = []
    df = births.join(deaths, how="outer")
    log.append(f"병합(outer join): 출생 {births.index.min()}~{births.index.max()}, "
               f"사망 {deaths.index.min()}~{deaths.index.max()} -> {df.index.min()}~{df.index.max()} {len(df)}개년")

    # 출생 파일의 '출생아수 - 자연증가'는 사망자수와 같아야 함 -> 두 통계표 간 교차검증
    diff = (df["deaths_reported"] - df["deaths_est"]).dropna()
    mism = diff[diff != 0]
    log.append(f"교차검증(사망자수 = 출생아수 - 자연증가): {len(diff)}개년 중 불일치 {len(mism)}건"
               + (f" -> {', '.join(f'{y}년 {int(v):+,}명' for y, v in mism.items())}" if len(mism) else ""))

    # 최종 사망자수: 확정 공표치 우선, 잠정치/미수록 연도는 최신 출생 파일(2026 다운로드)에서 역산한 값 사용
    use_derived = df["deaths_reported"].isna() | df["deaths_is_preliminary"].fillna(False).astype(bool)
    df["deaths"] = np.where(use_derived, df["deaths_est"], df["deaths_reported"]).astype("int64")
    df["deaths_source"] = np.where(use_derived, "출생표 역산(최신)", "사망표 공표치")
    log.append(f"최종 사망자수: 사망표 확정치 사용, {df.index[use_derived].tolist()}년은 "
               f"최신 출생표(출생-자연증가)로 대체 (2023년 사망표 값은 2024년 7월 기준 잠정치)")

    # 조사망률: 미수록 연도는 사망자수 / 추정인구로 산출
    cdr_calc = df["deaths"] / df["population_est"] * 1000
    gap = (cdr_calc - df["crude_death_rate"]).abs().dropna()
    log.append(f"조사망률 산출식 검증(사망자수/추정인구): 평균 오차 {gap.mean():.2f}‰, 최대 {gap.max():.2f}‰")
    df["crude_death_rate_filled"] = df["crude_death_rate"].fillna(cdr_calc.round(1))
    df["life_exp_gap"] = df["life_exp_female"] - df["life_exp_male"]
    df["birth_death_ratio"] = df["births"] / df["deaths"]
    return df, log


# ----------------------------------------------------------------------------
# 3. 통합 분석
# ----------------------------------------------------------------------------
def excess_deaths(df: pd.DataFrame) -> pd.DataFrame:
    a, b = EXCESS_BASELINE
    base = df.loc[a:b, "deaths"]
    slope, intercept = np.polyfit(base.index, base.values, 1)
    out = df.loc[2020:, ["deaths"]].copy()
    out["expected"] = (slope * out.index + intercept).round()
    out["excess"] = out["deaths"] - out["expected"]
    out["excess_pct"] = out["excess"] / out["expected"] * 100
    return out


def analyze(df: pd.DataFrame) -> list[str]:
    r = []
    sec = lambda title: r.extend(["", "=" * 72, f" {title}", "=" * 72])
    fmt = lambda n: f"{n:,.0f}"
    y0, y1 = df.index.min(), df.index.max()
    le_last = df["life_exp"].last_valid_index()

    sec("1. 출생 vs 사망 – 인구 자연증가의 종말")
    r.append(f"출생/사망 비율: {y0}년 {df.at[y0, 'birth_death_ratio']:.2f} (사망 1명당 출생 {df.at[y0, 'birth_death_ratio']:.1f}명) "
             f"-> {y1}년 {df.at[y1, 'birth_death_ratio']:.2f}")
    r.append(f"출생 감소: {fmt(df.at[y0, 'births'])} -> {fmt(df.at[y1, 'births'])}명 ({(df.at[y1, 'births'] / df.at[y0, 'births'] - 1) * 100:+.1f}%)")
    r.append(f"사망 증가: {fmt(df.at[y0, 'deaths'])} -> {fmt(df.at[y1, 'deaths'])}명 ({(df.at[y1, 'deaths'] / df.at[y0, 'deaths'] - 1) * 100:+.1f}%)")
    r.append(f"데드크로스(사망 > 출생): {first_year(df, df['deaths'] > df['births'])}년, "
             f"사망자 최다: {df['deaths'].idxmax()}년 {fmt(df['deaths'].max())}명")
    r.append("※ 출생은 1970년 대비 1/4로 줄었지만, 사망자수는 2000년대까지 24~25만 명으로 거의 일정 →"
             " 자연증가 감소는 주로 '출생 감소'가 만든 것이고 2010년대 이후 '고령화에 따른 사망 증가'가 가세함")

    sec("2. 인구변천(Demographic Transition) – 조출생률 vs 조사망률")
    cdr = df["crude_death_rate_filled"]
    r.append(f"조출생률: {df.at[y0, 'crude_birth_rate']:.1f}‰ -> {df.at[y1, 'crude_birth_rate']:.1f}‰")
    low = cdr.index[cdr == cdr.min()]
    r.append(f"조사망률: {cdr[y0]:.1f}‰ -> 최저 {low.min()}~{low.max()}년 {cdr.min():.1f}‰ -> {y1}년 {cdr[y1]:.1f}‰ (U자형)")
    r.append("  - 1970~2000년대: 영아·성인 사망률 개선으로 조사망률 하락")
    r.append("  - 2010년 이후: 기대수명은 계속 늘지만 고령인구 비중이 커져 조사망률 상승 (인구 고령화 효과)")
    check = (df["crude_birth_rate"] - cdr - df["natural_increase_rate"]).abs()
    r.append(f"검증: 조출생률 - 조사망률 = 자연증가율 (최대 오차 {check.max():.2f}‰, 반올림 오차 수준)")
    stages = pd.cut(df["natural_increase_rate"], [-np.inf, 0, 5, 15, np.inf],
                    labels=["자연감소", "저성장(0~5‰)", "중성장(5~15‰)", "고성장(15‰ 이상)"])
    run_id = (stages != stages.shift()).cumsum()
    for _, years in df.index.to_series().groupby(run_id):
        r.append(f"  {years.min()}~{years.max()}년 ({len(years):>2}개년): {stages[years.min()]}")

    sec(f"3. 기대수명 (1970~{le_last})")
    le = df["life_exp"]
    r.append(f"전체: {le[y0]:.1f}세 -> {le[le_last]:.1f}세 ({le[le_last] - le[y0]:+.1f}년), "
             f"최고 {le.idxmax()}년 {le.max():.1f}세")
    r.append(f"남자: {df.at[y0, 'life_exp_male']:.1f} -> {df.at[le_last, 'life_exp_male']:.1f}세 / "
             f"여자: {df.at[y0, 'life_exp_female']:.1f} -> {df.at[le_last, 'life_exp_female']:.1f}세")
    gap = df["life_exp_gap"]
    r.append(f"남녀 격차: {y0}년 {gap[y0]:.1f}년 -> 최대 {gap.idxmax()}년 {gap.max():.1f}년 -> {le_last}년 {gap[le_last]:.1f}년")
    for a, b in [(1970, 1990), (1990, 2010), (2010, 2021)]:
        r.append(f"  {a}~{b}: 연평균 +{(le[b] - le[a]) / (b - a):.2f}년/년")
    drops = le.diff()[le.diff() < 0]
    r.append(f"기대수명 감소 연도: {', '.join(f'{y}년({v:+.1f})' for y, v in drops.items()) or '없음'}"
             " ← 코로나19 사망 급증 영향")
    r.append(f"※ {le_last + 1}년 이후 기대수명은 원본 자료 미공표('-')로 분석에서 제외")

    sec(f"4. 코로나19 초과사망 (기준: {EXCESS_BASELINE[0]}~{EXCESS_BASELINE[1]} 선형 추세)")
    ex = excess_deaths(df)
    r.append(ex.to_string(float_format=lambda v: f"{v:,.1f}"))
    r.append(f"2020~{y1} 누적 초과사망: 약 {fmt(ex['excess'].sum())}명")
    r.append("※ 선형 추세는 가속하는 고령화를 다 반영하지 못해 2023년 이후 초과사망은 과대추정될 수 있음."
             " 2022년(+18%)은 오미크론 유행에 따른 명확한 초과사망")

    sec("5. 출산율 vs 기대수명 – 고령화의 두 축")
    pair = df[["tfr", "life_exp"]].dropna()
    lvl = pair.corr().iloc[0, 1]
    chg = pair.diff().dropna().corr().iloc[0, 1]
    r.append(f"수준 상관: {lvl:+.2f} (둘 다 시간에 따라 움직여 생기는 '추세 상관' — 인과로 해석 불가)")
    r.append(f"전년 대비 변화량 상관: {chg:+.2f} (추세 제거 시 관계 거의 없음)")
    r.append(f"합계출산율 {pair['tfr'].iloc[0]:.2f}명·기대수명 {pair['life_exp'].iloc[0]:.1f}세 -> "
             f"{pair['tfr'].iloc[-1]:.2f}명·{pair['life_exp'].iloc[-1]:.1f}세 ({pair.index[-1]}년)")
    r.append("→ '적게 태어나고 오래 사는' 구조가 동시에 진행되어 인구 고령화가 매우 빠르게 진행됨")

    sec("6. 연대별 통합 요약")
    dec = df.groupby("decade").agg(
        연평균출생=("births", "mean"), 연평균사망=("deaths", "mean"), 누적자연증가=("natural_increase", "sum"),
        평균합계출산율=("tfr", "mean"), 평균조사망률=("crude_death_rate_filled", "mean"),
        평균기대수명=("life_exp", "mean"),
    )
    r.append(dec.to_string(float_format=lambda v: f"{v:,.1f}"))
    return r


# ----------------------------------------------------------------------------
# 4. 통합 대시보드
# ----------------------------------------------------------------------------
def build_integrated(df: pd.DataFrame):
    setup_style()
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    years = df.index
    le = df.dropna(subset=["life_exp"])

    # (a) 출생 vs 사망 + 자연증가/감소 영역
    ax = axes[0, 0]
    b, d = df["births"] / 1e4, df["deaths"] / 1e4
    ax.fill_between(years, b, d, where=b >= d, color=BLUE, alpha=0.15, interpolate=True, lw=0)
    ax.fill_between(years, b, d, where=b < d, color=ORANGE, alpha=0.25, interpolate=True, lw=0)
    ax.plot(years, b, color=BLUE, lw=2, label="출생아수")
    ax.plot(years, d, color=ORANGE, lw=2, label="사망자수")
    ax.text(1985, 45, "자연증가", color=INK2, fontsize=10)
    ax.text(2022, 40, "자연감소", color=INK2, fontsize=10, ha="center")
    ax.legend(frameon=False, loc="upper right")
    ax.set_title("출생 vs 사망 (만 명)")

    # (b) 조출생률 vs 조사망률 (같은 ‰ 단위)
    ax = axes[0, 1]
    ax.plot(years, df["crude_birth_rate"], color=BLUE, lw=2, label="조출생률")
    ax.plot(years, df["crude_death_rate_filled"], color=ORANGE, lw=2, label="조사망률")
    m = df["crude_death_rate_filled"].idxmin()
    ax.annotate(f"조사망률 최저\n{m}년 {df.at[m, 'crude_death_rate_filled']:.1f}‰",
                xy=(m, df.at[m, "crude_death_rate_filled"]), xytext=(m - 12, 1.5), fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.legend(frameon=False, loc="upper right")
    ax.set_ylim(0, None)
    ax.set_title("인구변천: 조출생률 vs 조사망률 (인구 1천 명당)")

    # (c) 기대수명 남/여
    ax = axes[0, 2]
    ax.plot(le.index, le["life_exp_female"], color=ORANGE, lw=2, label="여자")
    ax.plot(le.index, le["life_exp"], color=INK2, lw=1.2, ls="--", label="전체")
    ax.plot(le.index, le["life_exp_male"], color=BLUE, lw=2, label="남자")
    last = le.index[-1]
    for col in ("life_exp_female", "life_exp_male"):
        ax.annotate(f"{le.at[last, col]:.1f}", xy=(last, le.at[last, col]), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK)
    ax.legend(frameon=False, loc="lower right")
    ax.set_title(f"기대수명 (세, 1970~{last})")

    # (d) 남녀 기대수명 격차
    ax = axes[1, 0]
    ax.bar(le.index, le["life_exp_gap"], color=BLUE, width=0.75)
    g = le["life_exp_gap"].idxmax()
    ax.annotate(f"최대 {g}년 {le.at[g, 'life_exp_gap']:.1f}년", xy=(g, le.at[g, "life_exp_gap"]),
                xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9, color=INK)
    ax.set_ylim(0, 10)
    ax.grid(axis="x", visible=False)
    ax.set_title("남녀 기대수명 격차 (여 - 남, 년)")

    # (e) 코로나19 초과사망
    ax = axes[1, 1]
    ex = excess_deaths(df)
    a, z = EXCESS_BASELINE
    hist = df.loc[2010:, "deaths"] / 1e4
    ax.bar(hist.index, hist, color=[GRAY if y < 2020 else BLUE for y in hist.index], width=0.75)
    trend_years = np.arange(a, df.index.max() + 1)
    base = df.loc[a:z, "deaths"]
    slope, intercept = np.polyfit(base.index, base.values, 1)
    ax.plot(trend_years, (slope * trend_years + intercept) / 1e4, color=INK, lw=1.5, ls="--")
    peak = ex["excess"].idxmax()
    ax.annotate(f"{peak}년 초과사망\n+{ex.at[peak, 'excess'] / 1e4:.1f}만 명 ({ex.at[peak, 'excess_pct']:+.0f}%)",
                xy=(peak, ex.at[peak, "deaths"] / 1e4), xytext=(2016.5, 36.5), fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.set_ylim(20, 40)
    ax.legend(handles=[Patch(color=GRAY, label="2010~2019"), Patch(color=BLUE, label="2020 이후"),
                       plt.Line2D([], [], color=INK, ls="--", label=f"{a}~{z} 추세(기대 사망)")],
              frameon=False, loc="upper left", fontsize=9)
    ax.grid(axis="x", visible=False)
    ax.set_title("사망자수 vs 코로나19 이전 추세 (만 명)")

    # (f) 합계출산율 vs 기대수명 경로 (연결 산점도: 한 축씩 사용)
    ax = axes[1, 2]
    pair = df[["tfr", "life_exp"]].dropna()
    ax.plot(pair["tfr"], pair["life_exp"], color=GRAY, lw=1.2, zorder=1)
    sc = ax.scatter(pair["tfr"], pair["life_exp"], c=pair.index, cmap="Blues", s=36,
                    edgecolor="#fcfcfb", linewidth=1, zorder=2, vmin=1950)
    for y, dx in ((1970, 6), (1983, 6), (2002, 6), (pair.index[-1], -30)):
        ax.annotate(str(y), xy=(pair.at[y, "tfr"], pair.at[y, "life_exp"]), xytext=(dx, -2),
                    textcoords="offset points", fontsize=9, color=INK)
    ax.set_xlabel("합계출산율 (명)")
    ax.set_ylabel("기대수명 (세)")
    ax.invert_xaxis()
    fig.colorbar(sc, ax=ax, label="연도", fraction=0.04, pad=0.02)
    ax.set_title("적게 태어나고 오래 산다 (합계출산율 → 기대수명)")

    fig.suptitle(f"대한민국 출생·사망·기대수명 통합 분석 ({years.min()}~{years.max()})", fontsize=16,
                 fontweight="bold", x=0.01, ha="left")
    fig.text(0.01, 0.005, "자료: 통계청 「인구동향조사」 KOSIS INH_1B8000F_01·02 / 2025년 출생·사망은 잠정치, "
             f"기대수명은 {le.index[-1]}년까지 공표", fontsize=9, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    return fig


def plot_integrated(df: pd.DataFrame, path: Path):
    fig = build_integrated(df)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    b_raw, b_meta = load_raw(DEFAULT_XLSX)
    births, b_log = clean(b_raw)
    d_raw, d_meta = load_raw(DEATHS_XLSX)
    deaths, d_log = clean_deaths(d_raw)
    df, m_log = merge(births, deaths)

    cols = ["births", "deaths", "deaths_source", "natural_increase", "birth_death_ratio",
            "crude_birth_rate", "crude_death_rate_filled", "natural_increase_rate", "tfr", "sex_ratio",
            "life_exp", "life_exp_male", "life_exp_female", "life_exp_gap", "population_est", "is_preliminary"]
    df[cols].to_csv(OUT_DIR / "integrated_clean.csv", encoding="utf-8-sig")

    report = [f"출처: {b_meta.get('통계표명')} ({b_meta.get('통계표ID')}, 다운로드 {b_meta.get('자료다운일자')})",
              f"      {d_meta.get('통계표명')} ({d_meta.get('통계표ID')}, 다운로드 {d_meta.get('자료다운일자')})",
              "", "[출생 데이터 클렌징]"] + [f"- {x}" for x in b_log]
    report += ["", "[사망 데이터 클렌징]"] + [f"- {x}" for x in d_log]
    report += ["", "[병합 및 교차검증]"] + [f"- {x}" for x in m_log]
    report += analyze(df)
    text = "\n".join(report)
    (OUT_DIR / "integrated_report.txt").write_text(text, encoding="utf-8")
    print(text)

    plot_integrated(df, OUT_DIR / "integrated_dashboard.png")
    print(f"\n저장 완료: {OUT_DIR}")


if __name__ == "__main__":
    main()
