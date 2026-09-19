"""
common.py  --  Gemeinsame Pfade und Hilfsfunktionen fuer alle Skripte ab AP2.

Alle Skripte ab AP2 arbeiten ausschliesslich auf data/processed/loans_clean.parquet
(und fuer die LGD auf data/processed/lgd_inputs.parquet), nie mehr auf der Rohdatei.
"""

from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
DUCKDB_FILE = DATA_DIR / "credit.duckdb"
CLEAN_PARQUET = PROCESSED_DIR / "loans_clean.parquet"
LGD_PARQUET = PROCESSED_DIR / "lgd_inputs.parquet"
REPORTS_DIR = REPO_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
DASHBOARD_DIR = REPO_ROOT / "03_dashboard"
EXCEL_DIR = REPO_ROOT / "04_excel"

# Letzter Monat im Datensatz. Wird gebraucht, um zu entscheiden, ob ein Kredit seine
# volle Laufzeit im Beobachtungsfenster hatte (Reifegrad, siehe 01_sql/03_vintage.sql).
DATA_END_DATE = "2018-12-01"

# --------------------------------------------------------------------------------------
# Zeitbasierter Train/Test-Split (AP3)
# --------------------------------------------------------------------------------------
# ENTSCHEIDUNG: Schnittdatum 1. Januar 2016. Training = Kredite mit issue_date vor 2016
# (2007 bis 2015, rund 62 % der Kredite), Test = Kredite ab 2016 (2016 bis 2018, rund 38 %).
# Zeitbasiert statt zufaellig, weil ein Modell im Einsatz die Zukunft vorhersagt und nicht
# eine zufaellige Teilmenge der Vergangenheit. 2016 als Schnitt, weil damit alle
# vollstaendig ausgereiften 36-Monats-Jahrgaenge (bis 2015) im Training liegen und der Test
# genug Kredite hat (ueber 500.000). Nachteil, bewusst in Kauf genommen: Der Testzeitraum ist
# nicht ausgereift, dort sind nur frueh abgeschlossene Kredite enthalten.
SPLIT_DATE = "2016-01-01"

# --------------------------------------------------------------------------------------
# Modellvariablen (AP3, AP4)
# Regel: nur Merkmale, die bei Kreditvergabe bekannt waren (Leckage-Spalten sind schon in
# AP1 entfernt). Zusaetzlich ausgeschlossen, mit Grund, siehe EXCLUDED_FROM_MODEL.
# --------------------------------------------------------------------------------------
NUMERIC_FEATURES = [
    "loan_amnt", "term_months", "annual_inc", "emp_length_years", "dti",
    "fico_range_low", "delinq_2yrs", "inq_last_6mths", "open_acc", "pub_rec",
    "pub_rec_bankruptcies", "revol_bal", "revol_util", "total_acc",
    "mths_since_last_delinq", "mths_since_last_record", "mths_since_recent_inq",
    "mort_acc", "acc_open_past_24mths", "bc_util", "tot_cur_bal", "total_rev_hi_lim",
    "num_tl_90g_dpd_24m", "mo_sin_old_rev_tl_op",
    # Abgeleitet in 02_woe_binning.py:
    "credit_history_months",   # Monate zwischen erster Kreditlinie und Kreditvergabe
    "loan_to_income",          # Kreditsumme geteilt durch Jahreseinkommen
]
CATEGORICAL_FEATURES = [
    "purpose", "home_ownership", "verification_status", "addr_state",
    "initial_list_status", "application_type",
]
MODEL_A_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# ENTSCHEIDUNG: grade, sub_grade und int_rate sind Lending Clubs eigenes Risikomodell. Sie
# kommen nur in das Benchmark-Modell B, nie in das Hauptmodell A.
BENCHMARK_NUMERIC = ["int_rate"]
BENCHMARK_CATEGORICAL = ["grade", "sub_grade"]
MODEL_B_FEATURES = MODEL_A_FEATURES + BENCHMARK_NUMERIC + BENCHMARK_CATEGORICAL

