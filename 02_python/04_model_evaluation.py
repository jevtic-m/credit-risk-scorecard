"""
04_model_evaluation.py  --  AP5: Modellguete (AUC, Gini, KS, Kalibrierung, Boosting-Vergleich, PSI)

Was dieses Skript tut, in Reihenfolge:
  1. Laedt data/processed/scored_loans.parquet (Score und PD aus AP4 fuer alle Kredite)
  2. Trennschaerfe je Modell und Stichprobe: AUC, Gini = 2*AUC-1, KS-Statistik, Brier-Score
  3. Kalibrierung: vorhergesagte PD gegen beobachtete Ausfallquote je PD-Dezil und je Testjahr
  4. Score-Verteilung Good vs. Bad, ROC-Kurve, KS-Plot, Kalibrierungsplot nach reports/figures/
  5. Benchmark Gradient Boosting (HistGradientBoosting) auf denselben 15 Rohvariablen wie Modell A
  6. PSI (Population Stability Index) der Score-Verteilung Train gegen Test
  7. Schreibt reports/model_metrics.csv, reports/calibration_table.csv, reports/psi_table.csv

Aufruf aus dem Repo-Root:
    .venv/Scripts/python.exe 02_python/04_model_evaluation.py
"""

import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

from common import (
    CATEGORICAL_FEATURES, FIGURES_DIR, NUMERIC_FEATURES, PROCESSED_DIR, REPORTS_DIR,
    load_model_frame,
)

SCORED_PARQUET = PROCESSED_DIR / "scored_loans.parquet"
SCORECARD_A_CSV = REPORTS_DIR / "scorecard_table_a.csv"
METRICS_CSV = REPORTS_DIR / "model_metrics.csv"
CALIBRATION_CSV = REPORTS_DIR / "calibration_table.csv"
PSI_CSV = REPORTS_DIR / "psi_table.csv"

# Vorab festgelegter Erwartungsbereich fuer Lending-Club-Daten ohne grade/int_rate
AUC_EXPECTED_LOW, AUC_EXPECTED_HIGH, AUC_LEAKAGE = 0.68, 0.72, 0.85


def ks_statistic(y_true: pd.Series, score_bad: pd.Series) -> float:
    """KS = groesster Abstand der kumulierten Verteilungen von Guten und Schlechten."""
    fpr, tpr, _ = roc_curve(y_true, score_bad)
    return float(np.max(tpr - fpr))


def discrimination_metrics(y: pd.Series, pd_pred: pd.Series) -> dict:
    auc = roc_auc_score(y, pd_pred)
    return {
        "auc": round(auc, 4),
        "gini": round(2 * auc - 1, 4),
        "ks": round(ks_statistic(y, pd_pred), 4),
        "brier": round(brier_score_loss(y, pd_pred), 4),
        "mean_pd": round(float(pd_pred.mean()), 4),
        "observed_rate": round(float(y.mean()), 4),
        "n": int(len(y)),
    }


def calibration_table(y: pd.Series, pd_pred: pd.Series, label: str, n_bins: int = 10) -> pd.DataFrame:
    """Je PD-Dezil: mittlere vorhergesagte PD und beobachtete Ausfallquote."""
    frame = pd.DataFrame({"y": y.values, "pd": pd_pred.values})
    frame["decile"] = pd.qcut(frame["pd"], n_bins, labels=False, duplicates="drop") + 1
    out = frame.groupby("decile").agg(
        loans=("y", "size"), predicted_pd=("pd", "mean"), observed_rate=("y", "mean"),
        pd_min=("pd", "min"), pd_max=("pd", "max"),
    ).reset_index()
    out["ratio_observed_to_predicted"] = out["observed_rate"] / out["predicted_pd"]
    out.insert(0, "segment", label)
    return out.round(4)


def psi(expected: pd.Series, actual: pd.Series, n_bins: int = 10) -> tuple[float, pd.DataFrame]:
    """PSI mit Bins aus den Dezilen der Referenz (Train). < 0,1 stabil, > 0,25 kritisch."""
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, n_bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    exp_share = np.histogram(expected, bins=edges)[0] / len(expected)
    act_share = np.histogram(actual, bins=edges)[0] / len(actual)
    # Kleine Konstante gegen Division durch null
    exp_share = np.clip(exp_share, 1e-6, None)
    act_share = np.clip(act_share, 1e-6, None)
    contrib = (act_share - exp_share) * np.log(act_share / exp_share)
    table = pd.DataFrame({
        "bin_lower": edges[:-1], "bin_upper": edges[1:],
        "train_share": exp_share.round(4), "test_share": act_share.round(4),
        "psi_contribution": contrib.round(5),
    })
    return float(contrib.sum()), table


