"""
07_dashboard_export.py  --  AP8: Export fuer Power BI

Was dieses Skript tut:
  1. Liest data/processed/portfolio_el.parquet (alle Kredite mit Score, PD, LGD, EAD, EL)
  2. Ergaenzt Dashboard-Spalten: Ausgabejahr, Quartal, Reifegrad-Flag, Einkommens-, DTI- und FICO-Klasse
     (dieselben Klassengrenzen wie in 01_sql/02_default_rates.sql)
  3. Schreibt 03_dashboard/scored_portfolio.csv (eine Zeile je Kredit, nur die Dashboard-Spalten)
  4. Schreibt 03_dashboard/model_quality.csv (Kennzahlen fuer Seite 3) und kopiert die statischen
     Charts fuer Seite 3 nach 03_dashboard/figures/

Aufruf aus dem Repo-Root:
    .venv/Scripts/python.exe 02_python/07_dashboard_export.py
"""

import shutil

import numpy as np
import pandas as pd

from common import DASHBOARD_DIR, DATA_END_DATE, FIGURES_DIR, PROCESSED_DIR, REPORTS_DIR

PORTFOLIO_EL_PARQUET = PROCESSED_DIR / "portfolio_el.parquet"
SCORED_PORTFOLIO_CSV = DASHBOARD_DIR / "scored_portfolio.csv"
MODEL_QUALITY_CSV = DASHBOARD_DIR / "model_quality.csv"
DASHBOARD_FIGURES = DASHBOARD_DIR / "figures"
CHARTS_FOR_PAGE_3 = ["roc_curve.png", "calibration_plot.png", "score_distribution.png", "ks_plot.png",
                     "cutoff_curve_test.png", "cutoff_tradeoff_test.png"]


def band(values: pd.Series, edges: list[float], labels: list[str]) -> pd.Series:
    """Ordnet Werte festen Klassen zu; fehlende Werte bekommen die Klasse 'fehlt'."""
    out = pd.cut(values, bins=[-np.inf] + edges + [np.inf], labels=labels, right=False).astype("object")
    return out.fillna("fehlt")


def main() -> None:
    DASHBOARD_FIGURES.mkdir(parents=True, exist_ok=True)
    p = pd.read_parquet(PORTFOLIO_EL_PARQUET)

    export = pd.DataFrame({
        "loan_id": p["id"],
        "issue_year": p["issue_date"].dt.year,
        "issue_quarter": p["issue_date"].dt.year.astype(str) + "-Q" + p["issue_date"].dt.quarter.astype(str),
        "sample": p["sample"],
        # Reifegrad wie in 01_sql/03_vintage.sql: volle Laufzeit vor Datenende
        "matured": (p["issue_date"] + pd.to_timedelta(p["term_months"] * 30.44, unit="D")
                    <= pd.Timestamp(DATA_END_DATE)).map({True: "ja", False: "nein"}),
        "grade": p["grade"],
        "sub_grade": p["sub_grade"],
        "term_months": p["term_months"],
        "purpose": p["purpose"],
        "addr_state": p["addr_state"],
        "home_ownership": p["home_ownership"],
        "income_band": band(p["annual_inc"], [40000, 60000, 80000, 120000],
                            ["1: unter 40k", "2: 40k bis 60k", "3: 60k bis 80k", "4: 80k bis 120k", "5: ab 120k"]),
        "dti_band": band(p["dti"], [10, 20, 30, 40],
                         ["1: unter 10", "2: 10 bis 20", "3: 20 bis 30", "4: 30 bis 40", "5: ab 40"]),
        "fico_band": band(p["fico_range_low"], [660, 680, 700, 720, 750],
                          ["1: unter 660", "2: 660 bis 679", "3: 680 bis 699", "4: 700 bis 719",
                           "5: 720 bis 749", "6: ab 750"]),
        "funded_amnt": p["funded_amnt"].round(0).astype(int),
        "default": p["default"].astype(int),
        "score": p["score_a"].round(0).astype(int),
        "pd": p["pd_a"].round(5),
        "lgd": p["lgd"].round(4),
        "el": p["el"].round(2),
    })
    export.to_csv(SCORED_PORTFOLIO_CSV, index=False)
    size_mb = SCORED_PORTFOLIO_CSV.stat().st_size / 1_000_000
    print(f"{SCORED_PORTFOLIO_CSV.name}: {len(export):,} Zeilen, {len(export.columns)} Spalten, {size_mb:.1f} MB")

    # Kennzahlen fuer Seite 3 (Modellguete) als kleine Tabelle
    metrics = pd.read_csv(REPORTS_DIR / "model_metrics.csv")
    metrics.to_csv(MODEL_QUALITY_CSV, index=False)
    for name in CHARTS_FOR_PAGE_3:
        shutil.copy(FIGURES_DIR / name, DASHBOARD_FIGURES / name)
    print(f"{MODEL_QUALITY_CSV.name} und {len(CHARTS_FOR_PAGE_3)} Charts nach {DASHBOARD_FIGURES}")

    # Kontrolle: Kernzahlen aus dem Export muessen zu AP7 passen
    test = export[export["sample"] == "test"]
    approved = test[test["score"] >= 515]
    print(f"Kontrolle Test, Cutoff 515: EL-Rate ohne Cutoff {100 * test['el'].sum() / test['funded_amnt'].sum():.2f} %, "
          f"mit Cutoff {100 * approved['el'].sum() / approved['funded_amnt'].sum():.2f} %, "
          f"Annahmequote {100 * len(approved) / len(test):.1f} %")


if __name__ == "__main__":
    main()
