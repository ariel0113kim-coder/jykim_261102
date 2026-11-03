"""
S&P 500 과거 데이터 클렌징 + Pandas 다각도 분석 + 종가 라인그래프 (콘솔 버전)

실행:  python sp500_analysis/sp500_analysis.py [CSV경로] [시작 YYYY-MM] [종료 YYYY-MM]
출력:  sp500_analysis/output/ 폴더에 정제 CSV, 차트 PNG, 엑셀 결과 저장
GUI 버전은 app.py 를 실행하세요.
"""
import sys
from pathlib import Path

import pandas as pd

import analyzer

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "output"

pd.set_option("display.width", 140)
pd.set_option("display.float_format", "{:,.2f}".format)


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR.parent / "S&P 500 과거 데이터.csv"
    start = sys.argv[2] if len(sys.argv) > 2 else "2000-01"
    end = sys.argv[3] if len(sys.argv) > 3 else "2019-12"
    OUT.mkdir(exist_ok=True)

    df, log = analyzer.load_and_clean(src)
    res = analyzer.analyze(df, log)

    section("1. 데이터 클렌징")
    for line in res.clean_log:
        print(f"- {line}")

    section("2. 핵심 지표")
    for k, v in res.summary.items():
        print(f"{k:<20} {v}")

    for i, (name, table) in enumerate(res.tables.items(), start=3):
        section(f"{i}. {name}")
        print(table)

    charts = analyzer.build_charts(res, start, end)
    for i, (name, fig) in enumerate(charts.items(), start=1):
        fig.savefig(OUT / f"{i:02d}_{name.replace('·', '_').replace(' ', '_')}.png", dpi=150)
    res.df.to_csv(OUT / "sp500_cleaned.csv", encoding="utf-8-sig")
    analyzer.export_excel(res, charts, OUT / "SP500_분석결과.xlsx")
    print(f"\n정제 CSV / 차트 PNG / 엑셀 저장 완료 -> {OUT}")


if __name__ == "__main__":
    main()