# Spalten aus loans_clean, die bewusst in keinem Modell stehen, mit Grund:
EXCLUDED_FROM_MODEL = {
    "id": "Schluessel, keine Information",
    "loan_status": "Zielvariable im Klartext",
    "default": "Zielvariable",
    "issue_date": "nur fuer den zeitbasierten Split, nicht als Merkmal (Jahrgang ist kein Antragsmerkmal)",
    "earliest_cr_line_date": "geht als credit_history_months ins Modell",
    "funded_amnt": "praktisch identisch mit loan_amnt, waere doppelt",
    "fico_range_high": "immer fico_range_low + 4, waere doppelt",
    # ENTSCHEIDUNG: installment ist aus Kreditsumme, Laufzeit UND Zinssatz berechnet. Ueber
    # den Zinssatz steckt darin Lending Clubs Risikoeinstufung. Deshalb nur im Benchmark B.
    "installment": "enthaelt int_rate (Rate = f(Betrag, Laufzeit, Zins)), deshalb nur Benchmark B",
}
MODEL_B_FEATURES = MODEL_B_FEATURES + ["installment"]

# Scorecard-Skalierung (AP4)
# ENTSCHEIDUNG: PDO = 20, 600 Punkte bei Odds 50:1 (gut:schlecht). Das ist die uebliche
# Lehrbuch-Parametrierung (Siddiqi, Credit Risk Scorecards): alle 20 Punkte verdoppeln sich die Odds.
PDO = 20
SCORE_AT_REFERENCE_ODDS = 600
REFERENCE_ODDS = 50


def load_model_frame():
    """Laedt loans_clean.parquet in pandas, leitet Zusatzmerkmale ab und setzt den Split.

    Es werden nur die Spalten gelesen, die Modell und Auswertung brauchen. Die Spalte
    `sample` ist 'train' fuer issue_date < SPLIT_DATE und 'test' sonst.
    """
    import pandas as pd  # hier importiert, damit run_sql.py ohne pandas-Import auskommt

    columns = sorted(
        set(NUMERIC_FEATURES) - {"credit_history_months", "loan_to_income"}
        | set(CATEGORICAL_FEATURES)
        | set(BENCHMARK_NUMERIC) | set(BENCHMARK_CATEGORICAL)
        | {"id", "default", "issue_date", "earliest_cr_line_date", "funded_amnt", "installment"}
    )
    con = duckdb.connect()
    # Spaltennamen in Anfuehrungszeichen, weil "default" ein reserviertes SQL-Wort ist
    quoted = ", ".join(f'"{c}"' for c in columns)
    df = con.execute(
        f"SELECT {quoted} FROM read_parquet('{CLEAN_PARQUET.as_posix()}')"
    ).fetchdf()
    con.close()

    # Abgeleitete Merkmale (beide bei Kreditvergabe bekannt)
    df["credit_history_months"] = (
        (df["issue_date"].dt.year - df["earliest_cr_line_date"].dt.year) * 12
        + (df["issue_date"].dt.month - df["earliest_cr_line_date"].dt.month)
    ).astype("float64")
    df["loan_to_income"] = df["loan_amnt"] / df["annual_inc"].where(df["annual_inc"] > 0)

    df["sample"] = "test"
    df.loc[df["issue_date"] < pd.Timestamp(SPLIT_DATE), "sample"] = "train"
    return df


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Oeffnet data/credit.duckdb und legt die Sicht `loans` auf die Parquet-Datei an.

    Alle SQL-Abfragen ab AP2 benutzen `loans` und lesen damit direkt die bereinigte
    Parquet-Datei, nicht die Rohtabelle loans_raw.
    """
    con = duckdb.connect(str(DUCKDB_FILE), read_only=read_only)
    if not read_only:
        con.execute(
            f"CREATE OR REPLACE VIEW loans AS "
            f"SELECT * FROM read_parquet('{CLEAN_PARQUET.as_posix()}')"
        )
    return con


def split_sql_statements(sql_text: str) -> list[str]:
    """Entfernt Kommentarzeilen und trennt den Text an Semikolons in einzelne Abfragen."""
    code_lines = [
        line for line in sql_text.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    return [s.strip() for s in "\n".join(code_lines).split(";") if s.strip()]


def run_sql_file(con: duckdb.DuckDBPyConnection, path: Path, print_results: bool = True) -> list:
    """Fuehrt alle Abfragen einer SQL-Datei aus und gibt die Ergebnisse als DataFrames zurueck."""
    results = []
    for code in split_sql_statements(path.read_text(encoding="utf-8")):
        result = con.execute(code)
        if code.lstrip().upper().startswith(("SELECT", "WITH", "PIVOT", "DESCRIBE")):
            df = result.fetchdf()
            results.append(df)
            if print_results:
                print(df.to_string(index=False, max_rows=80))
                print()
    return results
