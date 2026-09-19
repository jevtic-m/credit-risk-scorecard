"""
run_sql.py  --  Fuehrt eine SQL-Datei aus 01_sql/ gegen die bereinigte Parquet-Datei aus.

Aufruf aus dem Repo-Root, zum Beispiel:
    .venv/Scripts/python.exe 02_python/run_sql.py 01_sql/02_default_rates.sql

Ohne Argument werden alle AP2-Dateien (02, 03, 04) nacheinander ausgefuehrt.
Die Sicht `loans` zeigt auf data/processed/loans_clean.parquet (siehe common.py).
"""

import sys
from pathlib import Path

from common import REPO_ROOT, connect, run_sql_file

AP2_FILES = [
    REPO_ROOT / "01_sql" / "02_default_rates.sql",
    REPO_ROOT / "01_sql" / "03_vintage.sql",
    REPO_ROOT / "01_sql" / "04_cohorts.sql",
]


def main() -> None:
    files = [Path(arg) for arg in sys.argv[1:]] or AP2_FILES
    con = connect()
    for path in files:
        print(f"\n########## {path.name} ##########\n")
        run_sql_file(con, path, print_results=True)
    con.close()


if __name__ == "__main__":
    main()
