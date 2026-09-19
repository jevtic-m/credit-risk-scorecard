"""
06_cutoff_analysis.py  --  AP7: Cutoff-Analyse (das Herzstueck)

Was dieses Skript tut, in Reihenfolge:
  1. Laedt data/processed/portfolio_el.parquet (Score, PD, LGD, EAD, EL je Kredit aus AP6)
  2. Rechnet fuer jeden moeglichen Cutoff (Score-Schritte von 5 Punkten): Annahmequote, genehmigtes
     Volumen, Ausfallquote des angenommenen Portfolios, Expected Loss absolut und in Prozent,
     abgelehntes gutes Geschaeft
  3. Waehlt einen Referenz-Cutoff (Knick der Trade-off-Kurve) und formuliert den README-Satz
  4. Sensitivitaet des Referenz-Cutoffs bei LGD 30 % / empirisch / 60 %
  5. Schreibt reports/cutoff_table.csv, reports/cutoff_summary.csv, zwei Charts
     und 04_excel/score_bands.csv (aggregierte Score-Verteilung fuer den Excel-Rechner)

Aufruf aus dem Repo-Root:
    .venv/Scripts/python.exe 02_python/06_cutoff_analysis.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import EXCEL_DIR, FIGURES_DIR, PROCESSED_DIR, REPORTS_DIR

PORTFOLIO_EL_PARQUET = PROCESSED_DIR / "portfolio_el.parquet"
CUTOFF_TABLE_CSV = REPORTS_DIR / "cutoff_table.csv"
CUTOFF_SUMMARY_CSV = REPORTS_DIR / "cutoff_summary.csv"
SCORE_BANDS_CSV = EXCEL_DIR / "score_bands.csv"
SCORE_BANDS_FULL_CSV = EXCEL_DIR / "score_bands_full_portfolio.csv"

CUTOFF_STEP = 5
# ENTSCHEIDUNG: Fuer die Wahl des Referenz-Cutoffs werden nur Cutoffs betrachtet, die hoechstens
# 50 % des Volumens kosten. Darueber hinaus wuerde keine Bank ihr Geschaeft halbieren, und der
# Knick der Kurve haengt sonst davon ab, wie weit man die Kurve zeichnet.
MAX_VOLUME_LOST_PCT = 50.0
LGD_SENSITIVITY = {"lgd_30": 0.30, "lgd_60": 0.60}


def cutoff_table(portfolio: pd.DataFrame, label: str) -> pd.DataFrame:
    """Eine Zeile je Cutoff: Was passiert, wenn nur Kredite mit Score >= Cutoff angenommen werden?"""
    total_loans = len(portfolio)
    total_volume = float(portfolio["ead"].sum())
    total_el = float(portfolio["el"].sum())
    total_good = int((portfolio["default"] == 0).sum())
    total_bad = int((portfolio["default"] == 1).sum())
    base_el_rate = total_el / total_volume

    score_min = int(np.floor(portfolio["score_a"].min() / CUTOFF_STEP) * CUTOFF_STEP)
    score_max = int(np.ceil(portfolio["score_a"].max() / CUTOFF_STEP) * CUTOFF_STEP)
    rows = []
    for cutoff in range(score_min, score_max + CUTOFF_STEP, CUTOFF_STEP):
        approved = portfolio[portfolio["score_a"] >= cutoff]
        rejected = portfolio[portfolio["score_a"] < cutoff]
        if len(approved) == 0:
            break
        volume = float(approved["ead"].sum())
        el = float(approved["el"].sum())
        rows.append({
            "portfolio": label,
            "cutoff": cutoff,
            "approved_loans": len(approved),
            "approval_rate_pct": 100 * len(approved) / total_loans,
            "approved_volume_usd": volume,
            "volume_share_pct": 100 * volume / total_volume,
            "volume_lost_pct": 100 * (1 - volume / total_volume),
            "approved_bad_rate_pct": 100 * approved["default"].mean(),
            "approved_mean_pd_pct": 100 * approved["pd_a"].mean(),
            "expected_loss_usd": el,
            "el_rate_pct": 100 * el / volume,
            "el_rate_reduction_pct": 100 * (1 - (el / volume) / base_el_rate),
            "el_absolute_reduction_pct": 100 * (1 - el / total_el),
            "rejected_good_loans": int((rejected["default"] == 0).sum()),
            "rejected_good_share_pct": 100 * (rejected["default"] == 0).sum() / total_good,
            "rejected_bad_share_pct": 100 * (rejected["default"] == 1).sum() / total_bad,
            "rejected_bad_rate_pct": 100 * rejected["default"].mean() if len(rejected) else np.nan,
        })
    return pd.DataFrame(rows).round(3)


def find_knee(table: pd.DataFrame) -> int:
    """Referenz-Cutoff = Knick der Kurve 'EL-Rate-Senkung gegen verlorenes Volumen'.

    Der Knick ist der Punkt mit dem groessten Abstand zur Geraden zwischen Anfang (kein Cutoff) und
    Ende (50 % Volumen verloren). Bis dorthin bringt jeder Prozentpunkt verlorenes Volumen viel
    EL-Senkung, danach wird es teuer. Das ist eine einfache, nachvollziehbare Regel und kein Optimum
    im strengen Sinn; mit bekannter Marge wuerde man stattdessen den Break-even rechnen.
    """
    part = table[table["volume_lost_pct"] <= MAX_VOLUME_LOST_PCT]
    x = part["volume_lost_pct"].to_numpy()
    y = part["el_rate_reduction_pct"].to_numpy()
    x0, y0, x1, y1 = x[0], y[0], x[-1], y[-1]
    # Abstand jedes Punktes zur Verbindungsgeraden (Formel fuer Punkt-Gerade-Abstand)
    distance = np.abs((y1 - y0) * x - (x1 - x0) * y + x1 * y0 - y1 * x0) / np.hypot(y1 - y0, x1 - x0)
    return int(part.iloc[int(np.argmax(distance))]["cutoff"])


def plot_tradeoff(table: pd.DataFrame, reference: int, label: str, filename: str) -> None:
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(table["cutoff"], table["el_rate_pct"], color="#c0392b", marker=".", label="EL-Rate des angenommenen Portfolios (%)")
    ax1.set_xlabel("Cutoff (Kredite mit Score >= Cutoff werden angenommen)")
    ax1.set_ylabel("Expected Loss in % des genehmigten Volumens", color="#c0392b")
    ax2 = ax1.twinx()
    ax2.plot(table["cutoff"], table["approval_rate_pct"], color="#2c3e50", marker=".", label="Annahmequote (%)")
    ax2.set_ylabel("Annahmequote in %", color="#2c3e50")
    ax1.axvline(reference, color="grey", linestyle="--", label=f"Referenz-Cutoff {reference}")
    lines = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax1.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    ax1.legend(lines, labels, loc="center left", fontsize=8)
    ax1.set_title(f"Cutoff-Trade-off, {label}")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / filename, dpi=120)
    plt.close(fig)


def plot_curve(table: pd.DataFrame, reference: int, label: str, filename: str) -> None:
    part = table[table["volume_lost_pct"] <= MAX_VOLUME_LOST_PCT]
    ref = table[table["cutoff"] == reference].iloc[0]
    fig, ax = plt.subplots(figsize=(7, 5.5))
    ax.plot(part["volume_lost_pct"], part["el_rate_reduction_pct"], marker=".", color="#2c3e50")
    ax.plot([part["volume_lost_pct"].iloc[0], part["volume_lost_pct"].iloc[-1]],
            [part["el_rate_reduction_pct"].iloc[0], part["el_rate_reduction_pct"].iloc[-1]],
            color="grey", linestyle="--", linewidth=1, label="Verbindungsgerade")
    ax.scatter([ref["volume_lost_pct"]], [ref["el_rate_reduction_pct"]], color="#c0392b", zorder=5,
               label=f"Referenz-Cutoff {reference}: -{ref['el_rate_reduction_pct']:.1f} % EL-Rate, "
                     f"-{ref['volume_lost_pct']:.1f} % Volumen")
    for _, row in part[part["cutoff"] % 20 == 0].iterrows():
        ax.annotate(str(int(row["cutoff"])), (row["volume_lost_pct"], row["el_rate_reduction_pct"]),
                    textcoords="offset points", xytext=(4, -10), fontsize=7)
    ax.set_xlabel("verlorenes Volumen in % (abgelehnte Kredite)")
    ax.set_ylabel("Senkung der EL-Rate in % gegenueber 'alle annehmen'")
    ax.set_title(f"Trade-off-Kurve mit Knick, {label}")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / filename, dpi=120)
    plt.close(fig)


def score_bands(portfolio: pd.DataFrame, width: int = 10) -> pd.DataFrame:
    """Aggregierte Score-Verteilung fuer den Excel-Rechner: eine Zeile je Score-Band."""
    lower = (np.floor(portfolio["score_a"] / width) * width).astype(int)
    grouped = portfolio.groupby(lower).agg(
        loans=("id", "size"), volume_usd=("ead", "sum"), defaults=("default", "sum"),
        avg_pd=("pd_a", "mean"), expected_loss_usd=("el", "sum"),
    ).reset_index().rename(columns={"score_a": "band_lower"})
    grouped["band_upper"] = grouped["band_lower"] + width - 1
    grouped["observed_default_rate"] = grouped["defaults"] / grouped["loans"]
    grouped["el_rate"] = grouped["expected_loss_usd"] / grouped["volume_usd"]
    cols = ["band_lower", "band_upper", "loans", "volume_usd", "defaults", "observed_default_rate",
            "avg_pd", "expected_loss_usd", "el_rate"]
    return grouped[cols].round(6)


def main() -> None:
    portfolio_all = pd.read_parquet(PORTFOLIO_EL_PARQUET)
    lgd_used = float(portfolio_all["lgd"].iloc[0])

    # ENTSCHEIDUNG: Die Cutoff-Empfehlung wird auf dem zeitlich getrennten Testportfolio (2016-2018)
    # hergeleitet, weil dort die PDs echte Vorhersagen sind (das Modell hat diese Kredite nie gesehen).
    # Dasselbe wird fuer das Gesamtportfolio gerechnet und mit ausgegeben, damit man sieht, dass
    # die Empfehlung nicht von der Wahl des Portfolios abhaengt.
    portfolios = {
        "test (2016-2018)": portfolio_all[portfolio_all["sample"] == "test"],
        "gesamt (2007-2018)": portfolio_all,
    }
    tables, summaries = [], []
    for label, part in portfolios.items():
        table = cutoff_table(part, label)
        reference = find_knee(table)
        tables.append(table)
        base = table.iloc[0]
        ref = table[table["cutoff"] == reference].iloc[0]
        summary = {
            "portfolio": label,
            "reference_cutoff": reference,
            "loans_total": len(part),
            "volume_total_usd": float(part["ead"].sum()),
            "el_rate_no_cutoff_pct": base["el_rate_pct"],
            "el_rate_at_cutoff_pct": ref["el_rate_pct"],
            "el_rate_reduction_pct": ref["el_rate_reduction_pct"],
            "el_absolute_no_cutoff_usd": base["expected_loss_usd"],
            "el_absolute_at_cutoff_usd": ref["expected_loss_usd"],
            "el_absolute_reduction_pct": ref["el_absolute_reduction_pct"],
            "approval_rate_pct": ref["approval_rate_pct"],
            "volume_lost_pct": ref["volume_lost_pct"],
            "approved_bad_rate_pct": ref["approved_bad_rate_pct"],
            "bad_rate_no_cutoff_pct": base["approved_bad_rate_pct"],
            "rejected_good_share_pct": ref["rejected_good_share_pct"],
            "rejected_bad_share_pct": ref["rejected_bad_share_pct"],
            "rejected_bad_rate_pct": ref["rejected_bad_rate_pct"],
        }
        # Sensitivitaet: Bei konstanter LGD skaliert der EL proportional, der Knick bleibt gleich.
        for lgd_label, lgd_value in {"lgd_empirisch": lgd_used, **LGD_SENSITIVITY}.items():
            factor = lgd_value / lgd_used
            summary[f"{lgd_label}_el_rate_no_cutoff_pct"] = round(base["el_rate_pct"] * factor, 3)
            summary[f"{lgd_label}_el_rate_at_cutoff_pct"] = round(ref["el_rate_pct"] * factor, 3)
            summary[f"{lgd_label}_el_saved_usd"] = round((base["expected_loss_usd"] - ref["expected_loss_usd"]) * factor, 0)
        summaries.append(summary)

        print(f"\n=== Cutoff-Tabelle, {label} (Auszug in 10-Punkte-Schritten) ===")
        show = table[table["cutoff"] % 10 == 0][[
            "cutoff", "approval_rate_pct", "volume_lost_pct", "approved_bad_rate_pct",
            "el_rate_pct", "el_rate_reduction_pct", "rejected_good_share_pct", "rejected_bad_share_pct"]]
        print(show.to_string(index=False))
        print(f"\nReferenz-Cutoff (Knick): {reference}")
        print(f"  Ein Cutoff bei Score {reference} senkt den Expected Loss von "
              f"{base['el_rate_pct']:.2f} % auf {ref['el_rate_pct']:.2f} % des Portfoliovolumens "
              f"(-{ref['el_rate_reduction_pct']:.1f} %) und kostet {ref['volume_lost_pct']:.1f} % des "
              f"genehmigten Volumens (Annahmequote {ref['approval_rate_pct']:.1f} %).")
        print(f"  Beobachtete Ausfallquote: {base['approved_bad_rate_pct']:.2f} % ohne Cutoff, "
              f"{ref['approved_bad_rate_pct']:.2f} % mit Cutoff. Abgelehnt werden "
              f"{ref['rejected_bad_share_pct']:.1f} % der spaeteren Ausfaelle, aber auch "
              f"{ref['rejected_good_share_pct']:.1f} % der Kredite, die zurueckgezahlt worden waeren.")
        safe_label = "test" if label.startswith("test") else "full"
        plot_tradeoff(table, reference, label, f"cutoff_tradeoff_{safe_label}.png")
        plot_curve(table, reference, label, f"cutoff_curve_{safe_label}.png")

    pd.concat(tables, ignore_index=True).to_csv(CUTOFF_TABLE_CSV, index=False)
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(CUTOFF_SUMMARY_CSV, index=False)
    print("\n=== Sensitivitaet am Referenz-Cutoff (EL-Rate ohne / mit Cutoff, in %) ===")
    for s in summaries:
        print(f"{s['portfolio']}, Cutoff {s['reference_cutoff']}:")
        for lgd_label in ["lgd_30", "lgd_empirisch", "lgd_60"]:
            print(f"  {lgd_label:14s}: {s[f'{lgd_label}_el_rate_no_cutoff_pct']:.2f} % -> "
                  f"{s[f'{lgd_label}_el_rate_at_cutoff_pct']:.2f} %, gesparter EL "
                  f"{s[f'{lgd_label}_el_saved_usd'] / 1e6:,.1f} Mio. USD")

    score_bands(portfolios["test (2016-2018)"]).to_csv(SCORE_BANDS_CSV, index=False)
    score_bands(portfolios["gesamt (2007-2018)"]).to_csv(SCORE_BANDS_FULL_CSV, index=False)
    print(f"\nGespeichert: {CUTOFF_TABLE_CSV.name}, {CUTOFF_SUMMARY_CSV.name}, {SCORE_BANDS_CSV}, "
          f"{SCORE_BANDS_FULL_CSV.name}, Charts cutoff_tradeoff_*.png und cutoff_curve_*.png")


if __name__ == "__main__":
    main()
