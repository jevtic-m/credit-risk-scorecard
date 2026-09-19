"""
01_data_prep.py  --  AP1: Daten laden, Zielvariable, Leckage-Filter, bereinigte Parquet-Datei

Was dieses Skript tut, in Reihenfolge:
  1. Fuehrt 01_sql/00_setup.sql aus: Rohdatei (csv.gz) -> Tabelle loans_raw in data/credit.duckdb
  2. Fuehrt 01_sql/01_exploration.sql aus und druckt die Ergebnisse (Spalten, loan_status, Zeitraum)
  3. Baut die Zielvariable default (Charged Off / Default = 1, Fully Paid = 0, Rest raus)
  4. Wendet die Leckage-Ausschlussliste an: nur Spalten, die bei Kreditvergabe bekannt waren
  5. Bereinigt Datentypen (term, emp_length, issue_d, earliest_cr_line)
  6. Schreibt data/processed/loans_clean.parquet   (Grundlage fuer ALLE weiteren Arbeitspakete)
  7. Schreibt data/processed/lgd_inputs.parquet    (nur ausgefallene Kredite, nur fuer die LGD in AP6)
  8. Schreibt reports/ap1_summary.md mit den Kennzahlen dieses Laufs

Aufruf aus dem Repo-Root:
    .venv/Scripts/python.exe 02_python/01_data_prep.py
"""

from pathlib import Path

import duckdb

# --------------------------------------------------------------------------------------
# Pfade (alle relativ zum Repo-Root)
# --------------------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = REPO_ROOT / "data" / "raw" / "accepted_2007_to_2018Q4.csv.gz"
DUCKDB_FILE = REPO_ROOT / "data" / "credit.duckdb"
CLEAN_PARQUET = REPO_ROOT / "data" / "processed" / "loans_clean.parquet"
LGD_PARQUET = REPO_ROOT / "data" / "processed" / "lgd_inputs.parquet"
SETUP_SQL = REPO_ROOT / "01_sql" / "00_setup.sql"
EXPLORATION_SQL = REPO_ROOT / "01_sql" / "01_exploration.sql"
SUMMARY_MD = REPO_ROOT / "reports" / "ap1_summary.md"

# Laut Kaggle hat die Rohdatei genau so viele Kreditzeilen. Wir pruefen das nach dem Laden,
# damit ein Ladefehler (z. B. abgeschnittene Datei) sofort auffaellt.
EXPECTED_RAW_ROWS = 2_260_701


# --------------------------------------------------------------------------------------
# Leckage-Ausschlussliste
# Regel: Eine Spalte darf nur bleiben, wenn sie zum Zeitpunkt der Kreditvergabe bekannt war.
# Alles, was erst waehrend der Laufzeit oder nach einem Ausfall entsteht, fliegt raus.
# --------------------------------------------------------------------------------------
# ENTSCHEIDUNG: Die Leckage-Liste steht hier explizit im Code und nicht nur "im Kopf".
# Sie ist bewusst breiter als die bekannten Beispiele (Zahlungen, Rueckfluesse): Auch last_fico_range_*
# (FICO beim letzten Abruf, also nach Vergabe) und pymnt_plan (Zahlungsplan waehrend der
# Laufzeit) sind Wissen aus der Zukunft und deshalb raus.
LEAKAGE_COLUMNS = [
    # Zahlungen und Rueckfluesse: bekannt erst am Ende der Laufzeit
    "total_pymnt", "total_pymnt_inv",
    "total_rec_prncp", "total_rec_int", "total_rec_late_fee",
    # Existieren nur nach einem Ausfall
    "recoveries", "collection_recovery_fee",
    # Zeitpunkte und Betraege der letzten / naechsten Zahlung
    "last_pymnt_d", "last_pymnt_amnt", "next_pymnt_d",
    # Offener Restsaldo zum Datenstand
    "out_prncp", "out_prncp_inv",
    # Bonitaetsdaten, die NACH der Vergabe neu abgerufen wurden
    "last_credit_pull_d", "last_fico_range_high", "last_fico_range_low",
    # Zahlungsplan waehrend der Laufzeit
    "pymnt_plan",
    # Haertefallprogramm waehrend der Laufzeit
    "hardship_flag", "hardship_type", "hardship_reason", "hardship_status",
    "deferral_term", "hardship_amount", "hardship_start_date", "hardship_end_date",
    "payment_plan_start_date", "hardship_length", "hardship_dpd", "hardship_loan_status",
    "orig_projected_additional_accrued_interest", "hardship_payoff_balance_amount",
    "hardship_last_payment_amount",
    # Vergleichsvereinbarung nach Ausfall
    "debt_settlement_flag", "debt_settlement_flag_date", "settlement_status",
    "settlement_date", "settlement_amount", "settlement_percentage", "settlement_term",
]

