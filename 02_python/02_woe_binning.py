"""
02_woe_binning.py  --  AP3: Feature-Aufbereitung, zeitbasierter Split, WoE-Binning, Information Value

Was dieses Skript tut, in Reihenfolge:
  1. Laedt loans_clean.parquet (nur Modellspalten) und leitet zwei Merkmale ab
     (credit_history_months, loan_to_income), siehe common.load_model_frame()
  2. Zeitbasierter Train/Test-Split ueber issue_date (Schnitt: common.SPLIT_DATE)
  3. WoE-Binning mit optbinning auf den Trainingsdaten, fuer Modell A (ohne grade/int_rate)
     und zusaetzlich fuer die drei Benchmark-Merkmale grade, sub_grade, int_rate
  4. Information Value je Variable, Leckage-Warnung bei IV > 0,5, Auswahl bei IV >= 0,02
  5. Schreibt reports/iv_table.csv, reports/woe_bins.csv, Charts nach reports/figures/
     und den gefitteten Binning-Prozess nach data/processed/binning_process_a.pkl (fuer AP4)

Aufruf aus dem Repo-Root:
    .venv/Scripts/python.exe 02_python/02_woe_binning.py
"""

import time

import matplotlib
matplotlib.use("Agg")  # Charts nur in Dateien schreiben, kein Fenster
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from optbinning import BinningProcess

from common import (
    BENCHMARK_CATEGORICAL, BENCHMARK_NUMERIC, CATEGORICAL_FEATURES, FIGURES_DIR,
    MODEL_A_FEATURES, NUMERIC_FEATURES, PROCESSED_DIR, REPORTS_DIR, SPLIT_DATE,
    load_model_frame,
)

IV_TABLE_CSV = REPORTS_DIR / "iv_table.csv"
WOE_BINS_CSV = REPORTS_DIR / "woe_bins.csv"
BINNING_PICKLE = PROCESSED_DIR / "binning_process_a.pkl"
SPLIT_PARQUET = PROCESSED_DIR / "split.parquet"

# Uebliche IV-Schwellen in der Scorecard-Praxis
IV_MIN_KEEP = 0.02      # darunter: nicht praediktiv, raus
IV_LEAKAGE_WARNING = 0.5  # darueber: verdaechtig, auf Leckage pruefen

# ENTSCHEIDUNG: Binning-Parameter. Hoechstens 10 Bins je Variable, jeder Bin mindestens
# 2 % der Trainingsdaten, und bei Zahlenvariablen muss die Ausfallquote ueber die Bins
# monoton steigen oder fallen ("auto_asc_desc"). Monotonie kostet etwas Trennschaerfe,
# macht die Scorecard aber fachlich erklaerbar: mehr Verschuldung darf nie Punkte bringen.
BINNING_PARAMS = {"max_n_bins": 10, "min_bin_size": 0.02}
NUMERIC_FIT_PARAMS = {"monotonic_trend": "auto_asc_desc"}


def fit_binning(X: pd.DataFrame, y: pd.Series, numeric: list[str], categorical: list[str]) -> BinningProcess:
    """Fittet einen optbinning-BinningProcess. Fehlende Werte bekommen automatisch einen eigenen Bin."""
    variables = numeric + categorical
    fit_params = {v: NUMERIC_FIT_PARAMS for v in numeric}
    process = BinningProcess(
        variable_names=variables,
        categorical_variables=categorical,
        binning_fit_params=fit_params,
        **BINNING_PARAMS,
    )
    process.fit(X[variables], y)
    return process


def collect_bins(process: BinningProcess, variables: list[str], model_label: str) -> pd.DataFrame:
    """Sammelt die Binning-Tabellen aller Variablen in einem DataFrame (fuer woe_bins.csv)."""
    frames = []
    for var in variables:
        table = process.get_binned_variable(var).binning_table.build()
        table = table[table["Bin"].astype(str).str.strip() != "Totals"].copy()
        table.insert(0, "variable", var)
        table.insert(0, "model", model_label)
        frames.append(table[["model", "variable", "Bin", "Count", "Count (%)", "Non-event", "Event",
                             "Event rate", "WoE", "IV"]])
    return pd.concat(frames, ignore_index=True)