def plot_roc(test: pd.DataFrame, gb_pd: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    for label, pred in [("Modell A (Scorecard, ohne grade)", test["pd_a"]),
                        ("Modell B (Benchmark mit grade/int_rate)", test["pd_b"]),
                        ("Gradient Boosting (gleiche Variablen wie A)", gb_pd)]:
        fpr, tpr, _ = roc_curve(test["default"], pred)
        ax.plot(fpr, tpr, label=f"{label}: AUC {roc_auc_score(test['default'], pred):.3f}")
    ax.plot([0, 1], [0, 1], color="grey", linestyle="--", linewidth=1)
    ax.set_xlabel("Anteil faelschlich abgelehnte Gute (FPR)")
    ax.set_ylabel("Anteil erkannte Ausfaelle (TPR)")
    ax.set_title("ROC-Kurven, Test 2016-2018")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "roc_curve.png", dpi=120)
    plt.close(fig)


def plot_score_distribution(test: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bins = np.arange(440, 630, 5)
    ax.hist(test.loc[test["default"] == 0, "score_a"], bins=bins, density=True, alpha=0.6,
            color="#2c3e50", label="Zurueckgezahlt (Good)")
    ax.hist(test.loc[test["default"] == 1, "score_a"], bins=bins, density=True, alpha=0.6,
            color="#c0392b", label="Ausgefallen (Bad)")
    ax.set_xlabel("Score Modell A")
    ax.set_ylabel("Dichte")
    ax.set_title("Score-Verteilung Good vs. Bad, Test 2016-2018")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "score_distribution.png", dpi=120)
    plt.close(fig)


def plot_ks(test: pd.DataFrame) -> None:
    scores = np.sort(test["score_a"].unique())
    good = test.loc[test["default"] == 0, "score_a"]
    bad = test.loc[test["default"] == 1, "score_a"]
    cum_good = np.searchsorted(np.sort(good), scores, side="right") / len(good)
    cum_bad = np.searchsorted(np.sort(bad), scores, side="right") / len(bad)
    gap = cum_bad - cum_good
    k = int(np.argmax(gap))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(scores, cum_bad, color="#c0392b", label="kumuliert Bad")
    ax.plot(scores, cum_good, color="#2c3e50", label="kumuliert Good")
    ax.vlines(scores[k], cum_good[k], cum_bad[k], color="black", linestyle="--",
              label=f"KS = {gap[k]:.3f} bei Score {scores[k]:.0f}")
    ax.set_xlabel("Score Modell A")
    ax.set_ylabel("kumulierter Anteil")
    ax.set_title("KS-Plot, Test 2016-2018")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "ks_plot.png", dpi=120)
    plt.close(fig)


def plot_calibration(cal: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    for segment, marker in [("train", "s"), ("test", "o"), ("test_2016", "^"), ("test_2017", "v"),
                            ("test_2018", "d")]:
        part = cal[cal["segment"] == segment]
        if part.empty:
            continue
        ax.plot(part["predicted_pd"], part["observed_rate"], marker=marker, label=segment)
    lim = max(cal["predicted_pd"].max(), cal["observed_rate"].max()) * 1.05
    ax.plot([0, lim], [0, lim], color="grey", linestyle="--", linewidth=1, label="perfekt kalibriert")
    ax.set_xlabel("vorhergesagte PD (Mittel je Dezil)")
    ax.set_ylabel("beobachtete Ausfallquote")
    ax.set_title("Kalibrierung Modell A je PD-Dezil")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "calibration_plot.png", dpi=120)
    plt.close(fig)