# --------------------------------------------------------------------------------------
# Spalten, die in loans_clean.parquet landen. Alle waren bei Kreditvergabe bekannt.
# --------------------------------------------------------------------------------------
# ENTSCHEIDUNG: Wir nehmen die klassischen Modell- und Analysespalten (Kredit, Kreditnehmer, Bonitaet) plus eine
# kleine Zahl gaengiger Kreditbuero-Merkmale (z. B. mort_acc, pub_rec_bankruptcies), die
# ebenfalls aus der Kreditauskunft bei Antragstellung stammen. Die uebrigen ~90 Spalten
# (Zweitantragsteller, Detail-Kontozaehler) lassen wir weg: sie sind entweder sehr luecken-
# haft oder fuer einen Einsteiger schwer erklaerbar. Wer sie braucht, ergaenzt die Liste hier.
# loans_raw hat alle Spalten als Text (siehe 00_setup.sql). Hier legen wir fest, was Zahl
# wird und was Text bleibt. Vor dem Umwandeln prueft das Skript, dass jeder Wert wirklich
# eine Zahl ist. So faellt ein Prozentzeichen oder ein Tippfehler in den Daten sofort auf.
TEXT_COLUMNS = [
    # Kreditmerkmale
    "purpose", "initial_list_status", "application_type",
    # Lending Clubs eigene Risikoeinstufung: NUR fuer SQL-Analysen und Benchmark-Modell B
    "grade", "sub_grade",
    # Kreditnehmer
    "home_ownership", "verification_status", "addr_state",
    # Status: wird zur Zielvariable, bleibt zur Kontrolle im Klartext erhalten
    "loan_status",
]
NUMERIC_COLUMNS = [
    # Kreditmerkmale
    "loan_amnt", "funded_amnt", "installment",
    # Lending Clubs eigener Zinssatz: NUR fuer SQL-Analysen und Benchmark-Modell B
    "int_rate",
    # Kreditnehmer
    "annual_inc", "dti",
    # Bonitaetshistorie (Kreditauskunft bei Antrag)
    "fico_range_low", "fico_range_high",
    "delinq_2yrs", "inq_last_6mths", "open_acc", "pub_rec", "pub_rec_bankruptcies",
    "revol_bal", "revol_util", "total_acc",
    "mths_since_last_delinq", "mths_since_last_record", "mths_since_recent_inq",
    "mort_acc", "acc_open_past_24mths", "bc_util", "tot_cur_bal", "total_rev_hi_lim",
    "num_tl_90g_dpd_24m", "mo_sin_old_rev_tl_op",
]
# Diese vier Spalten werden nicht 1:1 uebernommen, sondern im SQL unten typbereinigt:
#   term -> term_months, emp_length -> emp_length_years,
#   issue_d -> issue_date, earliest_cr_line -> earliest_cr_line_date
KEEP_COLUMNS = ["id"] + TEXT_COLUMNS + NUMERIC_COLUMNS

# Status-Werte, die einen bekannten Ausgang haben. Der Zusatz "Does not meet the credit
# policy" markiert Kredite, die nach einer aelteren Vergaberegel angenommen wurden.
DEFAULT_STATUSES = [
    "Charged Off",
    "Default",
    "Does not meet the credit policy. Status:Charged Off",
]
PAID_STATUSES = [
    "Fully Paid",
    "Does not meet the credit policy. Status:Fully Paid",
]


