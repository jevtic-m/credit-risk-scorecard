"""
03_scorecard.py  --  AP4: Scorecard bauen (logistische Regression auf WoE, PDO-Skalierung)

Was dieses Skript tut, in Reihenfolge:
  1. Laedt die Modelldaten (common.load_model_frame) und die Variablenauswahl aus reports/iv_table.csv
  2. Modell A (Hauptmodell): Binning + logistische Regression auf den 17 ausgewaehlten Variablen,
     ohne grade / sub_grade / int_rate. Skalierung: PDO 20, 600 Punkte bei Odds 50:1.
  3. Modell B (Benchmark): dieselben Variablen plus grade, sub_grade, int_rate, installment
  4. Scorecard-Tabellen (Punkte je Bin) nach reports/scorecard_table_a.csv und _b.csv
  5. Score und PD fuer alle 1,35 Mio. Kredite nach data/processed/scored_loans.parquet
     (Grundlage fuer AP5 bis AP8), Modelle als Pickle nach data/processed/
  6. Ein Rechenbeispiel "von der PD zum Score-Punkt" fuer einen Kredit

Aufruf aus dem Repo-Root:
    .venv/Scripts/python.exe 02_python/03_scorecard.py
"""

import pickle
import time

import numpy as np
import pandas as pd
from optbinning import BinningProcess, Scorecard
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from common import (
    BENCHMARK_CATEGORICAL, BENCHMARK_NUMERIC, CATEGORICAL_FEATURES, NUMERIC_FEATURES, PDO,
    PROCESSED_DIR, REFERENCE_ODDS, REPORTS_DIR, SCORE_AT_REFERENCE_ODDS, clean_bin_label,
    load_model_frame,
)

IV_TABLE_CSV = REPORTS_DIR / "iv_table.csv"
SCORECARD_A_CSV = REPORTS_DIR / "scorecard_table_a.csv"
SCORECARD_B_CSV = REPORTS_DIR / "scorecard_table_b.csv"
SCORED_PARQUET = PROCESSED_DIR / "scored_loans.parquet"
MODEL_A_PICKLE = PROCESSED_DIR / "scorecard_a.pkl"
MODEL_B_PICKLE = PROCESSED_DIR / "scorecard_b.pkl"

# Dieselben Binning-Parameter wie in 02_woe_binning.py, damit die Bins identisch sind
BINNING_PARAMS = {"max_n_bins": 10, "min_bin_size": 0.02}
NUMERIC_FIT_PARAMS = {"monotonic_trend": "auto_asc_desc"}

# Spalten, die zur Auswertung und fuers Dashboard mit in die Score-Datei kommen
CARRY_COLUMNS = [
    "id", "sample", "default", "issue_date", "funded_amnt", "loan_amnt", "term_months",
    "grade", "sub_grade", "int_rate", "purpose", "addr_state", "home_ownership",
    "annual_inc", "dti", "fico_range_low",
]


def build_scorecard(numeric: list[str], categorical: list[str]) -> Scorecard:
    """Baut eine (noch nicht gefittete) Scorecard: Binning + logistische Regression + PDO-Skalierung."""
    binning = BinningProcess(
        variable_names=numeric + categorical,
        categorical_variables=categorical,
        binning_fit_params={v: NUMERIC_FIT_PARAMS for v in numeric},
        **BINNING_PARAMS,
    )
    # ENTSCHEIDUNG: Logistische Regression ohne starke Regularisierung (C = 1, Standard) und
    # ohne Klassengewichte. Mit 17 WoE-Variablen und 830.000 Zeilen besteht keine Gefahr der
    # Ueberanpassung, und ungewichtet bleiben die vorhergesagten PDs im Mittel auf dem Niveau
    # der echten Ausfallquote (wichtig fuer die Kalibrierung und die EL-Rechnung in AP6).
    estimator = LogisticRegression(max_iter=1000, solver="lbfgs")
    return Scorecard(
        binning_process=binning,
        estimator=estimator,
        scaling_method="pdo_odds",
        scaling_method_params={
            "pdo": PDO,
            "odds": REFERENCE_ODDS,
            "scorecard_points": SCORE_AT_REFERENCE_ODDS,
        },
        # rounding=True: ganze Punkte je Bin, wie in einer echten Scorecard
        rounding=True,
    )