def main() -> None:
    t0 = time.time()
    scored = pd.read_parquet(SCORED_PARQUET)
    train = scored[scored["sample"] == "train"]
    test = scored[scored["sample"] == "test"]

    # ----------------------------------------------------------------------------------
    # Schritt 2: Trennschaerfe
    # ----------------------------------------------------------------------------------
    rows = []
    for model, col in [("model_a", "pd_a"), ("model_b", "pd_b")]:
        for sample, part in [("train", train), ("test", test)]:
            rows.append({"model": model, "sample": sample, **discrimination_metrics(part["default"], part[col])})

    # ----------------------------------------------------------------------------------
    # Schritt 5: Gradient Boosting auf denselben Rohvariablen wie Modell A
    # ----------------------------------------------------------------------------------
    # ENTSCHEIDUNG: Das Boosting bekommt exakt die 15 Variablen des Hauptmodells (Rohwerte, keine
    # WoE), damit der Vergleich zeigt, was der Algorithmus bringt und nicht zusaetzliche Daten.
    # Fehlende Werte verarbeitet HistGradientBoosting nativ. Keine Hyperparameter-Suche:
    # Es ist ein Benchmark, kein Produktivmodell.
    features_a = pd.read_csv(SCORECARD_A_CSV)["variable"].unique().tolist()
    numeric_a = [v for v in NUMERIC_FEATURES if v in features_a]
    categorical_a = [v for v in CATEGORICAL_FEATURES if v in features_a]
    print(f"Boosting-Benchmark auf {len(features_a)} Variablen: {features_a}")

    frame = load_model_frame()
    frame = frame.set_index("id").loc[scored["id"].values].reset_index()
    X = frame[numeric_a + categorical_a].copy()
    for col in categorical_a:
        X[col] = X[col].astype("category")
    is_train = (frame["sample"] == "train").values
    t1 = time.time()
    booster = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
        categorical_features="from_dtype", random_state=42,
    )
    booster.fit(X[is_train], frame.loc[is_train, "default"].astype(int))
    gb_pd_all = booster.predict_proba(X)[:, 1]
    gb_pd_train = gb_pd_all[is_train]
    gb_pd_test = gb_pd_all[~is_train]
    print(f"Boosting gefittet in {time.time() - t1:.0f} s")
    rows.append({"model": "gradient_boosting", "sample": "train",
                 **discrimination_metrics(frame.loc[is_train, "default"], pd.Series(gb_pd_train))})
    rows.append({"model": "gradient_boosting", "sample": "test",
                 **discrimination_metrics(frame.loc[~is_train, "default"], pd.Series(gb_pd_test))})

    metrics = pd.DataFrame(rows)
    metrics.to_csv(METRICS_CSV, index=False)
    print("\n=== Trennschaerfe und Kalibrierung im Ueberblick ===")
    print(metrics.to_string(index=False))

    # ----------------------------------------------------------------------------------
    # AUC-Pruefung: 0,68 bis 0,72 erwartet, ueber 0,85 = Leckage-Signal
    # ----------------------------------------------------------------------------------
    auc_a_test = float(metrics.query("model == 'model_a' and sample == 'test'")["auc"].iloc[0])
    print("\n=== AUC-Pruefung Modell A (Test) ===")
    if auc_a_test > AUC_LEAKAGE:
        raise SystemExit(f"ABBRUCH: AUC {auc_a_test:.4f} > {AUC_LEAKAGE}. Leckage-Verdacht, bitte melden.")
    if AUC_EXPECTED_LOW <= auc_a_test <= AUC_EXPECTED_HIGH:
        print(f"AUC {auc_a_test:.4f} liegt im erwarteten Bereich {AUC_EXPECTED_LOW} bis {AUC_EXPECTED_HIGH}. OK.")
    else:
        print(f"AUC {auc_a_test:.4f} liegt ausserhalb von {AUC_EXPECTED_LOW} bis {AUC_EXPECTED_HIGH}, "
              f"aber unter der Leckage-Grenze {AUC_LEAKAGE}. Bitte einordnen.")

    # ----------------------------------------------------------------------------------
    # Schritt 3: Kalibrierung Modell A
    # ----------------------------------------------------------------------------------
    cal_parts = [
        calibration_table(train["default"], train["pd_a"], "train"),
        calibration_table(test["default"], test["pd_a"], "test"),
    ]
    for year in (2016, 2017, 2018):
        part = test[test["issue_date"].dt.year == year]
        cal_parts.append(calibration_table(part["default"], part["pd_a"], f"test_{year}"))
    cal_parts.append(calibration_table(test["default"], pd.Series(gb_pd_test, index=test.index),
                                       "test_gradient_boosting"))
    calibration = pd.concat(cal_parts, ignore_index=True)
    calibration.to_csv(CALIBRATION_CSV, index=False)

    print("\n=== Kalibrierung Modell A je PD-Dezil (Test 2016-2018) ===")
    print(calibration[calibration["segment"] == "test"].to_string(index=False))
    print("\n=== Mittlere PD gegen beobachtete Ausfallquote je Segment ===")
    summary = []
    for segment, part in [("train", train), ("test", test)] + [
        (f"test_{y}", test[test["issue_date"].dt.year == y]) for y in (2016, 2017, 2018)
    ]:
        summary.append({"segment": segment, "loans": len(part),
                        "mean_pd_a": round(part["pd_a"].mean(), 4),
                        "observed_rate": round(part["default"].mean(), 4),
                        "ratio": round(part["default"].mean() / part["pd_a"].mean(), 3)})
    print(pd.DataFrame(summary).to_string(index=False))

    # ----------------------------------------------------------------------------------
    # Schritt 6: PSI Train gegen Test
    # ----------------------------------------------------------------------------------
    psi_score, psi_table = psi(train["score_a"], test["score_a"])
    psi_table.insert(0, "variable", "score_a")
    psi_table.to_csv(PSI_CSV, index=False)
    verdict = "stabil" if psi_score < 0.1 else ("leicht verschoben" if psi_score < 0.25 else "kritisch")
    print(f"\n=== PSI Score Modell A, Train (2007-2015) gegen Test (2016-2018): {psi_score:.4f} ({verdict}) ===")
    print(psi_table.to_string(index=False))

    # ----------------------------------------------------------------------------------
    # Schritt 4: Charts
    # ----------------------------------------------------------------------------------
    plot_roc(test, gb_pd_test)
    plot_score_distribution(test)
    plot_ks(test)
    plot_calibration(calibration)
    print(f"\nCharts: roc_curve.png, score_distribution.png, ks_plot.png, calibration_plot.png in {FIGURES_DIR}")
    print(f"Gesamtlaufzeit {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
