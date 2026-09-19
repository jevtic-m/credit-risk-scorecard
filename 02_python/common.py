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