def plot_iv_ranking(iv_table: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 10))
    data = iv_table.sort_values("iv")
    colors = ["#c0392b" if m == "benchmark" else "#2c3e50" for m in data["model"]]
    ax.barh(data["variable"], data["iv"], color=colors)
    ax.axvline(IV_MIN_KEEP, color="grey", linestyle="--", linewidth=1)
    ax.axvline(IV_LEAKAGE_WARNING, color="red", linestyle="--", linewidth=1)
    ax.set_xlabel("Information Value (Train, 2007-2015)")
    ax.set_title("IV je Variable. Dunkel: Modell A, rot: Benchmark (grade, sub_grade, int_rate)\n"
                 "gestrichelt: 0,02 (Mindestwert) und 0,5 (Leckage-Warnung)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "iv_ranking.png", dpi=120)
    plt.close(fig)


def plot_woe(process: BinningProcess, var: str) -> None:
    table = process.get_binned_variable(var).binning_table.build()
    table = table[~table["Bin"].astype(str).str.strip().isin(["Totals"])]
    table = table[table["Count"] > 0]
    fig, ax1 = plt.subplots(figsize=(9, 4.5))
    labels = [str(b)[:28] for b in table["Bin"]]
    ax1.bar(labels, table["Count (%)"] * 100, color="#bdc3c7")
    ax1.set_ylabel("Anteil Kredite (%)")
    ax1.tick_params(axis="x", rotation=45)
    for label in ax1.get_xticklabels():
        label.set_horizontalalignment("right")
    ax2 = ax1.twinx()
    ax2.plot(labels, table["Event rate"] * 100, color="#c0392b", marker="o")
    ax2.set_ylabel("Ausfallquote (%)", color="#c0392b")
    ax1.set_title(f"{var}: Bins, Anteil und Ausfallquote (Train)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / f"woe_{var}.png", dpi=120)
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ----------------------------------------------------------------------------------
    # Schritt 1 und 2: Daten laden, zeitbasierter Split
    # ----------------------------------------------------------------------------------
    df = load_model_frame()
    train = df[df["sample"] == "train"]
    test = df[df["sample"] == "test"]

    # Kontrolle: Der Split ist wirklich zeitlich, kein Kredit im Test ist aelter als einer im Training
    assert train["issue_date"].max() < test["issue_date"].min(), "Split ist nicht zeitbasiert!"
    assert train["issue_date"].max() < pd.Timestamp(SPLIT_DATE) <= test["issue_date"].min()

    print(f"Geladen: {len(df):,} Kredite, {len(df.columns)} Spalten, {time.time() - t0:.0f} s")
    print(f"Split bei {SPLIT_DATE}:")
    print(f"  Train: {len(train):,} Kredite, {train['issue_date'].min():%Y-%m} bis "
          f"{train['issue_date'].max():%Y-%m}, Ausfallquote {100 * train['default'].mean():.2f} %")
    print(f"  Test:  {len(test):,} Kredite, {test['issue_date'].min():%Y-%m} bis "
          f"{test['issue_date'].max():%Y-%m}, Ausfallquote {100 * test['default'].mean():.2f} %")

    df[["id", "sample"]].to_parquet(SPLIT_PARQUET, index=False)

    # ----------------------------------------------------------------------------------
    # Schritt 3: Binning auf Train, Modell A und Benchmark-Merkmale getrennt
    # ----------------------------------------------------------------------------------
    y_train = train["default"].astype(int)

    print("\nBinning Modell A (ohne grade/sub_grade/int_rate) ...")
    t1 = time.time()
    process_a = fit_binning(train, y_train, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    print(f"  fertig in {time.time() - t1:.0f} s, {len(MODEL_A_FEATURES)} Variablen")

    print("Binning Benchmark-Merkmale (grade, sub_grade, int_rate) ...")
    process_b = fit_binning(train, y_train, BENCHMARK_NUMERIC, BENCHMARK_CATEGORICAL)

    # ----------------------------------------------------------------------------------
    # Schritt 4: IV-Tabelle, Warnungen, Auswahl
    # ----------------------------------------------------------------------------------
    summary_a = process_a.summary()[["name", "dtype", "n_bins", "iv", "status"]].assign(model="model_a")
    summary_b = process_b.summary()[["name", "dtype", "n_bins", "iv", "status"]].assign(model="benchmark")
    iv_table = pd.concat([summary_a, summary_b], ignore_index=True).rename(columns={"name": "variable"})
    iv_table["iv"] = iv_table["iv"].astype(float).round(4)

    def iv_class(iv: float) -> str:
        if iv < 0.02:
            return "nicht praediktiv"
        if iv < 0.1:
            return "schwach"
        if iv < 0.3:
            return "mittel"
        if iv < 0.5:
            return "stark"
        return "verdaechtig stark (Leckage pruefen)"

    iv_table["iv_class"] = iv_table["iv"].apply(iv_class)
    # ENTSCHEIDUNG: Auswahl der Modellvariablen rein nach IV >= 0,02 (uebliche Mindestschwelle).
    # Variablen mit IV > 0,5 werden NICHT automatisch entfernt, sondern gemeldet: Die
    # Entscheidung, ob es Leckage ist, trifft ein Mensch (siehe reports/findings.md).
    iv_table["selected_model_a"] = (iv_table["model"] == "model_a") & (iv_table["iv"] >= IV_MIN_KEEP)
    iv_table = iv_table.sort_values(["model", "iv"], ascending=[False, False]).reset_index(drop=True)
    iv_table.to_csv(IV_TABLE_CSV, index=False)

    print("\n=== IV-Tabelle (Train) ===")
    print(iv_table.to_string(index=False))

    leakage_a = iv_table[(iv_table["model"] == "model_a") & (iv_table["iv"] > IV_LEAKAGE_WARNING)]
    leakage_b = iv_table[(iv_table["model"] == "benchmark") & (iv_table["iv"] > IV_LEAKAGE_WARNING)]
    print("\n=== Leckage-Check (IV > 0,5) ===")
    if leakage_a.empty:
        print("Modell A: keine Variable ueber 0,5. OK.")
    else:
        print("Modell A: WARNUNG, folgende Variablen liegen ueber 0,5 und muessen geprueft werden:")
        print(leakage_a[["variable", "iv"]].to_string(index=False))
    if not leakage_b.empty:
        print("Benchmark: folgende Variablen liegen ueber 0,5. Das ist hier erwartet, weil grade/"
              "sub_grade/int_rate Lending Clubs eigenes Modell sind, keine Leckage:")
        print(leakage_b[["variable", "iv"]].to_string(index=False))

    failed = iv_table[iv_table["status"] != "OPTIMAL"]
    print("\n=== Loeser-Status ===")
    if failed.empty:
        print("Alle Variablen mit Status OPTIMAL gebinnt.")
    else:
        print("Nicht optimal geloest:")
        print(failed[["variable", "status"]].to_string(index=False))

    n_selected = int(iv_table["selected_model_a"].sum())
    dropped = iv_table[(iv_table["model"] == "model_a") & (~iv_table["selected_model_a"])]["variable"].tolist()
    print(f"\nModell A: {n_selected} von {len(MODEL_A_FEATURES)} Variablen ausgewaehlt (IV >= {IV_MIN_KEEP}).")
    print(f"Entfernt wegen IV < {IV_MIN_KEEP}: {dropped}")

    # ----------------------------------------------------------------------------------
    # Schritt 5: Bins, Charts, Binning-Prozess speichern
    # ----------------------------------------------------------------------------------
    bins = pd.concat([
        collect_bins(process_a, MODEL_A_FEATURES, "model_a"),
        collect_bins(process_b, BENCHMARK_NUMERIC + BENCHMARK_CATEGORICAL, "benchmark"),
    ], ignore_index=True)
    bins.to_csv(WOE_BINS_CSV, index=False)

    plot_iv_ranking(iv_table)
    top5 = iv_table[iv_table["model"] == "model_a"].head(5)["variable"].tolist()
    for var in top5:
        plot_woe(process_a, var)
    print(f"\nWoE-Charts fuer die 5 staerksten Variablen: {top5}")

    print("\n=== Binning-Tabellen der 5 staerksten Variablen (Train) ===")
    for var in top5:
        table = process_a.get_binned_variable(var).binning_table.build()
        print(f"\n--- {var} ---")
        print(table[["Bin", "Count", "Count (%)", "Event rate", "WoE", "IV"]].to_string(index=False))

    process_a.save(str(BINNING_PICKLE))
    print(f"\nBinning-Prozess Modell A gespeichert: {BINNING_PICKLE}")
    print(f"Gesamtlaufzeit {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
