"""
05_expected_loss.py  --  AP6: Expected Loss = PD x LGD x EAD

Was dieses Skript tut, in Reihenfolge:
  1. LGD empirisch aus den ausgefallenen Krediten schaetzen (data/processed/lgd_inputs.parquet):
     LGD = 1 - (recoveries + total_rec_prncp) / funded_amnt, Mittelwert, Median, Verteilung
  2. PD aus dem Scorecard-Modell A (scored_loans.parquet), EAD = funded_amnt
  3. EL je Kredit und fuer das Portfolio: gesamt, Train (ausgereift) und Test (2016-2018, zeitlich
     getrennt), absolut und in Prozent des Volumens
  4. Backtest auf dem ausgereiften Trainingsportfolio: modellierter EL gegen realisierten Verlust
  5. Sensitivitaet LGD 30 % / empirisch / 60 %
  6. Schreibt data/processed/portfolio_el.parquet (Grundlage fuer AP7 und AP8),
     reports/lgd_summary.csv, reports/expected_loss_summary.csv, reports/figures/lgd_distribution.png

Aufruf aus dem Repo-Root:
    .venv/Scripts/python.exe 02_python/05_expected_loss.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import FIGURES_DIR, LGD_PARQUET, PROCESSED_DIR, REPORTS_DIR

SCORED_PARQUET = PROCESSED_DIR / "scored_loans.parquet"
PORTFOLIO_EL_PARQUET = PROCESSED_DIR / "portfolio_el.parquet"
LGD_SUMMARY_CSV = REPORTS_DIR / "lgd_summary.csv"
EL_SUMMARY_CSV = REPORTS_DIR / "expected_loss_summary.csv"

LGD_SENSITIVITY = {"lgd_30": 0.30, "lgd_60": 0.60}


def estimate_lgd(scored: pd.DataFrame) -> tuple[float, float, pd.DataFrame, pd.DataFrame]:
    """Empirische LGD auf den ausgefallenen Krediten. Gibt Mittelwert, Median, Tabelle, Kreditdaten zurueck."""
    lgd = pd.read_parquet(LGD_PARQUET)
    # ENTSCHEIDUNG: LGD = 1 - (Rueckfluesse nach Ausfall + vor dem Ausfall getilgter Betrag) / Auszahlung.
    # Das ist die uebliche Naeherung fuer unbesicherte Ratenkredite. Die Inkassogebuehr (collection_recovery_fee) wird nicht
    # abgezogen, weil sie im Datensatz nicht sauber vom Erloes zu trennen ist; die LGD ist damit eher
    # etwas zu niedrig (optimistisch), was die Sensitivitaet mit 60 % abdeckt.
    # Werte ausserhalb 0 bis 1 (z. B. Rueckfluesse ueber der Auszahlung durch Zinsen) werden gekappt.
    lgd["recovered_share"] = (lgd["recoveries"] + lgd["total_rec_prncp"]) / lgd["funded_amnt"]
    lgd["lgd"] = (1 - lgd["recovered_share"]).clip(0, 1)
    lgd = lgd.merge(scored[["id", "sample", "term_months", "grade", "issue_date"]], on="id", how="left")

    mean_lgd = float(lgd["lgd"].mean())
    median_lgd = float(lgd["lgd"].median())
    # Volumengewichtet: Verlust in USD geteilt durch ausgefallenes Volumen in USD
    weighted_lgd = float((lgd["lgd"] * lgd["funded_amnt"]).sum() / lgd["funded_amnt"].sum())

    rows = [
        {"segment": "alle Ausfaelle", "loans": len(lgd), "lgd_mean": mean_lgd,
         "lgd_median": median_lgd, "lgd_volume_weighted": weighted_lgd},
    ]
    for label, part in [("train (2007-2015)", lgd[lgd["sample"] == "train"]),
                        ("test (2016-2018)", lgd[lgd["sample"] == "test"]),
                        ("36 Monate", lgd[lgd["term_months"] == 36]),
                        ("60 Monate", lgd[lgd["term_months"] == 60])]:
        rows.append({"segment": label, "loans": len(part), "lgd_mean": part["lgd"].mean(),
                     "lgd_median": part["lgd"].median(),
                     "lgd_volume_weighted": (part["lgd"] * part["funded_amnt"]).sum() / part["funded_amnt"].sum()})
    for grade, part in lgd.groupby("grade"):
        rows.append({"segment": f"grade {grade}", "loans": len(part), "lgd_mean": part["lgd"].mean(),
                     "lgd_median": part["lgd"].median(),
                     "lgd_volume_weighted": (part["lgd"] * part["funded_amnt"]).sum() / part["funded_amnt"].sum()})
    table = pd.DataFrame(rows).round(4)
    return mean_lgd, median_lgd, table, lgd


def plot_lgd(lgd: pd.DataFrame, mean_lgd: float, median_lgd: float) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(lgd["lgd"], bins=50, color="#2c3e50")
    ax.axvline(mean_lgd, color="#c0392b", linestyle="--", label=f"Mittelwert {mean_lgd:.1%}")
    ax.axvline(median_lgd, color="#e67e22", linestyle=":", label=f"Median {median_lgd:.1%}")
    ax.set_xlabel("LGD = 1 - (recoveries + total_rec_prncp) / funded_amnt")
    ax.set_ylabel("ausgefallene Kredite")
    ax.set_title(f"Empirische LGD-Verteilung, {len(lgd):,} ausgefallene Kredite")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "lgd_distribution.png", dpi=120)
    plt.close(fig)


def portfolio_summary(portfolio: pd.DataFrame, label: str, lgd_value: float, lgd_label: str) -> dict:
    ead = portfolio["ead"]
    el = portfolio["pd_a"] * lgd_value * ead
    return {
        "portfolio": label,
        "lgd_assumption": lgd_label,
        "lgd_value": round(lgd_value, 4),
        "loans": len(portfolio),
        "volume_usd": round(float(ead.sum()), 0),
        "mean_pd": round(float(portfolio["pd_a"].mean()), 4),
        "expected_loss_usd": round(float(el.sum()), 0),
        "el_rate_pct": round(100 * float(el.sum() / ead.sum()), 3),
    }


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    scored = pd.read_parquet(SCORED_PARQUET)

    # ----------------------------------------------------------------------------------
    # Schritt 1: LGD
    # ----------------------------------------------------------------------------------
    mean_lgd, median_lgd, lgd_table, lgd_loans = estimate_lgd(scored)
    lgd_table.to_csv(LGD_SUMMARY_CSV, index=False)
    plot_lgd(lgd_loans, mean_lgd, median_lgd)
    print("=== Empirische LGD (nur ausgefallene Kredite) ===")
    print(lgd_table.to_string(index=False))
    share_total_loss = float((lgd_loans["lgd"] >= 0.99).mean())
    share_full_recovery = float((lgd_loans["lgd"] <= 0.01).mean())
    print(f"\nAnteil Ausfaelle mit LGD >= 99 % (praktisch Totalverlust): {share_total_loss:.1%}")
    print(f"Anteil Ausfaelle mit LGD <= 1 % (praktisch alles zurueck):  {share_full_recovery:.1%}")

    # ENTSCHEIDUNG: Fuer die EL-Rechnung wird der einfache Mittelwert der LGD ueber alle ausgefallenen
    # Kredite verwendet, eine Zahl fuer das ganze Portfolio. Eine LGD je Laufzeit oder Grade waere
    # genauer, wuerde aber die Cutoff-Analyse und den Excel-Rechner komplizierter machen. Die
    # Unterschiede zwischen den Segmenten stehen in reports/lgd_summary.csv.
    lgd_used = mean_lgd

    # ----------------------------------------------------------------------------------
    # Schritt 2 und 3: EAD, EL je Kredit und Portfolio
    # ----------------------------------------------------------------------------------
    # ENTSCHEIDUNG: EAD = funded_amnt, der ausgezahlte Betrag. Bei Ratenkrediten ohne Rahmen ist das
    # Exposure bei Vergabe die Auszahlung. Der Restsaldo zum Ausfallzeitpunkt waere niedriger (Tilgung),
    # er steht aber nur in Leckage-Spalten. Die Annahme ist konservativ, also eher zu hoch.
    portfolio = scored.copy()
    portfolio["ead"] = portfolio["funded_amnt"]
    portfolio["lgd"] = lgd_used
    portfolio["el"] = portfolio["pd_a"] * portfolio["lgd"] * portfolio["ead"]
    portfolio.to_parquet(PORTFOLIO_EL_PARQUET, index=False)

    segments = [("gesamt (2007-2018)", portfolio),
                ("train (2007-2015, ausgereift)", portfolio[portfolio["sample"] == "train"]),
                ("test (2016-2018, zeitlich getrennt)", portfolio[portfolio["sample"] == "test"])]
    rows = []
    for label, part in segments:
        rows.append(portfolio_summary(part, label, lgd_used, "empirisch"))
        for lgd_label, lgd_value in LGD_SENSITIVITY.items():
            rows.append(portfolio_summary(part, label, lgd_value, lgd_label))
    el_summary = pd.DataFrame(rows)
    el_summary.to_csv(EL_SUMMARY_CSV, index=False)

    print("\n=== Expected Loss je Portfolio und LGD-Annahme ===")
    show = el_summary.copy()
    show["volume_bn_usd"] = (show["volume_usd"] / 1e9).round(3)
    show["expected_loss_mn_usd"] = (show["expected_loss_usd"] / 1e6).round(1)
    print(show[["portfolio", "lgd_assumption", "lgd_value", "loans", "volume_bn_usd", "mean_pd",
                "expected_loss_mn_usd", "el_rate_pct"]].to_string(index=False))

    # ----------------------------------------------------------------------------------
    # Schritt 4: Backtest auf dem ausgereiften Trainingsportfolio
    # Realisierter Verlust = Summe ueber ausgefallene Kredite von (LGD_i x funded_amnt), mit der
    # tatsaechlichen LGD jedes Kredits. Modell-EL = Summe PD x mittlere LGD x funded_amnt.
    # ----------------------------------------------------------------------------------
    train = portfolio[portfolio["sample"] == "train"]
    realized = lgd_loans[lgd_loans["sample"] == "train"]
    realized_loss = float((realized["lgd"] * realized["funded_amnt"]).sum())
    model_el = float(train["el"].sum())
    volume = float(train["ead"].sum())
    print("\n=== Backtest Train (ausgereift): Modell-EL gegen realisierten Verlust ===")
    print(f"Volumen:            {volume / 1e9:,.3f} Mrd. USD")
    print(f"Modell-EL:          {model_el / 1e6:,.1f} Mio. USD = {100 * model_el / volume:.2f} % des Volumens")
    print(f"Realisierter Verlust: {realized_loss / 1e6:,.1f} Mio. USD = {100 * realized_loss / volume:.2f} % des Volumens")
    print(f"Verhaeltnis realisiert / Modell: {realized_loss / model_el:.3f}")

    test = portfolio[portfolio["sample"] == "test"]
    realized_test = lgd_loans[lgd_loans["sample"] == "test"]
    realized_loss_test = float((realized_test["lgd"] * realized_test["funded_amnt"]).sum())
    print("\n=== Zum Vergleich Test (nicht ausgereift, Verlust nach oben verzerrt) ===")
    print(f"Modell-EL {100 * test['el'].sum() / test['ead'].sum():.2f} % gegen bisher realisiert "
          f"{100 * realized_loss_test / test['ead'].sum():.2f} % des Volumens")

    print(f"\nGespeichert: {PORTFOLIO_EL_PARQUET.name}, {LGD_SUMMARY_CSV.name}, {EL_SUMMARY_CSV.name}, "
          f"lgd_distribution.png")


if __name__ == "__main__":
    main()
