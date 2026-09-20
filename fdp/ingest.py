import csv
import hashlib
import re
from pathlib import Path

from psycopg import sql

from fdp.db import get_conn

TX_COLUMNS = ["transaction_id", "account_id", "counterparty_account_id", "amount",
              "currency", "transaction_type", "country", "transaction_timestamp"]
REF_COLUMNS = {
    "customers": ["customer_id", "country", "segment", "created_at"],
    "accounts": ["account_id", "customer_id", "currency", "status", "created_at"],
}


def read_csv(path: Path, expected: list[str]) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        if header != expected:  # contrat d'interface : on échoue bruyamment
            raise ValueError(f"Colonnes inattendues dans {path.name} : {header}")
        return list(reader)


def batch_id_from(path: Path) -> str:
    m = re.fullmatch(r"transactions_(\d{4}-\d{2}-\d{2})\.csv", path.name)
    if not m:
        raise ValueError(f"Nom de fichier inattendu : {path.name}")
    return m.group(1)


def load_transactions(conn, path: Path) -> int:
    batch_id = batch_id_from(path)
    rows = read_csv(path, TX_COLUMNS)
    copy_sql = sql.SQL("COPY raw.transactions ({}) FROM STDIN").format(
        sql.SQL(", ").join(map(sql.Identifier,
                               ["batch_id", "source_row", *TX_COLUMNS, "source_file"])))
    with conn.transaction():
        conn.execute("DELETE FROM raw.transactions WHERE batch_id = %s", (batch_id,))
        with conn.cursor() as cur, cur.copy(copy_sql) as copy:
            for i, row in enumerate(rows, start=1):
                copy.write_row([batch_id, i, *row, path.name])
    return len(rows)


def load_reference(conn, path: Path, table: str) -> int:
    cols = REF_COLUMNS[table]
    rows = read_csv(path, cols)
    with conn.transaction():
        conn.execute(sql.SQL("TRUNCATE raw.{}").format(sql.Identifier(table)))
        copy_sql = sql.SQL("COPY raw.{} ({}) FROM STDIN").format(
            sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, cols)))
        with conn.cursor() as cur, cur.copy(copy_sql) as copy:
            for row in rows:
                copy.write_row(row)
    return len(rows)

def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest_file(conn, path: Path) -> str:
    batch_id, checksum = batch_id_from(path), file_checksum(path)
    previous = conn.execute("SELECT checksum FROM raw.load_log WHERE batch_id = %s",
                            (batch_id,)).fetchone()
    if previous and previous[0] == checksum:
        return "skipped"
    with conn.transaction():  # données + journal : tout ou rien
        n = load_transactions(conn, path)
        conn.execute("""
            INSERT INTO raw.load_log (batch_id, source_file, checksum, row_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (batch_id) DO UPDATE
            SET source_file = EXCLUDED.source_file, checksum = EXCLUDED.checksum,
                row_count = EXCLUDED.row_count, loaded_at = now()
        """, (batch_id, path.name, checksum, n))
    return "reloaded" if previous else "loaded"


def main():
    landing = Path("data/landing")
    with get_conn() as conn:
        for table in REF_COLUMNS:
            print(table, load_reference(conn, landing / "reference" / f"{table}.csv", table))
        for path in sorted(landing.glob("transactions_*.csv")):
            print(path.name, ingest_file(conn, path))


if __name__ == "__main__":
    main()