import psycopg
import pytest

from fdp.db import get_conn
from fdp.ingest import load_transactions
from fdp.ingest import ingest_file


BATCH = "2099-01-01"
HEADER = ("transaction_id,account_id,counterparty_account_id,amount,"
          "currency,transaction_type,country,transaction_timestamp\n")
ROWS = [
    "T1,A0000001,X0000001,10.5,EUR,card_payment,FR,2099-01-01 10:00:00\n",
    ",A0000001,X0000002,-3,ZZZ,transfer,FR,2099-13-45 25:61:00\n",
    "T1,A0000001,X0000001,10.5,EUR,card_payment,FR,2099-01-01 10:00:00\n",
]


@pytest.fixture
def conn():
    with get_conn() as c:
        yield c
        c.execute("DELETE FROM raw.transactions WHERE batch_id = %s", (BATCH,))
        c.execute("DELETE FROM raw.load_log WHERE batch_id = %s", (BATCH,))


@pytest.fixture
def csv_file(tmp_path):
    p = tmp_path / f"transactions_{BATCH}.csv"
    p.write_text(HEADER + "".join(ROWS))
    return p


def count(conn):
    return conn.execute("SELECT count(*) FROM raw.transactions WHERE batch_id = %s",
                        (BATCH,)).fetchone()[0]


def test_raw_keeps_defective_rows(conn, csv_file):
    load_transactions(conn, csv_file)
    assert count(conn) == 3                       # rien n'est filtré en raw


def test_load_is_idempotent(conn, csv_file):
    load_transactions(conn, csv_file)
    load_transactions(conn, csv_file)
    assert count(conn) == 3


def test_rejects_unexpected_columns(conn, tmp_path):
    p = tmp_path / f"transactions_{BATCH}.csv"
    p.write_text("id,amount\n1,10\n")
    with pytest.raises(ValueError):
        load_transactions(conn, p)


def test_failed_reload_keeps_previous_data(conn, csv_file):
    load_transactions(conn, csv_file)
    csv_file.write_text(HEADER + ROWS[0] + "T2,A1,X1,1,EUR,transfer,FR,2099-01-01,EXTRA\n")
    with pytest.raises(psycopg.Error):
        load_transactions(conn, csv_file)         # ligne malformée → COPY échoue
    assert count(conn) == 3                       # rollback : l'ancien lot est intact

def test_unchanged_file_is_skipped(conn, csv_file):
    assert ingest_file(conn, csv_file) == "loaded"
    assert ingest_file(conn, csv_file) == "skipped"


def test_modified_file_is_reloaded(conn, csv_file):
    ingest_file(conn, csv_file)
    csv_file.write_text(HEADER + ROWS[0])         # la source renvoie un fichier corrigé
    assert ingest_file(conn, csv_file) == "reloaded"
    assert count(conn) == 1