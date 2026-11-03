"""
대한민국 연도별 출생아수 그래프 (1970~2025)

추천 그래프: 주석이 달린 막대그래프 + 합계출산율 보조 패널(같은 x축, 별도 y축 패널)
- 출생아수는 '연간 합계' 값이라 연도별 막대가 가장 정직하게 크기를 비교해 준다.
- 주요 사건(정점, 인구대체수준 붕괴, 외환위기, 황금돼지해, 데드크로스, 최저점, 반등)을
  직접 주석으로 달아 숫자의 '이유'를 함께 읽을 수 있게 했다.
- 2025년은 잠정치이므로 빗금 처리해 확정치와 구분한다.
- 이중 y축 대신, 아래에 합계출산율 패널을 따로 두어 두 지표를 혼동 없이 비교한다.

실행: python plot_births.py   (먼저 birth_analysis.py 실행 불필요 — 원본 엑셀을 직접 정제해서 사용)
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from birth_analysis import (BLUE, DEFAULT_XLSX, INK, INK2, OUT_DIR, REPLACEMENT_TFR, clean, load_raw,
                            setup_style)

START, END = 1970, 2025
BLUE_LIGHT = "#86b6ef"

# (연도, 주석 문구, 텍스트 y 위치(만 명))
EVENTS = [
    (1971, "1971년 최다 출생\n102만 명", 112),
    (1983, "1983년 합계출산율\n인구대체수준(2.1) 붕괴", 98),
    (1997, "1997년\n외환위기", 85),
    (2002, "2002년 50만 명 붕괴\n초저출산 진입", 70),
    (2007, "2007년\n황금돼지해", 62),
    (2020, "2020년 30만 명 붕괴\n첫 자연감소", 52),
    (2023, "2023년 역대 최저\n23만 명", 38),
]


def build_births_chart(df, start: int = START, end: int = END):
    setup_style()
    df = df.loc[start:end]
    start, end = int(df.index.min()), int(df.index.max())
    full_range = (start, end) == (START, END)
    years = df.index
    births = df["births"] / 1e4  # 만 명 단위

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(16, 9), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08})

    # --- 상단: 출생아수 막대 ---
    colors = [BLUE_LIGHT if p else BLUE for p in df["is_preliminary"]]
    hatches = ["////" if p else "" for p in df["is_preliminary"]]
    bars = ax.bar(years, births, width=0.75, color=colors, edgecolor="#fcfcfb", linewidth=0)
    for bar, h in zip(bars, hatches):
        if h:
            bar.set_hatch(h)
            bar.set_edgecolor(BLUE)

    # 5년 이동평균 (추세선)
    ax.plot(years, df["births_ma5"] / 1e4, color=INK, lw=1.5, alpha=0.7)

    # 주요 사건 주석 (전체 기간이 아니면 선택 구간 안의 사건만, 막대 위에 배치)
    top = 125 if full_range else births.max() * 1.45
    for year, text, ty in EVENTS:
        if not start <= year <= end:
            continue
        if not full_range:
            ty = births[year] + top * 0.12
        ax.annotate(text, xy=(year, births[year]), xytext=(year, ty), ha="center", va="bottom",
                    fontsize=9.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8, shrinkA=2, shrinkB=2))

    # 마지막 막대 값 라벨
    last = years[-1]
    note = "\n(잠정)" if df.at[last, "is_preliminary"] else ""
    ax.text(last, births[last] + top * 0.012, f"{births[last]:.1f}만{note}", ha="center", va="bottom",
            fontsize=9.5, color=INK, fontweight="bold")

    ax.set_ylim(0, top)
    ax.set_ylabel("출생아수 (만 명)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.grid(axis="x", visible=False)
    handles = [Patch(color=BLUE, label="출생아수 (확정)")]
    prelim = years[df["is_preliminary"]].tolist()
    if prelim:
        handles.append(Patch(facecolor=BLUE_LIGHT, edgecolor=BLUE, hatch="////",
                             label=f"출생아수 ({', '.join(map(str, prelim))} 잠정)"))
    handles.append(plt.Line2D([], [], color=INK, lw=1.5, alpha=0.7, label="5년 이동평균"))
    ax.legend(handles=handles, frameon=False, loc="upper right", fontsize=10)

    change = (df["births"].iloc[-1] / df["births"].iloc[0] - 1) * 100
    ax.set_title(f"대한민국 연도별 출생아수 ({start}~{end}) — {end - start}년 새 {abs(change):.0f}% "
                 f"{'감소' if change < 0 else '증가'}", fontsize=16, pad=14)

    # --- 하단: 합계출산율 ---
    ax2.plot(years, df["tfr"], color=BLUE, lw=2)
    ax2.axhline(REPLACEMENT_TFR, color=INK2, lw=0.8, ls="--")
    ax2.text(start + (end - start) * 0.55, REPLACEMENT_TFR + 0.15, "인구대체수준 2.1", fontsize=9, color=INK2)
    for y in dict.fromkeys((start, int(df["tfr"].idxmin()), end)):
        ax2.annotate(f"{df.at[y, 'tfr']:.2f}", xy=(y, df.at[y, "tfr"]), xytext=(0, 6),
                     textcoords="offset points", ha="center", fontsize=9, color=INK)
        ax2.plot(y, df.at[y, "tfr"], "o", ms=5, color=BLUE, mec="#fcfcfb", mew=1.5)
    ax2.set_ylim(0, 5.2)
    ax2.set_ylabel("합계출산율 (명)")
    step = 5 if end - start > 15 else 1
    ax2.set_xticks(range(start + (-start) % step, end + 1, step))
    ax2.set_xlim(start - 1, end + 1)
    ax2.grid(axis="x", visible=False)

    fig.text(0.01, 0.01, "자료: 통계청(국가데이터처) 「인구동향조사」, KOSIS (2025년은 잠정치)",
             fontsize=9, color=INK2)
    fig.subplots_adjust(left=0.06, right=0.93, top=0.92, bottom=0.07)
    return fig


def plot_births(df, path: Path):
    fig = build_births_chart(df)
    fig.savefig(path, dpi=150)
    plt.show() if "--show" in sys.argv else plt.close(fig)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    raw, _ = load_raw(DEFAULT_XLSX)
    df, _ = clean(raw)
    out = OUT_DIR / "births_1970_2025.png"
    plot_births(df, out)
    print(f"저장 완료: {out}")


if __name__ == "__main__":
    main()