def sql_list(values: list[str]) -> str:
    """Macht aus einer Python-Liste eine SQL-Liste: ('a', 'b', 'c')."""
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def run_sql_file(con: duckdb.DuckDBPyConnection, path: Path, print_results: bool) -> None:
    """Fuehrt jede mit ';' getrennte Abfrage einer SQL-Datei aus, optional mit Ausgabe."""
    sql_text = path.read_text(encoding="utf-8")
    # Erst Kommentarzeilen entfernen (ein Semikolon im Kommentar wuerde sonst als
    # Abfrage-Ende gelesen), dann an den Semikolons in einzelne Abfragen trennen.
    code_lines = [
        line for line in sql_text.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    statements = [s.strip() for s in "\n".join(code_lines).split(";") if s.strip()]
    for code in statements:
        result = con.execute(code)
        if print_results and code.lstrip().upper().startswith(("SELECT", "WITH", "DESCRIBE")):
            df = result.fetchdf()
            print(df.to_string(index=False, max_rows=60))
            print()


def main() -> None:
    if not RAW_FILE.exists():
        raise SystemExit(f"Rohdatei fehlt: {RAW_FILE}\nBitte Kaggle-Download nach data/raw/ legen.")

    CLEAN_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_FILE))

    # ----------------------------------------------------------------------------------
    # Schritt 1: Rohdatei einmalig nach DuckDB laden (dauert wenige Minuten)
    # ----------------------------------------------------------------------------------
    already_loaded = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'loans_raw'"
    ).fetchone()[0]
    if already_loaded:
        print("Tabelle loans_raw existiert bereits, Laden wird uebersprungen.")
    else:
        print("Lade Rohdatei nach DuckDB ...")
        run_sql_file(con, SETUP_SQL, print_results=False)

    raw_rows = con.execute("SELECT count(*) FROM loans_raw").fetchone()[0]
    raw_column_names = [
        row[0] for row in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'loans_raw' ORDER BY ordinal_position"
        ).fetchall()
    ]
    raw_cols = len(raw_column_names)
    print(f"loans_raw: {raw_rows:,} Zeilen, {raw_cols} Spalten")
    if raw_rows != EXPECTED_RAW_ROWS:
        raise SystemExit(
            f"Erwartet {EXPECTED_RAW_ROWS:,} Zeilen, gefunden {raw_rows:,}. Ladefehler pruefen."
        )

    # Sicherheitsnetz: Jede Spalte der Ausschlussliste muss wirklich existieren.
    # Ein Tippfehler in der Liste wuerde sonst still eine Leckage-Spalte durchlassen.
    unknown = [c for c in LEAKAGE_COLUMNS if c not in raw_column_names]
    if unknown:
        raise SystemExit(f"Leckage-Liste enthaelt unbekannte Spalten: {unknown}")
    overlap = [c for c in KEEP_COLUMNS if c in LEAKAGE_COLUMNS]
    if overlap:
        raise SystemExit(f"Spalten stehen gleichzeitig in KEEP und LEAKAGE: {overlap}")

    # ----------------------------------------------------------------------------------
    # Schritt 2: Exploration (Spaltenuebersicht, loan_status, issue_d) aus der SQL-Datei
    # ----------------------------------------------------------------------------------
    print("\n=== Exploration (01_sql/01_exploration.sql) ===\n")
    run_sql_file(con, EXPLORATION_SQL, print_results=True)

    # ----------------------------------------------------------------------------------
    # Schritt 3 bis 6: Zielvariable, Filter, Typbereinigung, Parquet schreiben
    # ----------------------------------------------------------------------------------
    # ENTSCHEIDUNG: Zielvariable. Charged Off und Default zaehlen als Ausfall (1), Fully Paid
    # als kein Ausfall (0). Alle anderen Status (Current, Late, In Grace Period) werden
    # ausgeschlossen, weil ihr Ausgang noch offen ist. Laufende Kredite als "gut" zu werten,
    # wuerde die Ausfallquote systematisch unterschaetzen (Zensierung).
    # ENTSCHEIDUNG: Die Status mit Zusatz "Does not meet the credit policy" behalten wir und
    # behandeln sie wie ihren Kernstatus, weil der Ausgang bekannt ist. Es sind nur wenige
    # tausend alte Kredite; ein Ausschluss haette das Ergebnis nicht veraendert.
    # Sicherheitsnetz vor dem Umwandeln: Gibt es Werte, die keine Zahl sind?
    # (In der Kaggle-Datei sind int_rate und revol_util bereits ohne Prozentzeichen.)
    cast_checks = ", ".join(
        f"count(*) FILTER (WHERE {c} IS NOT NULL AND TRY_CAST({c} AS DOUBLE) IS NULL) AS {c}"
        for c in NUMERIC_COLUMNS + ["id"]
    )
    # Nur echte Kreditzeilen pruefen: Die 33 Summenzeilen der Kaggle-Datei haben keinen
    # loan_status und einen Text in der id-Spalte, sie fliegen ohnehin raus.
    bad_values = con.execute(
        f"SELECT {cast_checks} FROM loans_raw WHERE loan_status IS NOT NULL"
    ).fetchdf().iloc[0]
    not_numeric = {col: int(n) for col, n in bad_values.items() if n > 0}
    if not_numeric:
        raise SystemExit(f"Nicht-numerische Werte gefunden, bitte pruefen: {not_numeric}")

    select_parts = (
        ["CAST(id AS BIGINT) AS id"]
        + TEXT_COLUMNS
        + [f"CAST({c} AS DOUBLE) AS {c}" for c in NUMERIC_COLUMNS]
    )
    keep_columns_sql = ",\n        ".join(select_parts)
    clean_sql = f"""
    CREATE OR REPLACE TABLE loans_clean AS
    SELECT
        {keep_columns_sql},
        -- Typbereinigung (term, emp_length, issue_d, earliest_cr_line sind in der Rohdatei Text)
        CAST(regexp_extract(term, '([0-9]+)', 1) AS INTEGER)   AS term_months,
        CASE
            WHEN emp_length IS NULL THEN NULL
            WHEN emp_length LIKE '< 1%' THEN 0
            WHEN emp_length LIKE '10+%' THEN 10
            ELSE CAST(regexp_extract(emp_length, '([0-9]+)', 1) AS INTEGER)
        END                                                     AS emp_length_years,
        CAST(strptime(issue_d, '%b-%Y') AS DATE)                AS issue_date,
        CAST(strptime(earliest_cr_line, '%b-%Y') AS DATE)       AS earliest_cr_line_date,
        -- Zielvariable
        CASE
            WHEN loan_status IN {sql_list(DEFAULT_STATUSES)} THEN 1
            WHEN loan_status IN {sql_list(PAID_STATUSES)} THEN 0
        END                                                     AS "default"
    FROM loans_raw
    WHERE loan_status IN {sql_list(DEFAULT_STATUSES + PAID_STATUSES)}
    """
    con.execute(clean_sql)
    con.execute(
        f"COPY loans_clean TO '{CLEAN_PARQUET.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )

    # ----------------------------------------------------------------------------------
    # Schritt 7: LGD-Eingaben separat ablegen
    # ----------------------------------------------------------------------------------
    # ENTSCHEIDUNG: recoveries und total_rec_prncp sind Leckage-Spalten und duerfen nicht in
    # loans_clean. Fuer die LGD-Schaetzung in AP6 sind sie auf den bereits ausgefallenen
    # Krediten aber legitim. Deshalb landen sie in einer eigenen kleinen Datei, so dass ab
    # AP2 nie mehr die Rohdatei angefasst werden muss und das PD-Modell sie nicht sehen kann.
    con.execute(f"""
    COPY (
        SELECT CAST(id AS BIGINT)                       AS id,
               CAST(funded_amnt AS DOUBLE)              AS funded_amnt,
               CAST(total_rec_prncp AS DOUBLE)          AS total_rec_prncp,
               CAST(recoveries AS DOUBLE)               AS recoveries,
               CAST(collection_recovery_fee AS DOUBLE)  AS collection_recovery_fee
        FROM loans_raw
        WHERE loan_status IN {sql_list(DEFAULT_STATUSES)}
    ) TO '{LGD_PARQUET.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    # ----------------------------------------------------------------------------------
    # Schritt 8: Kennzahlen ausgeben und als Markdown ablegen
    # ----------------------------------------------------------------------------------
    stats = con.execute("""
        SELECT
            count(*)                                    AS n_clean,
            sum("default")                              AS n_default,
            round(100.0 * avg("default"), 2)            AS default_rate_pct,
            strftime(min(issue_date), '%Y-%m')          AS first_issue,
            strftime(max(issue_date), '%Y-%m')          AS last_issue,
            count(*) FILTER (WHERE issue_date IS NULL)  AS issue_date_missing,
            count(*) FILTER (WHERE term_months IS NULL) AS term_missing
        FROM loans_clean
    """).fetchdf().iloc[0]
    clean_cols = con.execute(
        "SELECT count(*) FROM information_schema.columns WHERE table_name = 'loans_clean'"
    ).fetchone()[0]
    lgd_rows = con.execute(
        f"SELECT count(*) FROM read_parquet('{LGD_PARQUET.as_posix()}')"
    ).fetchone()[0]
    parquet_mb = CLEAN_PARQUET.stat().st_size / 1_000_000

    lines = [
        "# AP1 Kennzahlen (automatisch erzeugt von 02_python/01_data_prep.py)",
        "",
        f"- Zeilen Rohdatei: {raw_rows:,}",
        f"- Zeilen nach Filter auf abgeschlossene Kredite: {int(stats['n_clean']):,}",
        f"- davon Ausfaelle (default = 1): {int(stats['n_default']):,}",
        f"- Ausfallquote: {stats['default_rate_pct']:.2f} %",
        f"- Spalten Rohdatei: {raw_cols}",
        f"- Leckage-Spalten explizit ausgeschlossen: {len(LEAKAGE_COLUMNS)}",
        f"- Spalten in loans_clean.parquet: {clean_cols}",
        f"- Zeitraum issue_d: {stats['first_issue']} bis {stats['last_issue']}",
        f"- Fehlende issue_d nach Umwandlung: {int(stats['issue_date_missing'])}",
        f"- Fehlende term nach Umwandlung: {int(stats['term_missing'])}",
        f"- Groesse loans_clean.parquet: {parquet_mb:.1f} MB",
        f"- Zeilen lgd_inputs.parquet (nur Ausfaelle): {lgd_rows:,}",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n=== AP1 Kennzahlen ===")
    print("\n".join(lines))
    con.close()


if __name__ == "__main__":
    main()