def scorecard_table(model: Scorecard, label: str) -> pd.DataFrame:
    table = model.table(style="detailed")
    table["Bin"] = table["Bin"].apply(clean_bin_label)
    table.insert(0, "model", label)
    keep = ["model", "Variable", "Bin", "Count", "Count (%)", "Event rate", "WoE", "Coefficient", "Points"]
    return table[keep].rename(columns={"Bin": "bin", "Variable": "variable"})


def main() -> None:
    t0 = time.time()
    df = load_model_frame()
    train = df[df["sample"] == "train"]
    test = df[df["sample"] == "test"]
    y_train = train["default"].astype(int)
    y_test = test["default"].astype(int)

    # Variablenauswahl aus AP3 (IV >= 0,02)
    iv_table = pd.read_csv(IV_TABLE_CSV)
    selected = iv_table.loc[iv_table["selected_model_a"], "variable"].tolist()
    numeric_a = [v for v in NUMERIC_FEATURES if v in selected]
    categorical_a = [v for v in CATEGORICAL_FEATURES if v in selected]
    print(f"Modell A: {len(selected)} Variablen aus reports/iv_table.csv")
    print(f"  numerisch:   {numeric_a}")
    print(f"  kategorisch: {categorical_a}")

    # ----------------------------------------------------------------------------------
    # Modell A: Hauptmodell ohne grade / sub_grade / int_rate
    # ----------------------------------------------------------------------------------
    # ENTSCHEIDUNG: Vorzeichen-Regel. WoE ist so definiert, dass ein hoher WoE weniger Ausfaelle
    # bedeutet, also muss jeder Koeffizient negativ sein. Wird ein Koeffizient positiv, dann
    # bekommt die Variable in der Scorecard Punkte in die falsche Richtung (z. B. mehr Punkte
    # fuer groessere Kredite). Das passiert bei Variablen, die stark mit einer anderen
    # zusammenhaengen (loan_amnt steckt schon in loan_to_income). Solche Variablen werden
    # nacheinander entfernt, jeweils die mit dem groessten positiven Koeffizienten, bis alle
    # Vorzeichen stimmen. Alternative waere, sie zu behalten und nur den AUC anzuschauen; das
    # gaebe eine Scorecard, die niemand einem Kunden erklaeren koennte.
    removed_for_sign = []
    while True:
        print(f"\nFitte Modell A mit {len(numeric_a) + len(categorical_a)} Variablen ...")
        t1 = time.time()
        model_a = build_scorecard(numeric_a, categorical_a)
        model_a.fit(train[numeric_a + categorical_a], y_train)
        print(f"  fertig in {time.time() - t1:.0f} s")
        coefs = pd.Series(model_a.estimator_.coef_[0], index=numeric_a + categorical_a)
        positive = coefs[coefs > 0].sort_values(ascending=False)
        if positive.empty:
            break
        worst = positive.index[0]
        print(f"  Positiver Koeffizient bei {worst} ({positive.iloc[0]:+.4f}), Variable wird entfernt.")
        removed_for_sign.append((worst, round(float(positive.iloc[0]), 4)))
        numeric_a = [v for v in numeric_a if v != worst]
        categorical_a = [v for v in categorical_a if v != worst]
    if removed_for_sign:
        print(f"Wegen falschem Vorzeichen entfernt: {removed_for_sign}")
    print(f"Modell A endgueltig: {len(numeric_a) + len(categorical_a)} Variablen")

    # ----------------------------------------------------------------------------------
    # Modell B: Benchmark mit Lending Clubs eigener Einstufung
    # ----------------------------------------------------------------------------------
    numeric_b = numeric_a + BENCHMARK_NUMERIC + ["installment"]
    categorical_b = categorical_a + BENCHMARK_CATEGORICAL
    print("Fitte Modell B (Benchmark mit grade, sub_grade, int_rate, installment) ...")
    t1 = time.time()
    model_b = build_scorecard(numeric_b, categorical_b)
    model_b.fit(train[numeric_b + categorical_b], y_train)
    print(f"  fertig in {time.time() - t1:.0f} s")

    # ----------------------------------------------------------------------------------
    # Scorecard-Tabellen
    # ----------------------------------------------------------------------------------
    table_a = scorecard_table(model_a, "model_a")
    table_b = scorecard_table(model_b, "model_b")
    table_a.to_csv(SCORECARD_A_CSV, index=False)
    table_b.to_csv(SCORECARD_B_CSV, index=False)

    print("\n=== Scorecard Modell A (Punkte je Bin) ===")
    print(table_a[["variable", "bin", "Count (%)", "Event rate", "WoE", "Coefficient", "Points"]]
          .to_string(index=False))

    coef_a = pd.DataFrame({
        "variable": numeric_a + categorical_a,
        "coefficient": model_a.estimator_.coef_[0],
    }).sort_values("coefficient")
    print("\n=== Koeffizienten Modell A (Log-Odds des Ausfalls je Einheit WoE) ===")
    print(f"Intercept: {model_a.estimator_.intercept_[0]:.4f}")
    print(coef_a.to_string(index=False))
    # Plausibilitaet: WoE ist so definiert, dass hoher WoE = weniger Ausfaelle. Der Koeffizient
    # jeder Variable muss deshalb negativ sein. Ein positiver Koeffizient waere ein Warnsignal
    # (Multikollinearitaet oder Vorzeichenfehler).
    wrong_sign = coef_a[coef_a["coefficient"] > 0]
    if wrong_sign.empty:
        print("Alle Koeffizienten negativ, Vorzeichen plausibel.")
    else:
        print("WARNUNG, positive Koeffizienten (pruefen):")
        print(wrong_sign.to_string(index=False))

    # ----------------------------------------------------------------------------------
    # Score und PD fuer alle Kredite
    # ----------------------------------------------------------------------------------
    scored = df[CARRY_COLUMNS].copy()
    scored["score_a"] = model_a.score(df[numeric_a + categorical_a])
    scored["pd_a"] = model_a.predict_proba(df[numeric_a + categorical_a])[:, 1]
    scored["score_b"] = model_b.score(df[numeric_b + categorical_b])
    scored["pd_b"] = model_b.predict_proba(df[numeric_b + categorical_b])[:, 1]
    scored.to_parquet(SCORED_PARQUET, index=False)

    # Sinnrichtung pruefen: hoeherer Score muss niedrigere PD bedeuten
    corr = np.corrcoef(scored["score_a"], scored["pd_a"])[0, 1]
    assert corr < 0, "Score und PD laufen in dieselbe Richtung, reverse_scorecard pruefen!"

    print("\n=== Score-Verteilung Modell A ===")
    print(scored.groupby("sample")["score_a"].describe().round(1).to_string())

    # Erste Guete-Zahlen (die vollstaendige Auswertung folgt in AP5)
    print("\n=== AUC (vollstaendige Guete in AP5) ===")
    for label, col in [("Modell A", "pd_a"), ("Modell B", "pd_b")]:
        auc_train = roc_auc_score(y_train, scored.loc[train.index, col])
        auc_test = roc_auc_score(y_test, scored.loc[test.index, col])
        print(f"{label}: AUC Train {auc_train:.4f}, AUC Test {auc_test:.4f}")

    # ----------------------------------------------------------------------------------
    # Rechenbeispiel: von der PD zum Score
    # ----------------------------------------------------------------------------------
    factor = PDO / np.log(2)
    offset = SCORE_AT_REFERENCE_ODDS - factor * np.log(REFERENCE_ODDS)
    example = scored.loc[test.index].iloc[0]
    odds_good = (1 - example["pd_a"]) / example["pd_a"]
    print("\n=== Rechenbeispiel: von der PD zum Score (Modell A) ===")
    print(f"Factor = PDO / ln(2) = {PDO} / {np.log(2):.4f} = {factor:.4f}")
    print(f"Offset = {SCORE_AT_REFERENCE_ODDS} - Factor * ln({REFERENCE_ODDS}) = {offset:.4f}")
    print(f"Kredit id {int(example['id'])}: PD = {example['pd_a']:.4f}, "
          f"Odds gut:schlecht = {odds_good:.2f}")
    print(f"Score = Offset + Factor * ln(Odds) = {offset:.2f} + {factor:.2f} * {np.log(odds_good):.4f} "
          f"= {offset + factor * np.log(odds_good):.1f}")
    print(f"Scorecard-Summe der Punkte (gerundete Bins): {example['score_a']:.1f}")

    with open(MODEL_A_PICKLE, "wb") as f:
        pickle.dump(model_a, f)
    with open(MODEL_B_PICKLE, "wb") as f:
        pickle.dump(model_b, f)
    print(f"\nGespeichert: {SCORED_PARQUET.name}, {MODEL_A_PICKLE.name}, {MODEL_B_PICKLE.name}, "
          f"{SCORECARD_A_CSV.name}, {SCORECARD_B_CSV.name}")
    print(f"Gesamtlaufzeit {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
